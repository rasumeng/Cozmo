"""
AgentRuntime — autonomous agent with persistent state and structured planning.

Wraps the existing CozmoRuntime ReAct loop with AgentState persistence,
structured Planner, and cognitive lifecycle tracking.

Architecture:
  User → AgentRuntime
           ├── AgentState (persistent goals, plans, observations)
           ├── Planner (structured plan generation)
           └── CozmoRuntime (tool execution loop)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from ..llm import OllamaModel
from ..model_manager import ModelManager
from ..runtime import CozmoRuntime
from ..tool_registry import ToolRegistry
from .planner import Planner, PlanExecutor
from .state import AgentState, AgentStatus, Plan, StateStore
from .reflector import Reflector

log = logging.getLogger("cozmo.agent.runtime")


class AgentRuntime:
    """Autonomous agent with cognitive continuity across sessions."""

    def __init__(
        self,
        model_manager: ModelManager,
        tool_registry: ToolRegistry,
        planner_llm: OllamaModel,
        cfg: dict | None = None,
        skills: dict | None = None,
        state_path: str | Path = "",
    ):
        self.model_manager = model_manager
        self.tool_registry = tool_registry
        self.cfg = cfg or {}

        state_dir = Path(self.cfg.get("agent", {}).get("state_path", "~/.cozmo/agent_state"))
        self.state_store = StateStore(state_path or state_dir.expanduser() / "state.json")
        self.state = self.state_store.load()

        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in tool_registry.list()
        )
        self.planner = Planner(planner_llm, tool_descriptions)

        self.reflector = Reflector()
        self._executor: Optional[PlanExecutor] = None

    @property
    def has_active_goal(self) -> bool:
        return bool(self.state.current_goal) and self.state.status in (
            AgentStatus.PLANNING, AgentStatus.EXECUTING, AgentStatus.WAITING
        )

    def set_goal(self, goal: str):
        """Set a new goal and transition to planning state."""
        self.state.current_goal = goal
        self.state.status = AgentStatus.PLANNING
        self.state.active_plan = None
        self.state.failures.clear()
        self.state.tools_used = 0
        self.state.scratchpad = ""
        self.state_store.save(self.state)

    def generate_plan(self, context: str = "") -> Plan:
        """Generate and store a structured plan for the current goal."""
        plan = self.planner.create_plan(self.state.current_goal, context)
        issues = self.planner.validate(plan)
        if issues:
            log.warning("plan validation issues: %s", issues)
        self.state.active_plan = plan
        self.state.status = AgentStatus.WAITING  # waiting for approval
        self.state_store.save(self.state)
        return plan

    def approve_plan(self):
        """Mark plan as approved and transition to executing."""
        if self.state.active_plan:
            self.state.status = AgentStatus.EXECUTING
            self.state_store.save(self.state)

    def reject_plan(self):
        """Reset to idle on plan rejection."""
        self.state.status = AgentStatus.IDLE
        self.state.active_plan = None
        self.state_store.save(self.state)

    def record_tool_call(self, tool: str, args: dict, result: str):
        """Record a tool execution observation."""
        self.state.tools_used += 1
        status = "error" if result.startswith("Error") else "done"
        self.state.add_observation("tool_result", f"{tool}: {status}")
        if status == "error":
            self.state.add_failure(f"{tool} failed: {result[:200]}")
        self.state_store.save(self.state)

    def mark_complete(self, summary: str = ""):
        """Mark goal as complete and save state."""
        self.state.status = AgentStatus.COMPLETE
        if summary:
            self.state.scratchpad = summary[:2000]
        self.state_store.save(self.state)

    def mark_error(self, error: str):
        """Mark goal as errored."""
        self.state.status = AgentStatus.ERROR
        self.state.add_failure(error)
        self.state_store.save(self.state)

    def reset(self):
        """Clear agent state for a new session."""
        self.state = AgentState()
        self.state_store.save(self.state)

    def get_executor(self, exec_tool: Callable[[str, dict], str]) -> PlanExecutor:
        """Get or create a PlanExecutor bound to this runtime."""
        if not self._executor:
            self._executor = PlanExecutor(exec_tool, self.reflector)
        return self._executor

    def summary(self) -> str:
        """Return a summary of current agent state for prompt injection."""
        return self.state.summary()
