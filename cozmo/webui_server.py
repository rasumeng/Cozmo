"""
Cozmo WebUI server — FastAPI bridge between the React frontend and CozmoRuntime.

WebSocket protocol (/ws/chat), JSON messages:
  client → server:
    {"type": "chat", "content": "..."}                      start a run
    {"type": "stop"}                                         abort the current run
    {"type": "permission_response", "allowed": bool}
    {"type": "plan_response", "approved": bool}
    {"type": "reset"}                                        new chat (clears runtime history)
  server → client:
    {"type": "token",    "text": "..."}                      streamed answer token
    {"type": "thinking", "text": "..."}                      agent step (mode, tool runs)
    {"type": "status",   "text": "..."}                      transient status line
    {"type": "plan",     "plan": "..."}                      collab plan awaiting approval
    {"type": "permission_request", "tool": "...", "args": {...}}
    {"type": "done"}                                         run finished
    {"type": "error",    "text": "..."}

The runtime loop is synchronous, so each run executes in a worker thread and
events are marshalled back onto the event loop through an asyncio.Queue.
"""

import asyncio
import json
import os
import re
import uuid
import threading
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .tools import TOOL_REGISTRY

DIST_DIR = Path(__file__).parent / "webui" / "dist"
CHATS_DIR = Path.home() / ".cozmo" / "chats"
ATTACHMENTS_DIR = Path.home() / ".cozmo" / "attachments"
SKILLS_DIR = Path.home() / ".cozmo" / "skills"
DEFAULT_SKILLS_DIR = Path(__file__).parent / "default_skills"

# Module-level list of all MCPManagers so config-save can notify them
_builtin_mcp_managers: list = []

def build_runtime(cfg: dict):
    from .core.runtime import CozmoRuntime
    from .core.llm import OllamaModel
    from .core.model_manager import ModelManager
    from .memory.manager import MemoryManager
    from .code_indexer import ProjectIndex
    from .ollama_util import resolve_minicpm5
    from .core.tool_registry import ToolRegistry
    from .core.providers.mcp import MCPManager
    from .tools import TOOL_REGISTRY

    ollama_url = cfg.get("ollama", {}).get("url", "http://localhost:11434")
    lightweight_model = resolve_minicpm5(ollama_url)
    is_lightweight = cfg.get("runtime", {}).get("lightweight_mode", False)
    mm = ModelManager(ollama_url, cfg.get("models", {}),
                      lightweight_model=lightweight_model if is_lightweight else None)
    router_llm = OllamaModel(lightweight_model, ollama_url)
    memory = MemoryManager(router_llm, persist_dir=str(Path.home() / ".cozmo" / "memory"))
    project_index = ProjectIndex(Path.cwd())

    # Set up tool registry with builtins
    registry = ToolRegistry()
    for name, fn in TOOL_REGISTRY.items():
        registry.register(name, fn)

    # Start MCP connections (persistent background event loop)
    mcp = MCPManager(registry)
    mcp.start(cfg)
    _builtin_mcp_managers.append(mcp)

    runtime = CozmoRuntime(
        model_manager=mm,
        memory=memory,
        registry=registry,
        project_index=project_index,
        cfg=cfg,
        router_llm=router_llm,
    )
    runtime._mcp_manager = mcp  # keep ref for lifecycle
    return runtime


def seed_default_skills():
    """Copy default skills (e.g. skill-creator) into ~/.cozmo/skills/ on first run."""
    import shutil
    if not DEFAULT_SKILLS_DIR.exists():
        return
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for folder in DEFAULT_SKILLS_DIR.iterdir():
        if not folder.is_dir():
            continue
        target = SKILLS_DIR / folder.name
        if target.exists():
            continue
        shutil.copytree(str(folder), str(target), dirs_exist_ok=True)

class ChatSession:
    """One WebSocket connection = one runtime + one run at a time."""

    def __init__(self, cfg: dict, loop: asyncio.AbstractEventLoop):
        self.runtime = build_runtime(cfg)
        self.loop = loop
        self.events: asyncio.Queue = asyncio.Queue()
        self.stop_flag = threading.Event()
        self.runtime.stop_event = self.stop_flag
        self._perm_event = threading.Event()
        self._perm_allowed = False
        self._plan_event = threading.Event()
        self._plan_approved = False
        self._worker: threading.Thread | None = None
        self.current_conv_id = ""
        self.runtime.set_permission_callback(self._ask_permission)
        self.runtime.set_plan_callback(self._ask_plan)

    # runs in worker thread
    def _emit(self, payload: dict):
        cleaned = {k: v for k, v in payload.items() if v is not None}
        self.loop.call_soon_threadsafe(self.events.put_nowait, cleaned)

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

    # runs in worker thread — block until the browser approves/rejects plan
    def _ask_plan(self, plan_text: str) -> bool:
        self._plan_event.clear()
        self._emit({"type": "plan", "plan": plan_text})
        # 300s timeout → reject (fail safe)
        if not self._plan_event.wait(timeout=300):
            return False
        return self._plan_approved

    def answer_plan(self, approved: bool):
        self._plan_approved = approved
        self._plan_event.set()

    @property
    def busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _resolve_attachments(self, attachments_meta: list[dict]) -> list[dict]:
        resolved = []
        for a in attachments_meta:
            entry = dict(a)
            att_id = a.get("id", "")
            for p in ATTACHMENTS_DIR.iterdir():
                if p.stem == att_id and p.is_file():
                    entry["path"] = str(p)
                    break
            resolved.append(entry)
        return resolved

    def start_run(self, user_input: str, attachments_meta: list[dict] | None = None, project_context: str | None = None):
        self.stop_flag.clear()
        resolved_atts = self._resolve_attachments(attachments_meta) if attachments_meta else None
        if project_context:
            self.runtime._project_context = project_context
        else:
            self.runtime._project_context = ""

        def work():
            try:
                for item in self.runtime.run_stream(user_input, resolved_atts):
                    if self.stop_flag.is_set():
                        self._emit({"type": "thinking", "text": "Stopped by user", "detail": "Generation was cancelled by the user"})
                        break
                    kind, text = item[0], item[1]
                    detail = item[2] if len(item) > 2 else None
                    query = item[3] if len(item) > 3 else None
                    self._emit({"type": kind, "text": text, "detail": detail, "query": query})
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
            atts = m.get("attachments")
            if atts:
                lines.append(f"@attachments {json.dumps(atts)}")
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
                    msg = _build_msg(conv_id, current_role, current_text, len(messages))
                    messages.append(msg)
                current_role = "user" if m.group(1) == "User" else "assistant"
                current_text = []
            elif current_role:
                current_text.append(line)
        if current_role:
            msg = _build_msg(conv_id, current_role, current_text, len(messages))
            messages.append(msg)
        return messages

    def _build_msg(conv_id: str, role: str, lines: list, idx: int) -> dict:
        atts = None
        clean = []
        for l in lines:
            if l.startswith("@attachments "):
                try:
                    atts = json.loads(l[len("@attachments "):])
                except json.JSONDecodeError:
                    clean.append(l)
            else:
                clean.append(l)
        msg = {"role": role,
               "content": "\n".join(clean).strip(),
               "id": f"{conv_id}-{idx}",
               "createdAt": ""}
        if atts:
            msg["attachments"] = atts
        return msg

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

    def _conversation_by_id(conv_id: str) -> dict | None:
        idx = _conversations_idx()
        for c in idx["conversations"]:
            if c["id"] == conv_id:
                return {
                    "id": c["id"],
                    "title": c["title"],
                    "updatedAt": c.get("updatedAt", ""),
                    "pinned": c.get("pinned", False),
                    "mode": c.get("mode", "chat"),
                    "messages": _load_messages(c["id"]),
                }
        return None

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
        # notify all MCP managers so they sync their connections
        for mcp in _builtin_mcp_managers:
            try:
                mcp.refresh_from_config(cfg)
            except Exception:
                pass
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

    # seed default skills on startup
    seed_default_skills()

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

    # ── Projects ───────────────────────────────────────────────

    PROJECTS_DIR = Path.home() / ".cozmo" / "projects"
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_INDEX = PROJECTS_DIR / "index.json"

    def _projects_idx() -> dict:
        if PROJECTS_INDEX.exists():
            raw = json.loads(PROJECTS_INDEX.read_text("utf-8"))
            if "projects" not in raw:
                raw["projects"] = []
            return raw
        return {"projects": []}

    def _save_projects_idx(idx: dict):
        PROJECTS_INDEX.write_text(json.dumps(idx, indent=2), "utf-8")

    @app.get("/api/projects")
    def get_projects():
        idx = _projects_idx()
        return idx["projects"]

    @app.post("/api/projects")
    def create_project(body: dict):
        name = (body.get("name") or "").strip()
        if not name:
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "name required"}, status_code=400)
        ts = datetime.now(timezone.utc).isoformat()
        project = {
            "id": f"proj-{uuid.uuid4().hex[:8]}",
            "name": name,
            "description": (body.get("description") or "").strip(),
            "conversationIds": [],
            "sharedContext": (body.get("sharedContext") or "").strip(),
            "createdAt": ts,
            "updatedAt": ts,
        }
        idx = _projects_idx()
        idx["projects"].insert(0, project)
        _save_projects_idx(idx)
        return project

    @app.put("/api/projects/{proj_id}")
    def update_project(proj_id: str, body: dict):
        idx = _projects_idx()
        for p in idx["projects"]:
            if p["id"] == proj_id:
                if "name" in body:
                    p["name"] = body["name"].strip() or p["name"]
                if "description" in body:
                    p["description"] = body["description"].strip()
                if "sharedContext" in body:
                    p["sharedContext"] = body["sharedContext"].strip()
                if "conversationIds" in body:
                    p["conversationIds"] = body["conversationIds"]
                p["updatedAt"] = datetime.now(timezone.utc).isoformat()
                _save_projects_idx(idx)
                return p
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "not found"}, status_code=404)

    @app.delete("/api/projects/{proj_id}")
    def delete_project(proj_id: str):
        idx = _projects_idx()
        idx["projects"] = [p for p in idx["projects"] if p["id"] != proj_id]
        _save_projects_idx(idx)
        return {"ok": True}

    @app.get("/api/projects/{proj_id}/conversations")
    def get_project_conversations(proj_id: str):
        idx = _projects_idx()
        for p in idx["projects"]:
            if p["id"] == proj_id:
                convs = []
                for cid in p.get("conversationIds", []):
                    conv = _conversation_by_id(cid)
                    if conv:
                        convs.append(conv)
                return convs
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "not found"}, status_code=404)

    # ── Skills ────────────────────────────────────────────────

    @app.get("/api/skills")
    def get_skills():
        if not SKILLS_DIR.exists():
            return []
        skills = []
        for folder in sorted(SKILLS_DIR.iterdir()):
            if not folder.is_dir():
                continue
            skill_file = folder / "SKILL.md"
            if not skill_file.exists():
                continue
            content = skill_file.read_text("utf-8")
            name = folder.name
            description = ""
            if content.startswith("---"):
                import yaml
                end = content.find("\n---", 3)
                if end != -1:
                    fm = yaml.safe_load(content[3:end])
                    if isinstance(fm, dict):
                        description = fm.get("description", "") or ""
            skills.append({"name": name, "description": description})
        return skills

    @app.post("/api/skills")
    def create_skill(body: dict):
        name = (body.get("name") or "").strip()
        if not name:
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "name required"}, status_code=400)
        skill_dir = SKILLS_DIR / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        content = body.get("content") or ""
        desc = body.get("description", "")
        frontmatter = f"---\nname: {name}\ndescription: \"{desc}\"\n---\n\n"
        (skill_dir / "SKILL.md").write_text(frontmatter + content, "utf-8")
        return {"name": name, "description": desc}

    @app.post("/api/skills/upload")
    async def upload_skill(file: UploadFile = File(...)):
        content = await file.read()
        text = content.decode("utf-8")
        name = Path(file.filename or "skill.md").stem
        skill_dir = SKILLS_DIR / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(text, "utf-8")
        # parse description from frontmatter
        description = ""
        if text.startswith("---"):
            import yaml
            end = text.find("\n---", 3)
            if end != -1:
                fm = yaml.safe_load(text[3:end])
                if isinstance(fm, dict):
                    description = fm.get("description", "") or ""
        return {"name": name, "description": description}

    @app.delete("/api/skills/{skill_name}")
    def delete_skill(skill_name: str):
        import shutil
        target = SKILLS_DIR / skill_name
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
        return {"ok": True}

    # ── MCP Status ──────────────────────────────────────────────

    @app.get("/api/mcp/status")
    def get_mcp_status():
        if _builtin_mcp_managers:
            return _builtin_mcp_managers[0].get_status()
        return {}

    # ── MCP Server Detail ───────────────────────────────────────

    @app.get("/api/mcp/servers/{name}")
    def get_mcp_server_detail(name: str):
        detail: dict = {"name": name}
        if _builtin_mcp_managers:
            mgr = _builtin_mcp_managers[0]
            mcp_detail = mgr.get_server_detail(name)
            if mcp_detail:
                detail.update(mcp_detail)
        # merge catalog metadata if available
        from .core.providers.catalog import lookup_by_name
        meta = lookup_by_name(name)
        if meta:
            detail["source"] = "catalog"
            detail["description"] = meta["description"]
            detail["capabilities"] = meta["capabilities"]
            detail["category"] = meta["category"]
            detail["homepage"] = meta["homepage"]
        else:
            detail["source"] = "custom"
            detail["capabilities"] = []
        # merge permissions from config
        servers = cfg.get("mcp", {}).get("servers", {})
        server_cfg = servers.get(name)
        if server_cfg and "permissions" in server_cfg:
            detail["permissions"] = server_cfg["permissions"]
        return detail

    # ── MCP Catalog ─────────────────────────────────────────────

    @app.get("/api/mcp/catalog")
    def get_mcp_catalog():
        from .core.providers.catalog import get_catalog_serializable
        return get_catalog_serializable()

    # ── MCP Test ────────────────────────────────────────────────

    @app.post("/api/mcp/test")
    def test_mcp_connection(body: dict):
        name = body.get("name", "")
        if not name:
            return {"ok": False, "error": "name required"}
        servers = cfg.get("mcp", {}).get("servers", {})
        server_cfg = servers.get(name)
        if not server_cfg:
            return {"ok": False, "error": f"server '{name}' not found in config"}
        try:
            from .core.mcp_host import MCPHost
            import asyncio
            mcp = MCPHost({"servers": {name: server_cfg}})
            async def _test():
                await mcp.connect({name: server_cfg})
                wrappers = await mcp.get_tool_wrappers()
                await mcp.disconnect()
                return len(wrappers)
            count = asyncio.run(_test())
            return {"ok": True, "tools": count}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Attachments ────────────────────────────────────────────

    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

    @app.post("/api/attachments")
    async def upload_attachment(file: UploadFile = File(...)):
        ext = Path(file.filename or "file").suffix
        att_id = uuid.uuid4().hex
        filename = f"{att_id}{ext}"
        path = ATTACHMENTS_DIR / filename
        content = await file.read()
        path.write_bytes(content)

        mime = file.content_type or "application/octet-stream"
        is_image = mime.startswith("image/")

        att = {
            "id": att_id,
            "type": "image" if is_image else "file",
            "name": file.filename or filename,
            "mime": mime,
            "size": len(content),
            "url": f"/api/attachments/{att_id}/file",
        }

        if is_image:
            thumb_dir = ATTACHMENTS_DIR / "thumbs"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb_path = thumb_dir / filename
            try:
                from PIL import Image as PILImage
                img = PILImage.open(path)
                img.thumbnail((128, 128))
                img.save(thumb_path)
                att["thumbnail"] = f"/api/attachments/{att_id}/thumb"
            except ImportError:
                pass

        return att

    @app.get("/api/attachments/{att_id}/file")
    def get_attachment_file(att_id: str):
        for p in ATTACHMENTS_DIR.iterdir():
            if p.stem == att_id and p.is_file():
                mime_type, _ = mimetypes.guess_type(str(p))
                from fastapi.responses import FileResponse
                return FileResponse(str(p), media_type=mime_type or "application/octet-stream")
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "not found"}, status_code=404)

    @app.get("/api/attachments/{att_id}/thumb")
    def get_attachment_thumb(att_id: str):
        thumb_dir = ATTACHMENTS_DIR / "thumbs"
        if not thumb_dir.exists():
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "not found"}, status_code=404)
        for p in thumb_dir.iterdir():
            if p.stem == att_id and p.is_file():
                from fastapi.responses import FileResponse
                return FileResponse(str(p), media_type="image/jpeg")
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "not found"}, status_code=404)

    @app.delete("/api/attachments/{att_id}")
    def delete_attachment(att_id: str):
        for p in ATTACHMENTS_DIR.iterdir():
            if p.stem == att_id and p.is_file():
                p.unlink()
                thumb = ATTACHMENTS_DIR / "thumbs" / p.name
                if thumb.exists():
                    thumb.unlink()
                return {"ok": True}
        return {"ok": True}

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
                    attachments_meta = msg.get("attachments", [])
                    project_id = msg.get("project_id", "")
                    if not content and not attachments_meta:
                        continue
                    if session.busy:
                        await ws.send_text(json.dumps(
                            {"type": "error", "text": "A run is already in progress."}))
                        continue
                    project_context = ""
                    if project_id:
                        proj_idx = _projects_idx()
                        for p in proj_idx.get("projects", []):
                            if p["id"] == project_id:
                                project_context = p.get("sharedContext", "")
                                break
                    session.current_conv_id = conv_id
                    session.start_run(content, attachments_meta, project_context)
                elif mtype == "stop":
                    session.stop()
                elif mtype == "permission_response":
                    session.answer_permission(msg.get("allowed", False))
                elif mtype == "plan_response":
                    session.answer_plan(msg.get("approved", False))
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
