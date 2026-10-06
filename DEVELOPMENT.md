<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Development

The single entry point for working on `akande`: toolchain, how to
reproduce every CI gate locally, where tests live, and how releases happen.

## Toolchain

| Tool | Version | Where it is pinned |
| :--- | :--- | :--- |
| Python | 3.12 for local development; 3.10 is the floor | `pyproject.toml` (`requires-python = ">=3.10"`), CI matrix 3.10 to 3.14 |
| uv / pip | Latest | `requirements.txt` for pinned dependencies; `pyproject.toml` for ranges |

```bash
git clone https://github.com/sebastienrousseau/akande
cd akande
uv venv
uv pip install -e ".[all,dev]" mcp
```

## Reproducing every CI gate

| Gate | Local command | Purpose |
| :--- | :--- | :--- |
| Tests & Coverage | `uv run --extra dev pytest` | Run test suite with >= 95% line+branch coverage gate |
| Lint | `uv run --extra dev ruff check .` | Verify code quality and styling rules |
| Formatting | `uv run --extra dev ruff format --check .` | Verify code formatting |
| Typecheck | `uv run --extra dev mypy akande` | Static type checking |
| Security | `uv run --extra dev bandit -r akande -ll -q` | Security linter |
| Vulnerabilities | `uv run --extra dev pip-audit --skip-editable --ignore-vuln PYSEC-2026-2132` | Dependency CVE audit |
| Regression suite | `./scripts/regression.sh` | Clean-environment end-to-end regression |

## Test layout

```
tests/
  test_<module>.py      unit tests, one file per module or concern
  test_tools.py         tools testing including SSRF prevention
  test_server_routes.py route testing and voice hardening assertions
  test_stt.py           STT backend and transcriber tests
  test_watermark.py     AudioSeal watermarking unit and integration tests
```
