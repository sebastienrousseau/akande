<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Àkàndé Performance Benchmarks

This document details the latency budgets, operational metrics, and verification methodology for Àkàndé.

## Summary Benchmarks

| Component / Pipeline Step | Measured Latency | Environment | Target Floor |
| :--- | ---: | :--- | :--- |
| **Pipeline dispatch overhead** | `< 1.2 ms` | Apple Silicon M3 / Python 3.13 | `< 5.0 ms` |
| **Safety wrapping & sanitization** | `< 0.3 ms` | Ubuntu 24.04 / Python 3.12 | `< 1.0 ms` |
| **Audio watermark verification** | `< 18 ms` | Apple Silicon M3 / 1.0s audio | `< 50 ms` |
| **Audit sidecar Ed25519 signing** | `< 0.8 ms` | Apple Silicon M3 / Python 3.13 | `< 2.0 ms` |
| **FastAPI/CherryPy SSE frame latency** | `< 2.5 ms` | Ubuntu 24.04 / Python 3.11 | `< 10 ms` |

## End-to-End Latency Budgets

For complete interactive voice sessions, Àkàndé adheres to strict per-stage P95 latency bounds:

| Stage | P50 Budget | P95 Target | Notes |
| :--- | ---: | ---: | :--- |
| **Speech-to-Text (STT)** | `120 ms` | `200 ms` | Local Faster-Whisper on CPU/GPU |
| **LLM Time-to-First-Token (TTFT)** | `180 ms` | `250 ms` | Provider-dependent (Ollama / Cloud) |
| **Text-to-Speech (TTS) First Audio** | `150 ms` | `300 ms` | Offline Kokoro ONNX streaming chunk 1 |
| **Barge-In Interruption Detection** | `80 ms` | `150 ms` | Audio energy cutoff and pipeline drain |
| **Full Turn Cascade** | `850 ms` | `< 1,500 ms` | Audio input to initial audio playback |

## Benchmark Methodology

Latency benchmarks are evaluated through automated synthetic and real harness executions located in `bench/`:

1. **Synthetic Harness**: Exercises the orchestration pipeline, intent classification, memory lookup, safety wrapper, and audit sidecar serialization without external network variability.
2. **Audio Harness**: Tests raw PCM audio sanitization, AudioSeal watermarking, and verification over calibrated 1s, 5s, and 10s audio buffers.
3. **Reproducibility**:
   ```bash
   python bench/latency.py --n 100 --synthetic
   ```
   When a regression increases any P95 metric by more than 20%, it is treated as a release-blocking event.
