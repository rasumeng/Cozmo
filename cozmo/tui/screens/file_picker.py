from pathlib import Path
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual import events
from textual.widgets import Label, Static
from textual.containers import Vertical, ScrollableContainer
from textual.message import Message


class FilePickerScreen(ModalScreen[str]):
    CSS = """
    FilePickerScreen {
        align: center middle;
    }
    #file-picker {
        width: 80;
        height: 30;
        border: solid $primary;
        background: $surface;
    }
    #file-picker-title {
        dock: top;
        padding: 0 1;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    .file-item {
        padding: 0 1;
    }
    .file-item:hover {
        background: $primary 30%;
    }
    .file-dir {
        color: $accent;
    }
    """

    class FileSelected(Message):
        def __init__(self, path: str) -> None:
            self.path = path
            super().__init__()

    def __init__(self, start_dir: str = ".", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_dir = Path(start_dir).resolve()
        self.current_dir = self.start_dir
        self.selected_file = None

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker"):
            yield Label(f"Select file: {self.current_dir}", id="file-picker-title")
            with ScrollableContainer(id="file-list"):
                yield from self._list_files()

    def _list_files(self):
        items = []
        try:
            entries = sorted(self.current_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries[:50]:
                name = entry.name
                if entry.is_dir():
                    items.append(Label(f"  {name}/", classes="file-item file-dir"))
                else:
                    items.append(Label(f"  {name}", classes="file-item"))
        except PermissionError:
            items.append(Label("  Permission denied", classes="file-item"))
        return items

    def on_click(self, event: events.Click) -> None:
        if not event.widget.has_class("file-item"):
            return
        text = event.widget.renderable
        if isinstance(text, str):
            name = text.strip()
        else:
            name = str(text).strip()

        if name.endswith("/"):
            self.current_dir = self.current_dir / name[:-1]
            self.query_one("#file-picker-title", Label).update(f"Select file: {self.current_dir}")
            file_list = self.query_one("#file-list", ScrollableContainer)
            file_list.remove_children()
            file_list.mount(*self._list_files())
        else:
            self.selected_file = str(self.current_dir / name)
            self.dismiss(self.selected_file)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "backspace":
            if self.current_dir != self.start_dir:
                self.current_dir = self.current_dir.parent
                self.query_one("#file-picker-title", Label).update(f"Select file: {self.current_dir}")
                file_list = self.query_one("#file-list", ScrollableContainer)
                file_list.remove_children()
                file_list.mount(*self._list_files())
