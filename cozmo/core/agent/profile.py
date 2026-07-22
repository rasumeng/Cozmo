"""Agent Profiles — profile-based dispatch within agent mode.

Each profile defines a model override, allowed tools, and system prompt
extra tailored to a specific task type (research, coding, writing, etc.).
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("cozmo.agent.profile")

_PROFILE_PROMPT = """Given the user's goal, pick the best agent profile.

Profiles:
{profiles_text}

Goal: {goal}

Return exactly one word — the profile name. If unsure, say "default"."""


@dataclass
class AgentProfile:
    name: str
    description: str = ""
    model: Optional[str] = None
    tool_whitelist: Optional[list[str]] = None  # None = all tools
    system_prompt_extra: str = ""

    def to_text(self) -> str:
        parts = [f"- {self.name}: {self.description}"]
        if self.model:
            parts[0] += f" [model: {self.model}]"
        if self.tool_whitelist:
            parts[0] += f" [tools: {', '.join(self.tool_whitelist)}]"
        return parts[0]


# Default built-in profiles
DEFAULT_PROFILES: dict[str, AgentProfile] = {
    "default": AgentProfile(
        name="default",
        description="General-purpose agent — full tool access, standard model",
    ),
    "researcher": AgentProfile(
        name="researcher",
        description="Research and information gathering. Read-only tools, web search, no file modification",
        tool_whitelist=[
            "web_search", "web_search_pipeline", "web_fetch", "fetch_url",
            "search_knowledge", "read_knowledge", "read_file", "list_directory",
            "grep_search", "calculator", "search_memory", "current_time",
            "git_log", "git_diff", "git_status", "diagnostics",
        ],
        system_prompt_extra="Focus on gathering accurate, up-to-date information. Cite sources. Do not modify files.",
    ),
    "coder": AgentProfile(
        name="coder",
        description="Code writing and editing. Full access to file ops, git, and commands",
        system_prompt_extra="Focus on writing correct, idiomatic code. Test your changes. Prefer small incremental edits.",
    ),
    "writer": AgentProfile(
        name="writer",
        description="Documentation and prose writing. Read and write files, no shell commands",
        tool_whitelist=[
            "read_file", "list_directory", "grep_search", "write_file", "edit_file",
            "read_knowledge", "search_knowledge", "write_knowledge",
            "calculator", "current_time",
        ],
        system_prompt_extra="Focus on clear, well-structured writing. Edit for clarity and correctness.",
    ),
    "planner": AgentProfile(
        name="planner",
        description="Strategic planning and architecture. Reads files only, no modifications, no shell",
        tool_whitelist=[
            "read_file", "list_directory", "grep_search", "search_knowledge",
            "read_knowledge", "calculator",
        ],
        system_prompt_extra="Think step by step. Produce a detailed plan with rationale. Do not execute.",
    ),
}


class ProfileRouter:
    """Classifies a user's goal into an agent profile."""

    def __init__(self, profiles: Optional[dict[str, AgentProfile]] = None, llm=None):
        self.profiles = profiles or DEFAULT_PROFILES
        self._llm = llm  # Optional classifier LLM

    def classify(self, goal: str) -> AgentProfile:
        """Pick the best profile for a goal. Falls back to 'default'."""
        if self._llm is None:
            # No classifier — use simple keyword matching
            return self._keyword_match(goal)
        return self._llm_classify(goal)

    def _keyword_match(self, goal: str) -> AgentProfile:
        g = goal.lower()
        if any(kw in g for kw in ("write doc", "documentation", "readme", "prose", "article", "blog", "essay")):
            return self.profiles.get("writer", self.profiles["default"])
        if any(kw in g for kw in ("research", "investigate", "find out", "search", "gather information", "what is", "who is", "explore")):
            return self.profiles.get("researcher", self.profiles["default"])
        if any(kw in g for kw in ("plan", "architecture", "design", "spec", "proposal", "strategy")):
            return self.profiles.get("planner", self.profiles["default"])
        if any(kw in g for kw in ("code", "implement", "write code", "fix bug", "refactor", "function", "class", "test", "debug")):
            return self.profiles.get("coder", self.profiles["default"])
        return self.profiles["default"]

    def _llm_classify(self, goal: str) -> AgentProfile:
        try:
            profiles_text = "\n".join(p.to_text() for p in self.profiles.values())
            prompt = _PROFILE_PROMPT.format(profiles_text=profiles_text, goal=goal)
            raw = self._llm.generate(prompt, structured=False).strip().lower()
            for name in self.profiles:
                if name in raw:
                    return self.profiles[name]
        except Exception as e:
            log.warning("profile LLM classify failed: %s", e)
        return self.profiles["default"]
