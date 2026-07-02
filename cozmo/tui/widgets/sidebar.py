from textual.widgets import Static, TabbedContent, TabPane
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Click
from textual.message import Message


class Sidebar(Vertical):
    class NewChatRequested(Message):
        pass

    class NewTaskRequested(Message):
        pass

    class NewSessionRequested(Message):
        pass

    def compose(self):
        with TabbedContent(initial="chat"):
            with TabPane(" Chat", id="chat"):
                yield Static("+ New Chat", id="new-chat", classes="sidebar-action")
                with Vertical(id="chat-items", classes="sidebar-items"):
                    yield Static("Recent Chat 1", classes="sidebar-item")
                    yield Static("Recent Chat 2", classes="sidebar-item")
            with TabPane(" Collab", id="collab"):
                yield Static("+ New Task", id="new-task", classes="sidebar-action")
                with Vertical(id="collab-items", classes="sidebar-items"):
                    yield Static("Task placeholder", classes="sidebar-item")
            with TabPane(" Code", id="code"):
                yield Static("+ New Session", id="new-session", classes="sidebar-action")
                with Vertical(id="code-items", classes="sidebar-items"):
                    yield Static("Session placeholder", classes="sidebar-item")

    def on_click(self, event: Click) -> None:
        if event.widget.id == "new-chat":
            self.post_message(self.NewChatRequested())
            event.stop()
        elif event.widget.id == "new-task":
            self.post_message(self.NewTaskRequested())
            event.stop()
        elif event.widget.id == "new-session":
            self.post_message(self.NewSessionRequested())
            event.stop()
