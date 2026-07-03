"""
CozmoRuntime — single execution pipeline replacing all legacy agents.

Pipeline:
  USER INPUT
  → CONTEXT BUILDER (memory + history + project)
  → CLASSIFY + TOOL GATE (single LLM call)
  → EXECUTE TOOLS (sanitized, capped)
  → GENERATE RESPONSE (draft)
  → COMPILE (strip artifacts, normalize)
  → FINAL OUTPUT
"""

import json
import re
from pathlib import Path

from .llm import OllamaModel
from ..tools import TOOL_REGISTRY


# ── Prompts ──────────────────────────────────────────────────────────────────

_CLASSIFY_AND_GATE_PROMPT = """You are a routing engine. Analyze the user request and return a JSON object.

Classify the intent into exactly one mode:
- CHAT: greetings, conversation, explanations, definitions, general Q&A about KNOWN facts (e.g. "what is Python", "explain recursion")
- WORK: coding, file editing, debugging, running commands, writing code, system tasks
- RESEARCH: ANYTHING that needs current/real-time/external information, including:
  * Current events, news, sports scores, schedules, standings
  * Weather, prices, stock values, exchange rates
  * Recent releases, updates, announcements
  * Anything where the answer changes over time
  * Questions about "today", "this week", "latest", "next", "upcoming"
  * Anything you are NOT 100% certain about from training data

When in doubt, classify as RESEARCH.

Then decide if tools are needed. Available tools:
- web_search: search the web for current information
- web_search_pipeline: advanced multi-source search with synthesis
- web_fetch: fetch content from a URL
- calculator: math calculations
- read_file: read file contents
- write_file: create or overwrite a file
- edit_file: edit an existing file
- run_command: execute a shell command
- grep_search: regex search across files
- list_directory: list files in a directory
- git_diff: show git diff
- git_log: show recent git commits

Rules:
- CHAT mode: tools are NOT needed.
- WORK mode: tools are usually needed.
- RESEARCH mode: ALWAYS use web_search_pipeline for current/recent information.
- Return a maximum of 3 tool calls.
- Always provide a short reason.

Return ONLY valid JSON, no other text:
{
  "mode": "CHAT|WORK|RESEARCH",
  "use_tools": true/false,
  "tools": [{"name": "tool_name", "args": {"key": "value"}}],
  "reason": "one sentence"
}"""

_GENERATE_PROMPT = """You are Cozmo, a helpful AI assistant.

Mode: {mode}
{mode_instructions}

Previous conversation:
{history}

Relevant memories:
{memory}

Project context:
{project}

User request: {user_input}

Tool results:
{tool_results}

Instructions:
- Answer directly and confidently
- Do NOT use hedging phrases like "as of my last update" or "please note"
- Do NOT include tool call XML in your response
- Be concise unless the user asks for detail
- If tool results contain the answer, use them directly
- If no tools were used, answer from your knowledge"""

_MODE_INSTRUCTIONS = {
    "CHAT": "Be concise and conversational. Friendly but direct.",
    "WORK": "Be precise and technical. Show code when relevant. Explain changes briefly.",
    "RESEARCH": "Be thorough and cite sources from tool results. Be factual and direct.",
}

_COMPILE_STRIP_PATTERNS = [
    re.compile(r"<tool>.*?</tool>", re.DOTALL),
    re.compile(r"</?tool>", re.DOTALL),
    re.compile(r"<tool[^>]*>", re.DOTALL),
    re.compile(r"<web_search>.*?</web_search>", re.DOTALL),
    re.compile(r"<web_fetch>.*?</web_fetch>", re.DOTALL),
    re.compile(r"</?(?:web_search|web_fetch)>", re.DOTALL),
]


# ── Runtime ──────────────────────────────────────────────────────────────────

class CozmoRuntime:
    """Single runtime loop. Replaces all legacy agents."""

    def __init__(
        self,
        llm: OllamaModel,
        memory=None,
        tools: dict | None = None,
        project_index=None,
        cfg: dict | None = None,
    ):
        self.llm = llm
        self.memory = memory
        self.tools = tools or TOOL_REGISTRY
        self.project_index = project_index
        self.cfg = cfg or {}
        self.history: list[tuple[str, str]] = []

        rt_cfg = self.cfg.get("runtime", {})
        self.max_history = rt_cfg.get("max_history", 10)
        self.max_tool_calls = rt_cfg.get("max_tool_calls", 3)
        self.max_tool_output = rt_cfg.get("max_tool_output_chars", 8000)
        self.memory_distance_threshold = rt_cfg.get("memory_distance_threshold", 0.5)
        self.max_memory_results = rt_cfg.get("max_memory_results", 3)
        self.max_project_results = rt_cfg.get("max_project_results", 3)

    # ── Context Builder ──────────────────────────────────────────────────

    def build_context(self, user_input: str) -> dict:
        return {
            "history": self._trim_history(),
            "memory": self._query_memory(user_input),
            "project": self._query_project(user_input),
        }

    def _trim_history(self) -> str:
        if not self.history:
            return "(no previous conversation)"
        recent = self.history[-self.max_history:]
        lines = [f"User: {u}\nCozmo: {a}" for u, a in recent]
        return "\n".join(lines)

    def _query_memory(self, user_input: str) -> str:
        if not self.memory:
            return "(no memories)"
        try:
            results = self.memory.query(user_input, k=self.max_memory_results * 2)
            if not results:
                return "(no memories)"

            filtered = []
            for r in results:
                dist = r.get("distance", 0)
                if dist < self.memory_distance_threshold:
                    filtered.append(r)
            filtered = filtered[:self.max_memory_results]

            if not filtered:
                return "(no relevant memories)"
            return "\n".join(f"- {r['text']}" for r in filtered)
        except Exception:
            return "(memory unavailable)"

    def _query_project(self, user_input: str) -> str:
        if not self.project_index:
            return "(no project context)"
        try:
            raw = self.project_index.query(user_input, k=self.max_project_results)
            if not raw:
                return "(no project context)"
            return raw
        except Exception:
            return "(project context unavailable)"

    # ── Classify + Tool Gate (single LLM call) ───────────────────────────

    def classify_and_gate(self, user_input: str, context: dict) -> dict:
        prompt = (
            f"Conversation so far:\n{context['history']}\n\n"
            f"User request: {user_input}"
        )
        raw = self.llm.invoke(prompt, system_prompt=_CLASSIFY_AND_GATE_PROMPT)
        return self._parse_gate(raw)

    def _parse_gate(self, raw: str) -> dict:
        if not raw:
            return self._default_gate("CHAT")
        raw = raw.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return self._default_gate("CHAT")
        try:
            gate = json.loads(match.group())
            mode = gate.get("mode", "CHAT")
            if mode not in ("CHAT", "WORK", "RESEARCH"):
                mode = "CHAT"
            tools = gate.get("tools", [])
            if not isinstance(tools, list):
                tools = []
            tools = tools[:self.max_tool_calls]
            return {
                "mode": mode,
                "use_tools": gate.get("use_tools", False) and len(tools) > 0,
                "tools": tools,
                "reason": gate.get("reason", ""),
            }
        except json.JSONDecodeError:
            return self._default_gate("CHAT")

    def _default_gate(self, mode: str) -> dict:
        return {"mode": mode, "use_tools": False, "tools": [], "reason": "parse fallback"}

    # ── Tool Execution ───────────────────────────────────────────────────

    def execute_tools(self, gate: dict) -> list[dict]:
        if not gate.get("use_tools"):
            return []
        tool_calls = gate.get("tools", [])[:self.max_tool_calls]
        results = []
        for call in tool_calls:
            name = call.get("name", "")
            args = call.get("args", {})
            fn = self.tools.get(name)
            if fn is None:
                results.append({"tool": name, "output": f"Error: unknown tool '{name}'", "args": args})
                continue
            try:
                raw_output = str(fn(**args))
            except Exception as e:
                raw_output = f"Error: {e}"
            sanitized = self._sanitize_output(raw_output)
            results.append({"tool": name, "output": sanitized, "args": args})
        return results

    def _sanitize_output(self, text: str) -> str:
        if len(text) > self.max_tool_output:
            head = self.max_tool_output // 3
            tail = self.max_tool_output - head
            text = text[:head] + f"\n... [{len(text) - self.max_tool_output} chars truncated] ...\n" + text[-tail:]
        for pattern in _COMPILE_STRIP_PATTERNS:
            text = pattern.sub("", text)
        return text

    # ── Response Generation ──────────────────────────────────────────────

    def generate(self, user_input: str, context: dict, tool_results: list[dict], mode: str) -> str:
        mode_instructions = _MODE_INSTRUCTIONS.get(mode, _MODE_INSTRUCTIONS["CHAT"])

        if tool_results:
            tool_text = "\n\n".join(
                f"[Tool: {r['tool']}]\n{r['output']}" for r in tool_results
            )
        else:
            tool_text = "(no tools used)"

        prompt = _GENERATE_PROMPT.format(
            mode=mode,
            mode_instructions=mode_instructions,
            history=context["history"],
            memory=context["memory"],
            project=context["project"],
            user_input=user_input,
            tool_results=tool_text,
        )
        return self.llm.invoke(prompt)

    # ── Response Compiler ────────────────────────────────────────────────

    def compile(self, draft: str, mode: str = "CHAT") -> str:
        text = draft
        for pattern in _COMPILE_STRIP_PATTERNS:
            text = pattern.sub("", text)
        text = re.sub(r"^(Cozmo:\s*)+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ── Main Pipeline ────────────────────────────────────────────────────

    def run(self, user_input: str) -> str:
        try:
            context = self.build_context(user_input)
            gate = self.classify_and_gate(user_input, context)
            tool_results = self.execute_tools(gate)
            draft = self.generate(user_input, context, tool_results, gate["mode"])
            final = self.compile(draft, gate["mode"])
            self.history.append((user_input, final))
            self._trim_history_inplace()
            return final
        except Exception as e:
            return self.compile(f"I hit an error: {e}")

    # ── Hybrid Streaming ─────────────────────────────────────────────────

    def run_stream(self, user_input: str):
        """Yield (kind, text) tuples. kind is 'token', 'thinking', or 'status'."""
        try:
            context = self.build_context(user_input)
            yield ("status", "Classifying...")

            gate = self.classify_and_gate(user_input, context)
            mode = gate["mode"]
            yield ("thinking", f"Mode: {mode}")

            tool_results = []
            if gate.get("use_tools"):
                tool_names = [t.get("name", "?") for t in gate.get("tools", [])]
                yield ("thinking", f"Tools: {', '.join(tool_names)}")
                tool_results = self.execute_tools(gate)
                yield ("thinking", "Generating response...")

            mode_instructions = _MODE_INSTRUCTIONS.get(mode, _MODE_INSTRUCTIONS["CHAT"])
            if tool_results:
                tool_text = "\n\n".join(
                    f"[Tool: {r['tool']}]\n{r['output']}" for r in tool_results
                )
            else:
                tool_text = "(no tools used)"

            prompt = _GENERATE_PROMPT.format(
                mode=mode,
                mode_instructions=mode_instructions,
                history=context["history"],
                memory=context["memory"],
                project=context["project"],
                user_input=user_input,
                tool_results=tool_text,
            )

            buffer = ""
            in_tool_block = False
            full_response = ""

            for token in self.llm.stream(prompt):
                buffer += token
                full_response += token

                if not in_tool_block:
                    if "<tool>" in buffer or "<web_search>" in buffer or "<web_fetch>" in buffer:
                        in_tool_block = True
                        continue
                    yield ("token", token)
                else:
                    if "</tool>" in buffer or "</web_search>" in buffer or "</web_fetch>" in buffer:
                        in_tool_block = False
                        buffer = ""
                        continue

            final = self.compile(full_response, mode)
            self.history.append((user_input, final))
            self._trim_history_inplace()

            if final != full_response.strip():
                yield ("token", final[len(full_response.strip()):])

        except Exception as e:
            yield ("token", self.compile(f"I hit an error: {e}"))

    def _trim_history_inplace(self):
        while len(self.history) > self.max_history:
            self.history.pop(0)

    def swap_model(self, model_name: str):
        """Swap the LLM to a different model."""
        self.llm.swap_model(model_name)
