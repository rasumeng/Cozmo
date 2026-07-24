"""
WorkspaceContext — active project state for the current conversation.

Tracks the project directory, files of interest, git state, and current
objectives. Separates "what I'm currently working on" from "what I know"
(memory).

Architecture:
  WorkspaceContext is resolved at the start of each task and passed to
  the execution engine as part of the system prompt context.

  Memory = "what Cozmo knows" (vector store, facts, preferences)
  Workspace = "what Cozmo is working on" (files, git, project structure)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("cozmo.workspace")


@dataclass
class WorkspaceContext:
    """Describes the active project/workspace for a conversation."""

    project_dir: Optional[Path] = None
    project_name: str = ""
    description: str = ""
    git_branch: str = ""
    git_has_uncommitted: bool = False
    tracked_files: list[str] = field(default_factory=list)
    recent_files: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)

    def is_active(self) -> bool:
        return self.project_dir is not None

    def to_prompt_context(self) -> str:
        if not self.is_active():
            return ""
        parts = [f"=== Workspace: {self.project_name or self.project_dir.name} ==="]
        if self.description:
            parts.append(self.description)
        if self.project_dir:
            parts.append(f"Directory: {self.project_dir}")
        if self.git_branch:
            status = " (uncommitted changes)" if self.git_has_uncommitted else ""
            parts.append(f"Git branch: {self.git_branch}{status}")
        if self.goals:
            parts.append("Active goals:")
            for g in self.goals:
                parts.append(f"  - {g}")
        if self.recent_files:
            parts.append("Recently modified files:")
            for f in self.recent_files[:8]:
                parts.append(f"  - {f}")
        return "\n".join(parts)

    @staticmethod
    def from_project_dir(path: Path) -> "WorkspaceContext":
        """Build workspace context from a project directory."""
        ctx = WorkspaceContext(project_dir=path)
        ctx.project_name = path.name
        ctx._probe_git()
        ctx._probe_files()
        return ctx

    def _probe_git(self):
        if not self.project_dir:
            return
        try:
            import subprocess
            cwd = self.project_dir
            r = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, cwd=cwd, timeout=5
            )
            if r.returncode == 0:
                self.git_branch = r.stdout.strip()
                r2 = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True, text=True, cwd=cwd, timeout=5
                )
                self.git_has_uncommitted = bool(r2.stdout.strip())
        except Exception:
            pass

    def _probe_files(self):
        if not self.project_dir:
            return
        try:
            import subprocess
            cwd = self.project_dir
            if self.git_branch:
                r = subprocess.run(
                    ["git", "diff", "--name-only"],
                    capture_output=True, text=True, cwd=cwd, timeout=5
                )
                if r.stdout.strip():
                    self.recent_files = r.stdout.strip().splitlines()[:10]
                    self.tracked_files = self.recent_files
        except Exception:
            pass
