import re
from .llm import OllamaModel
from ..tools import TOOL_REGISTRY


class Agent:
    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        self.llm = OllamaModel(model_name, base_url)
        self.tools = TOOL_REGISTRY

    def _tool_help(self) -> str:
        lines = []
        for name, fn in self.tools.items():
            sig = f"{name}({', '.join(fn.__code__.co_varnames[:fn.__code__.co_argcount])})"
            lines.append(f"- {sig}: {fn.__doc__ or 'no description'}")
        return "\n".join(lines)

    def _run_tool(self, text: str) -> tuple[str, str | None]:
        match = re.search(r"TOOLS?:\s*(\w+)\(([^)]*)\)", text)
        if not match:
            return text, None
        name, args_str = match.group(1), match.group(2)
        fn = self.tools.get(name)
        if fn is None:
            return text, f"Error: unknown tool '{name}'"
        args = {}
        if args_str.strip():
            for pair in args_str.split(","):
                if "=" not in pair:
                    continue
                k, v = pair.split("=", 1)
                args[k.strip()] = v.strip().strip("\"'")
        try:
            result = fn(**args)
        except Exception as e:
            result = f"Error: {e}"
        return text, str(result)

    def run(self, prompt: str) -> str:
        tool_help = self._tool_help()
        system = (
            "You are Cozmo, a helpful AI assistant with access to tools.\n"
            f"Available tools:\n{tool_help}\n\n"
            "To use a tool, respond with:\n"
            "TOOL: tool_name(arg=value, arg2=value)\n\n"
            "Example: TOOL: calculator(expression=\"245 * 18 / 5\")\n\n"
            "After the tool result comes back, answer the user naturally."
        )

        response = self.llm.invoke(prompt, system_prompt=system)
        cleaned, tool_result = self._run_tool(response)
        if tool_result is None:
            return cleaned

        followup = (
            f"Original conversation so far:\n{prompt}\n\n"
            f"You used a tool and got this result:\n{tool_result}\n\n"
            f"Now answer based on this result. Do NOT repeat the TOOL line."
        )
        final = self.llm.invoke(followup, system_prompt=system)
        return final

    def interactive(self, initial_query: str | None = None):
        if initial_query:
            print(f"\nCozmo: {self.run(initial_query)}\n")
        while True:
            try:
                user = input("\nYou: ")
                if user.lower() in ("exit", "quit"):
                    break
                print(f"Cozmo: {self.run(user)}")
            except (EOFError, KeyboardInterrupt):
                break