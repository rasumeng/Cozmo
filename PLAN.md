# Cozmo — Local AI Agent

**Goal**: Fully local AI agent that runs on-device via Ollama. Specialist model routing by task type. Vector DB memory. Tool-use for desktop, web, messaging. Pip-installable, configurable for any hardware.

## Architecture

```
User → CLI / Telegram
         │
    Orchestrator
     ├── Heuristic pre-filter (0ms)
     ├── LLM classifier (qwen3:0.6b) → chat | coder | vision | research
     └── Router → picks specialist model
                    │
              Agent (specialist)
               ├── Specialist system prompt
               ├── Tool registry (all tools available)
               └── Memory (ChromaDB query + update)
```

## Model Registry

| Task     | Model            | Size   | Role |
|----------|-----------------|--------|------|
| classifier | qwen3:0.6b    | 522MB  | Routes tasks to correct specialist |
| chat     | phi4-mini:3.8b | 2.5GB  | General conversation, quick answers |
| coder    | ornith:9b      | 6.5GB | Coding, debugging, scripts |
| vision   | qwen2.5-vl:7b  | ~5GB   | Screenshot/image analysis |
| research | qwen3:8b       | 5.2GB  | Web search, deep analysis, summaries |

## Directory Structure

```
cozmo/
├── __init__.py
├── cli.py
├── config.py
├── telegram_bot.py
├── core/
│   ├── agent.py         # specialist prompts + tool execution loop
│   ├── llm.py           # Ollama wrapper
│   └── orchestrator.py  # classifier + router + memory injection
├── tools/
│   ├── __init__.py      # tool registry + decorator
│   ├── calculator.py
│   ├── file_ops.py
│   ├── web_search.py
│   ├── desktop.py       # screenshot (with vision), clipboard
│   └── telegram.py
├── memory/
│   ├── __init__.py
│   ├── manager.py
│   └── chroma_store.py
```

## Phases

### Phase 1 — Core
- Package structure, pyproject.toml, pip-installable
- CLI: `cozmo init`, `cozmo run`
- Tool registry, calculator, file_ops

### Phase 2 — Orchestrator
- Heuristic + LLM classifier
- Task routing to specialist models
- Conversation history

### Phase 3 — Memory + Tools
- ChromaDB memory with auto-summarization
- web_search, desktop (screenshot + clipboard), Telegram
- Cozmo Telegram bot

### Phase 4 — Specialist Agents (up next)
- Vision: screenshot analysis via qwen2.5-vl:7b
- Coder: ornith:9b for agentic coding
- Research: qwen3:8b for deep analysis

### Phase 5+ — Advanced
- Full desktop control (pyautogui)
- Obsidian vault indexing (graph + vector hybrid)
- Hardware auto-detect → model recommendations
- CI/CD, PyPI publishing
