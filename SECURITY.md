# Security Policy

## Supported Versions

Only the most recent minor release line receives security updates.

| Version | Supported |
|---------|-----------|
| 0.0.x   | ✅        |
| < 0.0.5 | ❌        |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security problems.

Email **sebastian.rousseau@gmail.com** with subject prefix
`[security][akande]`. Include:

- Type of issue (e.g. prompt injection, RCE, SSRF, auth bypass, path
  traversal, dependency CVE).
- Full paths of source files related to the manifestation of the issue.
- Affected commit / branch / tag.
- Step-by-step reproduction instructions.
- Proof-of-concept code where possible.
- Impact assessment: what an attacker can achieve.

We will acknowledge receipt within 72 hours, share a triage decision
within 7 days, and aim to ship a fix within 30 days for high-severity
issues. Coordinated disclosure is preferred; we will credit you in the
release notes unless you ask otherwise.

## Security model (v0.0.5 baseline)

The Web UI ships with:

- Content-Security-Policy with per-request nonces on `<script>` and
  `<style>`.
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy: microphone=(self)`.
- Custom-header CSRF check on POST/PUT routes.
- Per-IP rate limiting (in-memory, 20 req / 60 s; v0.0.6 adds a Redis
  backend for distributed deployments).
- CSV-formula injection prevention (`=`, `+`, `-`, `@`, `\t`, `\r`
  cells prefixed with `'`).
- Filename sanitisation strips `"`, `\r`, `\n`, `\\`.
- IP addresses SHA-256-hashed in logs (PII protection).

## v0.0.6 hardening adds

- API-key authentication on `/api/*` routes (`X-Akande-Key`).
- Pluggable rate-limit backend (in-memory default, Redis optional).
- Cache key uses HMAC-SHA256 over `(provider, model, prompt)`; default
  TTL reduced from 7 days to 24 hours.
- Optional PII redaction in cache via `AKANDE_CACHE_REDACT_PII=1`.
- EU AI Act Article 50 controls (AI-disclosure, audio watermarking,
  consent log) — see [docs/compliance/eu.md](docs/compliance/eu.md).
- Signed audit trail (Ed25519) embedded in briefing PDFs.

## Threats considered out of scope

- Physical access to a machine running Àkàndé.
- A user with valid `AKANDE_API_KEY` access misusing the server (use
  per-key quotas if this is a concern).
- LLM-provider-side data handling — see your provider's data policy.
- Side-channel attacks on speech recognition (e.g. acoustic leakage).

## Vulnerability disclosures

| ID | Severity | Fixed in | Notes |
|----|----------|----------|-------|
| — | — | — | None disclosed to date |
