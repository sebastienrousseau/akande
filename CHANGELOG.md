# Changelog

## [0.0.6](https://github.com/sebastienrousseau/akande/compare/v0.0.5...v0.0.6) (2026-06-15)


### Features

* **tui+design-system:** numbered menu redesign and final CSS tokenisation ([d963866](https://github.com/sebastienrousseau/akande/commit/d9638668f512b32babea59e3eece875d1a09e5a7))
* **tui:** Apple HIG dark theme, export modal, history screen, and accessibility ([42e87b3](https://github.com/sebastienrousseau/akande/commit/42e87b3a6c53f6de8048e0625615c465d46481c3))
* **v0.0.5:** Apple Messages-style Web UI, security hardening, TUI, and budgets ([bf5900b](https://github.com/sebastienrousseau/akande/commit/bf5900bdcfa6d7c7e3a3f30952ba4002cf1d8ff7))
* **v0.0.6-dev.10:** fresh-install regression suite + akande --help fix ([bdbea87](https://github.com/sebastienrousseau/akande/commit/bdbea875c3b8a024531609912ea94cc4f2b1c4dc))
* **v0.0.6-dev.1:** foundation green — CI gates, deps, auth, Docker, docs ([d2f1944](https://github.com/sebastienrousseau/akande/commit/d2f194419f8fa7fb7f369b59952fb94d98e9f1b2))
* **v0.0.6-dev.2:** Track B foundation — streaming, SSE, multi-turn store ([5e2953a](https://github.com/sebastienrousseau/akande/commit/5e2953a662d2075378497eb1d4cd0a66a2fe57cb))
* **v0.0.6-dev.3:** Track E foundation — EU AI Act Article 50 controls ([442d291](https://github.com/sebastienrousseau/akande/commit/442d291d20c82b34d7486e205fdd9e2a2a7ac485))
* **v0.0.6-dev.4:** Track B continuation — multi-turn, memory, telemetry ([38d925b](https://github.com/sebastienrousseau/akande/commit/38d925b3c34e618d2f05b421787b5e94856668ea))
* **v0.0.6-dev.5:** Track B closure + AudioSeal — TTS bytes, watermark, redaction ([453d729](https://github.com/sebastienrousseau/akande/commit/453d7296537e38dcd12423cb5d30c3db4373d4bf))
* **v0.0.6-dev.6:** Track C foundation — offline mode, tools, MCP ([45b73fe](https://github.com/sebastienrousseau/akande/commit/45b73fe36d7d5b0ace48d4e5c0694aa639360d11))
* **v0.0.6-dev.7:** Tracks A+B+C closure — STT, router, tools-in-SSE, S2S, pipeline ([0696d21](https://github.com/sebastienrousseau/akande/commit/0696d21f3ebed0445a962be56badcb3e8383dbe6))
* **v0.0.6-dev.8:** Track D foundation — skills, consent policy, CLI ([9f26358](https://github.com/sebastienrousseau/akande/commit/9f26358147e48d0382396b64164cea5a034e9c46))
* **v0.0.6-dev.9:** Track F foundation — installers, benches, HF Space, audit, release-please ([0671fc3](https://github.com/sebastienrousseau/akande/commit/0671fc30109840c6bb9e736c7dba0233189848df))
* **v0.0.6:** TUI redesign with Apple HIG alignment and feature parity ([df785cd](https://github.com/sebastienrousseau/akande/commit/df785cda82bfbeef01f3b4f2fd44ea24d89b1868))


### Bug Fixes

* **deps:** reconcile rebase — drop duplicate dev extras and strict mypy ([24c23ed](https://github.com/sebastienrousseau/akande/commit/24c23eddf3838875befa34e398d594af92eb8b87))
* **design-system:** add border-thin, radius-tight tokens and typing reduced-motion ([4971516](https://github.com/sebastienrousseau/akande/commit/4971516fce175985074784440ea5c8fc6b2f3324))
* **design-system:** fix semantic token misuse and tokenise layout constraints ([e3a0672](https://github.com/sebastienrousseau/akande/commit/e3a06720fe61133cc78eb5dfd2958617823926c5))
* **design-system:** fully tokenise typography, sizing, and structural CSS values ([7854998](https://github.com/sebastienrousseau/akande/commit/785499867add4140b538cd4a01badfd3a80e1765))
* **design-system:** tokenise all hardcoded values, enhance focus and reduced-motion ([96c5bd0](https://github.com/sebastienrousseau/akande/commit/96c5bd05138a84e666876e7147d80f7bd5fa87f8))
* **design-system:** tokenise content-max and consolidate focus styles ([d851bb6](https://github.com/sebastienrousseau/akande/commit/d851bb65e02ccb65e14c3693c8223def37db7414))
* **design-system:** tokenise motion durations and font-weight values ([a6ef66c](https://github.com/sebastienrousseau/akande/commit/a6ef66cb90d81fc2f26be3e6350819af3ec5f405))
* **lint:** resolve flake8 errors in akande, tui, and tests ([dfdf90d](https://github.com/sebastienrousseau/akande/commit/dfdf90d7597c81759a31f77d76c668d294290fb6))
* **tui:** revert to plain number shortcuts, remove input auto-focus ([f7d3212](https://github.com/sebastienrousseau/akande/commit/f7d3212a044b293320b657c694821466801f600b))
* **tui:** use Alt+number shortcuts so keys work while input is focused ([b81ff5c](https://github.com/sebastienrousseau/akande/commit/b81ff5c9b797940edc618ab216dd965d7b53a1d6))
* **v0.0.6-dev.16:** mypy unused-ignore in provider strict islands ([7f5a10f](https://github.com/sebastienrousseau/akande/commit/7f5a10fb36376f70698f9aaa00dff24af5bc1002))


### Documentation

* add system dependency steps to install guide and remove broken CONTRIBUTING.md link ([5a0cce0](https://github.com/sebastienrousseau/akande/commit/5a0cce06cef012b0c0341fc78a38863a8756785f))
* **v0.0.6-dev.20:** README QA pass — align style + refresh content ([7b1a603](https://github.com/sebastienrousseau/akande/commit/7b1a60311b9e946334dc5d7cbacdf2850e91ceaa))
* **v0.0.6-dev.21:** swap logo CDN to cloudcdn.pro SVG ([39a3c85](https://github.com/sebastienrousseau/akande/commit/39a3c856f72b8ee33f2660310dde29bdd9319035))
