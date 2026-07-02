from textual.app import App, ComposeResult
from .widgets.header import CozmoHeader


class CozmoApp(App):
    TITLE = "Cozmo"
    SUB_TITLE = "coding agent"

    def compose(self) -> ComposeResult:
        yield CozmoHeader(model="ornith:9b", agent="build")

    def on_key(self, event):
        match event.key:
            case "q":
                exit()
