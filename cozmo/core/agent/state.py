"""
AgentState — persistent cognitive state for the agent.

Tracks goals, plan progress, observations, failures, and tool history
across sessions. Survives restarts via JSON persistence.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

log = logging.getLogger("cozmo.agent.state")


class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class PlanStep:
    id: int
    description: str
    tool: str = ""
    args: dict = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)
    status: str = "pending"  # pending | ready | running | done | failed | skipped
    result: str = ""
    error: str = ""


@dataclass
class Plan:
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    context: str = ""
    created: str = ""

    def to_text(self) -> str:
        lines = [f"## Plan: {self.goal}"]
        for s in self.steps:
            dep = f" (after step {s.depends_on})" if s.depends_on else ""
            lines.append(f"{s.id}. {s.description} — {s.status}{dep}")
        return "\n".join(lines)

    def active_step(self) -> Optional[PlanStep]:
        for s in self.steps:
            if s.status in ("ready", "running"):
                return s
        return None

    def all_done(self) -> bool:
        return all(s.status in ("done", "skipped") for s in self.steps)

    def next_ready(self) -> list[PlanStep]:
        ready = []
        for s in self.steps:
            if s.status != "pending":
                continue
            if all(
                self.steps[d - 1].status in ("done", "skipped")
                for d in s.depends_on
            ):
                ready.append(s)
        return ready


@dataclass
class Observation:
    source: str  # "tool_result" | "user" | "reflection"
    content: str
    timestamp: str = ""


@dataclass
class AgentState:
    current_goal: str = ""
    status: AgentStatus = AgentStatus.IDLE
    active_plan: Optional[Plan] = None
    observations: list[Observation] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    tools_used: int = 0
    scratchpad: str = ""

    def add_failure(self, msg: str):
        self.failures.append(msg)
        if len(self.failures) > 50:
            self.failures = self.failures[-50:]

    def add_observation(self, source: str, content: str):
        self.observations.append(Observation(
            source=source,
            content=content[:500],
            timestamp=datetime.now().isoformat(),
        ))
        if len(self.observations) > 100:
            self.observations = self.observations[-100:]

    def summary(self) -> str:
        parts = [f"Status: {self.status.value}"]
        if self.current_goal:
            parts.append(f"Current goal: {self.current_goal[:200]}")
        if self.active_plan:
            parts.append(f"Active plan: {self.active_plan.to_text()[:300]}")
        if self.failures:
            parts.append(f"Recent failures: {self.failures[-3:]}")
        return "\n".join(parts)


class StateStore:
    """JSON persistence for AgentState."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> AgentState:
        if not self.path.exists():
            return AgentState()
        try:
            data = json.loads(self.path.read_text("utf-8"))
            state = AgentState(
                current_goal=data.get("current_goal", ""),
                status=AgentStatus(data.get("status", "idle")),
                failures=data.get("failures", []),
                tools_used=data.get("tools_used", 0),
                scratchpad=data.get("scratchpad", ""),
            )
            plan_data = data.get("active_plan")
            if plan_data:
                steps = [PlanStep(**s) for s in plan_data.get("steps", [])]
                state.active_plan = Plan(
                    goal=plan_data.get("goal", ""),
                    steps=steps,
                    context=plan_data.get("context", ""),
                    created=plan_data.get("created", ""),
                )
            return state
        except Exception as e:
            log.warning("failed to load agent state: %s", e)
            return AgentState()

    def save(self, state: AgentState):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "current_goal": state.current_goal,
                "status": state.status.value,
                "failures": state.failures[-20:],
                "tools_used": state.tools_used,
                "scratchpad": state.scratchpad[:2000],
            }
            if state.active_plan:
                data["active_plan"] = {
                    "goal": state.active_plan.goal,
                    "context": state.active_plan.context[:1000],
                    "created": state.active_plan.created,
                    "steps": [
                        {
                            "id": s.id,
                            "description": s.description,
                            "tool": s.tool,
                            "args": s.args,
                            "depends_on": s.depends_on,
                            "status": s.status,
                            "result": s.result[:500] if s.result else "",
                            "error": s.error[:200] if s.error else "",
                        }
                        for s in state.active_plan.steps
                    ],
                }
            self.path.write_text(json.dumps(data, indent=2), "utf-8")
        except Exception as e:
            log.warning("failed to save agent state: %s", e)
