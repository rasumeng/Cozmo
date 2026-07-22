"""
EventBus — decoupled typed event dispatch for runtime monitoring.

Replaces hardcoded yield tuples with a publish/subscribe system.
WebSocket / TUI / logging subscribe independently.

Architecture:
  Runtime → EventBus.emit(event) → [subscriber, subscriber, ...]
                                       ↕
                              WebSocket forwarder
                              Logging subscriber
                              Activity tracker
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

log = logging.getLogger("cozmo.agent.event_bus")


class EventType(str, Enum):
    # Lifecycle
    GOAL_STARTED = "goal_started"
    GOAL_COMPLETED = "goal_completed"
    PLAN_CREATED = "plan_created"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"

    # Execution
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    TOOL_FAILED = "tool_failed"

    # Agent state
    STATE_CHANGED = "state_changed"
    THINKING = "thinking"
    STATUS = "status"

    # Error recovery
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    REFLECTION_COMPLETED = "reflection_completed"

    # Streaming
    TOKEN = "token"


@dataclass
class Event:
    type: str
    data: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


EventHandler = Callable[[Event], None]


class EventBus:
    """Simple typed event bus. Thread-safe."""

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._wildcards: list[EventHandler] = []

    def on(self, event_type: str | EventType, handler: EventHandler):
        """Subscribe to a specific event type."""
        key = event_type.value if isinstance(event_type, EventType) else event_type
        with self._lock:
            self._subscribers.setdefault(key, []).append(handler)

    def on_any(self, handler: EventHandler):
        """Subscribe to ALL events."""
        with self._lock:
            self._wildcards.append(handler)

    def off(self, event_type: str | EventType, handler: EventHandler):
        """Unsubscribe a handler."""
        key = event_type.value if isinstance(event_type, EventType) else event_type
        with self._lock:
            self._subscribers.get(key, []).remove(handler)

    def emit(self, event_type: str | EventType, **data):
        """Emit an event to all subscribers."""
        ev = Event(
            type=event_type.value if isinstance(event_type, EventType) else event_type,
            data=data,
        )
        key = ev.type
        with self._lock:
            handlers = list(self._subscribers.get(key, []))
            wildcards = list(self._wildcards)
        for h in handlers:
            try:
                h(ev)
            except Exception as e:
                log.warning("event handler failed for %s: %s", key, e)
        for h in wildcards:
            try:
                h(ev)
            except Exception as e:
                log.warning("wildcard handler failed: %s", e)

    def clear(self):
        """Remove all subscribers."""
        with self._lock:
            self._subscribers.clear()
            self._wildcards.clear()
