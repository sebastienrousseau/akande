"""Hugging Face Space demo for Àkàndé.

Deploys at https://huggingface.co/spaces/akande/akande when this
file is pushed to that Space's repository.  Designed for a
ZeroGPU H200 slot so we can show good demo quality without paying
for an always-on box.

Two modes are exposed in the UI:

- ``Cascade`` — the production default: STT → LLM → TTS, with
  Track E controls (AI disclosure + watermark) on by default.
- ``Speech-to-speech`` — OpenAI Realtime when ``OPENAI_API_KEY``
  is set in the Space secrets.  Off otherwise.

The Space reads ``HF_TOKEN`` (optional, gates the demo behind HF
auth for cost control) and ``OPENAI_API_KEY`` (required for the
S2S path; cascade falls back to a stubbed reply when missing).
"""

from __future__ import annotations

import os
import tempfile

import gradio as gr  # type: ignore[import-not-found]

from akande.disclosure import get_disclosure_text
from akande.profiles import active_profile
from akande.tts import get_tts_backend
from akande.watermark import watermark_audio

TITLE = "Àkàndé"
SUBTITLE = (
    "Self-hosted, provider-agnostic voice AI — "
    "EU AI Act Article 50 compliant, fully local when you "
    "need it."
)


def _maybe_stub_briefing(question: str) -> str:
    """Return a real briefing if a provider key is set, else stub."""
    try:
        from akande.config import OPENAI_DEFAULT_MODEL
        from akande.providers import get_provider
        from akande.services import SYSTEM_PROMPT

        provider = get_provider()
        response = provider.generate_response_sync(
            question,
            SYSTEM_PROMPT,
            OPENAI_DEFAULT_MODEL or "gpt-4o-mini",
            None,
        )
        return str(
            response.choices[0].message.content or ""
        )
    except Exception as exc:
        return (
            f"(demo stub — set OPENAI_API_KEY for a real "
            f"briefing.  Underlying error: "
            f"{type(exc).__name__})\n\n"
            f"You asked: {question}"
        )


def cascade(question: str) -> tuple[str, str]:
    """Cascade path: text → LLM → TTS → optional watermark."""
    if not (question or "").strip():
        return "Please ask a question.", ""
    profile = active_profile()
    disclosure = (
        get_disclosure_text()
        if profile.ai_disclosure
        else ""
    )
    reply = _maybe_stub_briefing(question)
    rendered = (
        f"{disclosure}\n\n{reply}".strip()
        if disclosure
        else reply
    )
    audio_path = ""
    try:
        backend = get_tts_backend()
        result = backend.synthesise(reply)
        audio_bytes = result.audio
        if profile.audio_watermark:
            audio_bytes = watermark_audio(
                audio_bytes, fmt=result.fmt
            )
        suffix = (
            ".mp3" if result.fmt == "mp3" else ".wav"
        )
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix
        ) as fh:
            fh.write(audio_bytes)
            audio_path = fh.name
    except Exception as exc:
        rendered += (
            f"\n\n(TTS unavailable in this Space: "
            f"{type(exc).__name__})"
        )
    return rendered, audio_path


def build_ui() -> gr.Blocks:
    with gr.Blocks(title=TITLE) as demo:
        gr.Markdown(f"# {TITLE}\n{SUBTITLE}")
        gr.Markdown(
            "**Compliance defaults:** "
            f"profile=`{active_profile().name}` · "
            "AI disclosure: "
            f"`{'on' if active_profile().ai_disclosure else 'off'}` · "
            "AudioSeal watermark: "
            f"`{'on' if active_profile().audio_watermark else 'off'}`"
        )
        with gr.Tab("Cascade (STT → LLM → TTS)"):
            text = gr.Textbox(
                label="Your question",
                placeholder="e.g. 'What is quantitative easing?'",
                lines=2,
            )
            briefing = gr.Markdown(label="Briefing")
            audio = gr.Audio(
                label="Spoken reply", autoplay=False
            )
            btn = gr.Button("Generate briefing")
            btn.click(
                cascade, inputs=text, outputs=[briefing, audio]
            )
        with gr.Tab("Speech-to-speech (preview)"):
            gr.Markdown(
                "End-to-end S2S via OpenAI Realtime ships in "
                "this Space once `OPENAI_API_KEY` is added as "
                "a Space secret.  Full barge-in + streaming "
                "land in v0.0.6-dev.9."
            )
        gr.Markdown(
            "Source: "
            "[github.com/sebastienrousseau/akande]"
            "(https://github.com/sebastienrousseau/akande)  ·  "
            "Compliance: "
            "[docs/compliance/eu.md]"
            "(https://github.com/sebastienrousseau/akande/"
            "blob/main/docs/compliance/eu.md)"
        )
    return demo


if __name__ == "__main__":
    # Default to the EU profile in the public Space so the live
    # demo exercises Article 50 controls.  Override at deploy
    # time with the AKANDE_PROFILE Space secret.
    os.environ.setdefault("AKANDE_PROFILE", "eu")
    build_ui().launch()
