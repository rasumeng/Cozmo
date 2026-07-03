from pathlib import Path
from textual.screen import Screen
from textual.app import ComposeResult
from textual import events
from textual.widgets import TabbedContent
from textual.worker import Worker, WorkerState

from ..widgets.sidebar import Sidebar
from ..widgets.footer import AppFooter
from ..widgets.panels.panel import MainPanel, ChatPanel, CollabPanel, CodePanel
from ..widgets.input import ChatInput
from ..chat_manager import ChatManager
from ...core.runtime import CozmoRuntime
from ...core.llm import OllamaModel
from ...memory.manager import MemoryManager
from ...code_indexer import ProjectIndex
from ... import config
from .model_selector import ModelSelectorScreen
from .permission import PermissionModal, PermissionBridge


class MainScreen(Screen):
    CSS_PATH = str(Path(__file__).resolve().parents[1] / "css" / "app.tcss")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._model_selector_panel = None

    def on_mount(self) -> None:
        cfg = config.load()
        ollama_url = cfg.get("ollama", {}).get("url", "http://localhost:11434")

        classifier_model = cfg.get("models", {}).get("classifier", "qwen3:0.6b")
        chat_model = cfg.get("models", {}).get("chat", "qwen2.5:7b")
        llm = OllamaModel(chat_model, ollama_url)
        router_llm = OllamaModel(classifier_model, ollama_url)

        memory = MemoryManager(
            router_llm,  # cheap model for summaries
            persist_dir=str(Path.home() / ".cozmo" / "memory"),
        )

        project_index = ProjectIndex(Path.cwd())

        self.runtime = CozmoRuntime(
            llm=llm,
            memory=memory,
            project_index=project_index,
            cfg=cfg,
            router_llm=router_llm,
        )

        # route 'ask' permission decisions to the TUI modal (blocks the
        # worker thread, not the UI thread)
        self._perm_bridge = PermissionBridge(self.app)
        self.runtime.set_permission_callback(
            lambda tool, args: self._perm_bridge.ask(tool, args, "cozmo")
        )

        self.chat_manager = ChatManager(
            storage_dir=Path.home() / ".cozmo" / "chats",
            classifier_model=classifier_model,
            base_url=ollama_url,
        )

        main_panel = self.query_one(MainPanel)
        for panel_cls in (ChatPanel, CollabPanel, CodePanel):
            try:
                panel = self.query_one(panel_cls)
                panel.runtime = self.runtime
                panel.chat_manager = self.chat_manager
            except Exception:
                pass

        sidebar = self.query_one(Sidebar)
        sidebar.refresh_chats(self.chat_manager.list_chats())

    def compose(self) -> ComposeResult:
        yield Sidebar()
        yield MainPanel()
        yield AppFooter()

    def on_key(self, event: events.Key) -> None:
        if event.key == "tab":
            event.stop()
        elif event.key == "ctrl+q":
            self.app.exit()
        elif event.key == "ctrl+l":
            self.query_one(ChatPanel).reset()
            event.stop()

    def on_app_footer_settings_requested(self, event: AppFooter.SettingsRequested) -> None:
        self.app.push_screen("settings")

    def on_app_footer_sidebar_toggle_requested(self, event: AppFooter.SidebarToggleRequested) -> None:
        self.screen.toggle_class("collapsed")
        event.stop()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        tab_id = event.pane.id
        self.query_one(MainPanel).switch_to(tab_id)
        event.stop()

    def on_sidebar_new_chat_requested(self, event: Sidebar.NewChatRequested) -> None:
        self.query_one(ChatPanel).reset()
        event.stop()

    def on_sidebar_chat_selected(self, event: Sidebar.ChatSelected) -> None:
        self.query_one(ChatPanel).load_chat(event.chat_id)
        event.stop()

    def on_chat_panel_chat_created(self, event: ChatPanel.ChatCreated) -> None:
        self.query_one(Sidebar).add_recent(event.chat_id, event.title)
        event.stop()

    def on_sidebar_new_task_requested(self, event: Sidebar.NewTaskRequested) -> None:
        self.query_one(CollabPanel).reset()
        event.stop()

    def on_sidebar_new_session_requested(self, event: Sidebar.NewSessionRequested) -> None:
        self.query_one(CodePanel).reset()
        event.stop()

    def on_chat_input_model_label_clicked(self, event: ChatInput.ModelLabelClicked) -> None:
        event.stop()
        current_model = event.model_name
        self._model_selector_panel = None

        source = event.control
        while source is not None:
            if isinstance(source, ChatPanel):
                self._model_selector_panel = "chat"
                break
            elif isinstance(source, CollabPanel):
                self._model_selector_panel = "collab"
                break
            elif isinstance(source, CodePanel):
                self._model_selector_panel = "code"
                break
            source = getattr(source, "parent", None)

        self.app.push_screen(ModelSelectorScreen(current_model=current_model))

    def on_model_selector_screen_model_selected(self, event: ModelSelectorScreen.ModelSelected) -> None:
        event.stop()
        if self._model_selector_panel == "chat":
            self.query_one(ChatPanel).set_model(event.model_name)
        elif self._model_selector_panel == "collab":
            self.query_one(CollabPanel).set_model(event.model_name)
        elif self._model_selector_panel == "code":
            self.query_one(CodePanel).set_model(event.model_name)
        self._model_selector_panel = None

    def on_permission_modal_permission_result(self, event: PermissionModal.PermissionResult) -> None:
        if hasattr(self.app, "_perm_callback") and self.app._perm_callback:
            self.app._perm_callback(event)
            self.app._perm_callback = None
        event.stop()
