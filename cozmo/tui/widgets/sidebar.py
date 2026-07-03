from textual.widgets import Static, TabbedContent, TabPane, Label
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

    class ChatSelected(Message):
        def __init__(self, chat_id: str) -> None:
            self.chat_id = chat_id
            super().__init__()

    def compose(self):
        with TabbedContent(initial="chat"):
            with TabPane("💬 Chat", id="chat"):
                yield Static("+ New Chat", id="new-chat", classes="sidebar-action")
                yield Label("Recent Chats:")
                with Vertical(id="chat-items", classes="sidebar-items"):
                    pass
            with TabPane("🔗 Collab", id="collab"):
                yield Static("+ New Task", id="new-task", classes="sidebar-action")
                yield Label("Recent Tasks:")
                with Vertical(id="collab-items", classes="sidebar-items"):
                    yield Static("Task placeholder", classes="sidebar-item")
            with TabPane("</> Code", id="code"):
                yield Static("+ New Session", id="new-session", classes="sidebar-action")
                yield Label("Recent Sessions:")
                with Vertical(id="code-items", classes="sidebar-items"):
                    yield Static("Session placeholder", classes="sidebar-item")
            

    def refresh_chats(self, chats: list[dict]):
        container = self.query_one("#chat-items")
        container.remove_children()
        for chat in chats:
            btn = Static(chat["title"], classes="sidebar-item", id=f"chat-{chat['id']}")
            container.mount(btn)

    def add_recent(self, chat_id: str, title: str):
        container = self.query_one("#chat-items")
        btn = Static(title, classes="sidebar-item", id=f"chat-{chat_id}")
        container.mount(btn, before=0)

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
        elif event.widget.id and event.widget.id.startswith("chat-"):
            chat_id = event.widget.id[5:]
            self.post_message(self.ChatSelected(chat_id))
            event.stop()
