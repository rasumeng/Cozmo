# Cozmo — Open-Source Local AI Assistant

Cozmo is a fully local, privacy-first AI assistant platform. Three modes with distinct personalities:

- **Chat** — Fast conversational AI. Talk to your local model. No overhead.
- **Agent** — Jarvis-style autonomous assistant. Plans, remembers, uses tools.
- **Code** — Dedicated coding agent with file ops, terminal, diff review.

Powered by [Ollama](https://ollama.ai). No cloud dependency.

```bash
pip install cozmo
cozmo webui     # → http://127.0.0.1:8765
```

---

## Architecture

```
User → Router → ─── Chat  → ChatHandler  → LLM
                 ├── Agent → AgentRuntime → Planner → Tools → Memory
                 └── Code  → CodeRuntime  → FileOps → Terminal
```

### Chat
Lightweight conversational mode. No planning, no tools, no memory queries. Just model + conversation history.

### Agent
Cognitive assistant with persistent state, structured planning, tool execution, memory, and reflection.

### Code
Engineering workspace with file system access, terminal commands, diff review, and testing.

---

## Features

### Platform
- **No cloud** — everything runs locally via Ollama
- **3 interfaces** — WebUI (primary), Textual TUI, CLI
- **Specialist model routing** — per-role model dispatch (chat/coder/research/vision)
- **Configurable** — `~/.cozmo/config.toml`, WebUI settings modal, `cozmo config` CLI
- **Streaming** — token-by-token with thinking indicators and tool call status

### Agent
- **ReAct loop** — native tool-calling with text-JSON fallback
- **Planning** — Plan generation with user approval flow (structured Planner in progress)
- **20+ tools** — file ops, code ops, web search, git, calculator, desktop, image analysis, knowledge CRUD, Telegram
- **MCP support** — connect external tool servers via Model Context Protocol (stdio)
- **Memory** — ChromaDB-backed, auto-summarizes, persists across sessions
- **Project index** — ChromaDB codebase index, respects `.gitignore`
- **Skills system** — SKILL.md files on disk, `@skill` trigger, bundled skill-creator
- **Permission system** — pattern-based allow/ask/deny, 5 permission modes
- **Background tasks** — scheduled agent runs, task queue
- **Subagent spawning** — `task()` tool with explore/scout/general types

### Chat
- Pure conversational — no tool overhead
- Fast path: model + history only
- File & image attachments
- Speech-to-text (Chrome native + fallback)
- Conversation persistence (Markdown files)

### Code
- Terminal panel with live tool output
- Diff panel with unified diffs
- File change cards with added/removed counts
- Project directory picker
- 5 permission modes (Manual, Plan, Accept edits, Auto, Bypass)

---

## Interfaces

| Interface | Command | Primary audience |
|-----------|---------|-----------------|
| **WebUI** | `cozmo webui` | General use — full GUI at localhost:8765 |
| **TUI** | `cozmo tui` | Terminal users — Textual full-screen |
| **CLI** | `cozmo run` / `cozmo code` | Quick queries, scripting |
| **Telegram** | `cozmo telegram` | Mobile chat — bidirectional bot |

---

## Memory

- ChromaDB with `nomic-embed-text` embeddings
- Short-term buffer (default 5 turns), auto-summarizes via LLM
- Summary + metadata stored in ChromaDB, queried before each turn
- Cross-session persistence in `~/.cozmo/memory/`
- Memory types: conversation, preference, project, fact
- Importance-scored retrieval (relevance × recency × frequency)
- **Planned:** LanceDB migration, Sentence Transformers, OKF classification

---

## Tool System

| Category | Tools |
|----------|-------|
| **File** | `read_file`, `write_file`, `edit_file`, `list_directory` |
| **Code** | `grep_search`, `run_command`, `execute_python`, `git_diff`, `git_log` |
| **Web** | `web_search`, `web_search_pipeline`, `web_fetch`, `fetch_url` |
| **Knowledge** | `read_knowledge`, `write_knowledge` (OKF frontmatter) |
| **Desktop** | `screenshot`, `clipboard_read`, `analyze_image` |
| **Math** | `calculator` (safe AST parser) |
| **Comm** | `telegram_send` |
| **Agent** | `task` (subagent spawner with explore/scout/general types) |

---

## MCP Integration

```toml
[mcp.servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "./data"]
```

- Stdio transport, client session management
- Tool auto-discovery, multiple concurrent servers
- MCP tools registered in `TOOL_REGISTRY` alongside built-in tools
- WebUI connector manager with catalog, status, diagnostics

---

## Quick Start

```bash
git clone https://github.com/rasumeng/cozmo.git
cd cozmo
pip install -e .
pip install -e .[telegram]  # optional

cozmo init                   # creates ~/.cozmo/config.toml
cozmo webui                  # launch at http://127.0.0.1:8765
cozmo tui                    # or Textual TUI
cozmo run "hello"            # or CLI quick query
```

Requires Python >= 3.10 and [Ollama](https://ollama.ai) running locally with models pulled.

---

## Package Structure

```
cozmo/
├── core/
│   ├── chat/            # ChatHandler — lightweight conversational path
│   ├── agent/           # AgentRuntime, Planner, AgentState, Reflector
│   ├── runtime.py       # Orchestrator (coordinates chat/agent/code dispatch)
│   ├── model_manager.py # Per-role model dispatch
│   ├── llm.py           # Ollama model wrapper with per-temperature caching
│   ├── router.py        # Mode router (chat/work/research/agent/vision)
│   ├── permissions.py   # Pattern-based allow/ask/deny
│   ├── tool_registry.py # Tool registration and LangChain wrapping
│   ├── mcp_host.py      # MCP client host (stdio transport)
│   └── providers/       # External provider integrations (MCP)
│
├── tools/               # 20+ registered tools
├── memory/              # ChromaDB store + memory manager
├── webui/               # React/TypeScript frontend (Vite + Tailwind)
├── webui_server.py      # FastAPI WebSocket + REST server
├── tui/                 # Textual TUI (full-screen terminal UI)
├── cli.py               # CLI entry point
├── config.py            # TOML config loader/saver
├── code_indexer.py      # ChromaDB project indexer
├── telegram_bot.py      # Telegram bot integration
├── default_skills/      # Bundled skills (skill-creator)
└── docker/              # Sandbox Dockerfile for execute_python
```

---

## Status

Cozmo is under active development. Current state:

| Layer | Status | Notes |
|-------|--------|-------|
| **Chat** | Early | Core architecture extracted. Dedicated ChatHandler in progress. |
| **Agent** | Alpha | ReAct loop + tools + basic memory works. Structured planning, state, reflection in progress. |
| **Code** | Alpha | File/code tools + terminal + diff review works. Dedicated CodeRuntime in progress. |
| **Memory** | Alpha | ChromaDB with basic importance scoring. LanceDB + ST + OKF pipeline planned. |
| **MCP** | Beta | Stdio transport works. Streaming, notifications, sampling planned. |

**Vision:** An open-source local AI assistant that can think, remember, use tools, and help users accomplish real-world goals.

---

## License

MIT
