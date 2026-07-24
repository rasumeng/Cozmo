"""
Orchestrator — lightweight coordinator that turns user input into an ExecutionPlan.

Thin by design: classifies intent, estimates complexity, resolves capabilities,
selects model, and produces a plan for the Engine to execute. Does NOT execute
anything itself.

Architecture:
  user_input → Orchestrator → ExecutionPlan → Engine.run(plan)
"""

from __future__ import annotations

import logging
from typing import Optional

from ..orchestrator.task_types import (
    ExecutionPlan, ExecutionStrategy, Goal, IntentType, TaskProfile,
)
from ..orchestrator.intent import IntentDetector
from ..orchestrator.complexity import ComplexityEstimator
from ..capabilities import CapabilityRegistry

log = logging.getLogger("cozmo.orchestrator")

_INTENT_TO_STRATEGY = {
    IntentType.CONVERSATION: ExecutionStrategy.RESPOND,
    IntentType.RESEARCH: ExecutionStrategy.RESEARCH,
    IntentType.CODING: ExecutionStrategy.EXECUTE,
    IntentType.PLANNING: ExecutionStrategy.PLANNED,
    IntentType.VISION: ExecutionStrategy.RESPOND,
    IntentType.AUTONOMOUS: ExecutionStrategy.AUTONOMOUS,
    IntentType.CONTINUATION: ExecutionStrategy.EXECUTE,
}

_INTENT_TO_CAPABILITIES = {
    IntentType.CONVERSATION: ["conversation"],
    IntentType.RESEARCH: ["research", "conversation"],
    IntentType.CODING: ["coding", "filesystem", "terminal"],
    IntentType.PLANNING: ["planning", "conversation"],
    IntentType.VISION: ["vision", "conversation"],
}


class Orchestrator:
    """Lightweight coordinator. ~150 lines. Delegates everything."""

    def __init__(
        self,
        intent_detector: Optional[IntentDetector] = None,
        complexity_estimator: Optional[ComplexityEstimator] = None,
        capability_registry: Optional[CapabilityRegistry] = None,
        model_router=None,
    ):
        self.intent_detector = intent_detector or IntentDetector()
        self.complexity = complexity_estimator or ComplexityEstimator()
        self.capabilities = capability_registry or CapabilityRegistry()
        self.model_router = model_router

    def plan(
        self,
        user_input: str,
        history: Optional[list] = None,
        has_images: bool = False,
        force_capability: Optional[str] = None,
        force_model: Optional[str] = None,
    ) -> ExecutionPlan:
        """Turn user input into an ExecutionPlan.

        Overrides (force_capability / force_model) bypass detection.
        """
        # 1. Detect intent
        intent, confidence = self.intent_detector.detect(
            user_input, history, has_images
        )

        # 2. Estimate complexity
        complexity = self.complexity.estimate(user_input, intent)

        # 3. Resolve capabilities
        cap_ids = _INTENT_TO_CAPABILITIES.get(intent, ["conversation"])
        if force_capability:
            cap_ids = [force_capability]
        resolved_caps = self.capabilities.resolve(cap_ids)
        tool_names = self.capabilities.get_tool_names(cap_ids)

        # 4. Select strategy
        strategy = _INTENT_TO_STRATEGY.get(intent, ExecutionStrategy.RESPOND)

        # 5. Build task profile
        profile = TaskProfile(
            intent=intent,
            capabilities_needed=cap_ids,
            needs_planning=complexity.plan_level > 0,
            planning_level=complexity.plan_level,
            model_capability=force_capability or complexity.model_minimum,
            temperature=0.6 if intent == IntentType.CONVERSATION else 0.2,
            confidence=confidence,
        )

        # 6. Build plan
        plan = ExecutionPlan(
            goal=Goal(text=user_input[:500], intent=intent),
            strategy=strategy,
            capabilities=resolved_caps,
            tools=tool_names,
            model_spec={"capability": profile.model_capability, "model": force_model or ""},
            max_steps=complexity.max_steps,
            temperature=profile.temperature,
            context={"history": history or [], "has_images": has_images},
        )

        # 4b. Resolve model via ModelRouter with complexity awareness
        supports_tools = bool(tool_names) and intent != IntentType.VISION
        if self.model_router is not None:
            from ..runtime.model_router import ModelRequirement
            req = [ModelRequirement(
                capability=profile.model_capability,
                supports_tools=supports_tools,
                supports_vision=intent == IntentType.VISION,
            )]
            model_name = self.model_router.resolve(
                requirements=req,
                preferred=force_model,
                complexity_score=complexity,
            )
            plan.model_spec["model"] = model_name

        plan.model_spec["supports_tools"] = supports_tools

        return plan
