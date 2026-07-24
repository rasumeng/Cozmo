"""
SessionState — per-conversation persistent state.

Tracks current task, goals, plan progress, observations, failures.
Survives restarts via JSON persistence. Not mode-specific.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .event_bus import EventBus, EventType

log = logging.getLogger("cozmo.session")


@dataclass
class SessionState:
    conversation_id: str = ""
    current_task_id: str = ""
    goal: str = ""
    scratchpad: str = ""
    failures: list[str] = field(default_factory=list)
    tools_used: int = 0
    created_at: str = ""
    updated_at: str = ""

    def add_failure(self, msg: str):
        self.failures.append(msg)
        if len(self.failures) > 50:
            self.failures = self.failures[-50:]

    def summary(self) -> str:
        parts = []
        if self.goal:
            parts.append(f"Current goal: {self.goal[:200]}")
        if self.failures:
            parts.append(f"Recent failures: {self.failures[-3:]}")
        if self.scratchpad:
            parts.append(f"Context: {self.scratchpad[:200]}")
        return "\n".join(parts)


class SessionStore:
    """JSON persistence for SessionState."""

    def __init__(self, base_dir: str | Path = ""):
        p = Path(base_dir) if base_dir else Path.home() / ".cozmo" / "sessions"
        self.base_dir = p
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, conversation_id: str) -> Path:
        return self.base_dir / f"{conversation_id}.json"

    def load(self, conversation_id: str) -> SessionState:
        path = self._path(conversation_id)
        if not path.exists():
            state = SessionState(conversation_id=conversation_id)
            state.created_at = datetime.now().isoformat()
            return state
        try:
            data = json.loads(path.read_text("utf-8"))
            state = SessionState(
                conversation_id=data.get("conversation_id", conversation_id),
                current_task_id=data.get("current_task_id", ""),
                goal=data.get("goal", ""),
                scratchpad=data.get("scratchpad", ""),
                failures=data.get("failures", []),
                tools_used=data.get("tools_used", 0),
                created_at=data.get("created_at", datetime.now().isoformat()),
                updated_at=data.get("updated_at", ""),
            )
            return state
        except Exception as e:
            log.warning("failed to load session %s: %s", conversation_id, e)
            return SessionState(conversation_id=conversation_id)

    def save(self, state: SessionState):
        try:
            state.updated_at = datetime.now().isoformat()
            data = {
                "conversation_id": state.conversation_id,
                "current_task_id": state.current_task_id,
                "goal": state.goal,
                "scratchpad": state.scratchpad[:2000],
                "failures": state.failures[-20:],
                "tools_used": state.tools_used,
                "created_at": state.created_at,
                "updated_at": state.updated_at,
            }
            self._path(state.conversation_id).write_text(json.dumps(data, indent=2), "utf-8")
        except Exception as e:
            log.warning("failed to save session %s: %s", state.conversation_id, e)

    def delete(self, conversation_id: str):
        self._path(conversation_id).unlink(missing_ok=True)
