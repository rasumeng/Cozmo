import re
import json
from .llm import OllamaModel
from ..tools import TOOL_REGISTRY

SPECIALIST_PROMPTS = {
    "chat": "You are Cozmo, a friendly AI assistant. Be concise and helpful.",
    "coder": "You are Cozmo, an expert programmer. Write clean, working code with brief explanations.",
    "vision": "You are Cozmo, an AI that analyzes images and screenshots. Describe what you see clearly.",
    "research": "You are Cozmo, a research analyst. Provide thorough, well-structured answers with sources.",
}

class Agent:
    def __init__(self, model_name: str, task_type: str = "chat", base_url: str = "http://localhost:11434"):
        self.llm = OllamaModel(model_name, base_url)
        self.tools = TOOL_REGISTRY
        self.system_prompt = SPECIALIST_PROMPTS.get(task_type, SPECIALIST_PROMPTS["chat"])

    def _tool_help(self) -> str:
        lines = []
        for name, fn in self.tools.items():
            sig = f"{name}({', '.join(fn.__code__.co_varnames[:fn.__code__.co_argcount])})"
            doc = (fn.__doc__ or "no description").split(".")[0]
            lines.append(f"- {sig}: {doc}")
        return "\n".join(lines)

    def _run_tool(self, text: str) -> tuple[str, str | None]:
        match = re.search(r"<tool>(.*?)</tool>", text, re.DOTALL)
        if not match:
            return text, None
        try:
            call = json.loads(match.group(1))
            name = call["tool"]
            args = call.get("args", {})
        except (json.JSONDecodeError, KeyError):
            return text, "Error: malformed tool JSON"
        fn = self.tools.get(name)
        if fn is None:
            return text, f"Error: unknown tool '{name}'"
        try:
            result = fn(**args)
        except Exception as e:
            result = f"Error: {e}"
        return text, str(result)

    def run(self, prompt: str) -> str:
        tool_help = self._tool_help()
        schema_lines = []
        for name, fn in self.tools.items():
            params = fn.__code__.co_varnames[:fn.__code__.co_argcount]
            doc = (fn.__doc__ or "no description").split(".")[0]
            args_part = ", ".join('"' + p + '": "str"' for p in params)
            schema_lines.append('  "{}": {{"args": {{{}}}, "desc": "{}"}}'.format(name, args_part, doc))
        schemas = ",\n".join(schema_lines)

        system = (
            f"{self.system_prompt}\n\n"
            f"Available tools:\n{schemas}\n\n"
            "To use a tool, respond with:\n"
            "<tool>{\"tool\": \"tool_name\", \"args\": {\"arg1\": \"value1\", \"arg2\": \"value2\"}}</tool>\n\n"
            "Example: <tool>{\"tool\": \"calculator\", \"args\": {\"expression\": \"245 * 18 / 5\"}}</tool>\n\n"
            "After the tool result comes back, answer the user naturally."
        )

        response = self.llm.invoke(prompt, system_prompt=system)
        cleaned, tool_result = self._run_tool(response)
        if tool_result is None:
            return cleaned

        followup = (
            f"Original conversation so far:\n{prompt}\n\n"
            f"You used a tool and got this result:\n{tool_result}\n\n"
            f"Now answer based on this result. Do NOT repeat the <tool> block."
        )
        final = self.llm.invoke(followup, system_prompt=system)
        return final