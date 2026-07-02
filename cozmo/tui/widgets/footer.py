from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static
from textual.containers import Horizontal


class AppFooter(Widget):
    class SettingsRequested(Message):
        pass

    class SidebarToggleRequested(Message):
        pass

    def on_mount(self) -> None:
        self.border_subtitle = "CozmoTUI v1.0"

    def compose(self) -> ComposeResult:
        with Horizontal(id="footer-toolbar"):
            yield Label("Collapse", id="footer-model", classes="footer-btn")
            yield Label("Settings", id="footer-settings", classes="footer-btn")
            yield Static("", classes="footer-spacer")
            yield Label("Exit", id="footer-exit", classes="footer-btn")

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
