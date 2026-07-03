# Cozmo — Project Scope Document

> **Version**: 1.0 | **Date**: July 3, 2026 | **Status**: Phase 4 Complete

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Core Components](#core-components)
5. [Tools & Capabilities](#tools--capabilities)
6. [TUI Interface](#tui-interface)
7. [Search Pipeline](#search-pipeline)
8. [Memory System](#memory-system)
9. [Configuration](#configuration)
10. [Installation & Setup](#installation--setup)
11. [Development History](#development-history)
12. [Known Issues & Future Work](#known-issues--future-work)

---

## Project Overview

**Cozmo** is a fully local AI agent that competes with Claude Code, OpenCode, and other paid agentic AI services. It runs entirely on-device using Ollama as the backend, with no cloud dependencies.

### Key Features

- **Fully Local**: No paid APIs, no cloud dependency
- **Ollama Backend**: Uses local LLMs via Ollama
- **Textual TUI**: Rich terminal interface with chat, collab, and code panels
- **Specialized Agents**: Chat, Collab, Code, and Plan agents
- **Search Pipeline**: ChatGPT-style search with query rewrite, multi-source, and synthesis
- **Memory**: ChromaDB-backed, auto-summarizes, persists across sessions
- **Tools**: Calculator, file I/O, web search, code operations, desktop, Telegram

### Target Platform

- **OS**: Windows 11 (primary), Linux/macOS (secondary)
- **Python**: 3.10+
- **Textual**: 8.2+
- **Ollama**: Running locally with models pulled

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        TUI (Textual)                        │
├─────────────────────────────────────────────────────────────┤
│  ChatPanel  │  CollabPanel  │  CodePanel  │  MainPanel     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     Specialized Agents                      │
├─────────────────────────────────────────────────────────────┤
│  ChatAgent  │  CollabAgent  │  CodeAgent  │  PlanAgent     │
│  (3 turns)  │  (7 turns)    │  (5 turns)  │  (5 turns)    │
│  Min tools  │  All tools    │  All tools  │  Read-only     │
│  History    │  Observe-     │  Project    │  Project       │
│  Persist    │  Plan-Act-    │  Index      │  Index         │
│             │  Reflect      │             │                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Base Agent Layer                       │
├─────────────────────────────────────────────────────────────┤
│  parse_tool_call()  │  build_tool_schema()  │  exec_tool_call()  │
│  History  │  Compact  │  Trim  │  Permission Callback          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Ollama Backend (Local)                    │
├─────────────────────────────────────────────────────────────┤
│  LLM: ChatOllama  │  Embeddings: nomic-embed-text           │
│  Models: phi4-mini, qwen3, ornith, gemma, etc.              │
└─────────────────────────────────────────────────────────────┘
```

### Flow

1. **User Input** → TUI captures message
2. **Agent Selection** → Panel creates appropriate agent (Chat/Collab/Code)
3. **Orchestrator** → Classifies query, retrieves memory context
4. **Agent Loop** → ReAct loop with tool calls
5. **Tools** → Execute operations (search, file ops, etc.)
6. **Streaming** → Real-time token-by-token display
7. **Memory** → Store interaction, auto-compact if needed

---

## Directory Structure

```
Cozmo/
├── cozmo/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                    # CLI entry point
│   ├── config.py                 # TOML config loader
│   ├── config_cli.py             # Config management CLI
│   ├── code_indexer.py           # Project indexing for CodeAgent
│   ├── ollama_util.py            # Ollama management
│   ├── searxng_util.py           # SearXNG auto-setup
│   ├── telegram_bot.py           # Telegram integration
│   │
│   ├── core/
│   │   ├── agent.py              # Legacy agent (Orchestrator path)
│   │   ├── agent_registry.py     # Agent registry for CLI
│   │   ├── base_agent.py         # Shared agent utilities
│   │   ├── chat_agent.py         # Chat agent (minimal tools)
│   │   ├── code_agent.py         # Code agent (full tools)
│   │   ├── collab_agent.py       # Collab agent (Observe-Plan-Act-Reflect)
│   │   ├── plan_agent.py         # Plan agent (read-only)
│   │   ├── llm.py                # Ollama LLM wrapper
│   │   ├── orchestrator.py       # Task classification + routing
│   │   └── permissions.py        # Permission system
│   │
│   ├── memory/
│   │   ├── chroma_store.py       # ChromaDB vector store
│   │   └── manager.py            # Memory manager (short-term + long-term)
│   │
│   ├── tools/
│   │   ├── __init__.py           # Tool registry + decorator
│   │   ├── calculator.py         # Safe math evaluation (AST)
│   │   ├── code_ops.py           # File ops, grep, run_command, git
│   │   ├── desktop.py            # Screenshot, clipboard
│   │   ├── file_ops.py           # File read/write with sandboxing
│   │   ├── search_pipeline.py    # Full search pipeline
│   │   ├── telegram.py           # Telegram send tool
│   │   └── web_search.py         # Web search + fetch (trafilatura)
│   │
│   └── tui/
│       ├── app.py                # Main TUI application
│       ├── chat_manager.py       # Chat persistence (.md files)
│       ├── themes.py             # Theme definitions
│       ├── css/                  # Textual CSS styles
│       ├── screens/              # Modal screens
│       │   ├── main.py           # Main screen
│       │   ├── model_selector.py # Model selection
│       │   ├── permission.py     # Permission modal
│       │   ├── file_picker.py    # File picker
│       │   └── settings.py       # Settings screen
│       └── widgets/
│           ├── input.py          # Chat input with model selector
│           ├── code_input.py     # Code input with mode toggle
│           ├── footer.py         # Status bar (tokens, context %)
│           ├── sidebar.py        # Chat history sidebar
│           ├── sprite.py         # ASCII art sprite
│           └── panels/
│               ├── panel.py      # Chat, Collab, Code panels
│               └── chat_mixin.py # Shared panel helpers
│
├── AUDIT.md                     # Full codebase audit
├── DEVLOG.md                    # Development log
├── PLAN.md                      # Project roadmap
├── pyproject.toml               # Package config
└── requirements.txt             # Dependencies
```

---

## Core Components

### 1. BaseAgent (`core/base_agent.py`)

Shared agent logic with utilities for all agents.

**Key Features**:
- `parse_tool_call()` — Parses `<tool>` and raw JSON tool calls
- `build_tool_schema()` — Generates tool schema for system prompts
- `exec_tool_call()` — Executes tool calls safely
- `compact()` — Summarizes history when context grows
- `_trim_history()` — Keeps history within limits
- `set_permission_callback()` — Permission system integration

### 2. ChatAgent (`core/chat_agent.py`)

Minimal tools agent for general conversation.

**Configuration**:
- Max turns: 3
- Max history: 20
- Tools: calculator, web_search, web_fetch, web_search_pipeline

**System Prompt**:
- Use web_search_pipeline for current events
- Give confident, clean answers
- No disclaimers or hedging
- Tool calls hidden from user

### 3. CollabAgent (`core/collab_agent.py`)

Collaborative agent with Observe-Plan-Act-Reflect loop.

**Configuration**:
- Max turns: 7
- Max history: 30
- Tools: All tools

**Workflow**:
1. **Observe** — Gather project context (files, git status)
2. **Plan** — Propose changes
3. **Act** — Execute tools with user permission
4. **Reflect** — Evaluate results

### 4. CodeAgent (`core/code_agent.py`)

Full-featured coding agent with project indexing.

**Configuration**:
- Max turns: 5
- Max history: 30
- Tools: All tools

**Features**:
- Project index for codebase search
- Permission system (allow/deny/ask)
- Streaming with thinking status

### 5. PlanAgent (`core/plan_agent.py`)

Read-only agent for planning and analysis.

**Configuration**:
- Extends CodeAgent
- Permissions: write_file, edit_file, run_command denied

### 6. Orchestrator (`core/orchestrator.py`)

Task classification and routing.

**Classification**:
- Heuristic pre-filter (greetings → chat, code patterns → coder)
- LLM classifier (qwen3:0.6b) for complex queries
- Categories: chat, coder, vision, research

**Memory Integration**:
- Queries ChromaDB for relevant memories
- Injects context into prompts

---

## Tools & Capabilities

### Calculator (`tools/calculator.py`)

Safe math evaluation using AST parsing.

**Features**:
- Supports +, -, *, /, //, %, **
- No `eval()` — uses safe AST parser
- Handles complex expressions

### File Operations (`tools/file_ops.py`)

File read/write with sandboxing.

**Features**:
- `read_file()` — Read file contents
- `list_directory()` — List directory contents
- Path validation with `_safe_path()`
- Symlink traversal prevention via `realpath()`

### Code Operations (`tools/code_ops.py`)

File editing, search, and command execution.

**Features**:
- `write_file()` — Create/overwrite files
- `edit_file()` — Replace text in files
- `grep_search()` — Regex search across files
- `run_command()` — Execute shell commands (shlex.split, blocked commands)
- `git_diff()` / `git_log()` — Git operations

**Security**:
- `shell=False` — Uses argument list
- Blocked commands: rm, del, format, shutdown, etc.

### Web Search (`tools/web_search.py`)

Web search and content fetching.

**Features**:
- `web_search()` — DuckDuckGo search with timelimit
- `web_fetch()` — URL content extraction (trafilatura)

### Search Pipeline (`tools/search_pipeline.py`)

ChatGPT-style search with query rewrite, multi-source, and synthesis.

**Pipeline**:
1. **Query Rewrite** — LLM rewrites query for better results
2. **Multi-Source Search** — SearXNG + DuckDuckGo
3. **Fetch Full Pages** — trafilatura for article extraction
4. **Clean Content** — Remove boilerplate, extract main text
5. **Rerank** — Freshness + authority + relevance scoring
6. **LLM Synthesize** — Multi-source answer generation

**Features**:
- Auto-detects Docker for SearXNG
- Falls back to DuckDuckGo if Docker unavailable
- ThreadPoolExecutor for parallel fetching

### Desktop (`tools/desktop.py`)

Screenshot and clipboard operations.

**Features**:
- `screenshot()` — Capture screen
- `clipboard_read()` — Read clipboard
- Gated by `desktop.enabled` config flag

### Telegram (`tools/telegram.py`)

Telegram bot integration.

**Features**:
- `telegram_send()` — Send messages
- Bidirectional bot via `cozmo telegram`

---

## TUI Interface

### Main Screen (`tui/screens/main.py`)

Root screen with sidebar, main panel, and footer.

**Components**:
- `Sidebar` — Chat history, new chat/task/session
- `MainPanel` — Tabbed content (Chat, Collab, Code)
- `AppFooter` — Token count, context %, settings

**Keyboard Shortcuts**:
- `Ctrl+Q` — Exit
- `Ctrl+L` — Clear chat
- `Tab` — Switch panels

### Chat Panel (`tui/widgets/panels/panel.py`)

General chat interface.

**Features**:
- Model selector per-chat
- File attachment via `@filename`
- Streaming with thinking status
- Markdown rendering for responses

### Collab Panel

Collaborative interface for multi-step tasks.

**Features**:
- Persistent agent across messages
- Permission modals for dangerous operations
- Context compaction

### Code Panel

Coding interface with mode toggle.

**Features**:
- Build/Plan mode toggle (Tab key)
- CodeAgent (Build) / PlanAgent (Plan)
- Project indexing

### Model Selector (`tui/screens/model_selector.py`)

Modal screen for model selection.

**Features**:
- Queries Ollama for available models
- Updates model per-panel
- Sanitized IDs for Textual

### Permission Modal (`tui/screens/permission.py`)

User confirmation for dangerous operations.

**Features**:
- Allow Once / Always / Deny
- Thread-safe via PermissionBridge
- Escape to deny

### File Picker (`tui/screens/file_picker.py`)

Directory navigation for file attachment.

**Features**:
- Browse directories
- Click to select, backspace to go up
- Escape to cancel

### Chat Manager (`tui/chat_manager.py`)

Chat persistence system.

**Features**:
- Creates `.md` files for each chat
- `index.json` for chat listing
- Auto-generates titles from first message

---

## Search Pipeline

### Overview

ChatGPT-style search with query rewrite, multi-source, and synthesis.

```
User Query
    │
    ▼
┌─────────────────┐
│  Query Rewrite  │  LLM rewrites for better results
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Multi-Source   │  SearXNG + DuckDuckGo
│    Search       │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Fetch Pages    │  trafilatura extraction
└─────────────────┘
    │
    ▼
┌─────────────────┐
│    Rerank       │  Freshness + authority + relevance
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  LLM Synthesize │  Multi-source answer generation
└─────────────────┘
    │
    ▼
  Answer + Sources
```

### SearXNG Integration

**Auto-Setup**:
- Detects Docker availability
- Auto-starts SearXNG container
- Falls back to DuckDuckGo if Docker unavailable

**Configuration**:
```toml
[search]
backend = "auto"  # "searxng", "duckduckgo", "auto"
searxng_url = "http://localhost:8080"
max_results = 10
max_fetch = 3
```

### Content Extraction

**trafilatura**:
- Best HTML→text extraction
- Removes boilerplate, ads, navigation
- Extracts main article content

**Fallback**:
- Regex-based HTML stripping
- Basic text extraction

### Reranking

**Scoring Factors**:
- **Query relevance** — Word overlap with title/snippet
- **Freshness** — Recent content preferred (7d, 30d, 365d)
- **Authority** — Official sites, major publishers
- **Content depth** — Full articles preferred over snippets

---

## Memory System

### Architecture

```
Short-Term Buffer (5 turns)
    │
    ▼ (auto-summarize)
ChromaDB Vector Store
    │
    ▼ (similarity search)
Context Injection
```

### Components

**MemoryManager** (`memory/manager.py`):
- Short-term buffer (5 turns)
- Auto-summarize via classifier LLM
- Store summaries in ChromaDB
- Query past before each turn

**ChromaStore** (`memory/chroma_store.py`):
- ChromaDB wrapper
- Embeddings via nomic-embed-text
- Similarity search

### Context Compaction

**Trigger**: History > 6 turns

**Process**:
1. Summarize conversation (3-4 sentences)
2. Replace history with summary
3. Preserve key facts and decisions

---

## Configuration

### Config File: `~/.cozmo/config.toml`

```toml
[models]
classifier = "qwen3:0.6b"    # Task routing
chat = "phi4-mini:3.8b"      # General conversation
coder = "ornith:9b"           # Coding tasks
vision = "qwen2.5vl:7b"      # Image analysis
research = "qwen3:8b"         # Deep analysis

[ollama]
url = "http://localhost:11434"

[search]
backend = "auto"              # "searxng", "duckduckgo", "auto"
searxng_url = "http://localhost:8080"
max_results = 10
max_fetch = 3

[desktop]
enabled = false               # Screenshot + clipboard

[telegram]
enabled = false
bot_token = ""

[agents]
primary = ["build", "plan"]

[agents.build]
model = "ornith:9b"

[agents.plan]
model = "ornith:9b"
permissions.write_file = "deny"
permissions.edit_file = "deny"
permissions.run_command = "deny"
```

### Context Window Estimation

**Default**: 4096 tokens

**Known Models**:
- phi4-mini: 4096
- qwen3: 4096
- gemma: 8192
- llama3: 8192
- mistral: 8192
- codellama: 16384
- deepseek: 16384
- ornith: 8192

---

## Installation & Setup

### Prerequisites

1. **Python 3.10+**
2. **Ollama** — Running locally with models pulled
3. **Docker** (optional) — For SearXNG

### Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/cozmo.git
cd cozmo

# Install in development mode
pip install -e .

# Initialize config
cozmo init
```

### Pull Ollama Models

```bash
ollama pull phi4-mini:3.8b      # Chat
ollama pull ornith:9b            # Coding
ollama pull qwen3:0.6b           # Classifier
ollama pull qwen2.5vl:7b         # Vision (optional)
ollama pull qwen3:8b             # Research (optional)
ollama pull nomic-embed-text     # Embeddings
```

### Start SearXNG (Optional)

```bash
# Auto-starts if Docker is available
# Or manually:
docker run -d -p 8080:8080 --name cozmo-searxng searxng/searxng
```

### Launch TUI

```bash
cozmo tui
```

---

## Development History

### Phase 1: Package Refactor (June 29, 2026)

- Created `pyproject.toml` with entry points
- Moved flat scripts into `cozmo/` package structure
- Implemented config loader, tool registry, CLI

### Phase 2: Orchestrator + Model Routing (June 29, 2026)

- Implemented task classification (heuristic + LLM)
- Model routing to specialist agents
- Conversation history management

### Phase 3: Memory, Tools, Telegram (June 29, 2026)

- ChromaDB memory with auto-summarization
- Web search, desktop tools, Telegram bot
- Fixed 22 bugs across 8 files

### Phase 4: TUI + Specialized Agents (July 3, 2026)

- Textual TUI with chat, collab, code panels
- Specialized agents (Chat, Collab, Code, Plan)
- Model selector, permission modals
- Chat persistence (.md files)
- Context compaction

### Phase 5: Search Pipeline (July 3, 2026)

- ChatGPT-style search pipeline
- Query rewrite, multi-source search
- Content extraction (trafilatura)
- Reranking and synthesis
- SearXNG auto-setup

### Bug Fixes (2026-07-03)

- Fixed `q` exit from input fields → `Ctrl+Q`
- Fixed permission modal Escape hang
- Fixed sidebar typo "Sessoions"
- Fixed ModelLabelClicked crash
- Fixed CodeInput ToggleMode
- Fixed tool call JSON leaking to user
- Fixed outdated web search results

### Security Fixes (2026-07-03)

- Replaced `eval()` with safe AST parser
- Replaced `shell=True` with `shlex.split`
- Added symlink traversal prevention

### Architecture Cleanup (2026-07-03)

- Created BaseAgent with shared utilities
- Extracted ChatMixin for panel helpers
- Consolidated web tools
- Created AUDIT.md with full critique

---

## Known Issues & Future Work

### Known Issues

1. **Docker Desktop Startup**: If Cozmo launches before Docker Desktop initializes, SearXNG won't be available until Docker is ready.

2. **Model Selector**: Model changes don't take effect until next message (agent is created per-message).

3. **Context Window**: Token count is estimated, not exact.

### Future Work (Phase 6+)

1. **Consolidate CLI/TUI**: Remove dead code, unify paths
2. **Custom Agents**: User-defined agents via markdown files
3. **File Autocomplete**: `@` file attachment with fuzzy search
4. **Token/Cost Display**: More accurate token counting
5. **Streaming Improvements**: Faster token delivery
6. **Search Optimization**: Cache results, parallel queries
7. **Mobile Support**: Responsive TUI layout
8. **Plugin System**: Load custom tools and agents

---

## Summary

Cozmo is a fully functional local AI agent with:

- **4 Specialized Agents**: Chat, Collab, Code, Plan
- **9+ Tools**: Calculator, file ops, web search, code ops, desktop, Telegram
- **Search Pipeline**: ChatGPT-style with query rewrite, multi-source, synthesis
- **Memory System**: ChromaDB-backed, auto-summarizes, persists
- **Rich TUI**: Textual interface with streaming, permissions, model selector
- **Fully Local**: No cloud dependency, runs on Ollama

**Status**: Production-ready for personal use. Phase 4 complete.

---

*Last updated: July 3, 2026*
