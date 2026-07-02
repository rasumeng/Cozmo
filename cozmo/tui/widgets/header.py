from textual.containers import Horizontal
from textual.widgets import Static
from ..sprite import render_sprite


class CozmoHeader(Horizontal):
    DEFAULT_CSS = """
    CozmoHeader {
        height: 10;
        dock: top;
        background: $surface;
    }
    #sprite {
        width: 32;
        height: 32;
    }
    #title {
        height: 5;
        content-align: center middle;
        text-style: bold;
    }
    """

    def __init__(self, model: str = "", agent: str = ""):
        super().__init__()
        self.model = model
        self.agent = agent

    def compose(self):
        yield Static(render_sprite(32, 16), id="sprite")
        yield Static(f"Cozmo v0.1  [{self.model}]  [{self.agent}]", id="title")
