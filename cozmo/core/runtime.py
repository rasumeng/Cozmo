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

import json
import re
from datetime import datetime

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import StructuredTool

from .llm import OllamaModel
from .model_manager import ModelManager
from .permissions import PermissionResolver
from ..tools import TOOL_REGISTRY


# ── Prompts ──────────────────────────────────────────────────────────────────

_IDENTITY = (
    "You are Cozmo, a capable local AI coding agent (like Claude Code) running "
    "entirely on-device via Ollama. You help with coding, file editing, "
    "debugging, running commands, research, and general questions.\n"
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
        "- Search results are provided below and via tools. Base your answer "
        "ONLY on those results, never on training data — your training data "
        "is stale for this question.\n"
        "- If the provided results don't contain the answer, call web_search "
        "or web_search_pipeline again with a better query. Do NOT answer from "
        "memory.\n"
        "- If results conflict, prefer the most recent and say so.\n"
        "- Cite where facts came from (source names/domains from the results).\n"
        "- If you genuinely cannot find the answer in any results, say exactly "
        "that — do not fabricate."
    ),
}

_ROUTE_PROMPT = """Classify the user's latest request as exactly one word:
- chat: greetings, small talk, definitions, general Q&A answerable from timeless knowledge
- work: coding, editing files, debugging, shell commands, anything touching the project
- research: needs current/external info (news, events, wars, sports, prices, weather, releases, schedules, "today", "latest", "recent", "next", "upcoming", game banners, character tiers, gacha pulls, who to pull, what to build)

Anything about current events or things that change over time is research, even if phrased vaguely.
When unsure between chat and research, pick research. When it touches code or files, pick work.

Examples:
- "who should I pull in wuthering waves" → research
- "latest genshin banners" → research
- "what's the best team for abyss" → research
- "edit main.py and fix the bug" → work
- "what is a monad" → chat

Recent conversation (for context on vague follow-ups):
{history}

Request: {text}
Answer with one word:"""

# Pre-pass keywords that short-circuit to research mode before LLM call.
# Catches patterns the small router model might miss.
_RESEARCH_KEYWORDS = [
    "who should", "pull", "banner", "tier list", "meta",
    "new character", "gacha", "game update", "latest news",
    "current events", "what's new", "what is the best",
    "weather", "price", "release", "upcoming", "schedule",
    "today", "this week", "this month",
]

_COMPACT_PROMPT = """Condense this conversation into a short context note (4-6 sentences max).
Keep: what the user is working on, key facts established, decisions made, user preferences.
Drop: greetings, pleasantries, resolved dead-ends.

{text}

Context note:"""

# text-fallback: models that don't emit native tool_calls sometimes emit JSON.
_TEXT_TOOLCALL_RE = re.compile(r"\{.*\}", re.DOTALL)

_SEARCH_TOOL_PREFERENCE = ("web_search_pipeline", "web_search")


# ── Runtime ──────────────────────────────────────────────────────────────────

class CozmoRuntime:
    """Single agentic runtime loop with native tool calling."""

    def __init__(
        self,
        model_manager: ModelManager,
        memory=None,
        tools: dict | None = None,
        project_index=None,
        cfg: dict | None = None,
        router_llm: OllamaModel | None = None,
    ):
        self.model_manager = model_manager
        self.router_llm = router_llm
        self.memory = memory
        self.tools = tools or TOOL_REGISTRY
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
        }

        # which tools each mode may call (None = all registered tools)
        self._tool_gate = rt.get("tool_gate", {
            "chat": [],
            "research": ["web_search", "web_search_pipeline", "web_fetch", "calculator"],
            "work": None,
        })

        self._perms = PermissionResolver(self.cfg)
        self._permission_callback = None  # UI hook: (tool, args) -> bool
        self._lc_tools = self._build_lc_tools()

    def set_permission_callback(self, callback):
        """callback(tool_name, args) -> bool. Set by the UI layer for 'ask' rules."""
        self._permission_callback = callback

    # ── langchain tool wrappers ──────────────────────────────────────────

    def _build_lc_tools(self) -> dict:
        """Wrap registry functions as StructuredTools (schema from signatures)."""
        wrapped = {}
        for name, fn in self.tools.items():
            try:
                doc = (fn.__doc__ or f"{name} tool").strip()
                wrapped[name] = StructuredTool.from_function(
                    func=fn, name=name, description=doc.split("\n")[0]
                )
            except Exception:
                continue
        return wrapped

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
                       grounding: str = "") -> str:
        parts = [_IDENTITY.format(date=datetime.now().strftime("%A, %B %d, %Y"))]
        parts.append(_MODE_DISCIPLINE.get(mode, _MODE_DISCIPLINE["chat"]))

        if self._summary:
            parts.append(f"\nContext from earlier in this session:\n{self._summary}")

        memory = self._query_memory(user_input)
        if memory:
            parts.append(f"\nRelevant memory from past sessions:\n{memory}")

        if mode == "work":
            project = self._query_project(user_input)
            if project:
                parts.append(f"\nRelevant project context:\n{project}")

        if grounding:
            parts.append(
                "\nSearch results for the user's question (use these as your "
                f"primary source):\n{grounding}"
            )

        return "\n\n".join(parts)

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
        for mode in ("work", "research", "chat"):
            if mode in raw:
                return mode
        return "research"

    # ── forced grounding search (research mode) ──────────────────────────

    def _grounding_search(self, user_input: str) -> str:
        """Deterministically run one search before the loop. Small models
        skip tools and hallucinate current events if given the choice."""
        for name in _SEARCH_TOOL_PREFERENCE:
            fn = self.tools.get(name)
            if fn is None:
                continue
            try:
                return self._sanitize(str(fn(query=user_input)))
            except Exception as e:
                return f"(search failed: {e})"
        return ""

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
        decision = self._perms.resolve(name, args, agent="cozmo")
        if decision == "allow":
            return True
        if decision == "deny":
            return False
        # 'ask' — defer to the UI layer; no UI hook means deny (fail safe)
        if self._permission_callback:
            return self._permission_callback(name, args)
        return False

    def _exec_tool(self, name: str, args: dict) -> str:
        fn = self.tools.get(name)
        if fn is None:
            known = ", ".join(sorted(self.tools))
            return f"Error: unknown tool '{name}'. Available tools: {known}"
        if not self._check_permission(name, args):
            return (f"Error: the user DENIED permission for {name}. Do not retry "
                    f"this call — explain what you wanted to do and ask the user.")
        try:
            raw = str(fn(**args))
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

    def run_stream(self, user_input: str):
        """Yield (kind, text) tuples. kind is 'token', 'thinking', or 'status'."""
        try:
            yield ("status", "Routing...")
            mode = self._route(user_input)
            yield ("thinking", f"Mode: {mode}")

            grounding = ""
            if mode == "research":
                yield ("thinking", "Searching...")
                grounding = self._grounding_search(user_input)

            temp = self.temps.get(mode, 0.0)
            lc_tools = self._tools_for_mode(mode)
            runnable = (self.model_manager.bind_tools(mode, lc_tools, temperature=temp)
                        if lc_tools else self.model_manager.client(mode, temp))

            msgs = [SystemMessage(content=self._system_prompt(user_input, mode, grounding))]
            msgs += self._history_messages()
            msgs.append(HumanMessage(content=user_input))

            final = ""
            seen_calls: set[str] = set()  # break identical-call loops
            for step in range(self.max_steps):
                acc = None
                content_buf = ""
                suppress = False
                streamed = False

                for chunk in runnable.stream(msgs):
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
                    final = content_buf.strip()
                    break

                # model wants tools: record the turn, run them, feed results back
                msgs.append(ai if isinstance(ai, AIMessage)
                            else AIMessage(content=content_buf))
                names = ", ".join(c["name"] for c in calls)
                yield ("thinking", f"Running: {names}")

                for c in calls:
                    sig = f"{c['name']}:{json.dumps(c['args'], sort_keys=True, default=str)}"
                    if sig in seen_calls:
                        out = (f"Error: you already made this exact {c['name']} call "
                               f"and have its result above. Use it, or try a "
                               f"DIFFERENT call — do not repeat yourself.")
                    else:
                        seen_calls.add(sig)
                        out = self._exec_tool(c["name"], c["args"])
                    msgs.append(ToolMessage(content=out, tool_call_id=c["id"]))
                yield ("thinking", "Thinking...")
            else:
                # exhausted max_steps without a final answer
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

    def run(self, user_input: str) -> str:
        """Synchronous run. Returns the final answer text."""
        chunks = []
        for kind, text in self.run_stream(user_input):
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
        except Exception:
            pass

    def reset(self):
        """Clear conversation state (new chat)."""
        self.history.clear()
        self._summary = ""


