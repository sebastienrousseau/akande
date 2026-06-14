# syntax=docker/dockerfile:1.7

# -----------------------------------------------------------------------------
# Stage 1: builder — build wheels for akande and its runtime dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build deps for native wheels (PyAudio needs portaudio headers, etc.)
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        portaudio19-dev \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml requirements.txt setup.cfg setup.py README.md ./
COPY akande ./akande

RUN python -m pip install --upgrade pip setuptools wheel build \
    && python -m pip wheel --wheel-dir /wheels -r requirements.txt \
    && python -m pip wheel --wheel-dir /wheels .

# -----------------------------------------------------------------------------
# Stage 2: runtime — minimal image with only what's needed at run time
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    AKANDE_HOST=0.0.0.0 \
    AKANDE_PORT=8080

# Runtime system deps: PortAudio runtime, PulseAudio client, ffmpeg, tini.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        libportaudio2 \
        libsndfile1 \
        pulseaudio-utils \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 akande \
    && useradd  --system --uid 1000 --gid akande --create-home --home-dir /home/akande akande

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels akande \
    && rm -rf /wheels

# Application assets (Web UI, public/static, docs)
COPY --chown=akande:akande public ./public
COPY --chown=akande:akande pulse-client.conf /etc/pulse/client.conf

USER akande

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).status == 200 else 1)" \
        || exit 1

# tini handles PID 1 duties (signal forwarding, zombie reaping).
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "akande"]
