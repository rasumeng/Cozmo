# Cozmo — Fully Local AI Agent

Fully on-device AI agent platform powered by Ollama. Specialist model routing, ChromaDB memory, WebUI, Textual TUI, and CLI. No cloud dependency.

```bash
pip install cozmo
cozmo webui     # → http://127.0.0.1:8765
```

Requires [Ollama](https://ollama.ai) running locally with models pulled.

---

## Features

- **No cloud** — everything runs locally via Ollama on your machine
- **3 interfaces** — WebUI (primary), Textual TUI, CLI
- **Specialist model routing** — lightweight classifier (MiniCPM5-1B) routes tasks to role-optimized models: chat, work (coder), research, vision, collab
- **5 workspace modes** — Chat, Work (Code), Collab, Research, Vision — each with tailored system prompts, tool gates, and temperatures
- **Memory** — ChromaDB-backed, auto-summarizes every 5 turns, persists across sessions
- **Search pipeline** — query rewrite, SearXNG multi-source search, full-page fetch, content extraction, LLM synthesis
- **Project index** — ChromaDB codebase index, respects `.gitignore`, all file types
- **20+ tools** — file ops, code ops, web search, git, calculator, desktop, image analysis, knowledge CRUD, Telegram
- **MCP support** — connect external tool servers via Model Context Protocol (stdio)
- **Skills system** — SKILL.md files on disk, `@skill` trigger, bundled skill-creator
- **Permission system** — pattern-based allow/ask/deny, per-agent overrides, 5 modes for code
- **File & image attachments** — upload, paste, drag-drop; vision routing for images
- **Speech-to-text** — Chrome native streaming + browser fallback via Google Speech API
- **Projects** — group conversations with shared context, create/import/select wizard
- **Telegram bot** — `cozmo telegram`, bidirectional, headless
- **Streaming** — token-by-token with thinking indicators and tool call status
- **Configurable** — `~/.cozmo/config.toml`, WebUI settings modal, `cozmo config` CLI

## Interfaces

| Interface | Command | Primary audience |
|-----------|---------|-----------------|
| **WebUI** | `cozmo webui` | General use — full GUI at localhost:8765 |
| **TUI** | `cozmo tui` | Terminal users — Textual full-screen |
| **CLI** | `cozmo run` / `cozmo code` | Quick queries, scripting (deprecated for tui/webui) |
| **Telegram** | `cozmo telegram` | Mobile chat — bidirectional bot |

## Architecture

```
User → WebUI / TUI / CLI / Telegram
         │
    CozmoRuntime (ReAct loop, 10 max steps)
     ├── Keyword pre-pass → short-circuits to research
     ├── LLM classifier (MiniCPM5-1B) → chat | work | research | collab | vision
     └── ModelManager → dispatches per-role Ollama model
           │
    Loop: model.invoke → tool_calls → permission gate → exec → feed back → answer
           │
    Tools (20+)          Memory (ChromaDB)
    MCP Host (external)  Project Index (ChromaDB)
    Skills (SKILL.md)    Search Pipeline (SearXNG)
```

### Modes

| Mode | Alias | Model | Temp | Tools | Max steps | Purpose |
|------|-------|-------|------|-------|-----------|---------|
| Chat | — | qwen3:8b | 0.6 | Minimal | 3 | Conversation, definitions |
| Work | Code | ornith:9b | 0.0 | All | 10 | Coding, file editing, debugging |
| Research | — | qwen3:8b | 0.2 | Search + calculator | 10 | Current events, web queries |
| Collab | — | qwen3:8b | 0.2 | All | 10 | Multi-step planned tasks |
| Vision | — | qwen2.5vl:7b | 0.2 | Minimal | 3 | Image/screenshot analysis |

## Tools

| Category | Tools |
|----------|-------|
| **File** | `read_file`, `write_file`, `edit_file`, `list_directory` |
| **Code** | `grep_search`, `run_command`, `execute_python`, `git_diff`, `git_log` |
| **Web** | `web_search`, `web_search_pipeline`, `web_fetch`, `fetch_url` |
| **Knowledge** | `read_knowledge`, `write_knowledge` (OKF frontmatter) |
| **Desktop** | `screenshot` (auto-analyses via vision model), `clipboard_read`, `analyze_image` |
| **Math** | `calculator` (safe AST parser, no eval) |
| **Comm** | `telegram_send` |

## WebUI Features

- **Code mode** — Right panel with Terminal/Diff/Trace tabs, inline file change cards, directory picker, 5 permission modes
- **Collab mode** — Plan approval flow, project management popup
- **Settings modal** — Model presets, tool permissions (allow/ask/deny), memory, skills, connectors
- **Projects** — Group conversations with shared context, create wizard, import from chat
- **Attachments** — File/image upload with thumbnails, paste from clipboard, auto-vision routing
- **Search** — Full-text across all conversations with snippet previews
- **Sidebar** — Pinned/Recent sections, inline rename, delete, context menu
- **Speech-to-text** — Dual path: native Chrome API or MediaRecorder + backend transcription
- **Purple theme** — Matching TUI color palette, Cozmo pixel-art sprite

## Memory

- ChromaDB with `nomic-embed-text` embeddings
- Short-term buffer (configurable, default 5 turns)
- Auto-summarizes via classifier LLM when buffer fills
- Summary + metadata stored in ChromaDB, queried before each turn
- Cross-session persistence in `~/.cozmo/memory/`

## Search Pipeline

1. **Query rewrite** — LLM reformulates for better recall
2. **SearXNG** — Self-hosted metasearch engine (Docker)
3. **Full-page fetch** — HTTPX + trafilatura content extraction
4. **Rerank** — By freshness, authority, relevance
5. **LLM synthesis** — Multi-source answer generation

Fallback: `web_search` (fast, DDGS backend) before full pipeline.

## Permission System

- Pattern-based: `fnmatch` globs on tool arguments
- Priority: session allowlist → agent overrides → global rules → default allow
- Interactive prompts: Allow Once / Always / Deny
- WebUI modes: Manual, Plan, Accept edits, Auto, Bypass
- `--auto` flag (CLI) for headless/non-interactive mode

## MCP Support

```toml
[mcp.servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "./data"]
```

- Stdio transport, client session management
- Tool auto-discovery via `tools.json`
- Multiple concurrent servers
- MCP tools registered in `TOOL_REGISTRY` alongside built-in tools

## Skills

Skills are `SKILL.md` files in `~/.cozmo/skills/`. Each skill has:
- YAML frontmatter: `name`, `description`
- Body: instructions consumed by the agent
- Optional subfolders: `scripts/`, `references/`, `assets/`
- Trigger in chat: `@skill <name>`

Bundled skills: `skill-creator` (meta-skill for creating new skills).

## Configuration

`~/.cozmo/config.toml` — auto-generated by `cozmo init`:

```toml
[models]
classifier = "openbmb/minicpm5:Q4_K_M"
chat = "qwen3:8b"
coder = "ornith:9b"
vision = "qwen2.5vl:7b"
research = "qwen3:8b"
max_tokens = 2048

[desktop]
enabled = false

[telegram]
enabled = false
bot_token = ""

[permissions]
write_file = "ask"
edit_file = "ask"
run_command = { "*" = "ask", "git *" = "allow", "dir *" = "allow" }

[mcp.servers]
# name = { command = "npx", args = ["..."] }
```

## Requirements

- Python >= 3.10
- [Ollama](https://ollama.ai) running locally
- Models pulled per your config (recommended: MiniCPM5-1B, qwen3:8b, ornith:9b, qwen2.5vl:7b)
- Optional: Docker + SearXNG for search pipeline
- Optional: ffmpeg for speech-to-text
- Optional: `python-telegram-bot` for Telegram (`pip install cozmo[telegram]`)

## Quick Start

```bash
git clone https://github.com/rasumeng/cozmo.git
cd cozmo
pip install -e .
pip install -e .[telegram]  # optional

cozmo init                   # creates ~/.cozmo/config.toml
cozmo webui                  # launch at http://127.0.0.1:8765
cozmo tui                    # or use the Textual TUI
cozmo run "hello"            # or CLI quick query
```

## Package Structure

```
cozmo/
├── core/               # Runtime, model manager, permissions, LLM, MCP, router
├── tools/              # 20+ registered tools
├── memory/             # ChromaDB store + memory manager
├── webui/              # React/TypeScript frontend (Vite + Tailwind)
├── webui_server.py     # FastAPI WebSocket + REST server
├── tui/                # Textual TUI (full-screen terminal UI)
├── cli.py              # CLI entry point (run, code, tui, webui, telegram, mcp, config)
├── config.py           # TOML config loader/saver
├── code_indexer.py     # ChromaDB project indexer
├── telegram_bot.py     # Telegram bot integration
├── default_skills/     # Bundled skills (skill-creator)
└── docker/             # Sandbox Dockerfile for execute_python
```

## Known Issues

- **SearXNG** requires Docker Desktop to be initialized before startup
- **Model changes** take effect on next message (agent created per-message)
- **Token counts** are estimated, not exact
- **CLI `run` / `code`** subcommands deprecated — use `tui` or `webui`
- **PyPI** package not yet published (`pip install cozmo` not working yet)

## License

MIT
