from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage


class StatelessLLM:
    """Simple one-shot generate() wrapper. No history, no memory. Used by ToolRouter + Planner."""

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url

    def generate(self, prompt: str, system_prompt: str | None = None, structured: bool = False) -> str:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatOllama(model=self.model_name, base_url=self.base_url, temperature=0,
                         format="json" if structured else None)
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return llm.invoke(messages).content


class OllamaModel:
    """Wraps a single Ollama model. Lazy init on first invoke.

    Holds two underlying ChatOllama instances keyed by temperature so the
    same model can serve deterministic tool/code work (temp 0) and warmer
    chat (temp > 0) without re-instantiating on every call.
    """

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self._clients: dict[float, ChatOllama] = {}

    def client(self, temperature: float = 0.0) -> ChatOllama:
        """Get (or lazily build) the ChatOllama client for a temperature."""
        key = round(float(temperature), 2)
        if key not in self._clients:
            self._clients[key] = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=key,
            )
        return self._clients[key]

    def bind_tools(self, tools: list, temperature: float = 0.0):
        """Return a runnable with native Ollama tool calling bound.

        `tools` may be langchain tools, plain functions, or OpenAI tool dicts.
        The returned runnable emits `.tool_calls` on the AIMessage when the
        model decides to call a tool.
        """
        return self.client(temperature).bind_tools(tools)

    # ── message-based API (preferred for agent loops) ─────────────────────

    def invoke_messages(self, messages: list, temperature: float = 0.0):
        """Invoke with a full message list. Returns the raw AIMessage."""
        return self.client(temperature).invoke(messages)

    def stream_messages(self, messages: list, temperature: float = 0.0):
        """Stream chunks for a full message list. Yields AIMessageChunk."""
        yield from self.client(temperature).stream(messages)

    # ── legacy string API (memory summaries, classifier, titles) ──────────

    def invoke(self, prompt: str, system_prompt: str | None = None,
               temperature: float = 0.0) -> str:
        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            return self.client(temperature).invoke(messages).content
        except Exception as e:
            return f"Error: model unavailable — {e}"

    def stream(self, prompt: str, system_prompt: str | None = None,
               temperature: float = 0.0):
        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            for chunk in self.client(temperature).stream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"Error: model unavailable — {e}"

    def swap_model(self, model_name: str):
        """Swap to a different model. Drops all cached clients."""
        self.model_name = model_name
        self._clients = {}

    @property
    def name(self) -> str:
        return self.model_name
