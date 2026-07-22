"""LLM wrappers.

OllamaModel — backwards-compatible wrapper around LLMProvider (used everywhere).
StatelessLLM — one-shot generate for Planner + Router.
"""

from .providers.llm import OllamaProvider


class StatelessLLM:
    """Simple one-shot generate() wrapper. No history, no memory. Used by Planner + Router."""

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        self._provider = OllamaProvider(model_name, {"url": base_url})

    def generate(self, prompt: str, system_prompt: str | None = None, structured: bool = False) -> str:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatOllama(model=self._provider.model_name, base_url=self._provider.base_url, temperature=0,
                         format="json" if structured else None, reasoning=True)
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return llm.invoke(messages).content


class OllamaModel:
    """Wraps a single Ollama model via OllamaProvider.

    Holds per-temperature ChatModel cache for tool/code (temp 0) vs chat (temp > 0).
    Backward-compatible API — all existing callers unchanged.
    """

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self._provider = OllamaProvider(model_name, {"url": base_url})

    def client(self, temperature: float = 0.0):
        """Get (or lazily build) the ChatOllama client for a temperature."""
        return self._provider.get_chat_model(temperature)

    def bind_tools(self, tools: list, temperature: float = 0.0):
        """Return a runnable with native Ollama tool calling bound."""
        return self._provider.bind_tools(tools, temperature)

    def invoke_messages(self, messages: list, temperature: float = 0.0):
        """Invoke with a full message list. Returns the raw AIMessage."""
        return self._provider.invoke_messages(messages, temperature)

    def stream_messages(self, messages: list, temperature: float = 0.0):
        """Stream chunks for a full message list. Yields AIMessageChunk."""
        yield from self._provider.stream_messages(messages, temperature)

    def invoke(self, prompt: str, system_prompt: str | None = None,
               temperature: float = 0.0) -> str:
        return self._provider.invoke(prompt, system_prompt, temperature)

    def stream(self, prompt: str, system_prompt: str | None = None,
               temperature: float = 0.0):
        yield from self._provider.stream(prompt, system_prompt, temperature)
