"""
PolicyEngine — gates all tool calls: permissions, destructive patterns, workspace trust.

Resolution order:
  1. Permission mode (relaxed / normal / strict) sets baseline
  2. PermissionResolver checks config rules + session allowlist
  3. Destructive pattern detection catches batch ops, dangerous cmd patterns
  4. Workspace trust evaluation (is cwd a known project?)
  5. Final allow / deny / ask decision with reason

Architecture:
  Orchestrator.plan() → PolicyEngine.decide(tool, args, context) → PolicyDecision
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ..runtime.permissions import PermissionResolver
from ..runtime.tool_risk import ToolRisk, get_tool_risk

log = logging.getLogger("cozmo.policy")


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PolicyMode(str, Enum):
    RELAXED = "relaxed"
    NORMAL = "normal"
    STRICT = "strict"


@dataclass
class PolicyResult:
    """Result of a policy check."""

    decision: PolicyDecision = PolicyDecision.ALLOW
    reason: str = ""
    risk: ToolRisk = ToolRisk.LOW

    @property
    def allowed(self) -> bool:
        return self.decision == PolicyDecision.ALLOW


_DESTRUCTIVE_COMMAND_PATTERNS = [
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\b(?:del|rd|rmdir)\s+[/\\][s/q]?", re.IGNORECASE),
    re.compile(r"\b(?:format|fdisk|mkfs|dd)\s", re.IGNORECASE),
    re.compile(r"\b(?:shutdown|reboot|halt|poweroff)\b", re.IGNORECASE),
    re.compile(r"\b(?:chmod\s+777|chown\s)", re.IGNORECASE),
    re.compile(r"\b(?:>|>>)\s*(?:/dev/|/etc/|/boot/)", re.IGNORECASE),
    re.compile(r"\b:wq!\s*$", re.IGNORECASE),
    re.compile(r"\bsudo\s+rm\b", re.IGNORECASE),
]

_BATCH_DELETE_PATTERNS = [
    re.compile(r"delete\s+(all|every|multiple|several)\s+file", re.IGNORECASE),
    re.compile(r"remove\s+(all|every|multiple)\s+file", re.IGNORECASE),
    re.compile(r"\*\s*\.\s*\*"),  # glob patterns like *.*
]

_WORKSPACE_TRUST_INDICATORS = [
    ".git",
    "README.md",
    "package.json",
    "Cargo.toml",
    "pyproject.toml",
    "go.mod",
    "CMakeLists.txt",
    "Makefile",
    "composer.json",
    "Gemfile",
    "requirements.txt",
    "setup.py",
]


def _is_destructive_command(command: str) -> bool:
    """Check if a shell command contains destructive patterns."""
    for pattern in _DESTRUCTIVE_COMMAND_PATTERNS:
        if pattern.search(command):
            return True
    return False


def _is_batch_delete(tool: str, args: dict) -> bool:
    """Detect batch file deletion patterns."""
    if tool in ("delete_file", "remove_file"):
        path = str(args.get("path", args.get("pattern", "")))
        for pattern in _BATCH_DELETE_PATTERNS:
            if pattern.search(path):
                return True
    if tool == "run_command":
        cmd = args.get("command", "")
        for pattern in _BATCH_DELETE_PATTERNS:
            if pattern.search(cmd):
                return True
    return False


def _evaluate_workspace_trust(workspace_path: Optional[str]) -> tuple[bool, str]:
    """Evaluate whether the workspace is a known/trusted project."""
    if not workspace_path:
        return True, "no workspace context"
    ws = Path(workspace_path)
    if not ws.is_dir():
        return True, "workspace not on disk"
    trust_indicators = sum(
        1 for ind in _WORKSPACE_TRUST_INDICATORS if (ws / ind).exists()
    )
    if trust_indicators >= 2:
        return True, f"trusted project ({trust_indicators} indicators)"
    if trust_indicators == 1:
        return True, f"partially known ({trust_indicators} indicator)"
    return False, "unknown workspace — no project indicators found"


class PolicyEngine:
    """Gates tool calls based on permissions, risk, patterns, and workspace trust."""

    def __init__(
        self,
        permission_resolver: Optional[PermissionResolver] = None,
        mode: PolicyMode = PolicyMode.NORMAL,
    ):
        self.perm = permission_resolver
        self.mode = mode
        self._workspace_path: str = ""

    def set_workspace(self, path: str):
        self._workspace_path = path

    def decide(
        self,
        tool: str,
        args: dict,
        agent: str = "build",
    ) -> PolicyResult:
        """Evaluate a tool call against all policy layers.

        Returns PolicyResult with decision + reason.
        """
        # 1. Destructive pattern check (fast reject for dangerous commands)
        if tool in ("run_command", "run_bash", "run_powershell", "execute_shell"):
            cmd = str(args.get("command", args.get("script", "")))
            if _is_destructive_command(cmd):
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason="destructive command pattern detected",
                    risk=ToolRisk.CRITICAL,
                )

        if _is_batch_delete(tool, args):
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason="batch delete pattern detected",
                risk=ToolRisk.CRITICAL,
            )

        # 2. Permission mode baseline
        if self.mode == PolicyMode.RELAXED:
            base_decisions = {"allow"}
        elif self.mode == PolicyMode.STRICT:
            risk = get_tool_risk(tool)
            if risk in (ToolRisk.HIGH, ToolRisk.CRITICAL):
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=f"strict mode denies {risk.value} risk tools",
                    risk=risk,
                )
            base_decisions = {"allow", "ask"}
        else:
            base_decisions = {"allow", "ask"}

        # 3. PermissionResolver check
        if self.perm:
            perm_result = self.perm.resolve(tool, args, agent)
            if perm_result == "deny":
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=f"permission denied by config rules",
                    risk=get_tool_risk(tool),
                )
            if perm_result == "allow" and self.mode != PolicyMode.STRICT:
                return PolicyResult(
                    decision=PolicyDecision.ALLOW,
                    reason="allowed by config rules",
                    risk=get_tool_risk(tool),
                )

        # 4. Workspace trust evaluation (for HIGH risk tools only)
        risk = get_tool_risk(tool)
        if risk == ToolRisk.HIGH or risk == ToolRisk.CRITICAL:
            trusted, trust_reason = _evaluate_workspace_trust(self._workspace_path)
            if not trusted and self.mode == PolicyMode.STRICT:
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=f"untrusted workspace denies {risk.value} risk tool",
                    risk=risk,
                )
            if not trusted:
                return PolicyResult(
                    decision=PolicyDecision.ASK,
                    reason=f"untrusted workspace — allow {tool}?",
                    risk=risk,
                )

        # 5. Risk-based decision
        if risk == ToolRisk.LOW:
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason="low risk tool",
                risk=risk,
            )
        if risk == ToolRisk.CRITICAL:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason="critical risk tool requires explicit override",
                risk=risk,
            )

        # Default: ask for medium/high if not covered by config
        if self.mode == PolicyMode.RELAXED:
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason=f"relaxed mode: {risk.value} risk tool",
                risk=risk,
            )
        return PolicyResult(
            decision=PolicyDecision.ASK,
            reason=f"{risk.value} risk tool — user confirmation required",
            risk=risk,
        )
