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
  briefings.  Cascade today, realtime soon.
---

# Àkàndé on Hugging Face Spaces

Live demo of the [`akande`](https://github.com/sebastienrousseau/akande)
voice assistant, configured for the **EU profile** so every demo
request exercises the Article 50 controls (AI disclosure,
AudioSeal watermarking, signed audit trail).

## How to deploy / refresh this Space

```bash
# from the root of the akande repo
git remote add hf https://huggingface.co/spaces/akande/akande
git subtree push --prefix hf-space hf main
```

`hf-space/app.py` is the entry point.  Anything Gradio-shaped you
add to the package surface (e.g. a new tab for S2S streaming
once dev.9 ships it) lands here too.

## Space secrets

Set these via the Hugging Face UI under *Settings → Secrets*:

| Secret | Purpose |
|---|---|
| `OPENAI_API_KEY` | Cloud LLM + TTS + S2S backends |
| `ANTHROPIC_API_KEY` (optional) | Alt LLM provider |
| `AKANDE_PROFILE` | Override the default `eu` profile if needed |
| `HF_TOKEN` (optional) | Gate the Space behind HF auth |

Without `OPENAI_API_KEY` the Space falls back to a clearly-labelled
stub reply so the demo still loads end-to-end.

## ZeroGPU

The Space targets a ZeroGPU H200 slot — keep the model footprint
small so the cold-start is fast.  Heavy locals (torch / audioseal /
faster-whisper) are intentionally **not** pinned in the Space's
`requirements.txt`; the demo runs the cloud cascade by default and
falls open when local backends are unavailable.
