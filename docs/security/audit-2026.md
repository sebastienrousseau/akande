# External security audit — placeholder

> Status: **commissioned for v0.0.6 GA.**  This page is a tracking
> document; the actual report replaces it once the engagement
> closes.

## Why this page exists

The v0.0.6 plan (`~/Drop/akande-ip.md` §4 Track F) commits to a
real external audit before the release earns the "audit-grade"
positioning the README claims.  Until the engagement closes the
README points operators at the v0.0.5 self-assessment in
[SECURITY.md](../../SECURITY.md), and this page tracks remediation
of any findings that surface during the audit.

The previous "Euxis-audited" line was removed in v0.0.6-dev.1 —
this is its replacement.

## Scope of engagement

Engagement scope as proposed:

- Threat modelling of the web/HTTP surface (`akande/server/server.py`,
  the SSE briefing endpoint, the API-key auth flow).
- Review of the EU AI Act Article 50 controls and the Ed25519
  audit-signing chain in `akande/audit.py` / `akande/watermark.py`.
- Review of the MCP server + client (`akande/mcp/`) — both the
  tools we expose and the policy enforcement on tools we consume.
- Review of the prompt-injection envelope + outbound exfiltration
  scrub in `akande/safety.py`.
- Review of the sandbox boundary for any execution tools shipped
  in v0.0.6 (today this is just `python_eval` deferred to dev.9 —
  the audit can review it alongside dev.9).
- Dependency review against the dev.7 pyproject extras, focused
  on the optional packages that pull native code (`audioseal`,
  `faster-whisper`, `kokoro-onnx`).

## Findings + remediation

| ID | Severity | Title | Status | Notes |
|----|----------|-------|--------|-------|
| —  | —        | (none yet — engagement not started) | — | — |

## How to engage with the auditor

The maintainer (Sebastien Rousseau) drives the engagement; once
the auditor is selected this section will list:

- Auditor name + contact
- SOW link + start date
- Expected report delivery date
- PGP / signal key for sensitive findings

## When this page is replaced

The full report lands here, in this same path, with the
"placeholder" header replaced by the audit's executive summary
and a permalinked PDF in `docs/security/audit-2026.pdf`.  The
README's *Trust* section then links here directly.
