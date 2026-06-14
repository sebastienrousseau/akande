# EU AI Act Article 50 — Àkàndé compliance map

> Status: v0.0.6-dev.3 — Track E foundation
> Article 50 binding date: **2 August 2026**
> Maintainer contact: see [SECURITY.md](../../SECURITY.md)

This document maps each Article 50 obligation that applies to a
voice / chat AI assistant to the Àkàndé module that implements it,
together with the test that proves the control is wired up.
Operators deploying Àkàndé in the EU should run the system with
`AKANDE_PROFILE=eu` to activate all of the controls below.

## How to activate EU mode

```bash
# .env or environment
AKANDE_PROFILE=eu
```

That single flag flips every control in this matrix on.  The active
profile is logged at server startup (`Profile:Resolved` event).
Use `AKANDE_PROFILE=strict` for the same controls minus the EU
data-residency hint.

## Control matrix

| Article 50 obligation | Àkàndé control | Implementation | Verification |
|---|---|---|---|
| **§50(1)** Inform users they are interacting with AI unless the interaction is obvious | AI-disclosure utterance / banner emitted at session start | `akande/disclosure.py` → `should_disclose()`, `get_disclosure_text()`; wired into the SSE route in `akande/server/server.py` `_sse_briefing()` (`type: "disclosure"` event before any deltas) | `tests/test_disclosure.py`, `tests/test_sse_endpoint.py` |
| **§50(2)** Mark AI-generated synthetic audio in a machine-readable form | AudioSeal watermark on every TTS output | `akande/watermark.py` → `watermark_audio()`; invoked in `akande/akande.py` `speak()` when `Profile.audio_watermark` is true.  Install with `pip install akande[watermark]` (pulls audioseal + torch + torchaudio).  Fail-open posture if audioseal is missing — logs a throttled warning every 60 s rather than blocking delivery. | `tests/test_watermark.py`; AudioSeal round-trip test runs when the dep is installed |
| **§50(3)** Label deepfakes / cloned voices | Refuse to clone any reference voice without a recorded consent capture; cloned voices labelled in metadata | `Profile.refuse_voice_clone_without_consent` is always `True`; no cloning surface exists yet, so the refusal is enforced by absence.  Consent log & clone surface ship in v0.0.6-dev.4. | scheduled |
| **§50(4)** Inform users when they are exposed to AI-generated text on public-interest topics | Same AI-disclosure utterance covers the briefing path | `akande/disclosure.py` | `tests/test_disclosure.py` |
| **§50(5)** Provide information in a clear and distinguishable manner at the start of the interaction | Disclosure is the **first** SSE event after the meta frame; banner is the first paragraph in the Web UI conversation | `_sse_briefing()` event ordering | `tests/test_sse_endpoint.py` |

## Adjacent obligations the EU mode also handles

| Requirement | Control | Implementation |
|---|---|---|
| **GDPR Art. 9 — biometric voice data** | Voice cloning gated by explicit consent; no training on user voice without opt-in | `Profile.refuse_voice_clone_without_consent`; consent capture surface in v0.0.6-dev.4 |
| **GDPR Art. 15 — right of access** | `akande data export --user <id>` dumps all conversations + turns *and Mem0 long-term memories* to JSON | `akande/cli/data.py` `_dump_user()` (Mem0 wired in v0.0.6-dev.5) |
| **GDPR Art. 17 — right to erasure** | `akande data delete --user <id> --yes` cascades through the SQLite store *and forgets every Mem0 atom for that user* | `akande/cli/data.py` `_delete()` (Mem0 wired in v0.0.6-dev.5) |
| **GDPR Art. 30 — record of processing** | Ed25519-signed audit sidecar (`<pdf>.audit.json`) embedding model, provider, profile, prompt hash, response hash, timestamp | `akande/audit.py`, `akande/utils.py` `_maybe_sign_briefing()` |
| **EU AI Act Recital 60 — prompt injection resilience** | System-prompt envelope + user-input delimiters + outbound secret scrubbing | `akande/safety.py` |
| **Operator data-residency hint** | EU-only API endpoints when set | `Profile.eu_residency_hint` — surfaced to the operator now; provider-endpoint enforcement lands with the routing rewrite in v0.0.6-dev.5 |
| **Cache PII redaction** | Regex (default) or `presidio-analyzer` (when installed) redaction of email / phone / IBAN / credit-card patterns in cached responses | `akande/cache.py` `_redact_pii()`; gated by `Profile.cache_redact_pii` (on for `eu` / `strict` / `internal`) |

## Audit signature verification

Every signed briefing produces a sidecar at `<pdf-path>.audit.json`.

```bash
# Verify a single briefing
akande verify-pdf ~/.akande/output/2026-06-14/briefing-1413.pdf
# → OK  signature verifies for …/briefing-1413.pdf.audit.json
```

The signing key lives at `$AKANDE_HOME/keys/signing.ed25519` (0600
permissions; the public key is at `signing.pub`).  The keypair is
generated on first sign / verify call.  Rotation: delete the
private key and re-run; new briefings sign with the new key.

## What is *not yet* in v0.0.6-dev.5

These remain on the v0.0.6-dev.6+ list and are tracked on the
project board:

- **Voice cloning consent capture flow** with HMAC-signed consent
  log under `$AKANDE_HOME/consent/`.  Blocked on the voice-cloning
  surface itself, which isn't shipped yet.
- **PDF/A-3b embedded audit attachment** as an alternative to the
  sidecar JSON file (cleaner deliverable; same signature scheme).
- **Provider endpoint allow-list** for `Profile.eu_residency_hint`
  — currently the flag is surfaced to the operator but enforcement
  is documentation-only.
- **Watermark verification on inbound audio** in the SSE path —
  today the watermark is applied; verification of *inbound* user
  audio (for the same-AI detection that Article 50 §4 hints at)
  ships with the realtime cascade pipeline.

## Test evidence

Run the Track E test suite:

```bash
pytest tests/test_profiles.py tests/test_safety.py \
       tests/test_disclosure.py tests/test_audit.py \
       tests/test_cli_data.py tests/test_tts.py \
       tests/test_watermark.py tests/test_cache_redaction.py -v
```

Watermark integration tests (≥98 % bit-recovery after MP3 128 kbps)
run when `audioseal` is on the path; they self-skip otherwise:

```bash
pip install akande[watermark]
pytest tests/test_watermark.py::TestRoundTripIntegration -v
```

All controls are also exercised end-to-end via the SSE endpoint
tests in `tests/test_sse_endpoint.py`.

## Disclaimer

This document maps Àkàndé's technical controls to Article 50 of
the EU AI Act and to the most directly relevant GDPR articles.
It is **not legal advice**.  Operators deploying Àkàndé in the EU
must perform their own legal review.  The Àkàndé maintainers will
ratchet this matrix as implementation lands; the table above is
the source of truth for which control is verifiable in the current
release.
