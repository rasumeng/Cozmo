# Cozmo — Local AI Agent

**Goal**: Fully local AI agent with elegant TUI, specialist model routing, and modular tool system. Every component UI-agnostic — TUI is just one frontend.

## Architecture

```
UI Frontend (Textual TUI / CLI / Telegram)
         │
     AgentRegistry
      └── Agent (Build | Plan | Custom)
           ├── System prompt (per-agent)
           ├── Tool registry
           ├── PermissionResolver (pattern-based gating)
           └── Project index (Chroma)
```

## Model Registry

| Task       | Model            | Size   | Role |
|------------|-----------------|--------|------|
| classifier | qwen3:0.6b      | 522MB  | Routes tasks to correct specialist |
| chat       | phi4-mini:3.8b  | 2.5GB  | General conversation, quick answers |
| coder      | ornith:9b       | 6.5GB  | Coding, debugging, scripts |
| vision     | qwen2.5vl:7b    | 6.0GB  | Screenshot/image analysis |
| research   | qwen3:8b        | 5.2GB  | Web search, deep analysis, summaries |

## Directory Structure

```
cozmo/
├── __init__.py
├── cli.py                   # main + code + config subcommands
├── config.py                # TOML loader, DEFAULT_CONFIG
├── config_cli.py            # cozmo config set/show/reset
├── code_indexer.py          # Chroma project indexer
├── telegram_bot.py
├── core/
│   ├── agent.py             # Base Agent: tool loop, <tool> JSON parsing
│   ├── code_agent.py        # Build agent: project index, tool exec, permissions
│   ├── plan_agent.py        # Plan agent: read-only, blocks writes
│   ├── agent_registry.py    # Create/list/switch agents, custom markdown agents
│   ├── permissions.py       # PermissionResolver: fnmatch patterns, --auto
│   ├── orchestrator.py      # Classifier + router + memory injection
│   └── llm.py               # OllamaModel wrapper
├── tui/
│   ├── __init__.py           # CozmoApp export
│   ├── app.py                # CozmoApp (Textual App)
│   ├── sprite.py             # PNG → ANSI half-block art
│   └── widgets/
│       ├── __init__.py
│       └── header.py         # CozmoHeader with sprite + badges
├── tools/
│   ├── __init__.py           # Tool registry + @register_tool()
│   ├── calculator.py
│   ├── file_ops.py
│   ├── code_ops.py           # write_file, edit_file, grep, run_cmd, git
│   ├── web_search.py
│   ├── desktop.py            # screenshot, clipboard
│   └── telegram.py
├── memory/
│   ├── __init__.py
│   ├── manager.py
│   └── chroma_store.py
```

## Phases

### Phase 1 — Package scaffold ✅
- pyproject.toml, pip-installable, CLI skeleton
- `cozmo init`, `cozmo run`

### Phase 2 — Orchestrator ✅
- Heuristic + LLM classifier, task routing to specialist models
- Conversation history

### Phase 3 — Memory + Tools ✅
- ChromaDB memory, auto-summarization
- web_search, desktop, Telegram, specialist routing

### Phase 4 — Cozmo Code ✅
- `cozmo code` subcommand with CodeAgent
- code_ops tools: write_file, edit_file, grep, run_command, git
- ProjectIndex: walks CWD, chunks files, stores in Chroma `project_index`
- ChromaStore API: `add_texts(texts, metadatas)`, `similarity_search(query, k)`
- Tool `<tool>` JSON format (reliable with local Ollama models)
- Command gating: Allow Once / Allow Always / Deny

### Phase 5 — UX improvements ✅
- `!cmd` shell passthrough, `/` slash commands, `@file` autocomplete
- Status bar `[model:ornith:9b turns:3]`
- `cozmo config show|set|reset` with dot-notation keys
- `/compact` context compaction
- prompt_toolkit integration: FileHistory, completions, key bindings

### Phase 6 — Multi-agent system ✅
- AgentRegistry: create/list/switch agent instances
- PlanAgent: read-only, blocks write_file/edit_file/run_command
- Custom markdown agents (.cozmo/agents/*.md)
- F2 keybinding for agent cycling
- `/agent`, `/agents` commands

### Phase 7 — Permission system ✅
- PermissionResolver: fnmatch pattern matching, session allowlist
- `resolve(tool, args, agent) → allow|deny|ask`
- Interactive prompt: once / always / deny
- Per-agent permission overrides (PlanAgent = deny writes)
- `--auto` flag for non-interactive mode
- Pattern-based bash rules (`git *` → allow, `*` → ask)

### Phase 8 — Textual TUI ✅
**Goal**: Replace prompt_toolkit loop with full-screen Textual TUI.

**Completed 2026-07-02** via standalone [CozmoTUI](https://github.com/rasumeng/CozmoTUI) repo merged back.

**Done**:
- Standalone CozmoTUI built in separate repo (7/1-7/2/2026)
- Merged into main Cozmo project as `cozmo.tui` package
- `screens/main.py` — MainScreen: sidebar + panels + footer layout
- `screens/settings.py` — Settings modal (theme, model info)
- `widgets/sidebar.py` — Tabbed sidebar: Chat / Collab / Code
- `widgets/footer.py` — Bottom toolbar: Collapse / Settings / Exit
- `widgets/input.py` — Chat input with send button + attach placeholder
- `widgets/code_input.py` — Code input with Build/Plan mode toggle (Tab)
- `widgets/panels/panel.py` — ChatPanel, CollabPanel, CodePanel, MainPanel
- `widgets/sprite.py` — CozmoTUI's sprite renderer (port of old tui/sprite.py)
- `themes.py` — Custom "cozmo" theme (dark, purple accents)
- `css/app.tcss` — Full stylesheet for all widgets
- `cli.py` — `cozmo tui` subcommand launcher
- `textual>=8.2` added to pyproject.toml

**Wiring not yet done** (next phase):
- ChatPanel → Orchestrator (chat model)
- CollabPanel → Orchestrator (research model)
- CodePanel → AgentRegistry (coder model)
- Streaming, tool cards, status bar updates

**Not breaking**:
- `cozmo code "query"` (single-shot) stays on fast prompt_toolkit path
- AgentRegistry, CodeAgent, PermissionResolver unchanged
- Telegram bot, `cozmo run` CLI unchanged

### Phase 9 — Streaming + Tool Cards
- Token-by-token streaming via worker
- Tool execution cards with live status
- `/details` toggle for raw tool JSON
- `/thinking` toggle for reasoning blocks

### Phase 10 — Polish
- Theme system (tokyonight, catppuccin, etc.)
- Chat export to markdown
- `/undo`/`/redo` via git stash
- Session management UI
- Command palette (Ctrl+P)

## Config

```toml
[models]
classifier = "qwen3:0.6b"
chat = "phi4-mini:3.8b"
coder = "ornith:9b"
vision = "qwen2.5vl:7b"
research = "qwen3:8b"

[agents]
primary = ["build", "plan"]

[agents.build]
model = null
permissions = {}

[agents.plan]
model = null
permissions = {write_file = "deny", edit_file = "deny", run_command = "deny"}

[permissions]
write_file = "ask"
edit_file = "ask"
[permissions.run_command]
"*" = "ask"
"git *" = "allow"
"dir *" = "allow"

[memory]
type = "chroma"

[desktop]
enabled = false

[telegram]
enabled = false
bot_token = ""
```

## Design Principles

1. **UI-agnostic core**: Agent logic never imports from `tui/`. TUI is a frontend, not the system.
2. **One layer at a time**: Each phase builds on the previous without refactoring it.
3. **Single-shot still fast**: `cozmo code "query"` bypasses TUI entirely — no rendering overhead.
4. **All decisions in config.toml**: No hardcoded paths, models, or permissions.
5. **Fail toward simplicity**: If Textual breaks, fallback is prompt_toolkit Layout, not raw curses.
