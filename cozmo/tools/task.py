import concurrent.futures
import json
import threading
import logging
from pathlib import Path

import yaml

from . import register_tool

log = logging.getLogger("cozmo.subagent")

AGENT_DIR = Path.home() / ".cozmo" / "agents"

_SUBAGENT_DEPTH = threading.local()
_MAX_DEPTH = 3
_SUBAGENT_TIMEOUT = 60  # seconds

BUILTIN_AGENTS = {
    "explore": {
        "name": "explore",
        "description": "Read-only code exploration agent. Finds files, reads code, answers questions.",
        "model": None,
        "permissions": {"edit": "deny", "write": "deny", "execute": "deny"},
        "system": (
            "You are a read-only exploration agent. Your job is to find and read code, "
            "answer questions about the codebase, and report findings. "
            "You cannot modify files or execute commands. "
            "Always cite file paths and line numbers in your answers."
        ),
    },
    "scout": {
        "name": "scout",
        "description": "External research agent. Searches the web and fetches information.",
        "model": None,
        "permissions": {"edit": "deny", "write": "deny", "execute": "deny"},
        "system": (
            "You are a research agent. Your job is to search the web, fetch URLs, "
            "and compile information on a given topic. "
            "Provide sourced answers with URLs. You cannot modify local files."
        ),
    },
    "general": {
        "name": "general",
        "description": "Full agent with all tools. Use for complex multi-step tasks.",
        "model": None,
        "permissions": {},
        "system": "You are a general-purpose assistant. Complete the task thoroughly.",
    },
}


def _load_custom_agents() -> dict:
    agents = {}
    if not AGENT_DIR.exists():
        return agents
    for f in AGENT_DIR.glob("*.md"):
        try:
            content = f.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1])
                    body = parts[2].strip()
                    agents[meta["name"]] = {
                        "name": meta["name"],
                        "description": meta.get("description", ""),
                        "model": meta.get("model"),
                        "permissions": meta.get("permissions", {}),
                        "system": body,
                    }
        except Exception as e:
            log.warning("Failed to load agent %s: %s", f.name, e)
    return agents


def _get_agent(name: str) -> dict | None:
    all_agents = {**BUILTIN_AGENTS, **_load_custom_agents()}
    return all_agents.get(name)


def _current_depth() -> int:
    return getattr(_SUBAGENT_DEPTH, 'depth', 0)


def _format_result(text: str, subagent_type: str, success: bool) -> str:
    """Format subagent result as structured JSON for the calling agent."""
    payload = {
        "subagent": subagent_type,
        "success": success,
        "result": text[:4000],
    }
    return json.dumps(payload)


@register_tool()
def task(description: str, prompt: str, subagent_type: str = "general",
         timeout: int = 60, structured: bool = True) -> str:
    """Spawn a subagent to handle a focused task.

    Use this when you need to delegate work to a specialized agent:
    - 'explore': Read-only code exploration (find files, read code, answer questions)
    - 'scout': External web research (search, fetch, compile info)
    - 'general': Full agent with all tools for complex tasks
    - Any custom agent from ~/.cozmo/agents/*.md

    Args:
        description: Short task name (for display).
        prompt: Detailed instructions for the subagent.
        subagent_type: Agent type to spawn (default: 'general').
        timeout: Max seconds for subagent execution (default: 60).
        structured: Return structured JSON with success/result fields (default: True).
    """
    depth = _current_depth()
    if depth >= _MAX_DEPTH:
        err = f"Max subagent depth ({_MAX_DEPTH}) reached. Cannot spawn deeper."
        log.warning(err)
        return _format_result(err, subagent_type, False) if structured else err

    agent_cfg = _get_agent(subagent_type)
    if not agent_cfg:
        available = ", ".join(list(BUILTIN_AGENTS.keys()) + [a for a in _load_custom_agents()])
        err = f"Unknown agent type '{subagent_type}'. Available: {available}"
        return _format_result(err, subagent_type, False) if structured else err

    _SUBAGENT_DEPTH.depth = depth + 1
    try:
        from ..runtime.runtime import CozmoRuntime
        from ..models import ModelService, ModelRegistry
        from ..config import load_config
        from ..runtime.tool_registry import ToolRegistry

        cfg = load_config()
        model_registry = ModelRegistry()
        model_service = ModelService(cfg, model_registry)
        model_service.refresh()

        if agent_cfg.get("model"):
            force_model = agent_cfg["model"]
        else:
            force_model = ""

        registry = ToolRegistry()
        from ..tools import TOOL_REGISTRY
        for name, fn in TOOL_REGISTRY.items():
            registry.register(name, fn)

        sub_runtime = CozmoRuntime(
            model_service=model_service,
            memory=None,
            registry=registry,
            cfg=cfg,
        )
        sub_runtime.force_model = force_model

        system_parts = [agent_cfg.get("system", "")]
        if agent_cfg.get("permissions"):
            denied = [k for k, v in agent_cfg["permissions"].items() if v == "deny"]
            if denied:
                system_parts.append(f"Denied tools: {', '.join(denied)}")

        context_hint = description.strip()
        if context_hint:
            system_parts.append(f"\nParent task context: {context_hint}")
        system_parts.append(
            "\nYou are a subagent. Complete only the task given. "
            "Do not spawn further subagents. "
            "Return a complete, self-contained answer."
        )

        sub_runtime._agent_system = "\n".join(system_parts)
        sub_runtime.stop_event = threading.Event()

        def _run():
            result_parts = []
            for kind, text in sub_runtime.run_stream(prompt):
                if kind == "token":
                    result_parts.append(text)
            return "".join(result_parts).strip()

        actual_timeout = min(timeout, _SUBAGENT_TIMEOUT)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run)
            try:
                result = fut.result(timeout=actual_timeout)
            except concurrent.futures.TimeoutError:
                sub_runtime.stop_event.set()
                err = f"Subagent '{subagent_type}' timed out after {actual_timeout}s."
                log.warning(err)
                return _format_result(err, subagent_type, False) if structured else err

        if not result:
            err = f"Subagent '{subagent_type}' completed but produced no output."
            return _format_result(err, subagent_type, False) if structured else err

        return _format_result(result, subagent_type, True) if structured else result

    except Exception as e:
        log.error("Subagent '%s' failed: %s", subagent_type, e)
        err = str(e)
        return _format_result(err, subagent_type, False) if structured else err
    finally:
        _SUBAGENT_DEPTH.depth = _current_depth() - 1
