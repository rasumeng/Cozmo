from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static
from textual.containers import Horizontal

MODEL_CONTEXT_WINDOWS = {
    "phi4-mini": 4096,
    "qwen3": 4096,
    "qwen2": 4096,
    "gemma": 8192,
    "llama3": 8192,
    "mistral": 8192,
    "codellama": 16384,
    "deepseek": 16384,
    "ornith": 8192,
}


def _get_context_window(model_name: str) -> int:
    name = model_name.split(":")[0].lower()
    for key, size in MODEL_CONTEXT_WINDOWS.items():
        if key in name:
            return size
    return 4096


class AppFooter(Widget):
    class SettingsRequested(Message):
        pass

    class SidebarToggleRequested(Message):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._token_count = 0
        self._context_window = 4096

    def on_mount(self) -> None:
        self.border_subtitle = "CozmoTUI v1.0"

    def compose(self) -> ComposeResult:
        with Horizontal(id="footer-toolbar"):
            yield Label("Collapse", id="footer-model", classes="footer-btn")
            yield Label("Settings", id="footer-settings", classes="footer-btn")
            yield Label("Tokens: 0 (0%)", id="footer-tokens", classes="footer-stat")
            yield Static("", classes="footer-spacer")
            yield Label("Exit", id="footer-exit", classes="footer-btn")

    def update_model(self, model_name: str):
        self._context_window = _get_context_window(model_name)
        self._update_display()

    def update_tokens(self, count: int):
        self._token_count += count
        self._update_display()

    def _update_display(self):
        try:
            pct = min(100, int(self._token_count / self._context_window * 100))
            self.query_one("#footer-tokens", Label).update(
                f"Tokens: {self._token_count} ({pct}%)"
            )
        except Exception:
            pass

    def on_click(self, event: Click) -> None:
        if event.widget.id == "footer-model":
            self.post_message(self.SidebarToggleRequested())
            event.stop()
        elif event.widget.id == "footer-settings":
            self.post_message(self.SettingsRequested())
            event.stop()
        elif event.widget.id == "footer-exit":
            self.app.exit()
            event.stop()
