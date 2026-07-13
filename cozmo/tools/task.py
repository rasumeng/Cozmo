import threading
import logging
from pathlib import Path

import yaml

from . import register_tool

log = logging.getLogger("cozmo.subagent")

AGENT_DIR = Path.home() / ".cozmo" / "agents"

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
    """Load custom agent definitions from ~/.cozmo/agents/*.md"""
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
    """Get agent config by name. Checks builtins first, then custom."""
    all_agents = {**BUILTIN_AGENTS, **_load_custom_agents()}
    return all_agents.get(name)


@register_tool()
def task(description: str, prompt: str, subagent_type: str = "general") -> str:
    """Spawn a subagent to handle a focused task. Returns the subagent's response.

    Use this when you need to delegate work to a specialized agent:
    - 'explore': Read-only code exploration (find files, read code, answer questions)
    - 'scout': External web research (search, fetch, compile info)
    - 'general': Full agent with all tools for complex tasks
    - Any custom agent from ~/.cozmo/agents/*.md

    Args:
        description: Short task name (for display).
        prompt: Detailed instructions for the subagent.
        subagent_type: Agent type to spawn (default: 'general').
    """
    agent_cfg = _get_agent(subagent_type)
    if not agent_cfg:
        available = ", ".join(list(BUILTIN_AGENTS.keys()) + [a for a in _load_custom_agents()])
        return f"Error: Unknown agent type '{subagent_type}'. Available: {available}"

    try:
        from ..core.runtime import CozmoRuntime
        from ..core.model_manager import ModelManager
        from ..config import load_config

        cfg = load_config()
        rt_cfg = cfg.get("runtime", {})

        # Build a minimal runtime for the subagent
        mm = ModelManager(cfg.get("models", {}))
        if agent_cfg.get("model"):
            mm.set_lightweight_model(agent_cfg["model"])

        sub_runtime = CozmoRuntime(
            model_manager=mm,
            memory=None,  # No memory for subagents
            registry=None,  # Use default registry
            cfg=cfg,
        )

        # Build subagent system prompt
        system_parts = [agent_cfg.get("system", "")]
        if agent_cfg.get("permissions"):
            denied = [k for k, v in agent_cfg["permissions"].items() if v == "deny"]
            if denied:
                system_parts.append(f"Denied tools: {', '.join(denied)}")

        # Override system prompt
        sub_runtime._agent_system = "\n".join(system_parts)

        # Run the subagent
        result_parts = []
        for kind, text in sub_runtime.run_stream(prompt):
            if kind == "token":
                result_parts.append(text)

        result = "".join(result_parts).strip()
        if not result:
            return f"Subagent '{subagent_type}' completed but produced no output."
        return result

    except Exception as e:
        log.error("Subagent '%s' failed: %s", subagent_type, e)
        return f"Subagent error: {e}"
