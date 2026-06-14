# Contributing to Àkàndé

Thanks for your interest in contributing. This document describes the
ground rules and the local development loop.

## Code of Conduct

By participating you agree to abide by the [Code of Conduct](.github/CODE-OF-CONDUCT.md).

## Reporting bugs and security issues

- **Non-security bugs**: open a GitHub issue using the bug-report template.
- **Security vulnerabilities**: please do not open a public issue. Follow
  the disclosure process in [SECURITY.md](SECURITY.md).

## Development setup

```bash
git clone https://github.com/sebastienrousseau/akande.git
cd akande

# System deps (one-off)
# macOS:  brew install portaudio ffmpeg
# Ubuntu: sudo apt install portaudio19-dev ffmpeg

python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e ".[all,dev]"

cp .env.example .env
# Edit .env to set OPENAI_API_KEY or another provider
```

## Local quality gates (mirror of CI)

```bash
# Lint
flake8

# Type-check (strict islands enforced for providers/, cache.py, budgets.py)
mypy akande

# Tests + coverage (floor is 55% in v0.0.6-dev.2 after TUI debt
# from rebase; ratcheting back through 60% toward 75% by GA via
# a dedicated TUI-tests sub-track — do not lower, only raise)
pytest --cov=akande --cov-report=term-missing --cov-fail-under=55

# SAST
bandit -r akande -ll -q

# Vulnerable dependencies
pip-audit --strict
```

All five must pass before a PR is mergeable.

## Pull-request workflow

1. Fork the repo and create a feature branch from `main`
   (e.g. `feat/`*xxx*, `fix/`*yyy*, `docs/`*zzz*).
2. Keep PRs small and focused. Prefer multiple small PRs over a single
   large one.
3. Follow [Conventional Commits](https://www.conventionalcommits.org/)
   in commit messages (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`,
   `test:`, `perf:`, `ci:`).
4. Add or update tests for any user-visible behaviour change.
5. Update `README.md` and any affected docs.
6. Fill in the PR template; link the issue it resolves.
7. CI must be green (lint, test, typecheck, security, build).

## Commit signing

The project uses signed commits where possible. See the
[GitHub docs on commit signing](https://docs.github.com/en/authentication/managing-commit-signature-verification)
for setup.

## Style

- **Python**: black (line length 72), isort (black profile), flake8
  (max line length 79). pre-commit hooks enforce all three.
- **Type hints**: required for everything under `akande/providers/`,
  `akande/cache.py`, `akande/budgets.py`, and `akande/exceptions.py`.
  Encouraged everywhere else.
- **Docstrings**: short imperative summaries; avoid restating the
  signature.
- **Comments**: explain *why*, not *what*. Don't leave commented-out
  code in PRs.

## What we are *not* looking for in v0.0.x

To keep the v0.0.6 release scope coherent the following are out of
scope and will be politely declined or deferred:

- Tauri desktop / mobile wrappers (v0.0.7+).
- Wake-word implementations and skill marketplaces (v0.0.7+).
- Home Assistant integrations (v0.0.7+).
- Provider additions beyond the existing 10 (after MCP lands, route
  via MCP instead).
- Breaking API changes to the public CLI surface.

See `~/Drop/akande-ip.md` or the GitHub project board for the
authoritative scope.

## Release process

Maintainer-only. See `.github/workflows/ci.yml` — pushing a tag to
`main` triggers PyPI publication and a GitHub release.

## Licence

By contributing, you agree that your contributions will be dual
licensed under the [Apache 2.0](LICENSE-APACHE) and [MIT](LICENSE-MIT)
licences.
