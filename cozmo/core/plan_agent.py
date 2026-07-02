from .code_agent import CodeAgent


class PlanAgent(CodeAgent):
    @property
    def agent_name(self) -> str:
        return "plan"

    def __init__(self, model_name, cwd, cfg, agent_config=None, auto=False):
        agent_config = agent_config or {}
        if "permissions" not in agent_config:
            agent_config["permissions"] = {
                "write_file": "deny", "edit_file": "deny", "run_command": "deny"
            }
        super().__init__(model_name, cwd, cfg, agent_config, auto=auto)
        self.system_prompt = (
            "You are Cozmo the architect. Analyze code and suggest improvements. "
            "Do NOT modify files. Only read, search, and propose changes in your response."
        )
