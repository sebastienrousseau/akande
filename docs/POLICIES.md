<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Policies and Governance

This document establishes the toolchain baseline, versioning standards, and operational invariants governing Àkàndé.

## 1. Toolchain Support Policy

### Python Floor: Python >= 3.10
- Àkàndé supports all non-end-of-life Python releases from `3.10` upwards.
- Tested and verified CI matrix: `3.10`, `3.11`, `3.12`, `3.13`, `3.14`.
- **Policy for Raising the Floor**:
  - The minimum supported Python version is raised only when the oldest supported release reaches official upstream end-of-life (EOL).
  - Bumping the Python floor is treated as a breaking change and occurs only with advance deprecation notices.

## 2. Semantic Versioning Lifecycle

- **Initial Line**: All release cycles proceed along the `0.0.x` series.
- **Increment Policy**: Public versions strictly increment by `0.0.1` per release iteration (`v0.0.1` -> `v0.0.2` -> ... -> `v0.0.999` -> `v0.1.0`).
- **Milestone Maturity**: `v0.1.0` is permitted only after completing all releases through `v0.0.999`.
- **Source of Truth**: Version definitions must be synchronized across `pyproject.toml`, `akande/__init__.py`, and `CITATION.cff`.

## 3. Pull Request and Release Governance

- **Single Active Release PR**: There is at most one active pull request targeting `main`, corresponding to the current release iteration branch `feat/v<next-version>`.
- **Branch Funneling**: Dependabot updates, security patches, and auxiliary feature branches must funnel into the active release branch rather than merging directly into `main`.
- **Merge Authority**: Automated agents do not execute release merges; final merge authority belongs exclusively to the human maintainer.

## 4. Verification Gates

Before concluding changes or preparing release iterations, every gate must pass cleanly:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev mypy akande
uv run --extra dev bandit -r akande -ll -q
uv run --extra dev pip-audit --skip-editable --ignore-vuln PYSEC-2026-2132
```
