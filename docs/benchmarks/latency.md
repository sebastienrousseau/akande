# Àkàndé latency budget — synthetic mode

_N = 50 iterations per stage (placeholder — regenerate with the
real numbers before publishing)_

| stage | P50 (ms) | P95 (ms) | mean (ms) |
|---|---|---|---|
| STT  | TBD | TBD | TBD |
| LLM  | TBD | TBD | TBD |
| TTS  | TBD | TBD | TBD |
| E2E  | TBD | TBD | TBD |

Regenerate this file with:

```bash
python bench/latency.py --n 100 --real --output docs/benchmarks/latency.md
```

The numbers above are produced by the synthetic-mode benchmark
shipped alongside the codebase; the real-mode numbers will replace
them once a v0.0.6 release is cut against a known hardware
profile.

## What the targets are

The v0.0.6 plan in `~/Drop/akande-ip.md` §4 sets these budgets:

- STT (cascade local):     200 ms P95
- LLM first-token:         250 ms P95
- TTS first-audio:         300 ms P95
- Barge-in:                150 ms P95
- E2E cascade:           < 1,500 ms P95

The benchmark is intentionally simple so it can be re-run on every
release.  When a real-mode regression bumps any P95 by more than
20 % we treat it as a blocker for the release.
