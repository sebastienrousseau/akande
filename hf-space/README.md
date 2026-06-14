---
title: Àkàndé
emoji: 🗣️
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: "4.44.0"
app_file: app.py
pinned: true
license: apache-2.0
short_description: >
  EU AI Act-ready, self-hosted voice AI for structured executive
  briefings. Cascade today, realtime soon.
---

# `hf-space` — Àkàndé on Hugging Face Spaces

Live demo of the [`akande`](https://github.com/sebastienrousseau/akande)
voice assistant. The Space boots with `AKANDE_PROFILE=eu` so every
request exercises the Article 50 controls (AI disclosure, AudioSeal
watermark when installed, signed audit sidecars).

---

## One-off setup

```bash
# From the root of the akande repo.
git remote add hf https://huggingface.co/spaces/akande/akande
```

## Deploy or refresh the Space

```bash
# Push the hf-space/ subtree as the Space's main branch.
git subtree push --prefix hf-space hf main
```

`hf-space/app.py` is the Space entry point. Any Gradio surface added
to the package (for example, a new tab when S2S streaming ships)
lands here too.

---

## Space secrets

Set these from the Hugging Face UI under *Settings → Secrets*:

| Secret | Purpose |
|---|---|
| `OPENAI_API_KEY` | Cloud LLM + TTS + S2S backends |
| `ANTHROPIC_API_KEY` *(optional)* | Alternative LLM provider |
| `AKANDE_PROFILE` *(optional)* | Override the `eu` profile set by `app.py` |
| `HF_TOKEN` *(optional)* | Gate the Space behind Hugging Face auth |

Without `OPENAI_API_KEY` the Space falls back to a clearly-labelled
stub reply so the demo still loads end-to-end.

---

## ZeroGPU

The Space targets a ZeroGPU H200 slot — keep the model footprint
small so cold-start stays fast. Heavy local backends
(`torch`, `audioseal`, `faster-whisper`) are intentionally **not**
pinned in [`hf-space/requirements.txt`](requirements.txt); the demo
runs the cloud cascade by default and fails open when local
backends are unavailable.
