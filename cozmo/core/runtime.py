"""
CozmoRuntime — native tool-calling agentic loop.

A real ReAct loop: the model sees tool results and decides the NEXT action,
iterating until it chooses to answer. Tool calls use Ollama's native function
calling (`bind_tools`) with a text-JSON fallback for models that emit tool
calls as plain content instead of structured `tool_calls`.

Loop:
  USER INPUT
  → route (chat / work / research) → tool subset + temperature
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

log = logging.getLogger("cozmo.runtime")

ATTACHMENTS_DIR = Path.home() / ".cozmo" / "attachments"
SKILLS_DIR = Path.home() / ".cozmo" / "skills"


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

from .llm import OllamaModel
from .model_manager import ModelManager
from .permissions import PermissionResolver
from .tool_registry import ToolRegistry
from ..tools import TOOL_REGISTRY


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

_MODE_DISCIPLINE = {
    "chat": (
        "MODE: CHAT\n"
        "- Answer conversationally and concisely from your knowledge.\n"
        "- If the question actually needs current data or file access, say what "
        "you'd need instead of guessing."
    ),
    "work": (
        "MODE: WORK — you are operating on a real codebase.\n"
        "- ALWAYS read a file before editing it. Match the existing style.\n"
        "- Make edits with edit_file (exact-match replace) for changes to "
        "existing files; write_file only for new files.\n"
        "- VERIFY your work: after editing code, run a quick check with "
        "run_command (e.g. `python -m py_compile <file>`, the project's tests, "
        "or the relevant command) and fix anything that breaks.\n"
        "- Never claim something works without having verified it. If you "
        "could not verify, say so explicitly.\n"
        "- In your final answer: summarize WHAT changed, WHERE (file paths), "
        "and how it was verified."
    ),
    "research": (
        "MODE: RESEARCH — the user needs CURRENT information.\n"
        "- If search results are provided below, they are your PRIMARY source. "
        "Answer from them directly, never from training data — your training "
        "data is stale for this question. Do NOT re-search unless the results "
        "are clearly irrelevant.\n"
        "- If NO search results are provided below, call the web_search tool "
        "FIRST with a focused query, then answer from what it returns.\n"
        "- If results conflict, prefer the most recent and say so.\n"
        "- Cite where facts came from (source names/domains from the results).\n"
        "- If you genuinely cannot find the answer in any results, say exactly "
        "that — do not fabricate and do not claim you lack internet access "
        "(you have the web_search tool)."
    ),
    "collab": (
        "MODE: COLLAB — structured task execution with an approved plan.\n"
        "- The user approved the plan below. Execute each step in order.\n"
        "- Use tools to complete each step. Report progress after each step.\n"
        "- If a step fails, note the failure and continue with remaining steps.\n"
        "- In your final response, summarize what was completed and any issues.\n"
        "- Do NOT deviate from the approved plan without asking the user first."
    ),
}

_ROUTE_PROMPT = """Classify the user's latest request as exactly one word:
- chat: greetings, small talk, definitions, general Q&A answerable from timeless knowledge
- work: coding, editing files, debugging, shell commands, anything touching the project
- collab: structured multi-step tasks like writing specs, planning architecture, documenting, brainstorming, researching, creating reports or proposals
- research: needs current/external info (news, events, sports, prices, weather, releases, schedules, "today", "latest", "recent", "next", "upcoming")
- vision: image generation, image editing, processing .png/.jpeg/.bmp/.gif/.tiff/.webp

Anything about current events or things that change over time is research, even if phrased vaguely.
When unsure between chat and research, pick research. When it touches code or files, pick work.
Multi-step tasks that need planning (writing docs, creating specs, architecture design, research reports) → collab.

Examples:
- "what's the weather in new york" → research
- "latest stock price of apple" → research
- "who won the super bowl" → research
- "edit main.py and fix the bug" → work
- "what is a monad" → chat
- "help me brainstorm feature ideas" → collab
- "write a spec for the auth system" → collab
- "plan the architecture for a new feature" → collab
- "draft documentation for the API" → collab
- "summarize this article about AI" → research
- "create a presentation outline" → collab
- "fix the typo in README.md" → work
- "explain how DNS works" → chat
- "research competitors in the AI space" → collab

Recent conversation (for context on vague follow-ups):
{history}

Request: {text}
Answer with one word:"""

# Pre-pass keywords that short-circuit to research mode before LLM call.
# Catches patterns the small router model might miss.
_RESEARCH_KEYWORDS = [
    "latest news", "current events", "what's new",
    "weather", "price of", "release date", "upcoming", "schedule",
    "this week", "this month", "today", "right now",
    "who won", "score", "election", "breaking",
]

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
        model_manager: ModelManager,
        memory=None,
        registry: ToolRegistry | None = None,
        project_index=None,
        cfg: dict | None = None,
        router_llm: OllamaModel | None = None,
        skills: dict | None = None,
    ):
        self.model_manager = model_manager
        self.router_llm = router_llm
        self.memory = memory
        self._registry = registry or ToolRegistry()
        self.project_index = project_index
        self.cfg = cfg or {}
        self.history: list[tuple[str, str]] = []
        self._summary: str = ""  # compacted old history

        rt = self.cfg.get("runtime", {})
        self.max_history = rt.get("max_history", 10)
        self.max_steps = rt.get("max_steps", 10)
        self.max_tool_output = rt.get("max_tool_output_chars", 8000)
        self.memory_distance_threshold = rt.get("memory_distance_threshold", 0.5)
        self.max_memory_results = rt.get("max_memory_results", 3)
        self.max_project_results = rt.get("max_project_results", 3)

        temps = rt.get("temperatures", {})
        self.temps = {
            "chat": temps.get("chat", 0.6),
            "work": temps.get("work", 0.0),
            "research": temps.get("research", 0.2),
            "collab": temps.get("collab", 0.2),
            "vision": temps.get("vision", 0.2),
        }

        # which tools each mode may call (None = all registered tools)
        self._tool_gate = rt.get("tool_gate", {
            "chat": [],
            "research": ["web_search", "web_search_pipeline", "web_fetch", "calculator"],
            "work": None,
            "collab": None,
            "vision": [],
        })

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

    def _check_stop(self):
        """Stop the generator early if stop_event was set."""
        if self.stop_event and self.stop_event.is_set():
            return True
        return False

    def set_permission_callback(self, callback):
        """callback(tool_name, args) -> bool. Set by the UI layer for 'ask' rules."""
        self._permission_callback = callback

    def set_plan_callback(self, callback):
        """callback(plan_text) -> bool. Set by the UI layer for collab plan approval."""
        self._plan_callback = callback

    # ── langchain tool wrappers ──────────────────────────────────────────

    def _build_lc_tools(self) -> dict:
        """Wrap registry functions as StructuredTools (schema from signatures)."""
        return self._registry.as_lc_tools()

    def _tools_for_mode(self, mode: str) -> list:
        allowed = self._tool_gate.get(mode, None)
        if allowed is None:
            return list(self._lc_tools.values())
        return [self._lc_tools[n] for n in allowed if n in self._lc_tools]

    # ── context ──────────────────────────────────────────────────────────

    def _history_messages(self) -> list:
        msgs = []
        for user, assistant in self.history[-self.max_history:]:
            msgs.append(HumanMessage(content=user))
            msgs.append(AIMessage(content=assistant))
        return msgs

    def _query_memory(self, user_input: str) -> str:
        if not self.memory:
            return ""
        try:
            results = self.memory.query(user_input, k=self.max_memory_results * 2)
            if not results:
                return ""
            filtered = [r for r in results
                        if r.get("distance", 0) < self.memory_distance_threshold]
            filtered = filtered[:self.max_memory_results]
            if not filtered:
                return ""
            return "\n".join(f"- {r['text']}" for r in filtered)
        except Exception:
            return ""

    def _query_project(self, user_input: str) -> str:
        if not self.project_index:
            return ""
        try:
            return self.project_index.query(user_input, k=self.max_project_results) or ""
        except Exception:
            return ""

    def _system_prompt(self, user_input: str, mode: str,
                       grounding: str = "",
                       attachments: list[dict] | None = None,
                       activated_skills: list[dict] | None = None) -> str:
        parts = [_IDENTITY.format(date=datetime.now().strftime("%A, %B %d, %Y"))]
        parts.append(_MODE_DISCIPLINE.get(mode, _MODE_DISCIPLINE["chat"]))

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

        memory = self._query_memory(user_input)
        if memory:
            parts.append(f"\nRelevant memory from past sessions:\n{memory}")

        if mode == "work":
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

    # ── routing ──────────────────────────────────────────────────────────

    def _route(self, user_input: str) -> str:
        query_lower = user_input.lower()
        for kw in _RESEARCH_KEYWORDS:
            if kw in query_lower:
                return "research"
        recent = "\n".join(
            f"User: {u}\nCozmo: {a[:200]}" for u, a in self.history[-3:]
        ) or "(none)"
        raw = self.router_llm.invoke(
            _ROUTE_PROMPT.format(history=recent, text=user_input)
        ).strip().lower()
        for mode in ("collab", "work", "research", "chat"):
            if mode in raw:
                return mode
        # Unparseable classifier output: chat is the cheap, safe default.
        # Research mode forces a blocking search; chat mode can still
        # tell the user what it needs.
        log.warning("router returned unrecognized mode %r; defaulting to chat", raw)
        return "chat"

    # ── forced grounding search (research mode) ──────────────────────────

    def _grounding_search(self, user_input: str) -> str:
        """Deterministically run one search before the loop. Small models
        skip tools and hallucinate current events if given the choice.
        Timeout after 15s to prevent hanging."""
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

    # ── collab mode: plan generation ──────────────────────────────────────

    def _gather_collab_context(self, user_input: str) -> str:
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
            llm = self.model_manager.client("research", temperature=0.2)
            prompt = _COLLAB_PLAN_PROMPT.format(context=context, query=user_input)
            plan = llm.invoke(prompt)
            # model_manager clients return an AIMessage, not a str
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
        # Auto: auto-allow safe tools, ask for risky ones
        if mode == 'auto':
            safe = {'read_file', 'list_directory', 'grep_search', 'calculator',
                    'git_diff', 'git_log', 'web_search', 'web_search_pipeline',
                    'web_fetch', 'fetch_url'}
            if name in safe:
                return True
        # Manual (default) + fallback: config rules then UI callback
        decision = self._perms.resolve(name, args, agent="cozmo")
        if decision == "allow":
            return True
        if decision == "deny":
            return False
        # 'ask' — defer to the UI layer; no UI hook means deny (fail safe)
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
            return f"Error: unknown tool '{name}'. Available tools: {known}"
        if not self._check_permission(name, args):
            return (f"Error: the user DENIED permission for {name}. Do not retry "
                    f"this call — explain what you wanted to do and ask the user.")
        try:
            raw = str(info.fn(**args))
        except TypeError as e:
            return f"Error: bad arguments for {name}: {e}. Check the tool schema and retry."
        except Exception as e:
            raw = f"Error: {e}"
        return self._sanitize(raw)

    def _sanitize(self, text: str) -> str:
        if len(text) > self.max_tool_output:
            head = self.max_tool_output // 3
            tail = self.max_tool_output - head
            text = (text[:head]
                    + f"\n... [{len(text) - self.max_tool_output} chars truncated] ...\n"
                    + text[-tail:])
        return text

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

    def run_stream(self, user_input: str, attachments: list[dict] | None = None):
        """Yield (kind, text) tuples. kind is 'token', 'thinking', or 'status'."""
        try:
            has_images = attachments and any(a.get("type") == "image" for a in attachments)

            # ── skill activation (from the user's message) ────────────────
            activated_skills: list[dict] = self._scan_skills(user_input, [])

            yield ("status", "Routing...")
            mode = self._route(user_input) if not has_images else "vision"
            if activated_skills:
                names = ", ".join(s["name"] for s in activated_skills)
                yield ("thinking", f"Mode: {mode} — Skills: {names}", f"Operating in {mode} mode with skills: {names}", None)
            else:
                yield ("thinking", f"Mode: {mode}", f"Operating in {mode} mode", None)

            grounding = ""
            if mode == "research":
                yield ("thinking", "Searching...", "Searching the web for context", user_input)
                grounding = self._grounding_search(user_input)
            elif mode == "collab":
                yield ("thinking", "Planning...", "Generating a plan for review", user_input)
                context = self._gather_collab_context(user_input)
                plan = self._generate_plan(user_input, context)
                yield ("plan", plan, "Review and approve the proposed plan", None)
                approved = True
                if self._plan_callback:
                    approved = self._plan_callback(plan)
                if not approved:
                    yield ("token", "Plan not approved. Please refine your request and try again.")
                    return
                grounding = f"APPROVED PLAN:\n{plan}\n\nExecute each step of this approved plan in order. Report progress after each step."

            temp = self.temps.get(mode, 0.0)
            lc_tools = self._tools_for_mode(mode)

            _SEARCH_TOOL_NAMES = {"web_search", "web_search_pipeline", "web_fetch", "fetch_url"}
            _skip_search = bool(grounding)  # skip search tools on first step if we already have results
            if _skip_search:
                lc_tools = [t for t in lc_tools if t.name not in _SEARCH_TOOL_NAMES]

            runnable = (self.model_manager.bind_tools(mode, lc_tools, temperature=temp)
                        if lc_tools else self.model_manager.client(mode, temp))

            msgs = [SystemMessage(content=self._system_prompt(
                user_input, mode, grounding, attachments, activated_skills))]
            msgs += self._history_messages()

            if has_images:
                multimodal = self._build_multimodal_content(user_input, attachments)
                msgs.append(HumanMessage(content=multimodal))
            else:
                msgs.append(HumanMessage(content=user_input))

            final = ""
            seen_calls: set[str] = set()  # break identical-call loops
            failed_steps: list[str] = []  # track failures for error recovery
            for step in range(self.max_steps):
                acc = None
                content_buf = ""
                suppress = False
                streamed = False

                if mode == "collab":
                    yield ("thinking", f"Step {step + 1}/{self.max_steps}",
                           f"Executing step {step + 1}", None)

                for chunk in runnable.stream(msgs):
                    if self._check_stop():
                        return
                    acc = chunk if acc is None else acc + chunk
                    piece = chunk.content or ""
                    if piece:
                        content_buf += piece
                        # suppress content that looks like a text-fallback tool call
                        if not streamed and not suppress:
                            if content_buf.lstrip()[:1] == "{":
                                suppress = True
                        if not suppress:
                            streamed = True
                            yield ("token", piece)

                ai = acc if acc is not None else AIMessage(content=content_buf)
                calls = self._extract_calls(ai)

                if not calls:
                    # false-positive suppression: JSON-looking content that
                    # wasn't a real tool call — surface it after all.
                    if suppress and not streamed:
                        yield ("token", content_buf)
                    # the model may activate a skill by writing @skill <name>;
                    # inject it and keep looping so it can actually use it.
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

                # model wants tools: record the turn, run them, feed results back
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
                    yield ("tool_call", c["name"], c["args"], call_id)
                    if sig in seen_calls:
                        out = (f"Error: you already made this exact {c['name']} call "
                               f"and have its result above. Use it, or try a "
                               f"DIFFERENT call — do not repeat yourself.")
                    else:
                        seen_calls.add(sig)
                        out = self._exec_tool(c["name"], c["args"])
                    # Track failures for collab error recovery
                    if mode == "collab" and out.startswith("Error"):
                        failed_steps.append(f"Step {step + 1}: {c['name']} failed — {out[:200]}")
                    diff = self._compute_diff(c["name"], c["args"])
                    yield ("tool_result", c["name"], out, call_id, diff)
                    msgs.append(ToolMessage(content=out, tool_call_id=c["id"]))
                    if self._check_stop():
                        return
                yield ("thinking", "Thinking...", "Processing tool results and forming response", None)

                # after first step, restore full search tools
                if _skip_search:
                    _skip_search = False
                    full_tools = self._tools_for_mode(mode)
                    runnable = (self.model_manager.bind_tools(mode, full_tools, temperature=temp)
                                if full_tools else self.model_manager.client(mode, temp))
            else:
                # exhausted max_steps without a final answer
                final = ("I ran out of steps before finishing. Here's where I "
                         "got to — ask me to continue if you want me to keep going.")
                yield ("token", final)

            # Collab error recovery: append failure summary
            if mode == "collab" and failed_steps:
                fail_summary = "\n\n**Issues encountered:**\n" + "\n".join(f"- {f}" for f in failed_steps)
                final = (final or "") + fail_summary
                yield ("token", fail_summary)

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


