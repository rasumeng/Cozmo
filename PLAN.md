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

cozmo code                    cozmo serve
    │                              │
CodeAgent                    FastAPI WebUI
 ├── Project index (Chroma)    ├── POST /chat
 ├── Code tools (write,        ├── WS /stream
 │   edit, grep, git, cmd)     ├── Settings page
 └── Context retrieval         └── Mobile-responsive
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
├── cli.py                   # main + code + serve + config subcommands
├── config.py                # TOML loader, DEFAULT_CONFIG
├── config_cli.py            # cozmo config set/show/reset
├── telegram_bot.py
├── webui.py                 # cozmo serve — FastAPI + static HTML
├── core/
│   ├── agent.py             # specialist prompts + tool execution loop
│   ├── code_agent.py        # extends Agent: project index, code tools
│   └── orchestrator.py      # classifier + router + memory injection
├── tools/
│   ├── __init__.py           # tool registry + decorator
│   ├── calculator.py
│   ├── file_ops.py
│   ├── code_ops.py           # write_file, edit_file, grep, run_cmd, git
│   ├── web_search.py
│   ├── desktop.py            # screenshot (with vision), clipboard
│   └── telegram.py
├── memory/
│   ├── __init__.py
│   ├── manager.py
│   └── chroma_store.py
```

## Phases

### Phase 1 — Core ✅
- Package structure, pyproject.toml, pip-installable
- CLI: `cozmo init`, `cozmo run`
- Tool registry, calculator, file_ops

### Phase 2 — Orchestrator ✅
- Heuristic + LLM classifier
- Task routing to specialist models
- Conversation history

### Phase 3 — Memory + Tools ✅
- ChromaDB memory with auto-summarization
- web_search, desktop (screenshot + clipboard), Telegram
- Cozmo Telegram bot
- Specialist model routing (chat/coder/vision/research)

### Phase 4 — Cozmo Code (current)
**Goal**: `cozmo code` — dedicated coding session like OpenCode/Claude Code.

**CLI**:
```bash
cozmo code                          # interactive coding session in CWD
cozmo code /path/to/project         # start session in specific dir
cozmo code "refactor this function" # single-shot
cozmo code init                     # index project into Chroma
```

**New tools** (`tools/code_ops.py`):
| Tool | Description | Safety |
|------|-------------|--------|
| `write_file(path, content)` | Create/overwrite file | ✅ always allowed |
| `edit_file(path, old_text, new_text)` | Surgical text replacement | ✅ always allowed |
| `grep_search(pattern, path=".")` | Regex search across files | ✅ always allowed |
| `run_command(command)` | Execute shell command | ❌ gated (default false) |
| `git_diff()` | Show unstaged diff | ✅ always allowed |
| `git_log(lines=10)` | Show recent commits | ✅ always allowed |

**Command execution flow** (when enabled):
1. Agent proposes command: `run_command("rm -rf /")`
2. **Prompt user**: "Allow Once" / "Allow Always" / "Deny"
3. "Allow Always" → whitelist command or session
4. Result returned to agent

**Project index**:
- `cozmo code init` walks CWD recursively
- Respects `.gitignore`
- Splits source files into chunks
- Stores in Chroma collection `project_index`
- On each query: retrieve relevant snippets → inject as context
- Extensions: `.py`, `.js`, `.ts`, `.rs`, `.go`, `.md`, `.toml` (configurable)

**Model**: ornith:9b (256K context — can hold entire small projects)

**Memory**: shares Chroma with `cozmo run` — coding context + conversation context are unified.

### Phase 5 — Config CLI
```bash
cozmo config set models.chat "phi4-mini:3.8b"
cozmo config set desktop.enabled true
cozmo config show
cozmo config reset
```
Backed by `tomllib`/`tomli_w`. No manual TOML editing needed.

### Phase 6 — Obsidian Memory (Read-Only)
**Default**: Chroma backend unchanged.

**Optional backend** `type = "obsidian"`:
- On first run: walk Obsidian vault folder, index all `.md` files into separate Chroma collection `obsidian_vault`
- On each query: search both `cozmo_memories` + `obsidian_vault`, merge results
- Re-index on demand via `cozmo memory index`

**Config**:
```toml
[memory]
type = "chroma"                 # or "obsidian"
obsidian_vault_path = ""        # e.g. "C:/Users/you/Obsidian/MyVault"
```

**Future bidirectional**: Cozmo writes memory summaries as `.md` files with YAML frontmatter into the vault. You see/edit them in Obsidian.

### Phase 7 — WebUI
```bash
cozmo serve              # localhost:8080
cozmo serve --port 3000  # custom port
```

**Stack**: FastAPI + static HTML (single-file or htmx). Mobile-responsive.

**Endpoints**:
- `POST /chat` → Orchestrator.run(text)
- `WS /stream` → streaming token-by-token response
- `GET /history` → past conversations from Chroma
- `GET /settings` → mirror of `cozmo config show`

Phone-accessible on same network. Secure remote access via Tailscale later.

### Phase 8 — Advanced
- Full desktop control (pyautogui: mouse, keyboard, window management)
- Bidirectional Obsidian (Cozmo writes memory notes into vault)
- Hardware auto-detect → model recommendations (`cozmo doctor`)
- CI/CD + PyPI publishing

## Reference: OpenCode TUI Design

OpenCode's TUI (built on OpenTUI + SolidJS) provides a reference pattern:

**Layout**:
- Header bar: version, session status, agent mode, help
- Chat panel: scrollable message history with tool execution details
- Input area: prompt entry with `@` file autocomplete
- Status bar: status, modified files, token count, menu

**Key UX patterns**:
- `@` fuzzy file search in prompts
- `!` prefix runs shell command directly
- `/` slash commands (help, new, undo, redo, compact, export)
- `Ctrl+X` leader key for keyboard shortcuts
- Undo/redo via history stack
- `Ctrl+R` redraw screen if garbled

For Cozmo, start simple: `readline`-based input with `cozmo code` prefix commands. Add `@` file search and rich TUI later.

## Config

```toml
[models]
classifier = "qwen3:0.6b"
chat = "phi4-mini:3.8b"
coder = "ornith:9b"
vision = "qwen2.5vl:7b"
research = "qwen3:8b"

[code]
allow_commands = false

[memory]
type = "chroma"
obsidian_vault_path = ""

[desktop]
enabled = false

[telegram]
enabled = false
bot_token = ""
```
