"""
Reflector — error classification, retry strategies, learning from failures.

Analyses tool call failures, classifies the error type, recommends recovery
strategies, and persists lessons for future reference.

Architecture:
  Runtime → Reflector.before_step() / after_step()
              ├── Classify error → ErrorType
              ├── Recommend strategy → RetryStrategy
              ├── Modify args if needed
              └── Store lesson → LessonStore
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

log = logging.getLogger("cozmo.reflection")


class ErrorType(str, Enum):
    TIMEOUT = "timeout"
    AUTH = "auth"
    NOT_FOUND = "not_found"
    PARSE = "parse"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    LOGIC = "logic"
    UNKNOWN = "unknown"


class RetryStrategy(str, Enum):
    RETRY = "retry"
    MODIFY_PARAMS = "modify_params"
    CHANGE_TOOL = "change_tool"
    DECOMPOSE = "decompose"
    ABORT = "abort"


@dataclass
class ReflectionResult:
    success: bool
    error_type: ErrorType = ErrorType.UNKNOWN
    retry_strategy: RetryStrategy = RetryStrategy.ABORT
    suggestion: str = ""
    modified_args: dict = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class Lesson:
    id: str = ""
    error_type: str = ""
    tool: str = ""
    pattern: str = ""
    strategy: str = ""
    suggestion: str = ""
    count: int = 1
    last_seen: str = ""

    def matches(self, tool: str, error_text: str) -> float:
        score = 0.0
        if self.tool == tool:
            score += 0.4
        if self.pattern and re.search(self.pattern, error_text, re.IGNORECASE):
            score += 0.4
        if score > 0 and self.error_type:
            score += 0.2
        return score


class LessonStore:
    """Persists failure patterns with match scoring."""

    def __init__(self, path: str | Path = ""):
        p = Path(path) if path else Path.home() / ".cozmo" / "lessons.json"
        self.path = p
        self.lessons: list[Lesson] = []
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text("utf-8"))
            self.lessons = [Lesson(**item) for item in data.get("lessons", [])]
        except Exception as e:
            log.warning("failed to load lessons: %s", e)

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {"lessons": [vars(l) for l in self.lessons[-50:]]}
            self.path.write_text(json.dumps(data, indent=2), "utf-8")
        except Exception as e:
            log.warning("failed to save lessons: %s", e)

    def add(self, lesson: Lesson):
        existing = None
        for l in self.lessons:
            if l.tool == lesson.tool and l.error_type == lesson.error_type:
                existing = l
                break
        if existing:
            existing.count += 1
            existing.last_seen = datetime.now().isoformat()
            if lesson.pattern and not existing.pattern:
                existing.pattern = lesson.pattern
        else:
            lesson.id = f"lesson-{len(self.lessons)}-{datetime.now().timestamp()}"
            lesson.last_seen = datetime.now().isoformat()
            self.lessons.append(lesson)
        self._save()

    def find_matches(self, tool: str, error_text: str, top_k: int = 3) -> list[Lesson]:
        scored = [(l.matches(tool, error_text), l) for l in self.lessons]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [l for score, l in scored if score > 0.5][:top_k]

    def format_for_prompt(self, tool: str, error_text: str) -> str:
        matches = self.find_matches(tool, error_text)
        if not matches:
            return ""
        lines = ["Relevant lessons from past failures:"]
        for l in matches:
            lines.append(f"- When {l.tool} failed ({l.error_type}): {l.suggestion}")
        return "\n".join(lines)

    def count(self) -> int:
        return len(self.lessons)


_ERROR_CLASSIFIERS = [
    (r"timed?\s*out|timeout|time\s*out", ErrorType.TIMEOUT),
    (r"unauthorized|forbidden|access denied|auth|api\s*key|token.*invalid|permission denied", ErrorType.AUTH),
    (r"not\s*found|no such file|does not exist|cannot find|not exist", ErrorType.NOT_FOUND),
    (r"parse|syntax|json.*invalid|unexpected token|malformed", ErrorType.PARSE),
    (r"rate\s*limit|too many requests|429|throttl", ErrorType.RATE_LIMIT),
    (r"invalid argument|bad value|validation|must be|required", ErrorType.VALIDATION),
]


def classify_error(error_text: str) -> ErrorType:
    text_lower = error_text.lower()
    for pattern, err_type in _ERROR_CLASSIFIERS:
        if re.search(pattern, text_lower):
            return err_type
    return ErrorType.LOGIC if len(error_text) < 200 else ErrorType.UNKNOWN


class Reflector:
    """Analyzes tool failures and recommends recovery strategies."""

    def __init__(self, lesson_store: Optional[LessonStore] = None):
        self.lessons = lesson_store or LessonStore()

    def before_step(self, tool: str, args: dict) -> ReflectionResult:
        return ReflectionResult(success=True)

    def after_step(self, tool: str, args: dict, result: str) -> ReflectionResult:
        is_error = result.lower().startswith("error")
        if not is_error:
            return ReflectionResult(success=True)

        error_type = classify_error(result)
        strategy, suggestion = self._suggest(tool, error_type, args, result)

        lesson = Lesson(
            error_type=error_type.value,
            tool=tool,
            pattern=self._extract_pattern(result),
            strategy=strategy.value,
            suggestion=suggestion,
        )
        self.lessons.add(lesson)

        modified = self._modify_args(strategy, args, result)

        return ReflectionResult(
            success=False,
            error_type=error_type,
            retry_strategy=strategy,
            suggestion=suggestion,
            modified_args=modified,
            confidence=0.7 if error_type != ErrorType.UNKNOWN else 0.3,
        )

    def _suggest(self, tool: str, error_type: ErrorType, args: dict, result: str) -> tuple[RetryStrategy, str]:
        if error_type == ErrorType.TIMEOUT:
            return RetryStrategy.RETRY, "Operation timed out. Try retrying with a longer timeout."
        if error_type == ErrorType.AUTH:
            return RetryStrategy.ABORT, "Authentication failed. Check API keys and permissions."
        if error_type == ErrorType.NOT_FOUND:
            return RetryStrategy.CHANGE_TOOL, "Path or resource not found. Verify the path exists."
        if error_type == ErrorType.PARSE:
            return RetryStrategy.MODIFY_PARAMS, "Output format was not parseable. Try a different format or approach."
        if error_type == ErrorType.RATE_LIMIT:
            return RetryStrategy.RETRY, "Rate limited. Wait and retry."
        if error_type == ErrorType.VALIDATION:
            return RetryStrategy.MODIFY_PARAMS, "Invalid arguments. Check the tool's parameter requirements."
        return RetryStrategy.CHANGE_TOOL, "Tool failed. Try a different approach or tool."

    def _modify_args(self, strategy: RetryStrategy, args: dict, result: str) -> dict:
        if strategy != RetryStrategy.MODIFY_PARAMS:
            return args
        return dict(args)

    def _extract_pattern(self, error_text: str) -> str:
        clean = re.sub(r"[0-9a-f]{8,}", "<id>", error_text[:200])
        clean = re.sub(r"\d+", "<n>", clean)
        clean = re.sub(r"['\"][^'\"]+['\"]", "'<val>'", clean)
        return clean.strip()
