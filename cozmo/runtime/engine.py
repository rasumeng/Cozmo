"""Engine — stateless ReAct loop with checkpoint support.

Takes a Job + context, runs tool-calling loop, streams events.
Periodically yields checkpoints for pause/resume.

Architecture:
  Engine.run_stream(ctx, model_fn, execute_tool, on_event) → yields (kind, ...)
    ├── Executes ReAct loop (model → tool → result → model)
    ├── Emits checkpoint every `checkpoint_interval` steps
    └── Supports resume from Checkpoint (restore messages)

  Final yield is ("__result__", EngineResult) — caller collects it.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Generator, Optional

from ..jobs.job import Checkpoint

log = logging.getLogger("cozmo.engine")


@dataclass
class EngineContext:
    """Minimal context for engine execution."""

    job_id: str = ""
    task_id: str = ""
    model_spec: dict = field(default_factory=dict)
    system_prompt: str = ""
    messages: list = field(default_factory=list)
    tools: list = field(default_factory=list)
    max_steps: int = 10
    temperature: float = 0.6
    checkpoint_interval: int = 0
    checkpoint: Optional[Checkpoint] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class EngineEvent:
    """An event emitted by the engine during execution."""

    type: str = ""
    data: dict = field(default_factory=dict)
    step: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class EngineResult:
    """Final result from engine execution."""

    success: bool = False
    output: str = ""
    messages: list = field(default_factory=list)
    steps_taken: int = 0
    tokens_used: int = 0
    error: str = ""
    checkpoint: Optional[Checkpoint] = None
    events: list[EngineEvent] = field(default_factory=list)


# Text fallback regex for models that emit JSON tool calls as plain text
_TEXT_TOOLCALL_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_tool_calls(ai) -> list[dict]:
    """Extract tool calls from an AIMessage. Supports native + text fallback."""
    native = getattr(ai, "tool_calls", None)
    if native:
        return [{"name": c["name"], "args": c.get("args", {}),
                 "id": c.get("id") or c["name"],
                 "index": i} for i, c in enumerate(native)]
    return _parse_text_toolcall(getattr(ai, "content", "") or "")


def _parse_text_toolcall(content: str) -> list[dict]:
    """Fallback: some models emit {"name":..,"args":..} as plain text."""
    if "{" not in content:
        return []
    match = _TEXT_TOOLCALL_RE.search(content)
    if not match:
        return []
    try:
        obj = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    name = obj.get("name") or obj.get("tool")
    args = obj.get("arguments") or obj.get("args") or {}
    if name and isinstance(args, dict):
        return [{"name": name, "args": args, "id": name, "index": 0}]
    return []


# ── Model function helpers ──────────────────────────────────────────────

def model_from_manager(model_manager, model_name: str, tools: list,
                       temperature: float = 0.0):
    """Build a model_fn from a ModelManager instance.

    Returns a callable: (messages) -> generator yielding (token, reasoning).
    Last yield is always ("__done__", final_aimessage).
    """
    runnable = (model_manager.bind_model(model_name, tools, temperature)
                if tools else model_manager.client_for_model(model_name, temperature))

    def _stream_model(messages: list):
        acc = None
        for chunk in runnable.stream(messages):
            yield (getattr(chunk, "content", "") or "",
                   chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else "")
            acc = chunk if acc is None else acc + chunk
        if acc is not None:
            yield ("__done__", acc)

    return _stream_model


def model_simple_invoke(llm_model):
    """Build a model_fn from an OllamaModel or similar.

    Usage: model_fn = model_simple_invoke(my_ollama_model)
    """
    def _invoke(messages: list):
        ai = llm_model.invoke_messages(messages)
        yield ("", "")
        yield ("__done__", ai)
    return _invoke


# ── Engine ──────────────────────────────────────────────────────────────

class Engine:
    """Stateless ReAct loop with periodic checkpointing."""

    @staticmethod
    def run_stream(
        ctx: EngineContext,
        model_fn: Callable,
        execute_tool: Callable[[str, dict], str],
        on_event: Callable[[EngineEvent], None] | None = None,
    ) -> Generator[tuple, None, None]:
        """Execute the ReAct loop as a generator.

        Args:
            ctx: EngineContext with messages, tools, model_spec, etc.
            model_fn: callable(messages) -> generator yielding (token, reasoning) tuples.
                      Last yield must be ("__done__", final_aimessage).
            execute_tool: callable(name, args) -> result_string.
            on_event: optional callback for EngineEvents (checkpoints, steps).

        Yields:
            (kind, ...) tuples compatible with CozmoRuntime.run_stream:
              ("token", text)
              ("reasoning", text)
              ("thinking", summary, detail)
              ("tool_call", name, args, call_id, category)
              ("tool_result", name, result, call_id)
            Final yield: ("__result__", EngineResult)
        """
        events: list[EngineEvent] = []
        messages = list(ctx.messages)
        start_step = 0

        if ctx.checkpoint:
            start_step = ctx.checkpoint.step
            if ctx.checkpoint.messages:
                messages = list(ctx.checkpoint.messages)
            log.info("engine resume: job=%s from step %d", ctx.job_id, start_step)

        step = start_step
        final = ""
        last_checkpoint: Optional[Checkpoint] = None
        seen_calls: set[str] = set()

        try:
            for step in range(start_step, ctx.max_steps):
                # ── checkpoint ──────────────────────────────────────────
                if ctx.checkpoint_interval > 0 and step > start_step and step % ctx.checkpoint_interval == 0:
                    cp = Checkpoint(job_id=ctx.job_id, step=step, messages=list(messages))
                    last_checkpoint = cp
                    ev = EngineEvent(type="checkpoint", data={"step": step, "job_id": ctx.job_id}, step=step)
                    events.append(ev)
                    if on_event:
                        on_event(ev)

                # ── step event ──────────────────────────────────────────
                ev = EngineEvent(type="step", data={"step": step}, step=step)
                events.append(ev)
                if on_event:
                    on_event(ev)

                # ── invoke model ────────────────────────────────────────
                yield ("thinking", "Thinking...", f"Step {step+1}/{ctx.max_steps}")
                content_buf = ""
                ai = None
                stream = model_fn(messages)
                for token, reasoning in stream:
                    if token == "__done__":
                        ai = reasoning
                        break
                    if token:
                        content_buf += token
                        yield ("token", token)
                    if reasoning:
                        yield ("reasoning", reasoning)

                if ai is None and content_buf:
                    from langchain_core.messages import AIMessage
                    ai = AIMessage(content=content_buf)

                if ai is None:
                    continue

                # ── extract calls ───────────────────────────────────────
                calls = _extract_tool_calls(ai)

                if not calls:
                    final = content_buf.strip()
                    break

                # ── execute calls ───────────────────────────────────────
                messages.append(ai)
                names = ", ".join(c["name"] for c in calls)
                details = "; ".join(f"{c['name']}({json.dumps(c['args'], sort_keys=True, default=str)[:200]})" for c in calls)
                yield ("thinking", f"Running: {names}", details)

                for c in calls:
                    sig = f"{c['name']}:{json.dumps(c['args'], sort_keys=True, default=str)}"
                    call_id = c.get("id") or f"call-{step}-{c['name']}"
                    category = ctx.tools[0] if ctx.tools else "tool"

                    yield ("tool_call", c["name"], c["args"], call_id, category)

                    if sig in seen_calls:
                        out = (f"Error: you already made this exact {c['name']} call "
                               f"and have its result above. Use it, or try a "
                               f"DIFFERENT call — do not repeat yourself.")
                    else:
                        seen_calls.add(sig)
                        out = execute_tool(c["name"], c["args"])

                    yield ("tool_result", c["name"], out, call_id)

                    from langchain_core.messages import ToolMessage
                    messages.append(ToolMessage(content=out, tool_call_id=c["id"]))
                    yield ("thinking", "Thinking...", "Processing tool results")

            # ── final checkpoint ────────────────────────────────────────
            if ctx.checkpoint_interval > 0:
                cp = Checkpoint(job_id=ctx.job_id, step=step + 1, messages=list(messages))
                last_checkpoint = cp

            if not final:
                final = content_buf.strip() if content_buf else "(no response)"

            yield ("__result__", EngineResult(
                success=True,
                output=final,
                messages=messages,
                steps_taken=step - start_step + 1,
                checkpoint=last_checkpoint,
                events=events,
            ))

        except Exception as e:
            log.error("engine error: %s", e)
            yield ("__result__", EngineResult(
                success=False,
                error=str(e),
                messages=messages,
                steps_taken=step - start_step,
                checkpoint=last_checkpoint,
                events=events,
            ))

    @staticmethod
    def run(
        ctx: EngineContext,
        model_fn: Callable,
        execute_tool: Callable[[str, dict], str],
        on_event: Callable[[EngineEvent], None] | None = None,
    ) -> EngineResult:
        """Synchronous execution. Collects all yields and returns EngineResult."""
        result = None
        for item in Engine.run_stream(ctx, model_fn, execute_tool, on_event):
            if item[0] == "__result__":
                result = item[1]
        return result or EngineResult(success=False, error="engine did not return")
