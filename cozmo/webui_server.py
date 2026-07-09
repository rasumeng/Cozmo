"""
Cozmo WebUI server — FastAPI bridge between the React frontend and CozmoRuntime.

WebSocket protocol (/ws/chat), JSON messages:
  client → server:
    {"type": "chat", "content": "..."}          start a run
    {"type": "stop"}                             abort the current run
    {"type": "permission_response", "allowed": bool}
    {"type": "reset"}                            new chat (clears runtime history)
    {"type": "set_model", "model": "name"}       swap the main model
  server → client:
    {"type": "token",    "text": "..."}          streamed answer token
    {"type": "thinking", "text": "..."}          agent step (mode, tool runs)
    {"type": "status",   "text": "..."}          transient status line
    {"type": "permission_request", "tool": "...", "args": {...}}
    {"type": "done"}                             run finished
    {"type": "error",    "text": "..."}

The runtime loop is synchronous, so each run executes in a worker thread and
events are marshalled back onto the event loop through an asyncio.Queue.
"""

import asyncio
import json
import threading
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .tools import TOOL_REGISTRY

DIST_DIR = Path(__file__).parent / "webui" / "dist"


def build_runtime(cfg: dict):
    from .core.runtime import CozmoRuntime
    from .core.llm import OllamaModel
    from .memory.manager import MemoryManager
    from .code_indexer import ProjectIndex

    ollama_url = cfg.get("ollama", {}).get("url", "http://localhost:11434")
    classifier_model = cfg.get("models", {}).get("classifier", "qwen3:0.6b")
    chat_model = cfg.get("models", {}).get("chat", "qwen2.5:7b")
    llm = OllamaModel(chat_model, ollama_url)
    router_llm = OllamaModel(classifier_model, ollama_url)
    memory = MemoryManager(router_llm, persist_dir=str(Path.home() / ".cozmo" / "memory"))
    project_index = ProjectIndex(Path.cwd())
    return CozmoRuntime(llm=llm, memory=memory, project_index=project_index,
                        cfg=cfg, router_llm=router_llm)


class ChatSession:
    """One WebSocket connection = one runtime + one run at a time."""

    def __init__(self, cfg: dict, loop: asyncio.AbstractEventLoop):
        self.runtime = build_runtime(cfg)
        self.loop = loop
        self.events: asyncio.Queue = asyncio.Queue()
        self.stop_flag = threading.Event()
        self._perm_event = threading.Event()
        self._perm_allowed = False
        self._worker: threading.Thread | None = None
        self.runtime.set_permission_callback(self._ask_permission)

    # runs in worker thread
    def _emit(self, payload: dict):
        self.loop.call_soon_threadsafe(self.events.put_nowait, payload)

    # runs in worker thread — block until the browser answers
    def _ask_permission(self, tool: str, args: dict) -> bool:
        self._perm_event.clear()
        self._emit({"type": "permission_request", "tool": tool, "args": args})
        # 120s timeout → deny (fail safe, matches headless behavior)
        if not self._perm_event.wait(timeout=120):
            return False
        return self._perm_allowed

    def answer_permission(self, allowed: bool):
        self._perm_allowed = bool(allowed)
        self._perm_event.set()

    @property
    def busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def start_run(self, user_input: str):
        self.stop_flag.clear()

        def work():
            try:
                for kind, text in self.runtime.run_stream(user_input):
                    if self.stop_flag.is_set():
                        self._emit({"type": "thinking", "text": "Stopped by user"})
                        break
                    self._emit({"type": kind, "text": text})
            except Exception as e:
                self._emit({"type": "error", "text": str(e)})
            finally:
                self._emit({"type": "done"})

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def stop(self):
        self.stop_flag.set()
        # unblock a pending permission prompt as a denial
        self._perm_allowed = False
        self._perm_event.set()


def create_app(cfg: dict | None = None) -> FastAPI:
    cfg = cfg or config.load()
    app = FastAPI(title="Cozmo WebUI")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/models")
    def get_models():
        models = cfg.get("models", {})
        return [{"id": role, "name": name, "role": role, "active": role == "chat"}
                for role, name in models.items()]

    @app.get("/api/tools")
    def get_tools():
        return [{"id": name, "name": name,
                 "description": (fn.__doc__ or "").strip().split("\n")[0],
                 "enabled": True}
                for name, fn in sorted(TOOL_REGISTRY.items())]

    @app.websocket("/ws/chat")
    async def ws_chat(ws: WebSocket):
        await ws.accept()
        session = ChatSession(cfg, asyncio.get_running_loop())

        async def pump_events():
            while True:
                ev = await session.events.get()
                await ws.send_text(json.dumps(ev))

        pump = asyncio.create_task(pump_events())
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")

                if mtype == "chat":
                    content = (msg.get("content") or "").strip()
                    if not content:
                        continue
                    if session.busy:
                        await ws.send_text(json.dumps(
                            {"type": "error", "text": "A run is already in progress."}))
                        continue
                    session.start_run(content)
                elif mtype == "stop":
                    session.stop()
                elif mtype == "permission_response":
                    session.answer_permission(msg.get("allowed", False))
                elif mtype == "reset":
                    if not session.busy:
                        session.runtime.reset()
                        await ws.send_text(json.dumps({"type": "status", "text": "New chat"}))
                elif mtype == "set_model":
                    model = msg.get("model", "")
                    if model and not session.busy:
                        session.runtime.swap_model(model)
                        await ws.send_text(json.dumps(
                            {"type": "status", "text": f"Model: {model}"}))
        except WebSocketDisconnect:
            session.stop()
        finally:
            pump.cancel()

    # serve the built frontend when present (dev uses vite on :5173 instead)
    if DIST_DIR.exists():
        app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="webui")

    return app


def run_server(cfg: dict | None = None, host: str = "127.0.0.1", port: int = 8765):
    import uvicorn
    uvicorn.run(create_app(cfg), host=host, port=port)
