# Cozmo — Local AI Agent

**Goal**: Fully local AI agent that runs on-device via Ollama. Orchestrator pattern routes tasks to appropriate models. Vector DB memory. Tool-use for desktop, web, messaging. Pip-installable, configurable for any hardware.

## Architecture

```
CLI Interface
     │
Orchestrator (Core)
  ├── Router → classifies task complexity
  ├── Agent → ReAct loop (langchain-wrapped)
  └── Tool Exec → dispatches tool calls
     │
Model Registry (Ollama)
  ├── Fast   (phi3:3.8b)      — simple Q&A, email, summarization
  ├── Balanced (qwen3:8b)     — general reasoning, RAG
  └── Heavy  (qwen3:32b)      — coding, complex analysis
     │
Memory Layer (ChromaDB)
  ├── Working   — last N turns in-memory
  ├── Episodic  — past sessions + user preferences
  ├── Semantic  — documents + knowledge base (RAG)
  └── Procedural — tool usage patterns
     │
Tools Layer
  ├── calculator  — math evaluation
  ├── file_ops    — read/write/search files
  ├── web_search  — DuckDuckGo
  ├── desktop     — screenshot, clipboard (read-only Phase 1-3)
  ├── telegram    — bidirectional messaging
  ├── email       — IMAP/SMTP
  ├── browser     — playwright/selenium
  ├── code_exec   — sandboxed Python (Phase 4+)
  └── calendar    — local calendar
```

## Directory Structure

```
cozmo/
├── __init__.py
├── cli.py              # CLI entry: cozmo run, cozmo init
├── config.py           # TOML loader (tomllib), ~/.cozmo/config.toml
├── core/
│   ├── agent.py        # ReAct agent loop (langchain-wrapped)
│   ├── llm.py          # Ollama wrapper, model registry
│   ├── orchestrator.py # Task classifier → model router
│   └── session.py      # Per-session state management
├── tools/
│   ├── __init__.py     # Tool registry (decorator-based)
│   ├── calculator.py
│   ├── file_ops.py
│   ├── web_search.py
│   ├── desktop.py
│   └── telegram.py
├── memory/
│   ├── __init__.py
│   ├── manager.py      # working buffer + Chroma semantic
│   └── chroma_store.py # wraps existing RAG code
├── data/               # user documents (gitignored)
└── chroma_db/          # vector store (gitignored)
```

## Phases

### Phase 1 — Core
- Refactor into package structure
- `cozmo init` generates `~/.cozmo/config.toml`
- Model registry: fast / balanced / heavy
- CLI: `cozmo run` (interactive), `cozmo init`
- Tool registry pattern (decorator)
- Tools: calculator, file_ops (read-only)

### Phase 2 — Orchestrator
- Task classifier (heuristic: length + keyword)
- Model routing per task type
- Session context window management
- Fallback chain: fast → balanced → heavy

### Phase 3 — Memory + Messenger
- MemoryManager: working buffer (in-memory) + Chroma semantic
- Memory summarization for long sessions
- Telegram tool — bidirectional (push + pull)
- web_search tool
- desktop tool — screenshot + clipboard (read-only)
- Ship-ready: `pip install cozmo` works

### Phase 4+ — Advanced (separate milestones)
- Discord plugin
- Full desktop control (pyautogui)
- Sub-agents (coding, research, automation)
- Hardware auto-detect → model recommendations
