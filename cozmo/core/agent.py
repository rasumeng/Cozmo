from .base_agent import BaseAgent, parse_tool_call, build_tool_schema, exec_tool_call
from ..tools import TOOL_REGISTRY

SPECIALIST_PROMPTS = {
    "chat": "You are Cozmo, a friendly AI assistant. Be concise and helpful. Do not use tools or mention them.",
    "coder": "You are Cozmo, an expert programmer. Write clean, working code with brief explanations.",
    "vision": "You are Cozmo, an AI that analyzes images and screenshots. Describe what you see clearly.",
    "research": "You are Cozmo, a research analyst. Provide thorough, well-structured answers with sources.",
}


class Agent(BaseAgent):
    """Legacy agent. Used by Orchestrator path. Prefer ChatAgent/CollabAgent/CodeAgent."""

    def __init__(self, model_name: str, task_type: str = "chat", base_url: str = "http://localhost:11434"):
        super().__init__(model_name, base_url)
        self.task_type = task_type
        self.tools = TOOL_REGISTRY
        self.system_prompt = SPECIALIST_PROMPTS.get(task_type, SPECIALIST_PROMPTS["chat"])

    def _build_system(self) -> str:
        if self.task_type == "chat":
            return self.system_prompt
        schema = build_tool_schema(self.tools)
        return (
            f"{self.system_prompt}\n\n"
            f"Available tools:\n{schema}\n\n"
            "To use a tool, respond with:\n"
            "<tool>{\"tool\": \"tool_name\", \"args\": {\"arg1\": \"value1\"}}</tool>\n\n"
            "After the tool result comes back, answer naturally."
        )

    def run(self, prompt: str) -> str:
        if self.task_type == "chat":
            return self.llm.invoke(prompt, system_prompt=self.system_prompt)

        system = self._build_system()
        response = self.llm.invoke(prompt, system_prompt=system)
        call = parse_tool_call(response)
        if call is None:
            return response

        result = exec_tool_call(self.tools, call)
        followup = (
            f"Original conversation so far:\n{prompt}\n\n"
            f"You used a tool and got this result:\n{result}\n\n"
            f"Now answer based on this result. Do NOT repeat the <tool> block."
        )
        return self.llm.invoke(followup, system_prompt=system)

    def run_stream(self, prompt: str):
        system = self._build_system()
        for token in self.llm.stream(prompt, system_prompt=system):
            yield ("[token]", token)
