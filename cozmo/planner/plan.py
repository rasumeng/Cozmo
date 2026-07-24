"""
Plan and PlanStep dataclasses.

These are the shared types used by all planner strategies
(template, heuristic, LLM). The Plan carries goal + steps with
dependency tracking and status for execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PlanStep:
    id: int = 0
    description: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)
    status: str = "pending"
    result: str = ""
    error: str = ""


@dataclass
class Plan:
    goal: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    context: str = ""
    created: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now().isoformat()

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
