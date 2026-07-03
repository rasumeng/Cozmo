from functools import partial

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static
from textual.worker import Worker, WorkerState

from ..code_input import CodeInput
from ..input import ChatInput
from ..sprite import render_sprite
from .chat_mixin import ChatMixin

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


class ChatPanel(ChatMixin, Widget):
    class MessageSent(Message):
        def __init__(self, content: str) -> None:
            self.content = content
            super().__init__()

    class ChatCreated(Message):
        def __init__(self, chat_id: str, title: str) -> None:
            self.chat_id = chat_id
            self.title = title
            super().__init__()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.runtime = None
        self.chat_manager = None
        self.active_chat_id: str | None = None
        self.selected_model: str = "qwen2.5:7b"

    def _chat_history_id(self) -> str:
        return "chat-history"

    def set_model(self, model_name: str):
        self.selected_model = model_name
        if self.runtime:
            self.runtime.swap_model(model_name)
        try:
            self.query_one("#chat-input", ChatInput).update_model_label(model_name)
        except Exception:
            pass
        try:
            from ..footer import AppFooter
            self.app.query_one(AppFooter).update_model(model_name)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="chat-history"):
            with Vertical(id="chat-greeting"):
                with Vertical(classes="sprite"):
                    yield Static(render_sprite(), id="sprite")
                yield Label(WELCOME_TEXT, id="tagline")
        with Vertical(id="chat-input-wrapper"):
            yield ChatInput(id="chat-input")

    def _set_input_enabled(self, enabled: bool):
        self.query_one("#chat-input", ChatInput).set_enabled(enabled)

    def _show_greeting(self):
        self.query_one("#chat-greeting").display = True
        self.query_one("#chat-history").scroll_end(animate=False)

    def _hide_greeting(self):
        try:
            self.query_one("#chat-greeting").display = False
        except Exception:
            pass

    def reset(self) -> None:
        self.active_chat_id = None
        self._clear_messages()
        self._show_greeting()
        self._set_input_enabled(True)

    def load_chat(self, chat_id: str):
        self.active_chat_id = chat_id
        title, messages = self.chat_manager.load_chat(chat_id)
        self._clear_messages()
        self._hide_greeting()
        for msg in messages:
            self._add_message(msg["role"], msg["text"])
        self._set_input_enabled(True)

    def on_chat_input_message_sent(self, event: ChatInput.MessageSent) -> None:
        event.stop()
        text = event.content
        self._hide_greeting()
        self._add_message("user", text)

        if not self.active_chat_id:
            chat_id, title = self.chat_manager.create_chat(text)
            self.active_chat_id = chat_id
            self.post_message(self.ChatCreated(chat_id, title))

        self.chat_manager.append(self.active_chat_id, "user", text)
        self._set_input_enabled(False)
        self._show_thinking()

        self.run_worker(
            partial(self._stream_worker, text),
            name="llm-stream",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _stream_worker(self, text: str) -> str:
        self.app.call_from_thread(self._hide_thinking)
        self.app.call_from_thread(self._mount_stream_msg)

        full = ""
        token_count = 0
        for kind, chunk in self.runtime.run_stream(text):
            if kind == "token":
                full += chunk
                token_count += 1
                self.app.call_from_thread(self._update_stream_ui, full)
                if token_count % 10 == 0:
                    self.app.call_from_thread(self._update_token_count, token_count)
            elif kind == "thinking":
                self.app.call_from_thread(self._update_thinking, chunk)
            elif kind == "status":
                self.app.call_from_thread(self._update_thinking, chunk)

        self.app.call_from_thread(self._update_token_count, token_count)
        return full

    def _update_token_count(self, count: int):
        try:
            from ..footer import AppFooter
            footer = self.app.query_one(AppFooter)
            footer.update_tokens(count)
        except Exception:
            pass

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name == "llm-stream":
            if event.state == WorkerState.SUCCESS:
                full_text = event.worker.result
                self._remove_stream_msg()
                self._add_message("assistant", full_text)
                self.chat_manager.append(self.active_chat_id, "assistant", full_text)
            elif event.state == WorkerState.ERROR:
                self._hide_thinking()
                self._add_message("assistant", f"Sorry, I hit an error: {event.worker.error}")
            self._set_input_enabled(True)

    def on_chat_input_file_attach_requested(self, event: ChatInput.FileAttachRequested) -> None:
        event.stop()
        from ...screens.file_picker import FilePickerScreen
        self.app.push_screen(FilePickerScreen())

    def on_file_picker_screen_file_selected(self, event) -> None:
        if event.path:
            try:
                content = Path(event.path).read_text(encoding="utf-8")[:5000]
                name = Path(event.path).name
                field = self.query_one("#chat-input", ChatInput).query_one("#chat-input-field")
                current = field.value
                attachment = f"\n\n@{name}:\n```\n{content}\n```\n"
                field.value = current + attachment
            except Exception as e:
                self.notify(f"Error reading file: {e}", severity="error")


class CollabPanel(ChatMixin, Widget):
    class MessageSent(Message):
        def __init__(self, content: str) -> None:
            self.content = content
            super().__init__()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.runtime = None
        self.chat_manager = None
        self.active_chat_id: str | None = None
        self.selected_model: str = "qwen2.5:7b"

    def _chat_history_id(self) -> str:
        return "collab-history"

    def set_model(self, model_name: str):
        self.selected_model = model_name
        if self.runtime:
            self.runtime.swap_model(model_name)
        try:
            self.query_one("#collab-input", ChatInput).update_model_label(model_name)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="collab-history"):
            with Vertical(id="collab-greeting"):
                with Vertical(classes="sprite"):
                    yield Static(render_sprite(), id="sprite")
                yield Label(COLLAB_TEXT, id="tagline")
        with Vertical(id="collab-input-wrapper"):
            yield ChatInput(id="collab-input")

    def _set_input_enabled(self, enabled: bool):
        self.query_one("#collab-input", ChatInput).set_enabled(enabled)

    def _show_greeting(self):
        self.query_one("#collab-greeting").display = True
        self.query_one("#collab-history").scroll_end(animate=False)

    def _hide_greeting(self):
        try:
            self.query_one("#collab-greeting").display = False
        except Exception:
            pass

    def reset(self) -> None:
        self.active_chat_id = None
        self._clear_messages()
        self._show_greeting()
        self._set_input_enabled(True)

    def on_chat_input_message_sent(self, event: ChatInput.MessageSent) -> None:
        event.stop()
        text = event.content
        self._hide_greeting()
        self._add_message("user", text)

        if not self.active_chat_id:
            chat_id, title = self.chat_manager.create_chat(text)
            self.active_chat_id = chat_id

        self.chat_manager.append(self.active_chat_id, "user", text)
        self._set_input_enabled(False)
        self._show_thinking()

        self.run_worker(
            partial(self._stream_worker, text),
            name="collab-stream",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _stream_worker(self, text: str) -> str:
        self.app.call_from_thread(self._hide_thinking)
        self.app.call_from_thread(self._mount_stream_msg)

        full = ""
        for kind, chunk in self.runtime.run_stream(text):
            if kind == "token":
                full += chunk
                self.app.call_from_thread(self._update_stream_ui, full)
            elif kind == "thinking":
                self.app.call_from_thread(self._update_thinking, chunk)
            elif kind == "status":
                self.app.call_from_thread(self._update_thinking, chunk)

        return full

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name == "collab-stream":
            if event.state == WorkerState.SUCCESS:
                full_text = event.worker.result
                self._remove_stream_msg()
                self._add_message("assistant", full_text)
                self.chat_manager.append(self.active_chat_id, "assistant", full_text)
            elif event.state == WorkerState.ERROR:
                self._hide_thinking()
                self._add_message("assistant", f"Sorry, I hit an error: {event.worker.error}")
            self._set_input_enabled(True)

    def on_chat_input_file_attach_requested(self, event: ChatInput.FileAttachRequested) -> None:
        event.stop()
        from ...screens.file_picker import FilePickerScreen
        self.app.push_screen(FilePickerScreen())

    def on_file_picker_screen_file_selected(self, event) -> None:
        if event.path:
            try:
                content = Path(event.path).read_text(encoding="utf-8")[:5000]
                name = Path(event.path).name
                field = self.query_one("#collab-input", ChatInput).query_one("#chat-input-field")
                current = field.value
                attachment = f"\n\n@{name}:\n```\n{content}\n```\n"
                field.value = current + attachment
            except Exception as e:
                self.notify(f"Error reading file: {e}", severity="error")


class CodePanel(ChatMixin, Widget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.runtime = None
        self.chat_manager = None
        self.active_chat_id: str | None = None
        self.selected_model: str = "ornith:9b"
        self._mode: str = "Build"

    def _chat_history_id(self) -> str:
        return "code-history"

    def set_model(self, model_name: str):
        self.selected_model = model_name
        if self.runtime:
            self.runtime.swap_model(model_name)

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="code-history"):
            with Vertical(id="code-greeting"):
                with Vertical(classes="sprite"):
                    yield Static(render_sprite(), id="sprite")
                yield Label(CODE_TEXT, id="tagline")
        with Vertical(id="code-input-wrapper"):
            yield CodeInput(id="code-input")

    def _set_input_enabled(self, enabled: bool):
        self.query_one("#code-input", CodeInput).disabled = not enabled

    def _show_greeting(self):
        self.query_one("#code-greeting").display = True
        self.query_one("#code-history").scroll_end(animate=False)

    def _hide_greeting(self):
        try:
            self.query_one("#code-greeting").display = False
        except Exception:
            pass

    def reset(self) -> None:
        self.active_chat_id = None
        self._mode = "Build"
        self._clear_messages()
        self._show_greeting()
        self._set_input_enabled(True)
        try:
            self.query_one("#code-input", CodeInput).set_mode("Build")
        except Exception:
            pass

    def on_code_input_toggle_mode(self, event: CodeInput.ToggleMode) -> None:
        event.stop()
        self._mode = event.mode

    def on_code_input_message_sent(self, event) -> None:
        event.stop()
        text = event.content
        self._hide_greeting()
        self._add_message("user", text)

        if not self.active_chat_id:
            chat_id, title = self.chat_manager.create_chat(text)
            self.active_chat_id = chat_id

        self.chat_manager.append(self.active_chat_id, "user", text)
        self._set_input_enabled(False)
        self._show_thinking()

        self.run_worker(
            partial(self._stream_worker, text),
            name="code-stream",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _stream_worker(self, text: str) -> str:
        self.app.call_from_thread(self._hide_thinking)
        self.app.call_from_thread(self._mount_stream_msg)

        full = ""
        for kind, chunk in self.runtime.run_stream(text):
            if kind == "token":
                full += chunk
                self.app.call_from_thread(self._update_stream_ui, full)
            elif kind == "thinking":
                self.app.call_from_thread(self._update_thinking, chunk)
            elif kind == "status":
                self.app.call_from_thread(self._update_thinking, chunk)

        return full

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name == "code-stream":
            if event.state == WorkerState.SUCCESS:
                full_text = event.worker.result
                self._remove_stream_msg()
                self._add_message("assistant", full_text)
                self.chat_manager.append(self.active_chat_id, "assistant", full_text)
            elif event.state == WorkerState.ERROR:
                self._hide_thinking()
                self._add_message("assistant", f"Sorry, I hit an error: {event.worker.error}")
            self._set_input_enabled(True)


class MainPanel(Widget):
    def compose(self) -> ComposeResult:
        yield ChatPanel(id="chat")
        yield CollabPanel(id="collab")
        yield CodePanel(id="code")

    def switch_to(self, tab_id: str) -> None:
        self._hide_all()
        self.query_one(f"#{tab_id}").display = True

    def _hide_all(self) -> None:
        for child in self.children:
            if child.id != "status-bar":
                child.display = False
