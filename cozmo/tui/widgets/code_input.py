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

    def _toggle_mode(self) -> None:
        self.current_mode_index = (self.current_mode_index + 1) % 2
        mode = self.modes[self.current_mode_index]
        self.query_one("#code-mode-label", Static).update(f"{mode}  (coding model)")
        self.post_message(self.ToggleMode(mode))
