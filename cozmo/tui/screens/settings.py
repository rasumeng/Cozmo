from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical
from textual.widgets import Button, Label


class SettingsScreen(ModalScreen):
    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-dialog {
        width: 40;
        height: auto;
        padding: 2 4;
        background: $surface;
        border: thick $primary;
    }

    #settings-title {
        text-style: bold;
        content-align: center middle;
        height: 3;
    }

    #settings-theme, #settings-model {
        height: 3;
    }

    #close-settings {
        width: 100%;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Label("Settings", id="settings-title")
            yield Label("Theme: Cozmo", id="settings-theme")
            yield Label("Model: ornith:9b", id="settings-model")
            yield Button("Close", id="close-settings")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-settings":
            self.app.pop_screen()
