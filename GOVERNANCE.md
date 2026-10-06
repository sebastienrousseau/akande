<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Àkàndé Governance

This document describes how Àkàndé is run, how decisions are made, and how
to contribute. It exists to make the project legible and sustainable.

## Mission and scope

Àkàndé is a self-hosted, provider-agnostic voice assistant that delivers
structured executive briefings via voice or text across LLM providers.
Changes are weighed against that scope: correctness, privacy, and security
over feature breadth.

## Roles

| Role | Who | Can |
| :--- | :--- | :--- |
| **Maintainer** | Sebastien Rousseau (@sebastienrousseau) | Merge PRs, cut releases, triage, set direction |
| **Contributor** | Anyone with a merged PR | Propose changes, review, discuss |
| **User** | Everyone | File issues, ask questions, request features |

Maintainers are listed as code owners in [`.github/CODEOWNERS`](.github/CODEOWNERS)
for review routing.

## Decision making

- **Day-to-day changes** (fixes, docs, tests, additive features within scope)
  proceed by **lazy consensus**: open a PR; if no maintainer objects and CI is
  green, a maintainer merges it.
- **Significant changes** (new public APIs, breaking changes, new dependencies)
  need explicit approval from a maintainer in the PR, and should start as an issue
  or discussion.
- **Disagreement** is resolved by discussion aiming for consensus; if none is
  reached, the lead maintainer decides and records the rationale in the issue.

Every change must pass the full quality gate (tests at the >= 95% coverage floor,
`mypy akande`, `ruff check`, `bandit`, and `pip-audit`).
