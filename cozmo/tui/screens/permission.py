import threading
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Label, Static


class PermissionModal(ModalScreen):
    """Modal for tool permission requests. Blocks until user decides."""

    class PermissionResult(Message):
        def __init__(self, tool: str, args: dict, agent: str, allowed: bool, always: bool = False) -> None:
            self.tool = tool
            self.args = args
            self.agent = agent
            self.allowed = allowed
            self.always = always
            super().__init__()

    DEFAULT_CSS = """
    PermissionModal {
        align: center middle;
    }

    #perm-dialog {
        width: 50;
        height: auto;
        padding: 2 4;
        background: $surface;
        border: thick $warning;
    }

    #perm-title {
        text-style: bold;
        content-align: center middle;
        height: 3;
        color: $warning;
    }

    #perm-details {
        height: auto;
        margin: 1 0;
    }

    .perm-row {
        height: auto;
        padding: 0 1;
    }

    .perm-label {
        color: $foreground 60%;
    }

    .perm-value {
        color: $foreground;
        text-style: bold;
    }

    #perm-buttons {
        layout: horizontal;
        height: auto;
        margin-top: 1;
    }

    #perm-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, tool: str, args: dict, agent: str, **kwargs):
        super().__init__(**kwargs)
        self.tool = tool
        self.args = args
        self.agent = agent

    def compose(self) -> ComposeResult:
        args_str = ", ".join(f"{k}={v}" for k, v in self.args.items())
        with Vertical(id="perm-dialog"):
            yield Label("Permission Required", id="perm-title")
            with Vertical(id="perm-details"):
                yield Static(f"Agent: {self.agent}", classes="perm-row")
                yield Static(f"Tool: {self.tool}", classes="perm-row")
                if args_str:
                    yield Static(f"Args: {args_str}", classes="perm-row")
            with Vertical(id="perm-buttons"):
                yield Button("Allow Once", id="allow-once", variant="primary")
                yield Button("Always", id="allow-always", variant="success")
                yield Button("Deny", id="deny", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "allow-once":
            self._resolve(True, always=False)
        elif event.button.id == "allow-always":
            self._resolve(True, always=True)
        elif event.button.id == "deny":
            self._resolve(False)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self._resolve(False)

    def _resolve(self, allowed: bool, always: bool = False) -> None:
        self.post_message(self.PermissionResult(
            tool=self.tool,
            args=self.args,
            agent=self.agent,
            allowed=allowed,
            always=always,
        ))
        self.app.pop_screen()


class PermissionBridge:
    """Bridge between agent permission callbacks and TUI modal.

    Usage in agent:
        bridge = PermissionBridge(app)
        agent.set_permission_callback(bridge.ask)
    """

    def __init__(self, app):
        self.app = app
        self._result = None
        self._event = threading.Event()
        self._session_allow: set[str] = set()

    def ask(self, tool: str, args: dict, agent: str) -> bool:
        """Called from agent thread. Blocks until user decides."""
        key = f"{tool}:{args}"
        if key in self._session_allow:
            return True

        self._result = None
        self._event.clear()

        self.app.call_from_thread(self._show_modal, tool, args, agent)
        self._event.wait(timeout=120)

        if self._result is None:
            return False

        if self._result.always:
            self._session_allow.add(key)

        return self._result.allowed

    def _show_modal(self, tool: str, args: dict, agent: str) -> None:
        def on_result(message: PermissionModal.PermissionResult):
            self._result = message
            self._event.set()

        self.app._perm_callback = on_result
        self.app.push_screen(PermissionModal(tool, args, agent))
