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

    class ModelLabelClicked(Message):
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name
            super().__init__()

    def __init__(self, model_name: str = "qwen2.5:7b", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_name = model_name

    def compose(self) -> ComposeResult:
        yield Input(placeholder=PLACEHOLDER, id="chat-input-field")
        with Horizontal(id="chat-input-toolbar"):
            yield Static("+", id="chat-attach-btn", classes="toolbar-btn")
            yield Static("", classes="toolbar-spacer")
            yield Static(f"{self.model_name} >", id="model-selector-btn", classes="model-btn")
            yield Static("▶", id="chat-send-btn", classes="toolbar-btn")

    def update_model_label(self, model_name: str):
        self.model_name = model_name
        try:
            self.query_one("#model-selector-btn", Static).update(f"{model_name} >")
        except Exception:
            pass

    def set_enabled(self, enabled: bool):
        self.query_one("#chat-input-field", Input).disabled = not enabled

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input-field":
            self._send(event.value)

    def on_click(self, event: Click) -> None:
        if event.widget.id == "chat-send-btn":
            field = self.query_one("#chat-input-field", Input)
            self._send(field.value)
        elif event.widget.id == "chat-attach-btn":
            self.post_message(self.FileAttachRequested())
        elif event.widget.id == "model-selector-btn":
            self.post_message(self.ModelLabelClicked(self.model_name))

    def _send(self, content: str) -> None:
        if content.strip():
            self.post_message(self.MessageSent(content.strip()))
            self.query_one("#chat-input-field", Input).value = ""
