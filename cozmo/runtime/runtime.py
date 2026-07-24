"""
CozmoRuntime — native tool-calling agentic loop.

Unified pipeline (Phase 1): no mode branching. Intent detected at entry,
then the same ReAct loop runs regardless of intent. Grounding search
is triggered for research intent only.

Loop:
  USER INPUT
  → detect intent → build tools + prompt
  → research: FORCED grounding search before the loop (small local models
    skip tools and hallucinate current events if you let them choose)
  → LOOP: model.invoke → tool_calls? → permission gate → exec → feed back
                       ↘ no calls → stream final answer → done
  → compact history when it grows past the window
"""

import difflib
import json
import base64
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime
from pathlib import Path

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import StructuredTool

from ..orchestrator.intent import classify_intent, IntentType
from .model_router import ModelRequirement
from ..capabilities import CapabilityRegistry
from ..capabilities.builtin import register_builtin_capabilities
from .model_router import ModelRouter

_INTENT_TO_CAP_IDS = {
    "conversation": ["conversation"],
    "research": ["research", "conversation"],
    "coding": ["coding", "filesystem", "terminal"],
    "planning": ["planning", "conversation"],
    "vision": ["vision", "conversation"],
}

_INTENT_TO_ROLE = {
    "conversation": "chat",
    "research": "planner",
    "coding": "coder",
    "planning": "planner",
    "vision": "vision",
}

log = logging.getLogger("cozmo.runtime")

ATTACHMENTS_DIR = Path.home() / ".cozmo" / "attachments"
SKILLS_DIR = Path.home() / ".cozmo" / "skills"

_TOOL_CATEGORIES: dict[str, str] = {
    "read": "workspace",
    "read_file": "workspace",
    "write_file": "workspace",
    "edit_file": "workspace",
    "glob": "workspace",
    "glob_search": "workspace",
    "grep": "workspace",
    "grep_search": "workspace",
    "list_directory": "workspace",
    "diagnostics": "workspace",
    "sourcegraph": "workspace",
    "bash": "python",
    "run_command": "python",
    "execute_python": "python",
    "calculator": "python",
    "web_search": "web",
    "web_search_pipeline": "web",
    "search_web": "web",
    "web_fetch": "web",
    "fetch_url": "web",
    "webfetch": "web",
    "git_diff": "git",
    "git_log": "git",
    "read_knowledge": "memory",
    "search_knowledge": "memory",
    "write_knowledge": "memory",
    "schedule_task": "memory",
    "list_schedules": "memory",
    "remove_schedule": "memory",
    "screenshot": "workspace",
    "analyze_image": "workspace",
    "clipboard_read": "workspace",
    "telegram_send": "other",
    "task": "other",
}


# ── Skill loading ─────────────────────────────────────────────────────────────

_SKILL_RE = re.compile(r"@skill\s+([a-z0-9][a-z0-9-]*)", re.IGNORECASE)

# Max chars of bundled skill files injected into the prompt at once.
# SKILL.md itself is always included; extra files are trimmed to this budget.
_MAX_SKILL_FILES_CHARS = 6000


def _load_all_skills() -> dict[str, dict]:
    """Return {name: {name, description, content, files, path}} for every installed skill."""
    skills: dict[str, dict] = {}
    if not SKILLS_DIR.is_dir():
        return skills
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
            end = content.find("\n---", 3)
            if end != -1:
                import yaml
                try:
                    fm = yaml.safe_load(content[3:end])
                    if isinstance(fm, dict):
                        description = fm.get("description", "") or ""
                        name = fm.get("name", name)
                except Exception:
                    pass
        files: dict[str, str] = {}
        for f in folder.rglob("*"):
            if not f.is_file() or f.name == "SKILL.md":
                continue
            if f.suffix == ".pyc" or "__pycache__" in str(f):
                continue
            try:
                rel = str(f.relative_to(folder))
                files[rel] = f.read_text("utf-8")
            except Exception:
                pass
        skills[name] = {
            "name": name,
            "description": description,
            "content": content,
            "files": files,
            "path": folder,
        }
    return skills

from .permissions import PermissionResolver
from .tool_risk import ToolRisk, get_tool_risk, risk_to_label
from .tool_registry import ToolRegistry
from .event_bus import EventBus, EventType
from .lessons import LessonStore
from ..tools import TOOL_REGISTRY
from ..models import ModelUnavailableError


class _RouterLLM:
    """Lightweight wrapper around ModelService for intent classification & summarization.

    Provides the simple `invoke(prompt) -> str` API that `classify_intent`
    and history compaction expect. Falls back to None if no chat model configured.
    """

    def __init__(self, model_service, role: str = "chat"):
        self._model_service = model_service
        self._role = role
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                self._client = self._model_service.client_for_role(self._role)
            except ModelUnavailableError:
                return None
        return self._client

    def invoke(self, prompt: str, **kwargs) -> str:
        client = self._get_client()
        if client is None:
            raise ModelUnavailableError("chat", None, [])
        result = client.invoke(prompt, **kwargs)
        return result.content if hasattr(result, 'content') else str(result)


# ── Prompts ──────────────────────────────────────────────────────────────────

_IDENTITY = (
    "You are Cozmo, a capable local AI assistant running entirely on-device via Ollama. "
    "You help with coding, file editing, debugging, running commands, research, writing, "
    "analysis, and general questions.\n"
    "Today's date is {date}. Your training data is older than this — for "
    "anything time-sensitive, trust tool results over your own knowledge.\n\n"
    "AGENT BEHAVIOR:\n"
    "- You work in a LOOP. Call a tool, read its result, then decide the next "
    "step. Keep going until the task is actually done, then give a final answer.\n"
    "- Prefer acting with tools over guessing. To answer questions about files "
    "or the codebase, READ them first — never invent file contents.\n"
    "- If a tool returns an error, read the error and try a corrected call — "
    "do not give up after one failure, and do not repeat the identical call.\n"
    "- Take ONE concrete step at a time. Don't announce a plan and stop; execute it.\n"
    "- When the task is complete, respond with a normal message and NO tool call. "
    "That message is shown to the user as the final answer.\n"
    "- Be concise and direct. No hedging ('as of my last update'), no filler.\n"
)

_COLLAB_PLAN_PROMPT = """You are planning a multi-step task. Review the context and generate a clear, numbered plan.

CONTEXT:
{context}

USER REQUEST: {query}

Generate a numbered plan with concrete steps. Each step should say what you will do, which tools you'll use, and the expected output.

Format:
## Plan
1. [Step description] — tools: [tool names] — output: [expected result]
2. [Step description] — tools: [tool names] — output: [expected result]

Keep steps focused and actionable. 3-7 steps is typical for most tasks."""

_COMPACT_PROMPT = """Condense this conversation into a short context note (4-6 sentences max).
Keep: what the user is working on, key facts established, decisions made, user preferences.
Drop: greetings, pleasantries, resolved dead-ends.

{text}

Context note:"""

# text-fallback: models that don't emit native tool_calls sometimes emit JSON.
_TEXT_TOOLCALL_RE = re.compile(r"\{.*\}", re.DOTALL)

# Plain web_search first: grounding needs fast raw results. The full
# pipeline (rewrite LLM + page fetches + synthesis LLM) is too slow to
# run synchronously before every research answer.
_SEARCH_TOOL_PREFERENCE = ("web_search", "web_search_pipeline")


# ── Runtime ──────────────────────────────────────────────────────────────────

class CozmoRuntime:
    """Single agentic runtime loop with native tool calling."""

    def __init__(
        self,
        model_manager: object | None = None,
        model_service=None,
        memory=None,
        registry: ToolRegistry | None = None,
        project_index=None,
        cfg: dict | None = None,
        router_llm: object | None = None,
        skills: dict | None = None,
        event_bus=None,
    ):
        self.model_manager = model_manager
        self.model_service = model_service
        self.router_llm = router_llm
        self.memory = memory
        self._registry = registry or ToolRegistry()
        self.project_index = project_index
        self.cfg = cfg or {}
        self.event_bus = event_bus
        self.history: list[tuple[str, str]] = []
        self._summary: str = ""  # compacted old history

        rt = self.cfg.get("runtime", {})
        self.max_history = rt.get("max_history", 10)
        self.max_steps = rt.get("max_steps", 10)
        self.max_tool_output = rt.get("max_tool_output_chars", 8000)
        self.memory_distance_threshold = rt.get("memory_distance_threshold", 0.5)
        self.max_memory_results = rt.get("max_memory_results", 3)
        self.max_project_results = rt.get("max_project_results", 3)

        self.temperature = rt.get("temperature", 0.4)

        self._plan_callback = None  # UI hook: (plan_text) -> bool

        self._perms = PermissionResolver(self.cfg)
        self._permission_callback = None  # UI hook: (tool, args) -> bool
        self._perm_mode = "manual"
        self._lc_tools = self._build_lc_tools()
        # skills is shared/read-only when passed in by the server; only fall
        # back to a disk read when constructed standalone (e.g. CLI).
        self._skills = skills if skills is not None else _load_all_skills()
        self._skill_names_list = ", ".join(
            f"{n} ({s['description'][:60]})" for n, s in self._skills.items()
        ) if self._skills else "(none installed)"
        self.stop_event: threading.Event | None = None
        self._agent_system_extra: str = ""
        self.lesson_store = LessonStore()

        # Phase 4: capability-based tool resolution
        self._capability_registry = CapabilityRegistry()
        register_builtin_capabilities(self._capability_registry)

        llm_cfg = self.cfg.get("llm", {})
        default_model = llm_cfg.get("default_model") or "qwen3:8b"
        self._model_router = ModelRouter(default_model=default_model, resource_manager=None)
        if self.model_service:
            self._model_router.populate_from_service(self.model_service, self.cfg)

        self.force_capability = rt.get("force_capability", "") or ""
        self.force_model = rt.get("force_model", "") or ""
        if self.force_capability:
            log.info("force_capability set to %s (debug override)", self.force_capability)
        if self.force_model:
            log.info("force_model set to %s (debug override)", self.force_model)

    def _check_stop(self):
        """Stop the generator early if stop_event was set."""
        if self.stop_event and self.stop_event.is_set():
            return True
        return False

    def set_permission_callback(self, callback):
        """callback(tool_name, args) -> bool. Set by the UI layer for 'ask' rules."""
        self._permission_callback = callback

    def set_plan_callback(self, callback):
        """callback(plan_text) -> bool. Set by the UI layer for agent plan approval."""
        self._plan_callback = callback

    # ── langchain tool wrappers ──────────────────────────────────────────

    def _build_lc_tools(self) -> dict:
        """Wrap registry functions as StructuredTools (schema from signatures)."""
        return self._registry.as_lc_tools()

    def _tools_for_mode(self, capability: str = "", profile=None,
                        allowed_tools: list[str] | None = None) -> list:
        """Return tools filtered by capability-resolved allowlist.

        If allowed_tools is provided, only those tools are returned.
        Otherwise returns all registered tools.
        """
        if allowed_tools is not None:
            allowed = set(allowed_tools)
            return [t for t in self._lc_tools.values() if t.name in allowed]

        tools = list(self._lc_tools.values())
        if profile and hasattr(profile, 'tool_whitelist') and profile.tool_whitelist:
            whitelist = set(profile.tool_whitelist)
            tools = [t for t in tools if t.name in whitelist]
        return tools

    # ── context ──────────────────────────────────────────────────────────

    def _history_messages(self) -> list:
        msgs = []
        for user, assistant in self.history[-self.max_history:]:
            msgs.append(HumanMessage(content=user))
            msgs.append(AIMessage(content=assistant))
        return msgs

    def _query_memory(self, user_input: str, intent: str = "conversation") -> str:
        if not self.memory:
            return ""
        try:
            type_filter = self._memory_types_for_intent(intent)
            results = self.memory.query(
                user_input,
                k=self.max_memory_results * 3,
                distance_threshold=self.memory_distance_threshold,
                memory_types=type_filter,
            )
            if not results:
                return ""
            results = self._rank_memories(results)[:self.max_memory_results]
            sections = []
            type_labels = set()
            for r in results:
                meta = r.get("metadata", {})
                t = meta.get("type", "")
                if t not in type_labels:
                    type_labels.add(t)
                    sections.append(f"\n--- {t.capitalize()} ---") if t else None
                sections.append(f"  {r['text']}")
            return "\n".join(sections) if sections else ""
        except Exception:
            return ""

    def _rank_memories(self, results: list[dict]) -> list[dict]:
        """Rank by importance (frequency × recency × distance)."""
        now = datetime.now()
        scored = []
        for r in results:
            meta = r.get("metadata", {})
            freq = meta.get("frequency", 1)
            ts = meta.get("timestamp", "")
            try:
                age_hours = (now - datetime.fromisoformat(ts)).total_seconds() / 3600 if ts else 24
            except Exception:
                age_hours = 24
            recency = max(0.1, 1.0 - age_hours / 168)
            distance = r.get("distance", 0.5)
            importance = freq * recency * (1.0 - distance)
            scored.append((importance, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored]

    @staticmethod
    def _memory_types_for_intent(intent: str) -> list[str] | None:
        mapping = {
            "conversation": ["conversation", "preference", "fact"],
            "research": ["reference", "fact", "conversation"],
            "coding": ["project", "learning", "reference"],
            "planning": ["project", "reference", "fact"],
            "vision": ["reference", "conversation"],
        }
        return mapping.get(intent)

    def _query_project(self, user_input: str) -> str:
        if not self.project_index:
            return ""
        try:
            return self.project_index.query(user_input, k=self.max_project_results) or ""
        except Exception:
            return ""

    def _system_prompt(self, user_input: str, intent: str = "conversation",
                       grounding: str = "",
                       attachments: list[dict] | None = None,
                       activated_skills: list[dict] | None = None,
                       profile=None,
                       allowed_tools: list[str] | None = None) -> str:
        parts = [_IDENTITY.format(date=datetime.now().strftime("%A, %B %d, %Y"))]

        if profile and hasattr(profile, 'system_prompt_extra') and profile.system_prompt_extra:
            parts.append(f"PROFILE INSTRUCTIONS:\n{profile.system_prompt_extra}")

        if self._agent_system_extra:
            parts.append(f"AGENT INSTRUCTIONS:\n{self._agent_system_extra}")

        personality = (self.cfg.get("personality") or "").strip()
        if personality:
            parts.append(f"USER PREFERENCES:\n{personality}")

        if self._skills:
            skill_lines = "\n".join(
                f"  {n} — {s['description'][:120]}"
                for n, s in self._skills.items()
            )
            parts.append(
                "AVAILABLE SKILLS (you can activate one by writing @skill <name> in your response):\n"
                f"{skill_lines}"
            )

        if activated_skills:
            for sk in activated_skills:
                parts.append(self._skill_block(sk))

        if attachments:
            file_list = "\n".join(
                f"- {a['name']} ({a['type']}, {a.get('mime', 'unknown')}) — available at {a.get('path', a.get('url', 'unknown'))}"
                for a in attachments
            )
            parts.append(f"\nUser attached files:\n{file_list}\nReference these when relevant. For images, you can see them directly.")

        if self._summary:
            parts.append(f"\nContext from earlier in this session:\n{self._summary}")

        memory = self._query_memory(user_input, intent)
        if memory:
            parts.append(f"\nRelevant memory from past sessions:{memory}")

        lessons = self.lesson_store.get_context(tool_names=allowed_tools if allowed_tools else None)
        if lessons:
            parts.append(lessons)

        if intent in ("coding", "work"):
            project = self._query_project(user_input)
            if project:
                parts.append(f"\nRelevant project context:\n{project}")

        if getattr(self, '_project_context', None):
            parts.append(f"\nProject context:\n{self._project_context}")

        if grounding:
            parts.append(
                "\nSearch results for the user's question (use these as your "
                f"primary source):\n{grounding}"
            )

        return "\n\n".join(parts)

    # ── skills ────────────────────────────────────────────────────────────

    def _skill_block(self, sk: dict) -> str:
        """Render an activated skill for the prompt. Caps bundled file content
        so a large skill can't blow a small model's context window (progressive
        disclosure — SKILL.md always shown, files trimmed to a budget)."""
        out = [f"ACTIVATED SKILL: {sk['name']}\n{sk['content']}"]
        files = sk.get("files") or {}
        if files:
            rendered, skipped, used = [], [], 0
            for path, text in files.items():
                block = f"--- {path} ---\n{text}"
                if used + len(block) > _MAX_SKILL_FILES_CHARS:
                    skipped.append(path)
                    continue
                rendered.append(block)
                used += len(block)
            body = "\n\n".join(rendered)
            if skipped:
                skill_dir = sk.get("path", "the skill folder")
                body += (f"\n\n({len(skipped)} more skill file(s) not shown to "
                         f"save context: {', '.join(skipped)}. They live under "
                         f"{skill_dir} — read one with read_file if you need it.)")
            out.append(f"SKILL FILES ({sk['name']}):\n{body}")
        return "\n\n".join(out)

    def _scan_skills(self, text: str, already: list[dict]) -> list[dict]:
        """Return installed skills newly referenced via @skill in `text`
        (skipping any already activated). Used for both the user's message
        and the model's own output, so the model can self-activate skills."""
        found: list[dict] = []
        if not self._skills or not text:
            return found
        for m in _SKILL_RE.finditer(text):
            sk = self._skills.get(m.group(1).lower())
            if sk and sk not in already and sk not in found:
                found.append(sk)
        return found

    # ── forced grounding search (research mode) ──────────────────────────

    def _grounding_search(self, user_input: str) -> str:
        if not user_input or not user_input.strip():
            return ""
        if self._check_stop():
            return ""
        for name in _SEARCH_TOOL_PREFERENCE:
            info = self._registry.get(name)
            if info is None:
                continue
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(info.fn, query=user_input)
                    result = fut.result(timeout=15)
                text = self._sanitize(str(result))
                # A no-results/unavailable message is not grounding — return
                # empty so the loop keeps search tools available instead.
                if text.startswith("Web search unavailable"):
                    log.warning("grounding search returned no results (%s)", name)
                    return ""
                return text
            except FutureTimeout:
                log.warning("grounding search timed out (%s)", name)
                return ""
            except Exception as e:
                log.warning("grounding search failed (%s): %s", name, e)
                return ""
        return ""

    # ── agent mode: plan generation ──────────────────────────────────────

    def _gather_agent_context(self, user_input: str) -> str:
        """Gather memory, project info, and search results for plan context."""
        parts = []
        memory = self._query_memory(user_input)
        if memory:
            parts.append(f"Memory from past sessions:\n{memory}")
        if self._project_context:
            parts.append(f"Project context:\n{self._project_context}")
        if self.project_index:
            try:
                project = self.project_index.query(user_input, k=self.max_project_results)
                if project:
                    parts.append(f"Relevant project files:\n{project}")
            except Exception:
                pass
        if self._summary:
            parts.append(f"Session summary:\n{self._summary}")
        return "\n\n".join(parts) if parts else "(no additional context)"

    def _generate_plan(self, user_input: str, context: str) -> str:
        """Use the research model to generate a structured plan."""
        try:
            if self.model_service:
                llm = self.model_service.client_for_role("research", temperature=0.2)
            else:
                raise RuntimeError("model_service required for plan generation")
            prompt = _COLLAB_PLAN_PROMPT.format(context=context, query=user_input)
            plan = llm.invoke(prompt)
            text = getattr(plan, "content", plan)
            return text.strip() if isinstance(text, str) else str(text).strip()
        except Exception as e:
            return f"1. Investigate the request: {user_input}\n2. Execute based on available tools and context.\n(Plan generation failed: {e})"

    # ── tool call extraction (native + text fallback) ────────────────────

    def _extract_calls(self, ai) -> list[dict]:
        native = getattr(ai, "tool_calls", None)
        if native:
            return [{"name": c["name"], "args": c.get("args", {}),
                     "id": c.get("id") or c["name"]} for c in native]
        return self._parse_text_toolcall(getattr(ai, "content", "") or "")

    def _parse_text_toolcall(self, content: str) -> list[dict]:
        """Fallback: some models emit {"name":..,"arguments":..} as plain text."""
        if "{" not in content:
            return []
        match = _TEXT_TOOLCALL_RE.search(content)
        if not match:
            return []
        try:
            obj = json.loads(match.group())
        except json.JSONDecodeError:
            return []
        name = obj.get("name") or obj.get("tool")
        args = obj.get("arguments") or obj.get("args") or {}
        if name in self._lc_tools and isinstance(args, dict):
            return [{"name": name, "args": args, "id": name}]
        return []

    # ── tool execution ───────────────────────────────────────────────────

    def _check_permission(self, name: str, args: dict) -> bool:
        mode = getattr(self, '_perm_mode', 'manual')
        # Plan: deny all tool execution (agent generates plan only)
        if mode == 'plan':
            return False
        # Bypass: allow everything without asking
        if mode == 'bypass':
            return True
        # Accept edits: auto-allow file changes, ask for other tools
        if mode == 'accept-edits' and name in ('edit_file', 'write_file'):
            return True
        # Auto: auto-allow LOW risk, ask for MEDIUM+, deny CRITICAL
        if mode == 'auto':
            risk = get_tool_risk(name)
            if risk == ToolRisk.LOW:
                return True
            if risk == ToolRisk.CRITICAL:
                return False
        # Fallback: config rules (resolve uses risk internally)
        decision = self._perms.resolve(name, args, agent="cozmo")
        if decision == "allow":
            return True
        if decision == "deny":
            return False
        # 'ask' — defer to the UI layer; no UI hook means deny (fail safe)
        risk = get_tool_risk(name)
        if risk == ToolRisk.CRITICAL:
            return False
        if self._permission_callback:
            return self._permission_callback(name, args)
        return False

    def _compute_diff(self, name: str, args: dict) -> dict | None:
        if name == "edit_file":
            old = (args.get("old_text") or "").splitlines(keepends=True)
            new = (args.get("new_text") or "").splitlines(keepends=True)
            diff = list(difflib.unified_diff(old, new,
                         fromfile=args.get("path","?"), tofile=args.get("path","?"), n=3))
            text = "".join(diff[2:]) if len(diff) > 2 else ""
            added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
            return {"text": text, "added": added, "removed": removed}
        if name == "write_file":
            new = (args.get("content") or "").splitlines()
            return {"text": "\n".join(f"+{l}" for l in new), "added": len(new), "removed": 0}
        return None

    def _exec_tool(self, name: str, args: dict) -> str:
        info = self._registry.get(name)
        if info is None:
            known = ", ".join(sorted(t.name for t in self._registry.list()))
            out = f"Error: unknown tool '{name}'. Available tools: {known}"
            self.lesson_store.record(name, args, out)
            return out
        if not self._check_permission(name, args):
            out = (f"Error: the user DENIED permission for {name}. Do not retry "
                    f"this call — explain what you wanted to do and ask the user.")
            self.lesson_store.record(name, args, out)
            return out
        try:
            raw = str(info.fn(**args))
        except TypeError as e:
            out = f"Error: bad arguments for {name}: {e}. Check the tool schema and retry."
            self.lesson_store.record(name, args, out)
            return out
        except Exception as e:
            raw = f"Error: {e}"
        result = self._sanitize(raw)
        self.lesson_store.record(name, args, result)
        return result

    def _sanitize(self, text: str) -> str:
        if len(text) > self.max_tool_output:
            head = self.max_tool_output // 3
            tail = self.max_tool_output - head
            text = (text[:head]
                    + f"\n... [{len(text) - self.max_tool_output} chars truncated] ...\n"
                    + text[-tail:])
        return text

    @staticmethod
    def _tool_category(name: str) -> str:
        return _TOOL_CATEGORIES.get(name, "other")

    # ── main streaming loop ──────────────────────────────────────────────

    def _build_multimodal_content(self, text: str, attachments: list[dict]) -> list:
        content: list = [{"type": "text", "text": text}]
        for att in attachments:
            if att["type"] != "image":
                continue
            path = att.get("path", "")
            if not path or not Path(path).exists():
                continue
            try:
                data = Path(path).read_bytes()
                b64 = base64.b64encode(data).decode("utf-8")
                mime = att.get("mime", "image/png")
                content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
            except Exception:
                content.append({"type": "text", "text": f"[Image: {att['name']} — failed to load]"})
        return content

    def _emit_bus(self, event_type: str, **data):
        """Emit to event bus if one is attached."""
        if self.event_bus:
            try:
                self.event_bus.emit(event_type, **data)
            except Exception:
                pass

    def run_stream(self, user_input: str, attachments: list[dict] | None = None,
                   force_mode: str | None = None, agent_runtime=None,
                   force_capability: str | None = None,
                   force_model: str | None = None,
                   execution_plan: object | None = None):
        """Yield (kind, text) tuples. Unified pipeline — no mode branching.

        force_mode is deprecated compat: logged, ignored for routing.
        AgentRuntime support via agent_runtime param (legacy path).
        execution_plan: if provided, use plan.tools / plan.model_spec directly,
                        skipping capability re-resolution.
        """
        intent_str = "conversation"
        try:
            has_images = attachments and any(a.get("type") == "image" for a in attachments)
            activated_skills: list[dict] = self._scan_skills(user_input, [])

            # ── deprecated force_mode compat / execution plan ───────────
            if execution_plan is not None:
                intent_str = execution_plan.goal.intent.value
            elif force_mode is not None:
                log.warning("force_mode='%s' is deprecated. Use force_capability / force_model.", force_mode)
                intent_str = force_mode
            else:
                intent = classify_intent(user_input, self.router_llm, self.history, has_images)
                intent_str = intent.value

            yield ("status", "Routing...")
            if activated_skills:
                names = ", ".join(s["name"] for s in activated_skills)
                yield ("thinking", f"Intent: {intent_str} — Skills: {names}", f"Operating on {intent_str} intent with skills: {names}", None)
            else:
                yield ("thinking", f"Intent: {intent_str}", f"Operating on {intent_str} intent", None)
            self._emit_bus("intent_set", intent=intent_str)

            # ── optional grounding search (research intent) ──────────────
            grounding = ""
            if intent_str == "research":
                yield ("thinking", "Searching...", "Searching the web for context", user_input)
                grounding = self._grounding_search(user_input)

            # ── capability-based tool resolution (Phase 4) ────────────────
            profile = None
            if execution_plan is not None:
                allowed_tools = execution_plan.tools
                model_name = execution_plan.model_spec.get("model", "") or force_model or ""
                role = _INTENT_TO_ROLE.get(intent_str, "chat")
                if self.model_service and not force_model:
                    try:
                        _, role_model = self.model_service.resolve(role)
                        if role_model:
                            model_name = role_model
                    except Exception:
                        pass
                temp = execution_plan.temperature
                max_steps = execution_plan.max_steps
            else:
                cap_name = force_capability or intent_str
                cap_ids = _INTENT_TO_CAP_IDS.get(cap_name, ["conversation"])
                allowed_tools = self._capability_registry.get_tool_names(cap_ids)
                model_name = force_model or ""
                role = _INTENT_TO_ROLE.get(cap_name, "chat")
                if not model_name:
                    if self.model_service:
                        try:
                            _, role_model = self.model_service.resolve(role)
                            if role_model:
                                model_name = role_model
                        except Exception:
                            pass
                if not model_name:
                    req = [ModelRequirement(capability=cap_name)]
                    model_name = self._model_router.resolve(req)
                temp = self.temperature
                max_steps = self.max_steps

            yield ("model", model_name)

            # ── build ReAct loop ─────────────────────────────────────────
            lc_tools = self._tools_for_mode(capability=intent_str, profile=None,
                                            allowed_tools=allowed_tools)

            # Skip tool binding if model doesn't support tools (e.g. vision models)
            model_supports_tools = True
            if execution_plan is not None:
                model_supports_tools = execution_plan.model_spec.get("supports_tools", True)
            elif intent_str == "vision":
                model_supports_tools = False
            if not model_supports_tools:
                lc_tools = []

            _SEARCH_TOOL_NAMES = {"web_search", "web_search_pipeline", "web_fetch", "fetch_url"}
            _skip_search = bool(grounding)
            if _skip_search:
                lc_tools = [t for t in lc_tools if t.name not in _SEARCH_TOOL_NAMES]

            mm = self.model_service if self.model_service else self.model_manager
            runnable = (mm.bind_model(model_name, lc_tools, temperature=temp)
                        if lc_tools else mm.client_for_model(model_name, temp))

            msgs = [SystemMessage(content=self._system_prompt(
                user_input, intent_str, grounding, attachments, activated_skills, profile,
                allowed_tools=allowed_tools))]
            msgs += self._history_messages()

            if has_images:
                multimodal = self._build_multimodal_content(user_input, attachments)
                msgs.append(HumanMessage(content=multimodal))
            else:
                msgs.append(HumanMessage(content=user_input))

            final = ""
            seen_calls: set[str] = set()
            for step in range(max_steps):
                acc = None
                content_buf = ""

                for chunk in runnable.stream(msgs):
                    if self._check_stop():
                        return
                    acc = chunk if acc is None else acc + chunk
                    reasoning_content = chunk.additional_kwargs.get("reasoning_content", "")
                    if reasoning_content:
                        yield ("reasoning", reasoning_content)
                    piece = chunk.content or ""
                    if piece:
                        content_buf += piece
                        yield ("token", piece)

                ai = acc if acc is not None else AIMessage(content=content_buf)
                calls = self._extract_calls(ai)

                if not calls:
                    newly = self._scan_skills(content_buf, activated_skills)
                    if newly:
                        activated_skills.extend(newly)
                        names = ", ".join(s["name"] for s in newly)
                        yield ("thinking", f"Activating skill: {names}",
                               f"Loading skill instructions: {names}", None)
                        msgs.append(ai if isinstance(ai, AIMessage)
                                    else AIMessage(content=content_buf))
                        for sk in newly:
                            msgs.append(SystemMessage(content=self._skill_block(sk)))
                        continue
                    final = content_buf.strip()
                    break

                msgs.append(ai if isinstance(ai, AIMessage)
                            else AIMessage(content=content_buf))
                names = ", ".join(c["name"] for c in calls)
                arg_sigs = [json.dumps(c["args"], sort_keys=True, default=str) for c in calls]
                calls_detail = "; ".join(
                    f"{c['name']}({sig[:200]})"
                    for c, sig in zip(calls, arg_sigs)
                )
                yield ("thinking", f"Running: {names}", calls_detail, None)

                for c, args_sig in zip(calls, arg_sigs):
                    if self._check_stop():
                        return
                    sig = f"{c['name']}:{args_sig}"
                    call_id = f"call-{step}-{c['name']}"
                    yield ("tool_call", c["name"], c["args"], call_id, self._tool_category(c["name"]))
                    self._emit_bus("tool_called", tool=c["name"], args=c["args"], step=step)
                    if sig in seen_calls:
                        out = (f"Error: you already made this exact {c['name']} call "
                               f"and have its result above. Use it, or try a "
                               f"DIFFERENT call — do not repeat yourself.")
                    else:
                        seen_calls.add(sig)
                        out = self._exec_tool(c["name"], c["args"])

                    diff = self._compute_diff(c["name"], c["args"])
                    yield ("tool_result", c["name"], out, call_id, diff)
                    self._emit_bus("tool_result", tool=c["name"], call_id=call_id,
                                   is_error=out.startswith("Error"))
                    msgs.append(ToolMessage(content=out, tool_call_id=c["id"]))
                    if self._check_stop():
                        return
                yield ("thinking", "Thinking...", "Processing tool results and forming response", None)

                if _skip_search:
                    _skip_search = False
                    if model_supports_tools:
                        full_tools = self._tools_for_mode(capability=intent_str,
                                                          allowed_tools=allowed_tools)
                    else:
                        full_tools = []
                    mm = self.model_service if self.model_service else self.model_manager
                    runnable = (mm.bind_model(model_name, full_tools, temperature=temp)
                                if full_tools else mm.client_for_model(model_name, temp))
            else:
                final = ("I ran out of steps before finishing. Here's where I "
                         "got to — ask me to continue if you want me to keep going.")
                yield ("token", final)

            if not final:
                final = "(no response — the model returned empty output; try rephrasing)"
                yield ("token", final)

            self._remember(user_input, final)

        except Exception as e:
            msg = f"I hit an error: {e}"
            yield ("token", msg)
            self._remember(user_input, msg)

    def run(self, user_input: str, attachments: list[dict] | None = None) -> str:
        """Synchronous run. Returns the final answer text."""
        chunks = []
        for kind, text in self.run_stream(user_input, attachments):
            if kind == "token":
                chunks.append(text)
        return "".join(chunks).strip()

    # ── persistence + compaction ─────────────────────────────────────────

    def _remember(self, user_input: str, final: str):
        self.history.append((user_input, final))
        if len(self.history) > self.max_history:
            self._compact()
        if self.memory and hasattr(self.memory, "add_interaction"):
            try:
                self.memory.add_interaction(user_input, final)
            except Exception:
                pass

    def _compact(self):
        """Summarize the older half of history into a context note instead of
        dropping it. Keeps long sessions coherent within a small ctx window."""
        keep = self.max_history // 2
        old, self.history = self.history[:-keep], self.history[-keep:]
        text = "\n".join(f"User: {u}\nCozmo: {a}" for u, a in old)
        if self._summary:
            text = f"Earlier context:\n{self._summary}\n\n{text}"
        try:
            summary = self.router_llm.invoke(_COMPACT_PROMPT.format(text=text))
            if summary and not summary.lower().startswith("error"):
                self._summary = summary.strip()
        except Exception as e:
            log.warning("history compaction failed: %s", e)

    def reset(self):
        """Clear conversation state (new chat)."""
        self.history.clear()
        self._summary = ""


