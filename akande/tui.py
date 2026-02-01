# Copyright (C) 2024 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import contextlib
import os

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Input,
    Static,
    Button,
    RichLog,
)
from textual import work
from rich.text import Text

from .config import LLM_PROVIDER, OPENAI_DEFAULT_MODEL
from .exceptions import LLMError
from .utils import (
    generate_pdf,
    generate_csv,
    strip_markdown,
)


@contextlib.contextmanager
def _suppress_stderr():
    """Redirect fd 2 (stderr) to /dev/null.

    ALSA, PulseAudio, and pydub/ffplay write diagnostic noise
    directly to the stderr file descriptor from C code, bypassing
    Python's sys.stderr.  This corrupts Textual's alternate screen.

    Textual renders through stdout (fd 1), so suppressing only
    stderr is safe for the TUI.
    """
    try:
        devnull = os.open(os.devnull, os.O_RDWR)
        saved = os.dup(2)
        os.dup2(devnull, 2)
        os.close(devnull)
    except OSError:
        saved = None
    try:
        yield
    finally:
        if saved is not None:
            try:
                os.dup2(saved, 2)
                os.close(saved)
            except OSError:
                pass


class AkandeApp(App):
    """Textual TUI for the Akande voice assistant."""

    TITLE = "Akande"

    CSS = """
    Screen {
        background: #0c1220;
    }

    Header {
        background: #141e30;
        color: #f5f5f7;
        border-bottom: solid #1a2a40;
    }

    Footer {
        background: #141e30;
        color: #8e8e93;
        border-top: solid #1a2a40;
    }

    /* ── Layout ── */

    #main {
        background: #0c1220;
    }

    #welcome {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        text-align: center;
        padding: 2 4;
    }

    #chat {
        background: #0c1220;
        padding: 1 3;
        scrollbar-color: #1a2a40;
        scrollbar-color-hover: #0A84FF;
        scrollbar-color-active: #0A84FF;
    }

    #thinking {
        height: auto;
        padding: 0 3;
        color: #48484a;
        display: none;
    }

    #thinking.visible {
        display: block;
    }

    /* ── Input bar ── */

    #input-bar {
        height: auto;
        dock: bottom;
        background: #141e30;
        border-top: solid #1a2a40;
        padding: 1 2;
    }

    #question-input {
        width: 1fr;
        background: #1a2a40;
        color: #f5f5f7;
        border: tall #1a2a40;
    }

    #question-input:focus {
        border: tall #0A84FF;
    }

    #mic-btn {
        min-width: 5;
        background: transparent;
        color: #48484a;
        border: tall #1a2a40;
        margin: 0 1 0 0;
    }

    #mic-btn:hover {
        color: #8e8e93;
    }

    #mic-btn.recording {
        background: #ff453a;
        color: #ffffff;
        border: tall #ff453a;
    }

    #send-btn {
        min-width: 6;
        background: #0A84FF;
        color: #ffffff;
        border: tall #0A84FF;
        margin: 0 0 0 1;
    }

    #send-btn:hover {
        background: #0070e0;
        border: tall #0070e0;
    }

    /* ── Action bar ── */

    #action-bar {
        height: auto;
        dock: bottom;
        background: #141e30;
        padding: 0 2;
        border-top: solid #1a2a40;
    }

    .action-btn {
        min-width: 12;
        background: transparent;
        color: #8e8e93;
        border: none;
        margin: 0 1 0 0;
    }

    .action-btn:hover {
        color: #f5f5f7;
    }

    #quit-btn:hover {
        color: #ff453a;
    }

    #server-btn.running {
        color: #30d158;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+v", "toggle_voice", "Voice"),
        Binding("ctrl+s", "toggle_server", "Server"),
        Binding("ctrl+l", "clear", "Clear"),
    ]

    def __init__(self, akande_instance):
        super().__init__()
        self.akande = akande_instance
        self._recording = False
        self._welcome_visible = True

    # ── Compose ─────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        provider = LLM_PROVIDER or "openai"
        model = OPENAI_DEFAULT_MODEL or "default"
        yield Header()
        with Vertical(id="main"):
            yield Static(
                "\n[bold #f5f5f7]Akande[/]\n"
                "[#48484a]Executive Briefing Assistant[/]\n\n"
                "[#8e8e93]Type a question below, "
                "press [#0A84FF]Mic[/] or "
                "[#0A84FF]Ctrl+V[/] for voice input,\n"
                "[#0A84FF]Server[/] or "
                "[#0A84FF]Ctrl+S[/] for the web UI, "
                "[#0A84FF]Ctrl+Q[/] to quit.[/]\n\n"
                f"[#48484a]{provider}  ·  {model}[/]",
                id="welcome",
                markup=True,
            )
            yield RichLog(id="chat", wrap=True, markup=True)
            yield Static("", id="thinking")
        with Horizontal(id="action-bar"):
            yield Button("Server", id="server-btn",
                         classes="action-btn")
            yield Button("Clear", id="clear-btn",
                         classes="action-btn")
            yield Button("Quit", id="quit-btn",
                         classes="action-btn")
        with Horizontal(id="input-bar"):
            yield Button("Mic", id="mic-btn")
            yield Input(
                placeholder="Ask me anything...",
                id="question-input",
            )
            yield Button("Send", id="send-btn")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#chat", RichLog).display = False
        self.query_one("#question-input", Input).focus()

    # ── Welcome / Thinking state ────────────────────────────

    def _hide_welcome(self) -> None:
        if self._welcome_visible:
            self._welcome_visible = False
            self.query_one("#welcome").display = False
            self.query_one("#chat").display = True

    def _show_thinking(self) -> None:
        w = self.query_one("#thinking", Static)
        w.update("  Thinking...")
        w.add_class("visible")

    def _hide_thinking(self) -> None:
        w = self.query_one("#thinking", Static)
        w.remove_class("visible")
        w.update("")

    # ── Message writers ─────────────────────────────────────

    def _write_user(self, text: str) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(""))
        msg = Text()
        msg.append("you  ", style="#48484a")
        msg.append(text, style="#0A84FF")
        chat.write(msg)

    def _write_assistant(self, text: str) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(text, style="#f5f5f7"))

    def _write_file(self, text: str) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(text, style="#48484a"))

    def _write_error(self, text: str) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(text, style="#ff453a"))

    def _write_status(self, text: str) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(text, style="#30d158"))

    # ── Input handling ──────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted):
        question = event.value.strip()
        if question:
            self.akande.cancel_pending()
            event.input.value = ""
            self._hide_welcome()
            self._write_user(question)
            self._show_thinking()
            self.handle_question(question)

    async def on_button_pressed(self, event: Button.Pressed):
        btn = event.button.id
        if btn == "send-btn":
            inp = self.query_one("#question-input", Input)
            question = inp.value.strip()
            if question:
                self.akande.cancel_pending()
                inp.value = ""
                self._hide_welcome()
                self._write_user(question)
                self._show_thinking()
                self.handle_question(question)
                inp.focus()
        elif btn == "mic-btn":
            await self._toggle_voice()
        elif btn == "server-btn":
            await self._toggle_server()
        elif btn == "clear-btn":
            await self.action_clear()
        elif btn == "quit-btn":
            await self.akande.stop_server()
            self.exit()

    # ── Question worker ─────────────────────────────────────

    @work(exclusive=True, thread=True)
    def handle_question(self, question: str) -> None:
        import asyncio

        self.akande.reset_cancel()
        try:
            response = asyncio.run(
                self.akande.generate_response(question)
            )

            def _update_ui():
                self._hide_thinking()
                if not response:
                    self._write_error(
                        "No response was generated."
                    )
                    return

                clean = strip_markdown(response)
                self._write_assistant(clean)

                pdf_path = generate_pdf(question, response)
                csv_path = generate_csv(question, clean)
                parts = []
                if pdf_path:
                    parts.append(f"PDF  {pdf_path}")
                if csv_path:
                    parts.append(f"CSV  {csv_path}")
                if parts:
                    self._write_file("   ".join(parts))

            self.call_from_thread(_update_ui)

            if response:
                clean = strip_markdown(response)
                try:
                    with _suppress_stderr():
                        asyncio.run(
                            self.akande.speak(clean)
                        )
                except Exception:
                    pass
        except LLMError as llm_exc:
            msg = llm_exc.user_message

            def _show_llm_error():
                self._hide_thinking()
                self._write_error(msg)
            self.call_from_thread(_show_llm_error)
        except Exception as gen_exc:
            msg = str(gen_exc)

            def _show_error():
                self._hide_thinking()
                self._write_error(msg)
            self.call_from_thread(_show_error)

    # ── Voice ───────────────────────────────────────────────

    async def _toggle_voice(self) -> None:
        mic_btn = self.query_one("#mic-btn", Button)
        if self._recording:
            return

        self._recording = True
        mic_btn.add_class("recording")
        mic_btn.label = "Stop"
        self._hide_welcome()
        self._write_status("Listening...")

        try:
            with _suppress_stderr():
                text = await self.akande.listen(
                    speak_on_error=False
                )
        except Exception:
            text = ""
        finally:
            self._recording = False
            mic_btn.remove_class("recording")
            mic_btn.label = "Mic"

        if not text:
            self._write_error(
                "Could not understand. Try again or type "
                "your question."
            )
        elif text.lower() == "stop":
            await self.akande.stop_server()
            self.exit()
        else:
            self._write_user(text)
            self._show_thinking()
            self.handle_question(text)

    # ── Server ──────────────────────────────────────────────

    async def _toggle_server(self) -> None:
        self._hide_welcome()
        btn = self.query_one("#server-btn", Button)
        if self.akande.server_running:
            await self.akande.stop_server()
            btn.remove_class("running")
            btn.label = "Server"
            self._write_status("Server stopped.")
        else:
            await self.akande.run_server()
            btn.add_class("running")
            btn.label = "Server (on)"
            self._write_status(
                "Server running at http://127.0.0.1:8080"
            )

    # ── Actions ─────────────────────────────────────────────

    async def action_toggle_voice(self) -> None:
        await self._toggle_voice()

    async def action_toggle_server(self) -> None:
        await self._toggle_server()

    async def action_clear(self) -> None:
        self.query_one("#chat", RichLog).clear()
        self._welcome_visible = True
        self.query_one("#welcome").display = True
        self.query_one("#chat").display = False

    async def action_quit(self) -> None:
        await self.akande.stop_server()
        self.exit()
