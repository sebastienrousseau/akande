import cherrypy
import hashlib
import json
import logging
import os
import io
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
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_DEFAULT_MODEL,
)
from akande.providers import get_provider
from akande.services import SYSTEM_PROMPT, OpenAIImpl
from akande.utils import (
    validate_api_key,
    get_output_directory,
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


class RateLimiter:
    """Thread-safe in-memory per-IP rate limiter."""

    def __init__(self, window: int, max_requests: int):
        self.window = window
        self.max_requests = max_requests
        self._requests: dict = {}
        self._lock = threading.Lock()

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            timestamps = self._requests.get(ip, [])
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self.max_requests:
                self._requests[ip] = timestamps
                return False
            timestamps.append(now)
            self._requests[ip] = timestamps
        return True

    def cleanup(self):
        """Remove stale IPs with no recent requests."""
        cutoff = time.time() - self.window
        with self._lock:
            stale = [
                ip
                for ip, ts in self._requests.items()
                if not any(t > cutoff for t in ts)
            ]
            for ip in stale:
                del self._requests[ip]


def _hash_ip(ip: str) -> str:
    """Hash an IP address for logging (PII protection)."""
    return hashlib.sha256(ip.encode()).hexdigest()[:12]


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
        h["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' "
            "*.google-analytics.com "
            "https://cdn.jsdelivr.net "
            "www.googletagmanager.com "
            "x.clarity.ms "
            "https://www.googletagmanager.com "
            "https://www.google.com "
            "https://www.gstatic.com; "
            "frame-src 'self' https://www.google.com; "
            "connect-src 'self' www.googletagmanager.com "
            "https://region1.google-analytics.com; "
            "img-src 'self' data: https: blob: kura.pro "
            "www.googletagmanager.com; "
            "style-src 'self' 'unsafe-inline' "
            "https://cdn.jsdelivr.net "
            "https://fonts.googleapis.com "
            "https://cdnjs.cloudflare.com "
            "https://use.fontawesome.com; "
            "font-src 'self' https://use.fontawesome.com/; "
            "media-src 'self';"
        )


# Register security headers tool
cherrypy.tools.security_headers = SecurityHeadersTool()


class AkandeServer:
    _rate_limiter = RateLimiter(
        RATE_LIMIT_WINDOW, RATE_LIMIT_MAX_REQUESTS
    )

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
        self.public_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "public"
        )
        # Server-side cache
        directory_path = get_output_directory()
        cache_path = directory_path / CACHE_DB_NAME
        self.cache = SQLiteCache(cache_path)

        self.logger.info(
            "Server initialized",
            extra={
                "event": "Server:Initialized",
                "extra_data": {
                    "public_dir": str(self.public_dir),
                },
            },
        )

    def _get_correlation_id(self) -> str:
        """Get or generate a correlation ID for the request."""
        return cherrypy.request.headers.get(
            "X-Request-Id", str(uuid.uuid4())
        )

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

    @cherrypy.expose
    def health(self):
        """Health check endpoint."""
        cherrypy.response.headers["Content-Type"] = (
            "application/json"
        )
        return json.dumps(
            {"status": "ok", "service": "akande"}
        ).encode("utf-8")

    @cherrypy.expose
    def index(self):
        index_path = self.public_dir / "index.html"
        if not index_path.is_file():
            raise cherrypy.HTTPError(404, "Index page not found")
        return index_path.read_text(encoding="utf-8")

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
        return resolved.read_text(encoding="utf-8")

    @cherrypy.expose
    @cherrypy.tools.allow(methods=["POST"])
    def process_question(self):
        self._check_rate_limit()
        correlation_id = self._get_correlation_id()
        start_time = time.time()
        try:
            request_data = json.loads(
                cherrypy.request.body.read()
            )
            question = request_data.get("question", "")

            if (
                not isinstance(question, str)
                or not question.strip()
            ):
                cherrypy.response.status = 400
                return json.dumps(
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
                return json.dumps({"response": cached})

            response_object = (
                self.openai_service.generate_response_sync(
                    question,
                    SYSTEM_PROMPT,
                    OPENAI_DEFAULT_MODEL,
                    None,
                )
            )
            message_content = (
                response_object.choices[0].message.content
            )
            # Store in cache
            self.cache.set(prompt_hash, message_content)

            latency = (time.time() - start_time) * 1000
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
            return json.dumps({"response": message_content})

        except json.JSONDecodeError:
            self.logger.warning(
                "Invalid JSON in request",
                extra={
                    "event": "Server:BadRequest",
                    "correlation_id": correlation_id,
                },
            )
            cherrypy.response.status = 400
            return json.dumps({"error": "Invalid JSON"})
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
            return json.dumps(
                {"response": "An error occurred"}
            )

    @cherrypy.expose
    @cherrypy.tools.allow(methods=["POST"])
    def process_audio_question(self):
        self._check_rate_limit()
        correlation_id = self._get_correlation_id()
        start_time = time.time()
        try:
            audio_data = cherrypy.request.body.read()

            if len(audio_data) > MAX_AUDIO_SIZE:
                cherrypy.response.status = 400
                return json.dumps(
                    {"error": "Audio file too large"}
                )

            if len(audio_data) == 0:
                cherrypy.response.status = 400
                return json.dumps(
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
                    return json.dumps(
                        {
                            "error": processed_result.get(
                                "error",
                                "Audio processing failed",
                            )
                        }
                    )

                question = processed_result.get("text", "")
                if not question:
                    return json.dumps(
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
                    return json.dumps(
                        {"response": cached}
                    )

                response_object = (
                    self.openai_service.generate_response_sync(
                        question,
                        SYSTEM_PROMPT,
                        OPENAI_DEFAULT_MODEL,
                        None,
                    )
                )
                message_content = (
                    response_object.choices[0].message.content
                )
                self.cache.set(prompt_hash, message_content)

                latency = (time.time() - start_time) * 1000
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
                return json.dumps(
                    {"response": message_content}
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
            return json.dumps(
                {"error": "Failed to process audio"}
            ).encode("utf-8")

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
