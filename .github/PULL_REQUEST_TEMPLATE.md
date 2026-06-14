<!-- Thanks for the contribution. Please fill in the sections below. -->

## Summary

<!-- One or two sentences describing what changed and why. -->

## Type of change

<!-- Tick all that apply. -->

- [ ] `feat`: new user-visible capability
- [ ] `fix`: bug fix
- [ ] `perf`: performance improvement
- [ ] `refactor`: code change with no functional impact
- [ ] `docs`: documentation only
- [ ] `test`: test-only change
- [ ] `chore` / `ci`: tooling, deps, CI
- [ ] `security`: security-relevant change

## Linked issues

<!-- e.g. Closes #123 -->

## How was this tested?

<!-- Manual steps, new tests added, etc. Paste the relevant pytest
     summary or a screenshot for UI changes. -->

## Quality gates

- [ ] `flake8` passes
- [ ] `mypy akande` passes
- [ ] `pytest --cov` passes (coverage ≥ 55 % for v0.0.6-dev.2; ratcheting to 75 % by GA)
- [ ] `bandit -r akande -ll -q` clean
- [ ] `pip-audit --strict` clean
- [ ] README / docs updated where applicable

## Scope

- [ ] This change is in scope for the current v0.0.6 release plan
      (see `~/Drop/akande-ip.md` or the project board).
- [ ] If out of scope, I have flagged it for v0.0.7+ consideration.

## Breaking change?

- [ ] No
- [ ] Yes — described below, with migration notes for users:

<!-- Describe migration here if applicable. -->

## Compliance / Security review

<!-- Tick if the change touches any of these areas. -->

- [ ] Touches authentication, rate limiting, or input validation
- [ ] Touches PII handling, logging, or cache contents
- [ ] Touches voice cloning, watermarking, or AI disclosure
- [ ] Touches EU AI Act Article 50 controls

<!-- If any of the above are ticked, please add `@security-review` to
     reviewers and reference the relevant section of SECURITY.md. -->
