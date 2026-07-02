from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static
from ..code_input import CodeInput
from ..input import ChatInput
from ..sprite import render_sprite

WELCOME_TEXT = """
Welcome to Cozmo!

Cozmo is a AI Agent that utilizes opensource llms as the brains.
This was made and tested on the ornith:9b model"""

COLLAB_TEXT = """
Collaborate with Cozmo!

Work together on tasks, share context, and
coordinate multi-step objectives."""

CODE_TEXT = """
Code with Cozmo!

Switch between Plan and Build modes
with the Tab key."""


class ChatPanel(Widget):
    class MessageSent(Message):
        def __init__(self, content: str) -> None:
            self.content = content
            super().__init__()

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="chat-history"):
            with Vertical(id="chat-greeting"):
                with Vertical(classes="sprite"):
                    yield Static(render_sprite(), id="sprite")
                yield Label(WELCOME_TEXT, id="tagline")
        with Vertical(id="chat-input-wrapper"):
            yield ChatInput(id="chat-input")

    def reset(self) -> None:
        greeting = self.query_one("#chat-greeting")
        greeting.remove_children()
        sprite_box = Vertical(classes="sprite")
        greeting.mount(sprite_box)
        sprite_box.mount(Static(render_sprite(), id="sprite"))
        greeting.mount(Label(WELCOME_TEXT, id="tagline"))

    def on_chat_input_message_sent(self, event: ChatInput.MessageSent) -> None:
        event.stop()
        history = self.query_one("#chat-history", ScrollableContainer)
        history.mount(Static(f"You: {event.content}", classes="chat-msg"))
        history.scroll_end(animate=False)
        self.post_message(self.MessageSent(event.content))

    def on_chat_input_file_attach_requested(self, event: ChatInput.FileAttachRequested) -> None:
        event.stop()
        self.notify("File attach  coming soon", severity="information")


class CollabPanel(Widget):
    class MessageSent(Message):
        def __init__(self, content: str) -> None:
            self.content = content
            super().__init__()

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="collab-history"):
            with Vertical(id="collab-greeting"):
                with Vertical(classes="sprite"):
                    yield Static(render_sprite(), id="sprite")
                yield Label(COLLAB_TEXT, id="tagline")
        with Vertical(id="collab-input-wrapper"):
            yield ChatInput(id="collab-input")

    def reset(self) -> None:
        greeting = self.query_one("#collab-greeting")
        greeting.remove_children()
        sprite_box = Vertical(classes="sprite")
        greeting.mount(sprite_box)
        sprite_box.mount(Static(render_sprite(), id="sprite"))
        greeting.mount(Label(COLLAB_TEXT, id="tagline"))

    def on_chat_input_message_sent(self, event: ChatInput.MessageSent) -> None:
        event.stop()
        history = self.query_one("#collab-history", ScrollableContainer)
        history.mount(Static(f"You: {event.content}", classes="chat-msg"))
        history.scroll_end(animate=False)
        self.post_message(self.MessageSent(event.content))

    def on_chat_input_file_attach_requested(self, event: ChatInput.FileAttachRequested) -> None:
        event.stop()
        self.notify("File attach  coming soon", severity="information")


class CodePanel(Widget):
    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="code-history"):
            with Vertical(id="code-greeting"):
                with Vertical(classes="sprite"):
                    yield Static(render_sprite(), id="sprite")
                yield Label(CODE_TEXT, id="tagline")
        with Vertical(id="code-input-wrapper"):
            yield CodeInput(id="code-input")

    def reset(self) -> None:
        greeting = self.query_one("#code-greeting")
        greeting.remove_children()
        sprite_box = Vertical(classes="sprite")
        greeting.mount(sprite_box)
        sprite_box.mount(Static(render_sprite(), id="sprite"))
        greeting.mount(Label(CODE_TEXT, id="tagline"))


class MainPanel(Widget):
    def compose(self) -> ComposeResult:
        yield ChatPanel(id="chat")
        yield CollabPanel(id="collab")
        yield CodePanel(id="code")

    def switch_to(self, tab_id: str) -> None:
        self._hide_all()
        self.query_one(f"#{tab_id}").display = True
        labels = {"chat": "Chat", "collab": "Collab", "code": "Code"}

    def _hide_all(self) -> None:
        for child in self.children:
            if child.id != "status-bar":
                child.display = False
