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
| **§50(2)** Mark AI-generated synthetic audio in a machine-readable form | AudioSeal watermark on every TTS output | **Pending v0.0.6-dev.4** — TTS pipeline restructure required before AudioSeal integration | scheduled |
| **§50(3)** Label deepfakes / cloned voices | Refuse to clone any reference voice without a recorded consent capture; cloned voices labelled in metadata | `Profile.refuse_voice_clone_without_consent` is always `True`; no cloning surface exists yet, so the refusal is enforced by absence.  Consent log & clone surface ship in v0.0.6-dev.4. | scheduled |
| **§50(4)** Inform users when they are exposed to AI-generated text on public-interest topics | Same AI-disclosure utterance covers the briefing path | `akande/disclosure.py` | `tests/test_disclosure.py` |
| **§50(5)** Provide information in a clear and distinguishable manner at the start of the interaction | Disclosure is the **first** SSE event after the meta frame; banner is the first paragraph in the Web UI conversation | `_sse_briefing()` event ordering | `tests/test_sse_endpoint.py` |

## Adjacent obligations the EU mode also handles

| Requirement | Control | Implementation |
|---|---|---|
| **GDPR Art. 9 — biometric voice data** | Voice cloning gated by explicit consent; no training on user voice without opt-in | `Profile.refuse_voice_clone_without_consent`; consent capture surface in v0.0.6-dev.4 |
| **GDPR Art. 15 — right of access** | `akande data export --user <id>` dumps all conversations + turns to JSON | `akande/cli/data.py` |
| **GDPR Art. 17 — right to erasure** | `akande data delete --user <id> --yes` cascades through the SQLite store | `akande/cli/data.py` |
| **GDPR Art. 30 — record of processing** | Ed25519-signed audit sidecar (`<pdf>.audit.json`) embedding model, provider, profile, prompt hash, response hash, timestamp | `akande/audit.py`, `akande/utils.py` `_maybe_sign_briefing()` |
| **EU AI Act Recital 60 — prompt injection resilience** | System-prompt envelope + user-input delimiters + outbound secret scrubbing | `akande/safety.py` |
| **Operator data-residency hint** | EU-only API endpoints when set | `Profile.eu_residency_hint` — surfaced to the operator now; provider-endpoint enforcement lands with the routing rewrite in v0.0.6-dev.5 |
| **Cache PII redaction** | Optional regex / presidio-based redaction of prompts persisted in the SQLite cache | `Profile.cache_redact_pii`; integration lands with the cache redaction rewrite alongside watermarking |

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

## What is *not yet* in v0.0.6-dev.3

These are scheduled for v0.0.6-dev.4 and tracked on the project
board:

- **AudioSeal watermark** on TTS output (Article 50 §2 — required
  for full Article 50 coverage of synthetic audio).  Requires
  refactoring the TTS path in `akande/akande.py` to surface audio
  bytes before playback.
- **Voice cloning consent capture flow** with HMAC-signed consent
  log under `$AKANDE_HOME/consent/`.
- **PDF/A-3b embedded audit attachment** as an alternative to the
  sidecar JSON file (cleaner deliverable; same signature scheme).
- **Cache PII redaction** wired into `akande/cache.py` writes when
  `Profile.cache_redact_pii` is on.
- **Provider endpoint allow-list** for `Profile.eu_residency_hint`.

## Test evidence

Run the Track E test suite:

```bash
pytest tests/test_profiles.py tests/test_safety.py \
       tests/test_disclosure.py tests/test_audit.py \
       tests/test_cli_data.py -v
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
