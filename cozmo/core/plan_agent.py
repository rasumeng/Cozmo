# DEPRECATED: Use cozmo.core.runtime.CozmoRuntime instead.
# This file is kept for backward compatibility only.

from .code_agent import CodeAgent


class PlanAgent(CodeAgent):
    """Read-only agent. Can analyze but not modify files."""

    @property
    def agent_name(self) -> str:
        return "plan"

    def __init__(self, model_name, cwd=".", cfg=None, agent_config=None, auto=False):
        agent_config = agent_config or {}
        if "permissions" not in agent_config:
            agent_config["permissions"] = {
                "write_file": "deny",
                "edit_file": "deny",
                "run_command": "deny",
            }
        super().__init__(model_name, cwd, cfg, agent_config, auto=auto)
