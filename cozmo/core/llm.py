from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage


class OllamaModel:
    """Wraps a single Ollama model. Lazy init on first invoke."""

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self._llm = None

    def _ensure_llm(self):
        if self._llm is None:
            self._llm = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=0,
            )

    def invoke(self, prompt: str, system_prompt: str | None = None) -> str:
        try:
            self._ensure_llm()
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            response = self._llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"Error: model unavailable — {e}"

    def stream(self, prompt: str, system_prompt: str | None = None):
        try:
            self._ensure_llm()
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            for chunk in self._llm.stream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"Error: model unavailable — {e}"

    def swap_model(self, model_name: str):
        """Swap to a different model. Resets the underlying LLM instance."""
        self.model_name = model_name
        self._llm = None

    @property
    def name(self) -> str:
        return self.model_name