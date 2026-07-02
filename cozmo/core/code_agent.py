from pathlib import Path
from .agent import Agent
from ..code_indexer import ProjectIndex
from ..tools import TOOL_REGISTRY, code_ops
from .permissions import PermissionResolver
import json
import re

class CodeAgent(Agent):
    def __init__(self, model_name: str, cwd: str | Path, cfg: dict, agent_config: dict | None = None, base_url: str = "http://localhost:11434", auto: bool = False):
        super().__init__(model_name, task_type="coder", base_url=base_url)
        self.cwd = Path(cwd).resolve()
        self.cfg = cfg
        self.agent_config = agent_config or {}
        self.auto = auto or self.agent_config.get("auto", False)
        self.index = ProjectIndex(self.cwd)
        self.history: list[tuple[str, str]] = []
        self._perms = PermissionResolver(cfg, auto=self.auto)

    def _build_code_system(self, project_context: str) -> str:
        schema_lines = []
        for name, fn in self.tools.items():
            params = fn.__code__.co_varnames[:fn.__code__.co_argcount]
            doc = (fn.__doc__ or "no description").split(".")[0]
            args_part = ", ".join('"' + p + '": "str"' for p in params)
            schema_lines.append('  "{}": {{"args": {{{}}}, "desc": "{}"}}'.format(name, args_part, doc))
        schemas = ",\n".join(schema_lines)

        ctx = f"\nProject files:\n{project_context}\n" if project_context else ""

        return (
            "You are Cozmo, an expert programmer working in a codebase. "
            "Write clean, correct code. Be concise.\n\n"
            f"Working directory: {self.cwd}\n{ctx}"
            f"Available tools:\n{schemas}\n\n"
            "To use a tool, respond with:\n"
            '<tool>{"tool": "tool_name", "args": {"arg1": "val"}}</tool>\n\n'
            "Example: <tool>{\"tool\": \"grep_search\", \"args\": {\"pattern\": \"def foo\"}}</tool>\n\n"
            "After the tool result comes back, continue naturally."
        )
    
    @property
    def agent_name(self) -> str:
        return "build"

    def _exec_tool_call(self, text: str) -> str | None:
        match = re.search(r"<tool>(.*?)</tool>", text, re.DOTALL)
        if not match:
            return None
        try:
            call = json.loads(match.group(1))
            name = call["tool"]
            args = call.get("args", {})
        except (json.JSONDecodeError, KeyError):
            return "Error: malformed tool JSON"
        fn = TOOL_REGISTRY.get(name)
        if fn is None:
            return f"Error: unknown tool '{name}'"

        # Permission check
        decision = self._perms.resolve(name, args, self.agent_name)
        if decision == "deny":
            return f"Error: permission denied — {name} not allowed for {self.agent_name}"
        if decision == "ask":
            allowed = self._perms.prompt(name, args, self.agent_name)
            if not allowed:
                return f"Error: permission denied — {name} rejected by user"

        try:
            return str(fn(**args))
        except Exception as e:
            return f"Error: {e}"

    def run(self, user_input: str) -> str:
        context = self.index.query(user_input)
        system = self._build_code_system(context)

        history_str = "\n".join(
            f"{role}: {msg}" for role, msg in self.history[-6:]
        )
        prompt = f"{history_str}\nuser: {user_input}" if history_str else user_input

        final = ""
        max_turns = 5
        for _ in range(max_turns):
            response = self.llm.invoke(prompt, system_prompt=system)
            tool_result = self._exec_tool_call(response)

            if tool_result is None:
                final = response
                break

            prompt = (
                f"History:\n{prompt}\n\n"
                f"You used {json.dumps(self._parse_tool_call(response))} "
                f"and got:\n{tool_result}\n\n"
                f"Answer the user. Do NOT repeat the <tool> block."
            )
        else:
            final = "Error: tool call limit reached"

        cleaned = re.sub(r"<tool>.*?</tool>", "", final, flags=re.DOTALL).strip()

        self.history.append(("user", user_input))
        self.history.append(("assistant", cleaned))
        return final

    def compact(self):
        """Summarize history into a single context message."""
        if not self.history:
            return
        text = "\n".join(f"{r}: {m}" for r, m in self.history)
        summary = self.llm.invoke(
            "Summarize the conversation above in 3-4 sentences. "
            "Capture: what was asked, what was done, what files changed.",
            system_prompt=f"Conversation:\n{text}",
        )
        self.history.clear()
        self.history.append(("system", f"[compacted context]\n{summary}"))

    def _parse_tool_call(self, text: str) -> dict | None:
        match = re.search(r"<tool>(.*?)</tool>", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
        return None
