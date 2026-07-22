"""
Planner — structured plan generation, validation, and execution.

Replaces inline text-only _generate_plan() with typed Plan/PlanStep
dataclasses. Enables step tracking, dependency resolution, pause/resume.
"""

import json
import logging
import re
from datetime import datetime

import time
from typing import Callable, Optional

from ..llm import OllamaModel
from .state import Plan, PlanStep
from .reflector import Reflector, ErrorType, RetryStrategy

log = logging.getLogger("cozmo.agent.planner")

_PLANNER_PROMPT = """You are planning a multi-step task. Generate a structured JSON plan.

CONTEXT:
{context}

USER REQUEST: {query}

Available tools:
{tools}

Respond with ONLY a JSON object:
{{
  "goal": "One-line summary of the goal",
  "steps": [
    {{
      "id": 1,
      "description": "What to do in this step",
      "tool": "tool_name or empty if no tool needed",
      "args": {{}},
      "depends_on": []
    }}
  ]
}}

Rules:
- Each step should use at most one tool
- depends_on lists step IDs that must complete first (empty for first steps)
- 3-7 steps typical. Keep focused and actionable."""


class Planner:
    """Generates and validates structured plans."""

    def __init__(self, llm: OllamaModel, tool_descriptions: str = ""):
        self.llm = llm
        self.tool_descriptions = tool_descriptions

    def create_plan(self, query: str, context: str = "") -> Plan:
        """Generate a structured plan from a user request."""
        prompt = _PLANNER_PROMPT.format(
            context=context or "(no additional context)",
            query=query,
            tools=self.tool_descriptions or "(no tools listed)",
        )
        try:
            raw = self.llm.invoke(prompt, temperature=0.2)
            plan = self._parse(raw)
            if plan and plan.steps:
                return plan
        except Exception as e:
            log.warning("plan generation failed: %s", e)
        return self._fallback_plan(query)

    def _parse(self, raw: str) -> Plan | None:
        """Parse JSON plan from LLM output (handles code fences)."""
        text = raw.strip()
        # Strip markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON block
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return None

        steps = []
        for s in data.get("steps", []):
            steps.append(PlanStep(
                id=s.get("id", len(steps) + 1),
                description=s.get("description", ""),
                tool=s.get("tool", ""),
                args=s.get("args", {}),
                depends_on=s.get("depends_on", []),
            ))

        # Mark first steps as ready
        for step in steps:
            if not step.depends_on:
                step.status = "ready"

        return Plan(
            goal=data.get("goal", query),
            steps=steps,
            context=context[:1000] if (context := "") else "",
            created=datetime.now().isoformat(),
        )

    def _fallback_plan(self, query: str) -> Plan:
        """Simple fallback when LLM plan generation fails."""
        return Plan(
            goal=query,
            steps=[PlanStep(id=1, description=f"Investigate: {query}", status="ready")],
            created=datetime.now().isoformat(),
        )

    def validate(self, plan: Plan) -> list[str]:
        """Validate a plan. Returns list of issues (empty = valid)."""
        issues = []
        if not plan.steps:
            issues.append("plan has no steps")
        seen_ids = set()
        for s in plan.steps:
            if s.id in seen_ids:
                issues.append(f"duplicate step id {s.id}")
            seen_ids.add(s.id)
            for dep in s.depends_on:
                if dep not in seen_ids and dep > s.id:
                    issues.append(f"step {s.id} depends on unknown step {dep}")
        return issues


class PlanExecutor:
    """Executes a structured Plan step by step with retry and failure recovery.

    Flow:
      1. Start with Plan.next_ready() → ready steps
      2. Execute each step via tool call
      3. On success: mark step done, get next ready steps
      4. On failure: reflect, retry or skip, continue
      5. On all done: return summary
    """

    def __init__(
        self,
        exec_tool: Callable[[str, dict], str],
        reflector: Optional[Reflector] = None,
        max_retries: int = 2,
    ):
        self._exec_tool = exec_tool
        self.reflector = reflector
        self.max_retries = max_retries

    def execute(self, plan: Plan, step_callback: Optional[Callable[[PlanStep], None]] = None) -> dict:
        """Execute a plan. Returns summary dict with results and failures.

        step_callback(step) is called after each step execution for UI updates.
        """
        results: list[dict] = []
        failures: list[dict] = []
        plan.created = plan.created or datetime.now().isoformat()

        while not plan.all_done():
            ready = plan.next_ready()
            if not ready and not plan.all_done():
                # Stuck: some steps are pending but not ready (dependency not met)
                stuck = [s for s in plan.steps if s.status == "pending"]
                for s in stuck:
                    s.status = "skipped"
                    failures.append({"step": s.id, "reason": "dependency not met"})
                break

            for step in ready:
                step.status = "running"
                result = self._execute_step(plan, step)
                step.result = result.get("output", "")
                if result.get("success"):
                    step.status = "done"
                    if step_callback:
                        step_callback(step)
                    results.append({"step": step.id, "tool": step.tool, "output": step.result[:200]})
                else:
                    step.status = "failed"
                    step.error = result.get("error", "")
                    failures.append({"step": step.id, "tool": step.tool, "error": step.error[:200]})
                    if step_callback:
                        step_callback(step)

        return {
            "goal": plan.goal,
            "total_steps": len(plan.steps),
            "done": len([s for s in plan.steps if s.status == "done"]),
            "failed": len([s for s in plan.steps if s.status == "failed"]),
            "skipped": len([s for s in plan.steps if s.status == "skipped"]),
            "results": results,
            "failures": failures,
        }

    def _execute_step(self, plan: Plan, step: PlanStep) -> dict:
        """Execute a single plan step with retries."""
        if not step.tool:
            return {"success": True, "output": step.description}

        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                output = self._exec_tool(step.tool, step.args)
                if output.startswith("Error"):
                    last_error = output
                    # Reflector: analyze failure, maybe skip retry for certain errors
                    should_retry = True
                    if self.reflector:
                        reflection = self.reflector.after_step(step.tool, step.args, output)
                        if reflection.retry_strategy == RetryStrategy.ABORT:
                            should_retry = False
                        if reflection.modified_args:
                            step.args = reflection.modified_args
                    if should_retry and attempt < self.max_retries:
                        time.sleep(1)
                        continue
                    return {"success": False, "error": last_error[:500]}
                return {"success": True, "output": output[:2000]}
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue
                return {"success": False, "error": last_error[:500]}

        return {"success": False, "error": last_error[:500]}
