# Copyright (C) 2024 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import cherrypy
import hashlib
import json
import logging
import os
import io
import re
import secrets
import tempfile
import time
import threading
import uuid
import speech_recognition as sr
from pathlib import Path
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from akande.cache import SQLiteCache
from akande.config import (
    AKANDE_API_KEY,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_DEFAULT_MODEL,
    REDIS_URL,
)
from akande.akande import _friendly_llm_error
from akande.logger import MetricsCollector
from akande.providers import get_provider
from akande.server.rate_limit import (
    RateLimiterBackend,
    build_rate_limiter,
)
from akande.services import SYSTEM_PROMPT, OpenAIImpl
from akande.utils import (
    validate_api_key,
    get_output_directory,
    get_output_filename,
    strip_markdown,
)

ALLOWED_STATIC_FILES = {"sine-wave-generator.js"}
MAX_QUESTION_LENGTH = 5000
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10 MB
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 20  # per window per IP
CACHE_DB_NAME = "akande_cache.db"

# Magic bytes for audio format detection
AUDIO_SIGNATURES = {
    b"\x1a\x45\xdf\xa3": "webm",
    b"ID3": "mp3",
    b"\xff\xfb": "mp3",
    b"\xff\xf3": "mp3",
    b"\xff\xf2": "mp3",
    b"OggS": "ogg",
    b"fLaC": "flac",
}

# Module-level shared recognizer instance
_recognizer = sr.Recognizer()


def _detect_audio_format(data: bytes) -> str:
    """Detect audio format from magic bytes."""
    for signature, fmt in AUDIO_SIGNATURES.items():
        if data[: len(signature)] == signature:
            return fmt
    # Check for mp4 (ftyp at offset 4)
    if len(data) > 8 and data[4:8] == b"ftyp":
        return "mp4"
    return ""


# Backwards-compatible alias: external imports of ``RateLimiter`` from
# this module continue to work, but the implementation now lives in
# ``akande.server.rate_limit`` and is pluggable (in-memory / Redis).
from akande.server.rate_limit import (  # noqa: E402
    InMemoryRateLimiter as RateLimiter,
)


def _hash_ip(ip: str) -> str:
    """Hash an IP address for logging (PII protection)."""
    return hashlib.sha256(ip.encode()).hexdigest()[:12]


def _csv_safe(value: str) -> str:
    """Prevent CSV formula injection.

    Cells starting with ``=``, ``+``, ``-``, ``@``, ``\\t``,
    or ``\\r`` can be interpreted as formulas by spreadsheet
    applications.  Prefixing with a single-quote neutralises
    this without altering the visible content in most apps.
    """
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _sanitise_filename(name: str) -> str:
    """Strip characters that could enable header injection."""
    return re.sub(r'["\r\n\\]', "_", name)


class SecurityHeadersTool(cherrypy.Tool):
    """CherryPy tool to add security headers to all responses."""

    def __init__(self):
        super().__init__(
            "before_finalize", self._set_headers
        )

    def _set_headers(self):
        h = cherrypy.response.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )
        h["Permissions-Policy"] = "microphone=(self)"
        h["X-XSS-Protection"] = "1; mode=block"
        nonce = getattr(
            cherrypy.request, "_csp_nonce", None
        )
        if nonce:
            script_src = f"'nonce-{nonce}'"
            style_src = f"'nonce-{nonce}'"
        else:
            script_src = "'self'"
            style_src = "'self'"
        h["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' {script_src}; "
            f"style-src 'self' {style_src}; "
            "img-src 'self' data: blob: https://kura.pro; "
            "connect-src 'self'; "
            "media-src 'self' blob:; "
            "frame-src 'none'; "
            "font-src 'self';"
        )


# Register security headers tool
cherrypy.tools.security_headers = SecurityHeadersTool()


class AkandeServer:
    _cp_config = {
        "tools.security_headers.on": True,
    }

    def __init__(self):
        provider_name = LLM_PROVIDER or "openai"
        if provider_name == "openai":
            if not validate_api_key(OPENAI_API_KEY):
                raise RuntimeError(
                    "Invalid or missing OPENAI_API_KEY. "
                    "Server cannot start without a "
                    "valid API key."
                )
            self.openai_service = OpenAIImpl()
        else:
            self.openai_service = get_provider(
                provider_name
            )
        self.logger = logging.getLogger(__name__)
        self._metrics = MetricsCollector()
        self.public_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "public"
        )
        # Pluggable rate limiter (in-memory by default; Redis when
        # ``REDIS_URL`` is set in the environment).
        self._rate_limiter: RateLimiterBackend = build_rate_limiter(
            window=RATE_LIMIT_WINDOW,
            max_requests=RATE_LIMIT_MAX_REQUESTS,
            redis_url=REDIS_URL,
        )
        # Server-side cache
        directory_path = get_output_directory()
        cache_path = directory_path / CACHE_DB_NAME
        self.cache = SQLiteCache(str(cache_path))

        if not AKANDE_API_KEY:
            self.logger.warning(
                "AKANDE_API_KEY is not set — /api routes are "
                "OPEN. Set AKANDE_API_KEY in your environment "
                "before exposing this server beyond localhost.",
                extra={
                    "event": "Server:AuthDisabled",
                },
            )

        self.logger.info(
            "Server initialized",
            extra={
                "event": "Server:Initialized",
                "extra_data": {
                    "public_dir": str(self.public_dir),
                    "auth_required": bool(AKANDE_API_KEY),
                    "rate_limiter": type(
                        self._rate_limiter
                    ).__name__,
                },
            },
        )

    def _get_correlation_id(self) -> str:
        """Get or generate a correlation ID for the request."""
        return cherrypy.request.headers.get(
            "X-Request-Id", str(uuid.uuid4())
        )

    @staticmethod
    def _check_csrf():
        """Verify CSRF protection via custom header.

        Browsers prevent cross-origin requests from setting
        custom headers without a CORS preflight.  Since we
        do not set Access-Control-Allow-* headers, any
        cross-origin POST with X-Requested-With will be
        blocked by the browser.
        """
        header = cherrypy.request.headers.get(
            "X-Requested-With", ""
        )
        if header != "AkandeApp":
            raise cherrypy.HTTPError(
                403, "Missing or invalid CSRF header"
            )

    def _check_api_key(self):
        """Validate the ``X-Akande-Key`` header against ``AKANDE_API_KEY``.

        Behaviour:
        - If ``AKANDE_API_KEY`` is unset, the check is a no-op (a
          startup warning has already been logged).
        - Otherwise the request must supply a matching ``X-Akande-Key``
          header.  Comparison uses ``secrets.compare_digest`` to avoid
          timing side channels.  On mismatch we return 401 with an
          empty body and log the attempt with a hashed IP.
        """
        if not AKANDE_API_KEY:
            return
        provided = cherrypy.request.headers.get(
            "X-Akande-Key", ""
        )
        if not secrets.compare_digest(
            provided, AKANDE_API_KEY
        ):
            ip = cherrypy.request.remote.ip
            self.logger.warning(
                "Unauthorized API request",
                extra={
                    "event": "Server:Unauthorized",
                    "extra_data": {
                        "ip_hash": _hash_ip(ip),
                        "path": cherrypy.request.path_info,
                    },
                },
            )
            raise cherrypy.HTTPError(401, "Unauthorized")

    def _check_rate_limit(self):
        ip = cherrypy.request.remote.ip
        if not self._rate_limiter.is_allowed(ip):
            ip_hash = _hash_ip(ip)
            self.logger.warning(
                "Rate limit exceeded",
                extra={
                    "event": "Server:RateLimited",
                    "extra_data": {
                        "ip_hash": ip_hash,
                        "window": RATE_LIMIT_WINDOW,
                        "max_requests": RATE_LIMIT_MAX_REQUESTS,
                    },
                },
            )
            cherrypy.response.status = 429
            raise cherrypy.HTTPError(
                429, "Rate limit exceeded. Try again later."
            )

    @staticmethod
    def _json_response(data: dict) -> bytes:
        """Encode a dict as a UTF-8 JSON response."""
        cherrypy.response.headers["Content-Type"] = (
            "application/json; charset=utf-8"
        )
        return json.dumps(data).encode("utf-8")

    @cherrypy.expose
    def health(self):
        """Health check endpoint."""
        return self._json_response(
            {"status": "ok", "service": "akande"}
        )

    @cherrypy.expose
    def metrics(self):
        """Return collected timing metrics as JSON."""
        return self._json_response(
            self._metrics.summary()
        )

    @cherrypy.expose
    def index(self):
        cherrypy.response.headers["Content-Type"] = (
            "text/html; charset=utf-8"
        )
        index_path = self.public_dir / "index.html"
        if not index_path.is_file():
            raise cherrypy.HTTPError(404, "Index page not found")
        nonce = secrets.token_urlsafe(16)
        cherrypy.request._csp_nonce = nonce
        html = index_path.read_text(encoding="utf-8")
        return html.replace("__CSP_NONCE__", nonce)

    @cherrypy.expose
    def static(self, path):
        if path not in ALLOWED_STATIC_FILES:
            ip_hash = _hash_ip(
                cherrypy.request.remote.ip
            )
            self.logger.warning(
                "Forbidden static file access attempt",
                extra={
                    "event": "Server:ForbiddenAccess",
                    "extra_data": {
                        "ip_hash": ip_hash,
                        "path": path[:100],
                    },
                },
            )
            raise cherrypy.HTTPError(403, "Forbidden")
        file_path = self.public_dir / path
        resolved = file_path.resolve()
        if not str(resolved).startswith(
            str(self.public_dir.resolve())
        ):
            raise cherrypy.HTTPError(403, "Forbidden")
        if not resolved.is_file():
            raise cherrypy.HTTPError(404, "File not found")
        ext = resolved.suffix.lower()
        mime_map = {
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".svg": "image/svg+xml",
        }
        content_type = mime_map.get(ext, "text/plain")
        cherrypy.response.headers["Content-Type"] = (
            f"{content_type}; charset=utf-8"
        )
        return resolved.read_text(encoding="utf-8")

    @cherrypy.expose
    @cherrypy.tools.allow(methods=["POST"])
    def process_question(self):
        self._check_api_key()
        self._check_csrf()
        self._check_rate_limit()
        correlation_id = self._get_correlation_id()
        start_time = time.time()
        try:
            request_data = json.loads(
                cherrypy.request.body.read(
                    MAX_QUESTION_LENGTH * 4
                )
            )
            question = request_data.get("question", "")

            if (
                not isinstance(question, str)
                or not question.strip()
            ):
                cherrypy.response.status = 400
                return self._json_response(
                    {
                        "error": (
                            "Question must be a "
                            "non-empty string"
                        )
                    }
                )

            question = question.strip()[:MAX_QUESTION_LENGTH]

            self.logger.info(
                "Text question received",
                extra={
                    "event": "Server:RequestReceived",
                    "correlation_id": correlation_id,
                    "extra_data": {
                        "method": "POST",
                        "path": "/process_question",
                        "question_length": len(question),
                    },
                },
            )

            # Check cache first
            prompt_hash = hashlib.sha256(
                question.encode("utf-8")
            ).hexdigest()
            cached = self.cache.get(prompt_hash)
            if cached:
                latency = (time.time() - start_time) * 1000
                self._metrics.record(
                    "process_question", latency
                )
                self.logger.info(
                    "Served from cache",
                    extra={
                        "event": "Server:RequestCompleted",
                        "correlation_id": correlation_id,
                        "extra_data": {
                            "status": 200,
                            "cache_hit": True,
                            "latency_ms": round(latency, 2),
                        },
                    },
                )
                return self._json_response(
                    {"response": strip_markdown(cached)}
                )

            response_object = (
                self.openai_service.generate_response_sync(
                    question,
                    SYSTEM_PROMPT,
                    OPENAI_DEFAULT_MODEL,
                    None,
                )
            )
            raw_content = (
                response_object.choices[0].message.content
            )
            # Store raw markdown in cache
            self.cache.set(prompt_hash, raw_content)

            latency = (time.time() - start_time) * 1000
            self._metrics.record(
                "process_question", latency
            )
            self.logger.info(
                "Text question processed",
                extra={
                    "event": "Server:RequestCompleted",
                    "correlation_id": correlation_id,
                    "extra_data": {
                        "status": 200,
                        "cache_hit": False,
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            return self._json_response(
                {"response": strip_markdown(raw_content)}
            )

        except json.JSONDecodeError:
            self.logger.warning(
                "Invalid JSON in request",
                extra={
                    "event": "Server:BadRequest",
                    "correlation_id": correlation_id,
                },
            )
            cherrypy.response.status = 400
            return self._json_response(
                {"error": "Invalid JSON"}
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.logger.error(
                f"Failed to process question: "
                f"{type(e).__name__}",
                exc_info=True,
                extra={
                    "event": "Server:RequestFailed",
                    "correlation_id": correlation_id,
                    "extra_data": {
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            cherrypy.response.status = 500
            return self._json_response(
                {"error": _friendly_llm_error(e)}
            )

    @cherrypy.expose
    @cherrypy.tools.allow(methods=["POST"])
    def process_audio_question(self):
        self._check_api_key()
        self._check_csrf()
        self._check_rate_limit()
        correlation_id = self._get_correlation_id()
        start_time = time.time()
        try:
            audio_data = cherrypy.request.body.read()

            if len(audio_data) > MAX_AUDIO_SIZE:
                cherrypy.response.status = 400
                return self._json_response(
                    {"error": "Audio file too large"}
                )

            if len(audio_data) == 0:
                cherrypy.response.status = 400
                return self._json_response(
                    {"error": "No audio data received"}
                )

            # Use Content-Type hint from browser if available
            content_type = cherrypy.request.headers.get(
                "Content-Type", ""
            )

            self.logger.info(
                "Audio question received",
                extra={
                    "event": "Server:RequestReceived",
                    "correlation_id": correlation_id,
                    "extra_data": {
                        "method": "POST",
                        "path": "/process_audio_question",
                        "audio_size": len(audio_data),
                        "content_type": content_type,
                    },
                },
            )

            wav_file_path = self.convert_to_wav(
                audio_data, content_type, correlation_id
            )
            try:
                processed_result = self.process_audio(
                    wav_file_path, correlation_id
                )

                if not processed_result.get("success"):
                    return self._json_response(
                        {
                            "error": processed_result.get(
                                "error",
                                "Audio processing failed",
                            )
                        }
                    )

                question = processed_result.get("text", "")
                if not question:
                    return self._json_response(
                        {"error": "No speech detected"}
                    )

                # Check cache first
                prompt_hash = hashlib.sha256(
                    question.encode("utf-8")
                ).hexdigest()
                cached = self.cache.get(prompt_hash)
                if cached:
                    latency = (
                        time.time() - start_time
                    ) * 1000
                    self._metrics.record(
                        "process_audio_question", latency
                    )
                    self.logger.info(
                        "Audio question served from cache",
                        extra={
                            "event": (
                                "Server:RequestCompleted"
                            ),
                            "correlation_id": correlation_id,
                            "extra_data": {
                                "status": 200,
                                "cache_hit": True,
                                "latency_ms": round(
                                    latency, 2
                                ),
                            },
                        },
                    )
                    return self._json_response(
                        {"response": strip_markdown(cached)}
                    )

                response_object = (
                    self.openai_service.generate_response_sync(
                        question,
                        SYSTEM_PROMPT,
                        OPENAI_DEFAULT_MODEL,
                        None,
                    )
                )
                raw_content = (
                    response_object.choices[
                        0
                    ].message.content
                )
                self.cache.set(prompt_hash, raw_content)

                latency = (time.time() - start_time) * 1000
                self._metrics.record(
                    "process_audio_question", latency
                )
                self.logger.info(
                    "Audio question processed",
                    extra={
                        "event": "Server:RequestCompleted",
                        "correlation_id": correlation_id,
                        "extra_data": {
                            "status": 200,
                            "cache_hit": False,
                            "latency_ms": round(latency, 2),
                        },
                    },
                )
                return self._json_response(
                    {
                        "response": strip_markdown(
                            raw_content
                        )
                    }
                )
            finally:
                if os.path.exists(wav_file_path):
                    os.remove(wav_file_path)

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.logger.error(
                f"Failed to process audio: "
                f"{type(e).__name__}",
                exc_info=True,
                extra={
                    "event": "Server:RequestFailed",
                    "correlation_id": correlation_id,
                    "extra_data": {
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            cherrypy.response.status = 500
            return self._json_response(
                {"error": _friendly_llm_error(e)}
            )

    @cherrypy.expose
    @cherrypy.tools.allow(methods=["POST"])
    def export_conversation(self):
        """Export a conversation as PDF or CSV and return the file."""
        self._check_api_key()
        self._check_csrf()
        self._check_rate_limit()
        correlation_id = self._get_correlation_id()
        try:
            body = json.loads(
                cherrypy.request.body.read(1024 * 1024)
            )
            fmt = body.get("format", "pdf")
            title = (body.get("title") or "Conversation")[:200]
            messages = body.get("messages", [])

            if fmt not in ("pdf", "csv"):
                cherrypy.response.status = 400
                return self._json_response(
                    {"error": "Format must be pdf or csv"}
                )

            if not messages or not isinstance(messages, list):
                cherrypy.response.status = 400
                return self._json_response(
                    {"error": "No messages to export"}
                )

            # Sanitise messages
            clean = []
            for m in messages[:500]:
                role = str(m.get("role", ""))[:20]
                content = str(m.get("content", ""))[:10000]
                ts = str(m.get("timestamp", ""))[:30]
                if role and content:
                    clean.append(
                        {"role": role, "content": content,
                         "timestamp": ts}
                    )

            if not clean:
                cherrypy.response.status = 400
                return self._json_response(
                    {"error": "No valid messages"}
                )

            directory_path = get_output_directory()

            if fmt == "csv":
                import csv as csv_mod

                filename = get_output_filename(".csv")
                file_path = directory_path / filename
                with open(
                    file_path, "w", newline="",
                    encoding="utf-8",
                ) as f:
                    w = csv_mod.writer(f)
                    w.writerow([
                        "timestamp", "role", "content",
                        "conversation_title",
                    ])
                    for m in clean:
                        w.writerow([
                            m["timestamp"], m["role"],
                            _csv_safe(m["content"]),
                            _csv_safe(title),
                        ])
                try:
                    os.chmod(str(file_path), 0o600)
                except OSError:
                    pass

                safe_fn = _sanitise_filename(filename)
                cherrypy.response.headers["Content-Type"] = (
                    "text/csv; charset=utf-8"
                )
                cherrypy.response.headers[
                    "Content-Disposition"
                ] = (
                    f"attachment; filename=\"{safe_fn}\""
                )
                return file_path.read_bytes()

            # PDF
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import (
                getSampleStyleSheet,
                ParagraphStyle,
            )
            from reportlab.platypus import (
                SimpleDocTemplate,
                Paragraph,
                Spacer,
            )
            from reportlab.lib.enums import TA_LEFT, TA_RIGHT
            from xml.sax.saxutils import escape as xml_escape

            filename = get_output_filename(".pdf")
            file_path = directory_path / filename
            doc = SimpleDocTemplate(
                str(file_path), pagesize=letter
            )
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                "ConvTitle",
                parent=styles["Heading1"],
                fontSize=16,
                spaceAfter=12,
            )
            user_style = ParagraphStyle(
                "UserMsg",
                parent=styles["Normal"],
                fontSize=10,
                textColor="#0056d6",
                alignment=TA_RIGHT,
                spaceAfter=4,
            )
            asst_style = ParagraphStyle(
                "AsstMsg",
                parent=styles["Normal"],
                fontSize=10,
                alignment=TA_LEFT,
                spaceAfter=4,
            )
            ts_style = ParagraphStyle(
                "Timestamp",
                parent=styles["Normal"],
                fontSize=7,
                textColor="#8e8e93",
                spaceAfter=8,
            )

            flowables = [
                Paragraph(xml_escape(title), title_style),
                Spacer(1, 12),
            ]
            for m in clean:
                role = m["role"]
                content = xml_escape(m["content"])
                ts = xml_escape(m["timestamp"])
                style = (
                    user_style if role == "user"
                    else asst_style
                )
                label = "You" if role == "user" else "Akande"
                flowables.append(
                    Paragraph(
                        f"<b>{label}:</b> {content}",
                        style,
                    )
                )
                if ts:
                    flowables.append(
                        Paragraph(ts, ts_style)
                    )

            doc.build(flowables)
            try:
                os.chmod(str(file_path), 0o600)
            except OSError:
                pass

            safe_fn = _sanitise_filename(filename)
            cherrypy.response.headers["Content-Type"] = (
                "application/pdf"
            )
            cherrypy.response.headers[
                "Content-Disposition"
            ] = (
                f"attachment; filename=\"{safe_fn}\""
            )
            return file_path.read_bytes()

        except json.JSONDecodeError:
            cherrypy.response.status = 400
            return self._json_response(
                {"error": "Invalid JSON"}
            )
        except Exception as e:
            self.logger.error(
                f"Export failed: {type(e).__name__}",
                exc_info=True,
                extra={
                    "event": "Server:ExportFailed",
                    "correlation_id": correlation_id,
                },
            )
            cherrypy.response.status = 500
            return self._json_response(
                {"error": "Export failed"}
            )

    @staticmethod
    def convert_to_wav(
        audio_data,
        content_type="",
        correlation_id="",
    ):
        convert_start = time.time()
        logger = logging.getLogger(__name__)
        try:
            audio_segment = None

            # Try Content-Type hint first
            ct_format_map = {
                "audio/webm": "webm",
                "audio/mp4": "mp4",
                "audio/mpeg": "mp3",
                "audio/ogg": "ogg",
                "audio/flac": "flac",
            }
            ct_fmt = ct_format_map.get(content_type, "")
            if ct_fmt:
                try:
                    audio_segment = AudioSegment.from_file(
                        io.BytesIO(audio_data), format=ct_fmt
                    )
                except CouldntDecodeError:
                    pass

            # Try magic-byte detection if Content-Type didn't work
            if audio_segment is None:
                detected = _detect_audio_format(audio_data)
                if detected:
                    try:
                        audio_segment = AudioSegment.from_file(
                            io.BytesIO(audio_data),
                            format=detected,
                        )
                    except CouldntDecodeError:
                        pass

            # Fall back to brute-force
            if audio_segment is None:
                for fmt in [
                    "webm",
                    "mp3",
                    "mp4",
                    "ogg",
                    "flac",
                ]:
                    try:
                        audio_segment = AudioSegment.from_file(
                            io.BytesIO(audio_data), format=fmt
                        )
                        break
                    except CouldntDecodeError:
                        pass

            if audio_segment is None:
                raise ValueError("Unsupported audio format")

            audio_segment = audio_segment.set_channels(
                1
            ).set_frame_rate(16000)

            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            )
            tmp.close()
            os.chmod(tmp.name, 0o600)
            audio_segment.export(tmp.name, format="wav")

            latency = (time.time() - convert_start) * 1000
            logger.info(
                "Audio converted to WAV",
                extra={
                    "event": "Server:AudioConverted",
                    "correlation_id": correlation_id,
                    "extra_data": {
                        "input_size": len(audio_data),
                        "content_type": content_type,
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            return tmp.name

        except Exception as e:
            logger.error(
                f"Audio conversion failed: "
                f"{type(e).__name__}",
                exc_info=True,
                extra={
                    "event": "Server:AudioConversionFailed",
                    "correlation_id": correlation_id,
                },
            )
            raise RuntimeError(f"Error converting audio: {e}")

    @staticmethod
    def process_audio(file_path, correlation_id=""):
        logger = logging.getLogger(__name__)
        try:
            with sr.AudioFile(file_path) as source:
                audio_data = _recognizer.record(source)

            text = _recognizer.recognize_google(audio_data)
            logger.info(
                "Audio speech recognized",
                extra={
                    "event": "Speech:RecognitionCompleted",
                    "correlation_id": correlation_id,
                    "extra_data": {
                        "success": True,
                        "transcript_length": len(text),
                    },
                },
            )
            return {"text": text, "success": True}

        except sr.UnknownValueError:
            logger.warning(
                "Audio speech not understood",
                extra={
                    "event": "Speech:RecognitionCompleted",
                    "correlation_id": correlation_id,
                    "extra_data": {"success": False},
                },
            )
            return {
                "error": "Audio could not be understood",
                "success": False,
            }
        except sr.RequestError:
            logger.error(
                "Speech recognition service error",
                exc_info=True,
                extra={
                    "event": "Speech:RecognitionFailed",
                    "correlation_id": correlation_id,
                },
            )
            return {
                "error": "Speech recognition service error",
                "success": False,
            }


def main():
    # Only configure logging if no handlers exist yet
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)

    cherrypy.config.update(
        {
            "server.socket_host": "127.0.0.1",
            "server.socket_port": 8080,
            "server.thread_pool": 30,
            "server.max_request_body_size": MAX_AUDIO_SIZE,
            "request.show_tracebacks": False,
            "request.show_mismatched_params": False,
        }
    )
    cherrypy.quickstart(AkandeServer())


if __name__ == "__main__":
    main()
