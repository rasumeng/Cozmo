"""ChatMixin — shared panel helpers for message display, thinking, streaming."""

from rich.style import Style
from rich.text import Text
from textual.containers import ScrollableContainer
from textual.widgets import Static, Markdown


MSG_COLOR_USER = "#7A6EE0"
MSG_COLOR_ASSISTANT = "#6358C0"


class ChatMixin:
    """Mixin for panels that show chat messages. Requires self to be a Widget with query_one."""

    def _chat_history_id(self) -> str:
        """Override to return the history container ID."""
        raise NotImplementedError

    def _add_message(self, role: str, text: str):
        history = self.query_one(f"#{self._chat_history_id()}", ScrollableContainer)
        label = "You" if role == "user" else "Cozmo"
        color = MSG_COLOR_USER if role == "user" else MSG_COLOR_ASSISTANT
        if role == "assistant":
            msg = Markdown(f"**{label}:**\n\n{text}", classes="chat-msg")
        else:
            msg = Static(Text.assemble((f"{label}: ", Style(color=color)), text), classes="chat-msg")
        history.mount(msg)
        history.scroll_end(animate=False)

    def _show_thinking(self, text: str = "Cozmo is thinking..."):
        self._hide_thinking()
        history = self.query_one(f"#{self._chat_history_id()}", ScrollableContainer)
        thinking = Static(text, id="chat-thinking", classes="chat-thinking")
        history.mount(thinking)
        history.scroll_end(animate=False)

    def _hide_thinking(self):
        try:
            self.query_one("#chat-thinking").remove()
        except Exception:
            pass

    def _update_thinking(self, text: str):
        try:
            self.query_one("#chat-thinking", Static).update(text)
        except Exception:
            pass

    def _clear_messages(self):
        history = self.query_one(f"#{self._chat_history_id()}", ScrollableContainer)
        for child in list(history.children):
            if "chat-msg" in (child.classes or "") or child.id in ("chat-thinking", "streaming-msg"):
                child.remove()

    def _update_stream_ui(self, text: str):
        try:
            color = Style(color=MSG_COLOR_ASSISTANT)
            self.query_one("#streaming-msg", Static).update(
                Text.assemble(("Cozmo: ", color), text)
            )
            self.query_one(f"#{self._chat_history_id()}", ScrollableContainer).scroll_end(animate=False)
        except Exception:
            pass

    def _create_stream_msg(self) -> Static:
        color = Style(color=MSG_COLOR_ASSISTANT)
        return Static(
            Text.assemble(("Cozmo: ", color), ""),
            classes="chat-msg",
            id="streaming-msg",
        )

    def _mount_stream_msg(self):
        # defensive: a previous stream that errored/emptied may have left one behind
        self._remove_stream_msg()
        history = self.query_one(f"#{self._chat_history_id()}", ScrollableContainer)
        history.mount(self._create_stream_msg())
        history.scroll_end(animate=False)

    def _remove_stream_msg(self):
        try:
            self.query_one("#streaming-msg").remove()
        except Exception:
            pass
