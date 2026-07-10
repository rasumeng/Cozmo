# Cozmo — Local AI Agent

Fully on-device AI agent powered by Ollama. Task-specific model routing (chat, coder, vision, research), ChromaDB memory, and tools for desktop, web, and messaging. No cloud dependency.

Requires [Ollama](https://ollama.ai) running locally with models pulled.

## Features

- **Specialist model routing** — LLM classifier (qwen3:0.6b) routes tasks to the right specialist model: chat (phi4-mini), coder (ornith:9b), vision (qwen2.5vl:7b), or research (qwen3:8b)
- **Memory** — ChromaDB-backed, auto-summarizes every 5 turns, persists across sessions
- **Tools**: calculator, file I/O, web search, screenshot (with vision analysis), clipboard, Telegram
- **Telegram bot** — `cozmo telegram` runs as a bidirectional bot (`pip install cozmo[telegram]`)
- **Vision** — screenshot tool automatically analyzes images via qwen2.5vl:7b; describe what's on your screen
- **Configurable** — `~/.cozmo/config.toml` — choose models that fit your hardware
- **No cloud** — everything runs locally via Ollama
- **Search pipeline** — query rewrite, multi-source search, content extraction, synthesis
- **Streaming** — token-by-token display with thinking indicators
- **MCP support** — connect external tool servers via Model Context Protocol

## Architecture

```
User → CLI / Telegram / WebUI
         │
    Orchestrator
     ├── Heuristic pre-filter (greetings → chat, code patterns → coder)
     ├── LLM classifier (qwen3:0.6b) → chat | coder | vision | research
     └── Router → picks specialist model
                    │
              Agent (specialist system prompt + tool registry)
              ├── ChatAgent — minimal tools, 3 turns
              ├── CollabAgent — observe-plan-act-reflect, 7 turns
              ├── CodeAgent — full tools, project index, 5 turns
              └── PlanAgent — read-only, blocks writes
                    │
              MemoryManager → ChromaDB (summaries persist across sessions)
```

### Component Summary

| Component | Role |
|-----------|------|
| **Orchestrator** | Heuristic + LLM query classification, routes to specialist |
| **Agent System** | ReAct loop with tool calling, permission gating, streaming |
| **Memory** | ChromaDB-backed, auto-summarizes every 5 turns, cross-session |
| **Search Pipeline** | Query rewrite → multi-source (web+SearXNG) → extract → synthesize |
| **Tools** | Calculator, file I/O, web search, code ops, git, desktop, Telegram |
| **MCP Host** | External tool server protocol (stdin/stdout or HTTP SSE) |
| **Code Index** | ChromaDB project index for codebase-aware queries |

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

Production-ready for personal use. Core agent, specialist routing, ChromaDB memory, full tool set (code ops, search, desktop, Telegram), WebUI, and MCP support. See [PLAN.md](PLAN.md) for roadmap.

### Known Issues

- **Docker Desktop startup**: SearXNG unavailable if Docker hasn't initialized
- **Model changes**: Take effect next message (agent created per-message)
- **Token count**: Estimated, not exact

### Quick Start (Development)

```bash
git clone https://github.com/rasumeng/cozmo.git
cd cozmo
pip install -e .
pip install -e .[telegram]  # optional Telegram support

cozmo init          # creates ~/.cozmo/config.toml
cozmo run "hello"   # interactive CLI
cozmo webui         # launch WebUI at http://127.0.0.1:8765
```

Requires [Ollama](https://ollama.ai) running locally with models pulled.

## Install from PyPI (not yet published)

```bash
pip install cozmo              # once published
pip install cozmo[telegram]    # with Telegram support
```

## License

MIT
