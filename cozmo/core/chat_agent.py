# DEPRECATED: Use cozmo.core.runtime.CozmoRuntime instead.
# This file is kept for backward compatibility only.

from .base_agent import BaseAgent, parse_tool_call, build_tool_schema, exec_tool_call
from ..tools import TOOL_REGISTRY

CHAT_TOOLS = {
    name: TOOL_REGISTRY[name]
    for name in ("calculator", "web_search", "web_fetch", "web_search_pipeline")
    if name in TOOL_REGISTRY
}

CHAT_SYSTEM_PROMPT = (
    "You are Cozmo, a helpful AI assistant. Be concise and direct.\n\n"
    "RULES:\n"
    "1. Use web_search_pipeline for current events, news, sports, weather, prices, dates, schedules\n"
    "2. web_search_pipeline automatically rewrites queries, searches multiple sources, and synthesizes answers\n"
    "3. Give confident, clean answers without disclaimers\n"
    "4. Do NOT say 'as of my last update' or 'please note' or similar hedging\n"
    "5. Do NOT show tool calls in your response - use them silently\n"
    "6. Answer directly based on search results\n"
)

TOOL_USE_PROMPT = (
    "To use a tool, respond with:\n"
    '<tool>{"tool": "web_search_pipeline", "args": {"query": "search terms"}}</tool>\n\n'
    "After the tool result comes back, give a clean, confident answer. "
    "Do NOT repeat the <tool> block. Do NOT add disclaimers."
)


class ChatAgent(BaseAgent):
    """Smart chat agent. Minimal tools, history, streaming."""

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        super().__init__(model_name, base_url)
        self.tools = CHAT_TOOLS
        self.max_history = 20

    def _build_system(self) -> str:
        schema = build_tool_schema(self.tools)
        return (
            f"{CHAT_SYSTEM_PROMPT}\n\n"
            f"Available tools:\n{schema}\n\n"
            f"{TOOL_USE_PROMPT}"
        )

    def run_stream(self, prompt: str):
        """Yield tokens during chat. Simple ReAct: think → respond, tools optional."""
        system = self._build_system()

        history_str = "\n".join(f"{r}: {m}" for r, m in self.history[-10:])
        full_prompt = f"{history_str}\n\nuser: {prompt}" if history_str else f"user: {prompt}"

        max_turns = 3
        response = ""
        for turn in range(max_turns):
            response = ""
            in_tool_block = False
            for token in self.llm.stream(full_prompt, system_prompt=system):
                response += token
                if "<tool>" in token or "<web_search>" in token or "<web_fetch>" in token:
                    in_tool_block = True
                if '"tool":' in token or '"tool" :' in token:
                    in_tool_block = True
                if not in_tool_block:
                    yield ("[token]", token)
                if "</tool>" in token or "</web_search>" in token or "</web_fetch>" in token:
                    in_tool_block = False

            call = parse_tool_call(response)
            if call is None:
                break

            tool_name = call.get("tool", "tool")
            yield ("[thinking]", "Searching...")
            result = exec_tool_call(self.tools, call)

            full_prompt = (
                f"Conversation:\n{full_prompt}\n\n"
                f"Tool result ({tool_name}): {result}\n\n"
                f"Now answer the user based on these results. "
                f"Give a clean, confident answer. No disclaimers."
            )

        self.history.append(("user", prompt))
        self.history.append(("assistant", response))
        self._trim_history()
        self.compact()
