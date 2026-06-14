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
from datetime import datetime, timezone

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    OptionList,
    RichLog,
    Static,
)

from .config import LLM_PROVIDER, OPENAI_DEFAULT_MODEL
from .exceptions import LLMError
from .utils import (
    generate_csv,
    generate_pdf,
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

    # ── Design tokens (Apple HIG dark) ───────────────────
    # bg-primary:      #1c1c1e
    # bg-secondary:    #2c2c2e
    # bg-tertiary:     #3a3a3c
    # text-primary:    #f5f5f7
    # text-secondary:  #98989d
    # text-tertiary:   #636366
    # border-primary:  #48484a
    # accent:          #0a84ff
    # blue-hover:      #0070e6
    # success:         #32d74b
    # error:           #ff453a

    CSS = """
    Screen {
        background: #1c1c1e;
    }

    Header {
        background: #2c2c2e;
        color: #f5f5f7;
        border-bottom: solid #48484a;
    }

    Footer {
        background: #2c2c2e;
        color: #98989d;
        border-top: solid #48484a;
    }

    /* ── Layout ── */

    #main {
        background: #1c1c1e;
        min-height: 3;
    }

    #welcome {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        text-align: center;
        padding: 2 4;
    }

    #chat {
        background: #1c1c1e;
        padding: 1 3;
        scrollbar-color: #3a3a3c;
        scrollbar-color-hover: #0A84FF;
        scrollbar-color-active: #0A84FF;
    }

    #thinking {
        height: auto;
        padding: 0 3;
        color: #636366;
        display: none;
    }

    #thinking.visible {
        display: block;
    }

    /* ── Input bar ── */

    #input-bar {
        height: auto;
        dock: bottom;
        background: #2c2c2e;
        border-top: solid #48484a;
        padding: 1 2;
    }

    #question-input {
        width: 1fr;
        background: #3a3a3c;
        color: #f5f5f7;
        border: tall #48484a;
    }

    #question-input:focus {
        border: tall #0A84FF;
    }

    #mic-btn {
        min-width: 5;
        background: transparent;
        color: #636366;
        border: tall #48484a;
        margin: 0 1 0 0;
    }

    #mic-btn:hover {
        color: #98989d;
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
        background: #0070e6;
        border: tall #0070e6;
    }

    /* ── Action bar ── */

    #action-bar {
        height: auto;
        dock: bottom;
        background: #2c2c2e;
        padding: 0 2;
        border-top: solid #48484a;
    }

    .action-btn {
        min-width: 12;
        background: transparent;
        color: #98989d;
        border: none;
        margin: 0 1 0 0;
    }

    .action-btn:hover {
        color: #f5f5f7;
    }

    .action-btn:focus {
        border: tall #0a84ff;
        color: #f5f5f7;
    }

    #quit-btn:hover {
        color: #ff453a;
    }

    #server-btn.running {
        color: #32d74b;
    }

    #action-bar.compact .action-btn {
        min-width: 8;
    }

    Button:focus {
        border: tall #0A84FF;
    }
    """

    BINDINGS = [
        Binding("escape", "quit", "Exit", priority=True),
        Binding("1", "toggle_voice", "1 Record", priority=True),
        Binding("2", "toggle_server", "2 Web UI", priority=True),
        Binding("3", "clear", "3 Clear", priority=True),
        Binding("4", "quit", "4 Quit", priority=True),
        Binding("5", "export", "5 Export", priority=True),
        Binding("6", "history", "6 History", priority=True),
        Binding("f1", "show_help", "Help", priority=True),
    ]

    # ── Export modal ─────────────────────────────────────

    class ExportScreen(ModalScreen):
        """Export the last response as PDF or CSV."""

        CSS = """
        ExportScreen {
            align: center middle;
        }
        #export-dialog {
            background: #2c2c2e;
            border: solid #48484a;
            padding: 2 4;
            width: 50;
            height: auto;
        }
        #export-dialog Button {
            width: 100%;
            margin: 1 0 0 0;
        }
        #export-title {
            text-align: center;
            color: #f5f5f7;
            text-style: bold;
            padding: 0 0 1 0;
        }
        .export-btn {
            background: #3a3a3c;
            color: #f5f5f7;
            border: solid #48484a;
        }
        .export-btn:hover {
            background: #48484a;
        }
        #export-cancel {
            background: transparent;
            color: #0a84ff;
            border: none;
        }
        """

        def compose(self) -> ComposeResult:  # pragma: no cover - needs mounted Textual app
            with Vertical(id="export-dialog"):
                yield Static(
                    "Export Last Response",
                    id="export-title",
                )
                yield Button(
                    "PDF", id="export-pdf", classes="export-btn"
                )
                yield Button(
                    "CSV", id="export-csv", classes="export-btn"
                )
                yield Button(
                    "Cancel", id="export-cancel"
                )

        async def on_button_pressed(  # pragma: no cover - event-driven
            self, event: Button.Pressed
        ) -> None:
            self.dismiss(event.button.id)

    # ── History modal ────────────────────────────────────

    class HistoryScreen(ModalScreen):
        """Browse in-session conversation history."""

        CSS = """
        HistoryScreen {
            align: center middle;
        }
        #history-dialog {
            background: #2c2c2e;
            border: solid #48484a;
            padding: 2 4;
            width: 70;
            height: 20;
        }
        #history-title {
            text-align: center;
            color: #f5f5f7;
            text-style: bold;
            padding: 0 0 1 0;
        }
        #history-list {
            height: 1fr;
            background: #1c1c1e;
            color: #f5f5f7;
            scrollbar-color: #3a3a3c;
        }
        #history-cancel {
            width: 100%;
            margin: 1 0 0 0;
            background: transparent;
            color: #0a84ff;
            border: none;
        }
        """

        def __init__(self, history: list):
            super().__init__()
            self._history = history

        def compose(self) -> ComposeResult:  # pragma: no cover - mounted Textual
            with Vertical(id="history-dialog"):
                yield Static(
                    "Conversation History",
                    id="history-title",
                )
                option_list = OptionList(id="history-list")
                for entry in self._history:
                    ts = entry["timestamp"]
                    q = entry["question"]
                    label = f"[{ts}] {q[:50]}"
                    if len(q) > 50:
                        label += "..."
                    option_list.add_option(label)
                yield option_list
                yield Button(
                    "Cancel", id="history-cancel"
                )

        async def on_option_list_option_selected(  # pragma: no cover - event-driven
            self, event: OptionList.OptionSelected
        ) -> None:
            idx = event.option_index
            self.dismiss(idx)

        async def on_button_pressed(  # pragma: no cover - event-driven
            self, event: Button.Pressed
        ) -> None:
            if event.button.id == "history-cancel":
                self.dismiss(None)

    # ── Init ─────────────────────────────────────────────

    def __init__(self, akande_instance):
        super().__init__()
        self.akande = akande_instance
        self._recording = False
        self._welcome_visible = True
        self._last_question: str = ""
        self._last_response: str = ""
        self._history: list[dict] = []

    # ── Compose ─────────────────────────────────────────────

    def compose(self) -> ComposeResult:  # pragma: no cover - mounted Textual
        provider = LLM_PROVIDER or "openai"
        model = OPENAI_DEFAULT_MODEL or "default"
        yield Header()
        with Vertical(id="main"):
            yield Static(
                "\n[bold #f5f5f7]Akande[/]\n"
                "[#636366]Executive Briefing Assistant[/]\n\n"
                "[#98989d]Type a question below or "
                "use the menu:[/]\n\n"
                "[#0A84FF][1][/] [#98989d]Record  [/]"
                "[#0A84FF][2][/] [#98989d]Web UI  [/]"
                "[#0A84FF][3][/] [#98989d]Clear  [/]"
                "[#0A84FF][4][/] [#98989d]Quit  [/]"
                "[#0A84FF][5][/] [#98989d]Export  [/]"
                "[#0A84FF][6][/] [#98989d]History[/]\n\n"
                "[#636366]Tab to navigate · "
                "Escape to exit · "
                "F1 for help[/]\n\n"
                f"[#636366]{provider}  ·  {model}[/]",
                id="welcome",
                markup=True,
            )
            yield RichLog(id="chat", wrap=True, markup=True)
            yield Static("", id="thinking")
        with Horizontal(id="action-bar"):
            yield Button(
                "[1] Record", id="mic-btn-action",
                classes="action-btn",
                tooltip="Record voice input",
            )
            yield Button(
                "[2] Web UI", id="server-btn",
                classes="action-btn",
                tooltip="Toggle web UI server",
            )
            yield Button(
                "[3] Clear", id="clear-btn",
                classes="action-btn",
                tooltip="Clear chat",
            )
            yield Button(
                "[4] Quit", id="quit-btn",
                classes="action-btn",
                tooltip="Quit application",
            )
            yield Button(
                "[5] Export", id="export-btn",
                classes="action-btn",
                tooltip="Export last response",
            )
            yield Button(
                "[6] History", id="history-btn",
                classes="action-btn",
                tooltip="Conversation history",
            )
        with Horizontal(id="input-bar"):
            yield Button(
                "Mic", id="mic-btn",
                tooltip="Record voice input",
            )
            yield Input(
                placeholder="Ask me anything...",
                id="question-input",
            )
            yield Button(
                "Send", id="send-btn",
                tooltip="Send question",
            )
        yield Footer()

    def on_mount(self) -> None:  # pragma: no cover - mounted Textual
        provider = LLM_PROVIDER or "openai"
        model = OPENAI_DEFAULT_MODEL or "default"
        self.sub_title = f"{provider} · {model}"
        self.query_one("#chat", RichLog).display = False

    def on_resize(self, event) -> None:  # pragma: no cover - mounted Textual
        bar = self.query_one("#action-bar")
        if event.size.width < 60:
            bar.add_class("compact")
        else:
            bar.remove_class("compact")

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
        msg.append("you  ", style="#636366")
        msg.append(text, style="#0A84FF")
        chat.write(msg)

    def _write_assistant(self, text: str) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(text, style="#f5f5f7"))

    def _write_file(self, text: str) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(text, style="#636366"))

    def _write_error(self, text: str) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(text, style="#ff453a"))

    def _write_status(self, text: str) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(text, style="#32d74b"))

    # ── Input handling ──────────────────────────────────────

    async def on_input_submitted(  # pragma: no cover - event-driven
        self, event: Input.Submitted
    ):
        question = event.value.strip()
        if question:
            self.akande.cancel_pending()
            event.input.value = ""
            self._hide_welcome()
            self._write_user(question)
            self._show_thinking()
            self.handle_question(question)

    async def on_button_pressed(  # pragma: no cover - event-driven
        self, event: Button.Pressed
    ):
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
        elif btn == "mic-btn-action":
            await self._toggle_voice()
        elif btn == "quit-btn":
            await self.akande.stop_server()
            self.exit()
        elif btn == "export-btn":
            await self.action_export()
        elif btn == "history-btn":
            await self.action_history()

    # ── Question worker ─────────────────────────────────────

    @work(exclusive=True, thread=True)
    def handle_question(self, question: str) -> None:  # pragma: no cover - thread worker
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

                self._last_question = question
                self._last_response = response

                self._history.append({
                    "question": question,
                    "response": response,
                    "timestamp": datetime.now(
                        tz=timezone.utc
                    ).strftime("%H:%M:%S"),
                })

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

    async def _toggle_voice(self) -> None:  # pragma: no cover - mounted Textual
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

    async def _toggle_server(self) -> None:  # pragma: no cover - mounted Textual
        self._hide_welcome()
        btn = self.query_one("#server-btn", Button)
        if self.akande.server_running:
            await self.akande.stop_server()
            btn.remove_class("running")
            btn.label = "Web UI"
            self._write_status("Server stopped.")
        else:
            await self.akande.run_server()
            btn.add_class("running")
            btn.label = "Web UI (on)"
            url = "http://127.0.0.1:8080"
            chat = self.query_one("#chat", RichLog)
            chat.write("")
            chat.write(
                "[bold #32d74b]Web UI is running[/]\n"
                "\n"
                f"[#f5f5f7]{url}[/]\n"
                "\n"
                "[#98989d]Your browser should open "
                "automatically.\n"
                "The web interface lets you chat "
                "from any browser —\n"
                "full conversation history, voice "
                "input, dark mode,\n"
                "and PDF / CSV export built in.[/]"
            )
            import webbrowser
            webbrowser.open(url)

    # ── Actions ─────────────────────────────────────────────

    async def action_toggle_voice(self) -> None:  # pragma: no cover - mounted
        await self._toggle_voice()

    async def action_toggle_server(self) -> None:  # pragma: no cover - mounted
        await self._toggle_server()

    async def action_clear(self) -> None:  # pragma: no cover - mounted
        self.query_one("#chat", RichLog).clear()
        self._welcome_visible = True
        self.query_one("#welcome").display = True
        self.query_one("#chat").display = False

    async def action_export(self) -> None:  # pragma: no cover - mounted
        if not self._last_question:
            self._hide_welcome()
            self._write_error(
                "Nothing to export yet. Ask a question first."
            )
            return

        def _handle_export(result: str | None) -> None:
            if result == "export-pdf":
                path = generate_pdf(
                    self._last_question, self._last_response
                )
                if path:
                    self._write_file(f"PDF exported  {path}")
            elif result == "export-csv":
                clean = strip_markdown(self._last_response)
                path = generate_csv(
                    self._last_question, clean
                )
                if path:
                    self._write_file(f"CSV exported  {path}")

        self.push_screen(self.ExportScreen(), _handle_export)

    async def action_history(self) -> None:  # pragma: no cover - mounted
        if not self._history:
            self._hide_welcome()
            self._write_error(
                "No history yet. Ask a question first."
            )
            return

        def _handle_history(result: int | None) -> None:
            if result is not None and 0 <= result < len(
                self._history
            ):
                entry = self._history[result]
                self._hide_welcome()
                self._write_user(entry["question"])
                clean = strip_markdown(entry["response"])
                self._write_assistant(clean)

        self.push_screen(
            self.HistoryScreen(self._history),
            _handle_history,
        )

    async def action_show_help(self) -> None:  # pragma: no cover - mounted
        self._hide_welcome()
        chat = self.query_one("#chat", RichLog)
        chat.write(Text(""))
        help_text = Text()
        help_text.append(
            "Keyboard Shortcuts\n", style="bold #f5f5f7"
        )
        help_text.append(
            "  [1]      Record voice input\n"
            "  [2]      Toggle web UI server\n"
            "  [3]      Clear chat\n"
            "  [4]      Quit\n"
            "  [5]      Export last response\n"
            "  [6]      Conversation history\n"
            "  Escape   Exit to terminal\n"
            "  Tab      Navigate menu\n"
            "  F1       Show this help\n",
            style="#98989d",
        )
        chat.write(help_text)

    async def action_quit(self) -> None:
        await self.akande.stop_server()
        self.exit()
