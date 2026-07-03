from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, ScrollableContainer
from textual.message import Message
from textual.widgets import Button, Label, Static

from ...ollama_util import get_ollama_models


class ModelSelectorScreen(ModalScreen):
    class ModelSelected(Message):
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name
            super().__init__()

    DEFAULT_CSS = """
    ModelSelectorScreen {
        align: center middle;
    }

    #model-dialog {
        width: 40;
        height: auto;
        max-height: 30;
        padding: 2 4;
        background: $surface;
        border: thick $primary;
    }

    #model-title {
        text-style: bold;
        content-align: center middle;
        height: 3;
    }

    #model-list {
        height: auto;
        max-height: 20;
        overflow-y: scroll;
    }

    .model-item {
        height: auto;
        padding: 0 1;
        width: 100%;
    }

    .model-item:hover {
        background: $primary 20%;
    }

    .model-item-selected {
        color: $accent;
    }

    #close-models {
        width: 100%;
        margin-top: 1;
    }
    """

    def __init__(self, current_model: str = "", **kwargs):
        super().__init__(**kwargs)
        self.current_model = current_model
        self._model_ids: dict[str, str] = {}

    @staticmethod
    def _sanitize_id(model_name: str) -> str:
        return model_name.replace(":", "_").replace(".", "_")

    def compose(self) -> ComposeResult:
        with Vertical(id="model-dialog"):
            yield Label("Select Model", id="model-title")
            with ScrollableContainer(id="model-list"):
                models = get_ollama_models()
                if not models:
                    yield Label("No models found. Is Ollama running?", classes="model-item")
                else:
                    for model in models:
                        prefix = "  " if model != self.current_model else " "
                        display = f"{prefix}{model}"
                        safe_id = self._sanitize_id(model)
                        self._model_ids[safe_id] = model
                        yield Static(display, classes="model-item", id=f"model-{safe_id}")
            yield Button("Close", id="close-models")

    def on_click(self, event) -> None:
        widget_id = event.widget.id
        if widget_id and widget_id.startswith("model-"):
            safe_id = widget_id[6:]
            model_name = self._model_ids.get(safe_id)
            if model_name:
                self.post_message(self.ModelSelected(model_name))
                self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-models":
            self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-models":
            self.app.pop_screen()
