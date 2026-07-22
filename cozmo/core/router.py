"""
Mode router — classifies user input into chat/work/research/agent/vision.

Uses keyword pre-pass (fast path, no LLM call) for obvious research queries,
then falls back to LLM classification via a lightweight router model.

Architecture:
  user_input → keyword_pre_pass? → return "research"
            → router_llm classify → return mode
            → default → "chat"
"""

import logging
from typing import Optional

from .llm import OllamaModel

log = logging.getLogger("cozmo.router")

# Keywords that short-circuit to research mode before any LLM call.
_RESEARCH_KEYWORDS = [
    "latest news", "current events", "what's new",
    "weather", "price of", "release date", "upcoming", "schedule",
    "this week", "this month", "today", "right now",
    "who won", "score", "election", "breaking",
]

_ROUTE_PROMPT = """Classify the user's latest request as exactly one word:
- chat: greetings, small talk, definitions, general Q&A answerable from timeless knowledge
- work: coding, editing files, debugging, shell commands, anything touching the project
- agent: autonomous multi-step tasks like writing specs, planning architecture, documenting, brainstorming, researching, creating reports or proposals
- research: needs current/external info (news, events, sports, prices, weather, releases, schedules, "today", "latest", "recent", "next", "upcoming")
- vision: image generation, image editing, processing .png/.jpeg/.bmp/.gif/.tiff/.webp

Anything about current events or things that change over time is research, even if phrased vaguely.
When unsure between chat and research, pick research. When it touches code or files, pick work.
Multi-step tasks that need planning (writing docs, creating specs, architecture design, research reports) → agent.

Examples:
- "what's the weather in new york" → research
- "latest stock price of apple" → research
- "who won the super bowl" → research
- "edit main.py and fix the bug" → work
- "what is a monad" → chat
- "help me brainstorm feature ideas" → agent
- "write a spec for the auth system" → agent
- "plan the architecture for a new feature" → agent
- "draft documentation for the API" → agent
- "summarize this article about AI" → research
- "create a presentation outline" → agent
- "fix the typo in README.md" → work
- "explain how DNS works" → chat
- "research competitors in the AI space" → agent

Recent conversation (for context on vague follow-ups):
{history}

Request: {text}
Answer with one word:"""


def route(user_input: str,
          router_llm: Optional[OllamaModel] = None,
          history: Optional[list[tuple[str, str]]] = None,
          has_images: bool = False) -> str:
    """Classify input into a mode: chat | work | research | agent | vision.

    Priority:
    1. has_images → vision
    2. keyword match → research
    3. LLM classification → parsed mode
    4. fallback → chat
    """
    if has_images:
        return "vision"

    query_lower = user_input.lower()
    for kw in _RESEARCH_KEYWORDS:
        if kw in query_lower:
            return "research"

    if router_llm is None:
        return "chat"

    recent = ""
    if history:
        recent = "\n".join(
            f"User: {u}\nCozmo: {a[:200]}" for u, a in history[-3:]
        ) or "(none)"

    try:
        raw = router_llm.invoke(
            _ROUTE_PROMPT.format(history=recent, text=user_input)
        ).strip().lower()
        for mode in ("agent", "work", "research", "chat"):
            if mode in raw:
                return mode
    except Exception as e:
        log.warning("router LLM failed: %s", e)

    return "chat"
