# Cozmo — Local AI Agent

Fully on-device AI agent powered by Ollama. Routes tasks to appropriate models, remembers conversations via Chroma vector DB, and can search the web, read your clipboard, take screenshots, and send Telegram messages.

## Quick Start

```bash
pip install cozmo
cozmo init          # creates ~/.cozmo/config.toml
cozmo run "hello"   # start interactive session
```

Requires [Ollama](https://ollama.ai) running locally with models pulled.

## Features

- **Model routing** — hybrid heuristic + LLM classifier picks the right model per task (fast/balanced/heavy)
- **Fallback chain** — if a model fails, tries the next tier automatically
- **Memory** — Chroma-backed, auto-summarizes every 5 turns, persists across sessions
- **Tools**: calculator, file I/O, web search, clipboard, screenshot, Telegram
- **Telegram bot** — `cozmo telegram` runs as a bidirectional bot (install with `pip install cozmo[telegram]`)
- **Configurable** — `~/.cozmo/config.toml` — model names, memory limits, desktop permissions, Telegram token
- **No cloud dependency** — everything runs on your machine via Ollama

## Architecture

```
User input → Orchestrator → Heuristic + LLM classifier → Model router → Agent → Tool execution → Response
                                   ↓
                             MemoryManager → ChromaDB (summaries persist across sessions)
```

See [PLAN.md](PLAN.md) for full architecture and [DEVLOG.md](DEVLOG.md) for development history.

## Configuration

```toml
[models]
fast = "phi4-mini:3.8b"
balanced = "qwen3:8b"
heavy = "qwen2.5-coder:14b"
classifier = "qwen3:0.6b"

[desktop]
enabled = false         # set true to allow screenshot + clipboard

[telegram]
enabled = false
bot_token = ""
```

## Project Status

Phase 3/6 complete. Core agent loop, orchestrator with model routing, memory system, tools (calculator, file ops, web search, desktop, Telegram). See `PLAN.md` for roadmap.

## License

MIT
