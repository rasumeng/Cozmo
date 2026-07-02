from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.widgets import Input, Static


PLACEHOLDER = "Type a message..."


class ChatInput(Vertical):
    class MessageSent(Message):
        def __init__(self, content: str) -> None:
            self.content = content
            super().__init__()

    class FileAttachRequested(Message):
        def __init__(self) -> None:
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Input(placeholder=PLACEHOLDER, id="chat-input-field")
        with Horizontal(id="chat-input-toolbar"):
            yield Static("+", id="chat-attach-btn", classes="toolbar-btn")
            yield Static("", classes="toolbar-spacer")
            yield Static(">", id="chat-send-btn", classes="toolbar-btn")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input-field":
            self._send(event.value)

    def on_click(self, event: Click) -> None:
        if event.widget.id == "chat-send-btn":
            field = self.query_one("#chat-input-field", Input)
            self._send(field.value)
        elif event.widget.id == "chat-attach-btn":
            self.post_message(self.FileAttachRequested())

    def _send(self, content: str) -> None:
        if content.strip():
            self.post_message(self.MessageSent(content.strip()))
            self.query_one("#chat-input-field", Input).value = ""
