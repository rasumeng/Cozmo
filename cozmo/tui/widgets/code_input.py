from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.message import Message
from textual.widgets import Input, Static


PLACEHOLDER = "Type a command..."


class CodeInput(Vertical):
    class ToggleMode(Message):
        def __init__(self, mode: str) -> None:
            self.mode = mode
            super().__init__()

    class MessageSent(Message):
        def __init__(self, content: str) -> None:
            self.content = content
            super().__init__()

    modes = ["Build", "Plan"]
    current_mode_index = 0

    def compose(self) -> ComposeResult:
        yield Input(placeholder=PLACEHOLDER, id="code-input-field")
        with Horizontal(id="code-input-toolbar"):
            yield Static("Build  (coding model)", id="code-mode-label")

    def on_key(self, event: Key) -> None:
        if event.key == "tab":
            event.stop()
            self._toggle_mode()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "code-input-field" and event.value.strip():
            self.post_message(self.MessageSent(event.value.strip()))
            event.input.value = ""

    def _toggle_mode(self) -> None:
        self.current_mode_index = (self.current_mode_index + 1) % 2
        mode = self.modes[self.current_mode_index]
        self._update_mode_label(mode)
        self.post_message(self.ToggleMode(mode))

    def _update_mode_label(self, mode: str) -> None:
        try:
            self.query_one("#code-mode-label", Static).update(f"{mode}  (coding model)")
        except Exception:
            pass

    def set_mode(self, mode: str) -> None:
        if mode in self.modes:
            self.current_mode_index = self.modes.index(mode)
            self._update_mode_label(mode)
