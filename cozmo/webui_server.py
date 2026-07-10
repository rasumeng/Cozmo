"""
Cozmo WebUI server — FastAPI bridge between the React frontend and CozmoRuntime.

WebSocket protocol (/ws/chat), JSON messages:
  client → server:
    {"type": "chat", "content": "..."}          start a run
    {"type": "stop"}                             abort the current run
    {"type": "permission_response", "allowed": bool}
    {"type": "reset"}                            new chat (clears runtime history)
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
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .tools import TOOL_REGISTRY

DIST_DIR = Path(__file__).parent / "webui" / "dist"
CHATS_DIR = Path.home() / ".cozmo" / "chats"

def build_runtime(cfg: dict):
    from .core.runtime import CozmoRuntime
    from .core.llm import OllamaModel
    from .core.model_manager import ModelManager
    from .memory.manager import MemoryManager
    from .code_indexer import ProjectIndex
    from .ollama_util import resolve_minicpm5

    ollama_url = cfg.get("ollama", {}).get("url", "http://localhost:11434")
    lightweight_model = resolve_minicpm5(ollama_url)
    is_lightweight = cfg.get("runtime", {}).get("lightweight_mode", False)
    mm = ModelManager(ollama_url, cfg.get("models", {}),
                      lightweight_model=lightweight_model if is_lightweight else None)
    router_llm = OllamaModel(lightweight_model, ollama_url)
    memory = MemoryManager(router_llm, persist_dir=str(Path.home() / ".cozmo" / "memory"))
    project_index = ProjectIndex(Path.cwd())
    return CozmoRuntime(model_manager=mm, memory=memory, project_index=project_index,
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
        self.current_conv_id = ""
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

    # ── Conversation persistence ──────────────────────────────

    CHATS_DIR.mkdir(parents=True, exist_ok=True)

    def _conversations_idx():
        idx = CHATS_DIR / "index.json"
        if idx.exists():
            raw = json.loads(idx.read_text("utf-8"))
            if "conversations" not in raw:
                raw["conversations"] = []
            return raw
        return {"conversations": []}

    def _save_idx(idx: dict):
        (CHATS_DIR / "index.json").write_text(json.dumps(idx, indent=2), "utf-8")

    def _conv_to_file(conv: dict):
        mode = conv.get("mode", "chat")
        title = conv.get("title", "Untitled")
        lines = [f"# {title}", f"mode: {mode}", ""]
        for m in conv.get("messages", []):
            role = "User" if m.get("role") == "user" else "Cozmo"
            lines.append(f"## {role}")
            lines.append(m.get("content", ""))
            lines.append("")
        return "\n".join(lines)

    @app.get("/api/conversations")
    def get_conversations():
        idx = _conversations_idx()
        return [
            {
                "id": c["id"],
                "title": c["title"],
                "updatedAt": c.get("updatedAt", ""),
                "pinned": c.get("pinned", False),
                "mode": c.get("mode", "chat"),
                "messages": _load_messages(c["id"]),
            }
            for c in idx.get("conversations", [])
        ]

    def _load_messages(conv_id: str) -> list:
        md_path = CHATS_DIR / f"{conv_id}.md"
        if not md_path.exists():
            return []
        content = md_path.read_text("utf-8")
        messages = []
        current_role = None
        current_text = []
        for line in content.split("\n")[1:]:
            m = re.match(r"^## (User|Cozmo)$", line.strip())
            if m:
                if current_role:
                    messages.append({"role": current_role,
                                     "content": "\n".join(current_text).strip(),
                                     "id": f"{conv_id}-{len(messages)}",
                                     "createdAt": ""})
                current_role = "user" if m.group(1) == "User" else "assistant"
                current_text = []
            elif current_role:
                current_text.append(line)
        if current_role:
            messages.append({"role": current_role,
                             "content": "\n".join(current_text).strip(),
                             "id": f"{conv_id}-{len(messages)}",
                             "createdAt": ""})
        return messages

    @app.put("/api/conversations")
    def put_conversation(body: dict):
        conv_id = body.get("id", "").strip()
        title = body.get("title", "Untitled")
        pinned = body.get("pinned", False)
        mode = body.get("mode", "chat")
        messages = body.get("messages", [])

        if not conv_id:
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "id required"}, status_code=400)

        ts = datetime.now(timezone.utc).isoformat()
        idx = _conversations_idx()

        existing = [c for c in idx["conversations"] if c["id"] == conv_id]
        if existing:
            entry = existing[0]
            entry["title"] = title
            entry["pinned"] = pinned
            entry["mode"] = mode
            entry["updatedAt"] = ts
        else:
            entry = {
                "id": conv_id,
                "title": title,
                "pinned": pinned,
                "mode": mode,
                "createdAt": ts,
                "updatedAt": ts,
            }
            idx["conversations"].insert(0, entry)

        _save_idx(idx)
        # write .md file
        (CHATS_DIR / f"{conv_id}.md").write_text(
            _conv_to_file({"title": title, "mode": mode, "messages": messages}),
            "utf-8",
        )
        return {"ok": True}

    @app.get("/api/conversations/search")
    def search_conversations(q: str = ""):
        if not q.strip():
            return []
        ql = q.lower()
        results = []
        for c in _conversations_idx().get("conversations", []):
            md_path = CHATS_DIR / f"{c['id']}.md"
            if not md_path.exists():
                continue
            body = md_path.read_text("utf-8")
            idx = body.lower().find(ql)
            if idx < 0:
                continue
            start = max(0, idx - 60)
            end = min(len(body), idx + len(q) + 60)
            snippet = body[start:end].strip().replace("\n", " ")
            results.append({
                "id": c["id"], "title": c["title"],
                "pinned": c.get("pinned", False),
                "mode": c.get("mode", "chat"),
                "match": snippet,
            })
        return results[:20]

    @app.delete("/api/conversations/{conv_id}")
    def delete_conversation(conv_id: str):
        idx = _conversations_idx()
        idx["conversations"] = [c for c in idx["conversations"] if c["id"] != conv_id]
        _save_idx(idx)
        md_path = CHATS_DIR / f"{conv_id}.md"
        if md_path.exists():
            md_path.unlink()
        return {"ok": True}

    # ── Config CRUD ─────────────────────────────────────────────

    def _sanitize_config(cfg: dict) -> dict:
        safe = {}
        for k, v in cfg.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict):
                sv = _sanitize_config(v)
                if sv:
                    safe[k] = sv
            elif isinstance(v, (str, int, float, bool, list)):
                safe[k] = v
        return safe

    @app.get("/api/config")
    def get_config():
        return _sanitize_config(cfg)

    @app.put("/api/config")
    def put_config(body: dict):
        def deep_merge(base: dict, patch: dict):
            for k, v in patch.items():
                if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                    if k == "models":
                        base[k] = v
                    else:
                        deep_merge(base[k], v)
                else:
                    base[k] = v
        deep_merge(cfg, body)
        import tomli_w
        CONFIG_PATH = config.CONFIG_PATH
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(tomli_w.dumps(cfg), "utf-8")
        return {"ok": True}

    # ── Ollama available models ─────────────────────────────────

    @app.get("/api/ollama/models")
    def get_ollama_models():
        import httpx
        url = cfg.get("ollama", {}).get("url", "http://localhost:11434")
        try:
            r = httpx.get(f"{url}/api/tags", timeout=5)
            if r.is_success:
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    # ── Endpoints ─────────────────────────────────────────────

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

    @app.post("/api/transcribe")
    async def transcribe_audio(file: UploadFile = File(...)):
        import tempfile, os
        import speech_recognition as sr
        from pydub import AudioSegment
        data = await file.read()
        if not data:
            return {"text": ""}
        src_path = ""
        wav_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(data)
                src_path = f.name
            seg = AudioSegment.from_file(src_path)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                seg.export(f.name, format="wav")
                wav_path = f.name
            r = sr.Recognizer()
            with sr.AudioFile(wav_path) as src:
                audio = r.record(src)
            text = r.recognize_google(audio)
            return {"text": text}
        except sr.UnknownValueError:
            return {"text": ""}
        except Exception:
            return {"text": ""}
        finally:
            if src_path: os.unlink(src_path)
            if wav_path: os.unlink(wav_path)

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
                    conv_id = msg.get("conversation_id", "")
                    if not content:
                        continue
                    if session.busy:
                        await ws.send_text(json.dumps(
                            {"type": "error", "text": "A run is already in progress."}))
                        continue
                    session.current_conv_id = conv_id
                    session.start_run(content)
                elif mtype == "stop":
                    session.stop()
                elif mtype == "permission_response":
                    session.answer_permission(msg.get("allowed", False))
                elif mtype == "reset":
                    if not session.busy:
                        session.runtime.reset()
                        await ws.send_text(json.dumps({"type": "status", "text": "New chat"}))
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
