# DEPRECATED: Use cozmo.core.runtime.CozmoRuntime instead.
# This file is kept for backward compatibility only.

import subprocess
from pathlib import Path
from .base_agent import BaseAgent, parse_tool_call, build_tool_schema, exec_tool_call
from .permissions import PermissionResolver
from ..tools import TOOL_REGISTRY

COLLAB_SYSTEM_PROMPT = (
    "You are Cozmo, a collaborative developer working alongside the user. "
    "You can read, edit, and create files, run commands, and search the web.\n\n"
    "Before making changes:\n"
    "1. Observe the current state (read relevant files, check git status)\n"
    "2. Propose a clear plan\n"
    "3. Execute tools with user permission\n"
    "4. Reflect on results\n\n"
    "Always show your plan before acting on files. Be concise. "
    "After each tool use, report what changed."
)

TOOL_USE_PROMPT = (
    "To use a tool, respond with:\n"
    '<tool>{"tool": "tool_name", "args": {"arg1": "value"}}</tool>\n\n'
    "After the tool result comes back, reflect and continue. "
    "Do NOT repeat the <tool> block."
)


class CollabAgent(BaseAgent):
    """Collaborative agent. Observe-Plan-Act-Reflect with human-in-loop."""

    def __init__(
        self,
        model_name: str,
        project_path: str | Path = ".",
        cfg: dict | None = None,
        base_url: str = "http://localhost:11434",
    ):
        super().__init__(model_name, base_url)
        self.project_path = Path(project_path).resolve()
        self.cfg = cfg or {}
        self.tools = TOOL_REGISTRY
        self.max_history = 30
        self._perms = PermissionResolver(self.cfg)

    def _build_system(self) -> str:
        schema = build_tool_schema(self.tools)
        return (
            f"{COLLAB_SYSTEM_PROMPT}\n\n"
            f"Working directory: {self.project_path}\n\n"
            f"Available tools:\n{schema}\n\n"
            f"{TOOL_USE_PROMPT}"
        )

    def _observe(self) -> str:
        """Gather project context."""
        context_parts = []
        try:
            entries = list(self.project_path.iterdir())[:20]
            names = [e.name + ("/" if e.is_dir() else "") for e in entries]
            context_parts.append(f"Project files: {', '.join(names)}")
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.project_path,
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                context_parts.append(f"Git status:\n{result.stdout.strip()}")
        except Exception:
            pass
        return "\n".join(context_parts) if context_parts else ""

    def _check_permission(self, tool_name: str, args: dict) -> bool:
        decision = self._perms.resolve(tool_name, args, "collab")
        if decision == "allow":
            return True
        if decision == "deny":
            return False
        if decision == "ask":
            if self._permission_callback:
                return self._permission_callback(tool_name, args, "collab")
            return self._perms.prompt(tool_name, args, "collab")
        return False

    def run_stream(self, prompt: str):
        """Yield tokens during Observe-Plan-Act-Reflect loop."""
        system = self._build_system()
        context = self._observe()

        history_str = "\n".join(f"{r}: {m}" for r, m in self.history[-10:])
        full_prompt = f"{context}\n\n{history_str}\n\nuser: {prompt}" if history_str else f"{context}\n\nuser: {prompt}"

        max_turns = 7
        response = ""
        for turn in range(max_turns):
            yield ("[thinking]", "Thinking...")
            response = ""
            for token in self.llm.stream(full_prompt, system_prompt=system):
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

            full_prompt = (
                f"Conversation:\n{full_prompt}\n\n"
                f"Tool result ({tool_name}): {result}\n\n"
                f"Reflect on this result and continue or answer the user."
            )

        self.history.append(("user", prompt))
        self.history.append(("assistant", response))
        self._trim_history()
        self.compact()
