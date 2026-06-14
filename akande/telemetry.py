# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""OpenTelemetry traces + metrics for Àkàndé.

This module is the single seam between Àkàndé's hot paths and any
external observability backend.  It exposes a small typed surface
— :func:`tracer`, :func:`span`, :func:`record_metric` — that the
caller can use without importing ``opentelemetry`` directly.  When
the ``opentelemetry-api`` package is unavailable, or when the
operator's profile opts out of telemetry, the helpers degrade to
silent no-ops so existing call sites never branch.

Configuration
-------------
- ``AKANDE_TELEMETRY=1`` is the *master switch*.  Without it the
  module is a no-op regardless of OTel availability.  We default
  off so simply installing Àkàndé never quietly emits telemetry.
- ``OTEL_EXPORTER_OTLP_ENDPOINT`` set → install an OTLP exporter.
- Unset → install the console exporter (useful in development).
- ``AKANDE_PROFILE`` with ``telemetry_opt_in=False`` (the default
  for ``eu``, ``strict``, ``internal``) **forces** telemetry off
  even when ``AKANDE_TELEMETRY=1`` is set.  This makes compliance
  the dominant policy: a misconfigured ``AKANDE_TELEMETRY`` cannot
  defeat the operator's chosen profile.

Naming
------
Span names follow ``<surface>.<stage>``: ``llm.stream``,
``stt.transcribe``, ``tts.synthesise``, ``cache.get``,
``cache.set``, ``audit.sign``, ``conversation.append_turn``.
Metric names use the same convention with ``.duration_ms``,
``.tokens_in``, ``.tokens_out``, ``.chars_out`` suffixes.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

# Lazy-loaded once on first :func:`init` call; treated as immutable
# afterwards so concurrent callers see a consistent view.
_initialised = False
_enabled = False
_tracer: Any = None
_meter: Any = None


def _opentelemetry_available() -> bool:
    try:
        import opentelemetry.trace  # noqa: F401
        import opentelemetry.metrics  # noqa: F401
    except ImportError:  # pragma: no cover - dep-presence check
        return False
    return True


def init(force: bool = False) -> bool:
    """Initialise tracer + meter providers based on env + profile.

    Returns ``True`` when telemetry is active after the call,
    ``False`` if disabled.  Subsequent calls are no-ops unless
    ``force=True`` (tests).
    """
    global _initialised, _enabled, _tracer, _meter
    if _initialised and not force:
        return _enabled

    _initialised = True
    _enabled = False
    _tracer = None
    _meter = None

    # Avoid an import cycle — profiles imports nothing else heavy,
    # but keep the import local.
    if os.getenv("AKANDE_TELEMETRY", "0") != "1":
        logger.debug(
            "Telemetry disabled — AKANDE_TELEMETRY not set",
            extra={"event": "Telemetry:NotRequested"},
        )
        return False

    from akande.profiles import active_profile

    profile = active_profile()
    if not profile.telemetry_opt_in:
        logger.info(
            "Telemetry disabled by profile",
            extra={
                "event": "Telemetry:OptedOut",
                "extra_data": {"profile": profile.name},
            },
        )
        return False

    if not _opentelemetry_available():
        logger.info(
            "Telemetry disabled — opentelemetry-api not installed",
            extra={"event": "Telemetry:NotInstalled"},
        )
        return False

    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )

    resource = Resource.create(
        {
            "service.name": "akande",
            "service.namespace": "akande",
        }
    )

    otlp_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    tracer_provider = TracerProvider(resource=resource)
    span_exporter: Any
    if otlp_endpoint:  # pragma: no cover - needs OTLP endpoint
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            span_exporter = OTLPSpanExporter(
                endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces"
            )
        except ImportError:
            logger.warning(
                "OTLP HTTP exporter not installed — falling "
                "back to console exporter",
                extra={"event": "Telemetry:OtlpUnavailable"},
            )
            span_exporter = ConsoleSpanExporter()
    else:
        span_exporter = ConsoleSpanExporter()
    tracer_provider.add_span_processor(
        BatchSpanProcessor(span_exporter)
    )
    trace.set_tracer_provider(tracer_provider)
    _tracer = trace.get_tracer("akande")

    metric_reader = PeriodicExportingMetricReader(
        ConsoleMetricExporter(),
        export_interval_millis=60_000,
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    metrics.set_meter_provider(meter_provider)
    _meter = metrics.get_meter("akande")

    _enabled = True
    logger.info(
        "Telemetry initialised",
        extra={
            "event": "Telemetry:Initialised",
            "extra_data": {
                "exporter": (
                    "otlp" if otlp_endpoint else "console"
                ),
                "endpoint": otlp_endpoint or "(console)",
            },
        },
    )
    return True


def is_enabled() -> bool:
    return _enabled


def tracer() -> Any:
    return _tracer


def meter() -> Any:
    return _meter


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """Open a span with ``attributes`` set, yielding the span object.

    When telemetry is disabled this is a zero-cost generator that
    yields ``None``; callers can write::

        with telemetry.span("llm.stream", provider=p) as s:
            ...

    without branching on whether OTel is wired up.
    """
    if not _enabled or _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name) as sp:
        for key, value in attributes.items():
            try:
                sp.set_attribute(key, value)
            except Exception:  # pragma: no cover
                pass
        try:
            yield sp
        except Exception as exc:  # pragma: no cover - re-raises
            try:
                sp.record_exception(exc)
            except Exception:  # pragma: no cover
                pass
            raise


def record_metric(
    name: str,
    value: float,
    unit: str = "1",
    **attributes: Any,
) -> None:
    """Record a histogram observation by name.

    Histograms are created lazily and cached on the meter object so
    repeated calls don't allocate; this matches the OTel SDK's own
    pattern.
    """
    if not _enabled or _meter is None:
        return
    cache = getattr(_meter, "_akande_hist_cache", None)
    if cache is None:
        cache = {}
        try:
            setattr(_meter, "_akande_hist_cache", cache)
        except Exception:  # pragma: no cover
            return
    hist = cache.get(name)
    if hist is None:
        try:
            hist = _meter.create_histogram(
                name, unit=unit
            )
            cache[name] = hist
        except Exception:  # pragma: no cover
            return
    try:
        hist.record(value, attributes=attributes)
    except Exception:  # pragma: no cover
        pass


def _reset_for_tests() -> None:
    """Reset module state so tests can re-init with patched env."""
    global _initialised, _enabled, _tracer, _meter
    _initialised = False
    _enabled = False
    _tracer = None
    _meter = None
