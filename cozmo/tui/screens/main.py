from pathlib import Path
from textual.screen import Screen
from textual.app import ComposeResult
from textual import events
from textual.widgets import TabbedContent

from ..widgets.sidebar import Sidebar
from ..widgets.footer import AppFooter
from ..widgets.panels.panel import MainPanel, ChatPanel, CollabPanel, CodePanel


class MainScreen(Screen):
    CSS_PATH = str(Path(__file__).resolve().parents[1] / "css" / "app.tcss")

    def compose(self) -> ComposeResult:
        yield Sidebar()
        yield MainPanel()
        yield AppFooter()

    def on_key(self, event: events.Key) -> None:
        if event.key == "tab":
            event.stop()
        elif event.key == "q":
            exit()

    def on_app_footer_settings_requested(self, event: AppFooter.SettingsRequested) -> None:
        self.app.push_screen("settings")

    def on_app_footer_sidebar_toggle_requested(self, event: AppFooter.SidebarToggleRequested) -> None:
        self.screen.toggle_class("collapsed")
        event.stop()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        tab_id = event.pane.id
        self.query_one(MainPanel).switch_to(tab_id)
        event.stop()

    def on_sidebar_new_chat_requested(self, event: Sidebar.NewChatRequested) -> None:
        self.query_one(ChatPanel).reset()
        event.stop()

    def on_sidebar_new_task_requested(self, event: Sidebar.NewTaskRequested) -> None:
        self.query_one(CollabPanel).reset()
        event.stop()

    def on_sidebar_new_session_requested(self, event: Sidebar.NewSessionRequested) -> None:
        self.query_one(CodePanel).reset()
        event.stop()
