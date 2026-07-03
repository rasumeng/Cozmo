import inspect
import json
import re
from .llm import OllamaModel
from ..tools import TOOL_REGISTRY


def parse_tool_call(text: str) -> dict | None:
    """Parse <tool>{"tool": "...", "args": {...}}</tool> from model output."""
    match = re.search(r"<tool>(.*?)</tool>", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    match = re.search(r"<(web_search|web_fetch)>(.*?)</\1>", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(2))
        except json.JSONDecodeError:
            return None
    return None


def build_tool_schema(tools: dict) -> str:
    """Generate tool schema for system prompt using inspect."""
    schema_lines = []
    for name, fn in tools.items():
        try:
            sig = inspect.signature(fn)
            params = {}
            for pname, param in sig.parameters.items():
                annotation = param.annotation
                if annotation is inspect.Parameter.empty:
                    params[pname] = "str"
                else:
                    params[pname] = str(annotation.__name__) if hasattr(annotation, '__name__') else str(annotation)
            doc = (fn.__doc__ or "no description").split("\n")[0].strip()
            args_json = ", ".join(f'"{k}": "{v}"' for k, v in params.items())
            schema_lines.append(f'  "{name}": {{"args": {{{args_json}}}, "desc": "{doc}"}}')
        except (ValueError, TypeError):
            doc = (fn.__doc__ or "no description").split("\n")[0].strip()
            schema_lines.append(f'  "{name}": {{"args": {{}}, "desc": "{doc}"}}')
    return ",\n".join(schema_lines)


def exec_tool_call(tools: dict, call: dict) -> str:
    """Execute a tool call dict. Returns result string."""
    name = call.get("tool", "")
    args = call.get("args", {})
    fn = tools.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"
    try:
        return str(fn(**args))
    except Exception as e:
        return f"Error: {e}"


class BaseAgent:
    """Shared agent logic. Subclasses set tools, system prompt, and loop."""

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        self.llm = OllamaModel(model_name, base_url)
        self.tools: dict = {}
        self.history: list[tuple[str, str]] = []
        self.max_history: int = 20
        self._permission_callback = None

    def set_permission_callback(self, callback):
        """Set callback for permission requests. callback(tool, args, agent) -> bool"""
        self._permission_callback = callback

    def _build_system(self) -> str:
        """Override in subclass to set system prompt + tool schema."""
        raise NotImplementedError

    def _check_permission(self, tool_name: str, args: dict) -> bool:
        """Override in subclass for permission checks. Default: allow."""
        return True

    def _on_thinking(self, text: str):
        """Called when agent status changes. Override or set callback."""
        pass

    def run_stream(self, prompt: str):
        """Override in subclass. Yield (kind, text) tuples."""
        raise NotImplementedError

    def run(self, prompt: str) -> str:
        """Synchronous run. Returns final response."""
        chunks = []
        for kind, text in self.run_stream(prompt):
            if kind == "[token]":
                chunks.append(text)
        return "".join(chunks)

    def compact(self):
        """Summarize history into a single context message."""
        if len(self.history) < 6:
            return
        text = "\n".join(f"{r}: {m}" for r, m in self.history[-20:])
        summary = self.llm.invoke(
            "Summarize the conversation above in 3-4 sentences. "
            "Capture: what was asked, what was done, key decisions.",
            system_prompt=f"Conversation:\n{text}",
        )
        self.history.clear()
        self.history.append(("system", f"[compacted context]\n{summary}"))

    def _trim_history(self):
        """Keep history within max_history limit."""
        while len(self.history) > self.max_history:
            self.history.pop(0)
