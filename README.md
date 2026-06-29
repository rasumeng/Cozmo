# Cozmo — Local AI Agent

Fully on-device AI agent powered by Ollama. Task-specific model routing (chat, coder, vision, research), ChromaDB memory, and tools for desktop, web, and messaging. No cloud dependency.

## Quick Start

```bash
# From GitHub
pip install git+https://github.com/YOUR_USERNAME/cozmo.git

# Or from local clone
git clone https://github.com/YOUR_USERNAME/cozmo.git
cd cozmo
pip install -e .

cozmo init          # creates ~/.cozmo/config.toml
cozmo run "hello"   # start interactive session
```

Requires [Ollama](https://ollama.ai) running locally with models pulled.

## Features

- **Specialist model routing** — LLM classifier (qwen3:0.6b) routes tasks to the right specialist model: chat (phi4-mini), coder (ornith:9b), vision (qwen2.5vl:7b), or research (qwen3:8b)
- **Memory** — ChromaDB-backed, auto-summarizes every 5 turns, persists across sessions
- **Tools**: calculator, file I/O, web search, screenshot (with vision analysis), clipboard, Telegram
- **Telegram bot** — `cozmo telegram` runs as a bidirectional bot (`pip install cozmo[telegram]`)
- **Vision** — screenshot tool automatically analyzes images via qwen2.5vl:7b; describe what's on your screen
- **Configurable** — `~/.cozmo/config.toml` — choose models that fit your hardware
- **No cloud** — everything runs locally via Ollama

## Architecture

```
User → CLI / Telegram
         │
    Orchestrator
     ├── Heuristic pre-filter (greetings → chat, code patterns → coder)
     ├── LLM classifier (qwen3:0.6b) → chat | coder | vision | research
     └── Router → picks specialist model
                    │
              Agent (specialist system prompt + tool registry)
                    │
              MemoryManager → ChromaDB (summaries persist across sessions)
```

## Configuration

```toml
[models]
classifier = "qwen3:0.6b"    # 522MB — routes tasks to specialists
chat = "phi4-mini:3.8b"      # 2.5GB — general conversation
coder = "ornith:9b"           # 6.5GB — coding, debugging, scripts
vision = "qwen2.5vl:7b"      # 6.0GB — screenshot & image analysis
research = "qwen3:8b"         # 5.2GB — deep analysis, web search

[desktop]
enabled = false               # set true to allow screenshot + clipboard

[telegram]
enabled = false
bot_token = ""
```

## Project Status

Phase 3 complete. Core agent, orchestrator with specialist routing, ChromaDB memory, tools (calculator, file ops, web search, desktop with vision, Telegram). See [PLAN.md](PLAN.md) for full roadmap.

## Install from PyPI (not yet published)

```bash
pip install cozmo              # once published
pip install cozmo[telegram]    # with Telegram support
```

## License

MIT
