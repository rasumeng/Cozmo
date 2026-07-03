# DEPRECATED: Use cozmo.core.runtime.CozmoRuntime instead.
# This file is kept for backward compatibility only.

import json
from pathlib import Path
from .base_agent import BaseAgent, parse_tool_call, build_tool_schema, exec_tool_call
from ..code_indexer import ProjectIndex
from ..tools import TOOL_REGISTRY
from .permissions import PermissionResolver

CODE_SYSTEM_PROMPT = (
    "You are Cozmo, an expert programmer working in a codebase. "
    "Write clean, correct code. Be concise.\n\n"
    "To use a tool, respond with:\n"
    '<tool>{"tool": "tool_name", "args": {"arg1": "val"}}</tool>\n\n'
    "Example: <tool>{\"tool\": \"grep_search\", \"args\": {\"pattern\": \"def foo\"}}</tool>\n\n"
    "After the tool result comes back, continue naturally."
)


class CodeAgent(BaseAgent):
    def __init__(
        self,
        model_name: str,
        cwd: str | Path = ".",
        cfg: dict | None = None,
        agent_config: dict | None = None,
        base_url: str = "http://localhost:11434",
        auto: bool = False,
    ):
        super().__init__(model_name, base_url)
        self.cwd = Path(cwd).resolve()
        self.cfg = cfg or {}
        self.agent_config = agent_config or {}
        self.auto = auto or self.agent_config.get("auto", False)
        self.index = ProjectIndex(self.cwd)
        self.tools = TOOL_REGISTRY
        self.max_history = 30
        self._perms = PermissionResolver(self.cfg, auto=self.auto)

    @property
    def agent_name(self) -> str:
        return "build"

    def _build_system(self, project_context: str = "") -> str:
        schema = build_tool_schema(self.tools)
        ctx = f"\nProject files:\n{project_context}\n" if project_context else ""
        return (
            f"{CODE_SYSTEM_PROMPT}\n\n"
            f"Working directory: {self.cwd}\n{ctx}"
            f"Available tools:\n{schema}"
        )

    def _check_permission(self, tool_name: str, args: dict) -> bool:
        decision = self._perms.resolve(tool_name, args, self.agent_name)
        if decision == "allow":
            return True
        if decision == "deny":
            return False
        if decision == "ask":
            if self._permission_callback:
                return self._permission_callback(tool_name, args, self.agent_name)
            return self._perms.prompt(tool_name, args, self.agent_name)
        return False

    def _run_loop(self, user_input: str):
        """Core ReAct loop. Yields (kind, text) tuples."""
        context = self.index.query(user_input)
        system = self._build_system(context)

        history_str = "\n".join(f"{role}: {msg}" for role, msg in self.history[-10:])
        prompt = f"{history_str}\nuser: {user_input}" if history_str else user_input

        max_turns = 5
        response = ""
        for _ in range(max_turns):
            yield ("[thinking]", "Thinking...")
            response = ""
            for token in self.llm.stream(prompt, system_prompt=system):
                response += token
                yield ("[token]", token)

            call = parse_tool_call(response)
            if call is None:
                break

            tool_name = call.get("tool", "unknown")
            yield ("[thinking]", f"Using {tool_name}...")

            if not self._check_permission(tool_name, call.get("args", {})):
                result = f"Error: permission denied for {tool_name}"
            else:
                result = exec_tool_call(self.tools, call)

            prompt = (
                f"History:\n{prompt}\n\n"
                f"You used {json.dumps(call)} "
                f"and got:\n{result}\n\n"
                f"Answer the user. Do NOT repeat the <tool> block."
            )

        self.history.append(("user", user_input))
        self.history.append(("assistant", response))
        self._trim_history()
        self.compact()

    def run_stream(self, user_input: str):
        yield from self._run_loop(user_input)

    def run(self, user_input: str) -> str:
        chunks = []
        for kind, text in self._run_loop(user_input):
            if kind == "[token]":
                chunks.append(text)
        return "".join(chunks)
