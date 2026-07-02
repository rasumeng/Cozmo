# Cozmo Devlog

_Chronological development notes. Each entry = date + what changed + why + decisions._

---

### 2026-06-29 — Project inception

**Context**: User wants fully local AI agent as alternative to paid agentic AI services (Claude Code, Cursor, etc.). Runs on Windows 11, Ollama backend, limited GPU — must be model-efficient.

**Existing codebase**:
- `main.py` — basic ReAct agent with calculator tool (phi3 via langchain)
- `rag_local.py` — PDF ingestion → ChromaDB → RAG chain with qwen3:8b
- `tools.py` — empty (placeholder for tool system)
- `rag_local.py` had 2 bugs: `OllamaEmbeddings()` positional arg (fixed), `vectorstore.persist()` removed (Chroma auto-persists now)

**Decisions**:
- Keep langchain for Phase 1 (quick wins), decouple by Phase 3
- Config format: TOML (`tomllib` stdlib in Python 3.11+)
- Messenger: Telegram preferred (simpler, smaller deps). Discord as optional plugin later.
- Desktop control: read-only Phase 1-3 (screenshot, clipboard). Full autonomy Phase 4+.
- First public release after Phase 3 (core + orchestrator + memory + Telegram)

**Project structure planned** — see [PLAN.md](PLAN.md)

---

### 2026-06-29 — Phase 1: Package refactor

**Changes**:
- Created `pyproject.toml` with `[project.scripts]` entry point → `cozmo` CLI
- Moved flat scripts into `cozmo/` package structure
- `config.py` — TOML loader/saver for `~/.cozmo/config.toml`
- `tools/__init__.py` — `TOOL_REGISTRY` + `@register_tool()` decorator
- `tools/calculator.py` — moved from `main.py`, registered via decorator
- `cli.py` — argparse: `cozmo init` + `cozmo run [query]`
- `__main__.py` — allows `python -m cozmo`

**Bugs fixed during refactor**:
- `pyproject.toml`: typos in deps (`lancgchain`→`langchain`), wrong build backend, missing package discovery config
- `config.py`: indent bug in `load()`, wrong file mode (`"w"`→`"wb"` for binary)
- `cli.py`: missing `interactive_session()` stub, missing `__main__` guard
- `calculator.py`: placeholder `...` → real eval impl

**Status**: `pip install -e .` → `cozmo init` generates config. `cozmo run "query"` starts interactive session.

### 2026-06-29 — Phase 1: Tool execution + agent loop

**Changes**:
- `core/agent.py`: Added `_tool_help()` generates live tool list from registry. Added `_run_tool()` parses `TOOL: func(arg=val)` pattern and executes registered function. `run()` now does tool-calling loop — LLM responds → tool parsed → tool executed → result fed back → final answer.
- `tools/__init__.py`: Added `from . import calculator, file_ops` so decorators populate registry on import.
- `tools/calculator.py`: docstring clarified for LLM prompting.

**Fixed bug**: `TOOL_REGISTRY` was empty because tool modules were never imported. The `@register_tool()` decorator only runs on import. Added explicit imports in `__init__.py`.

**Working**:
- `cozmo run "what is 33 * 12"` → LLM calls `calculator(expression="33 * 12")` → returns 396
- `cozmo run "list files"` → LLM calls `list_directory(path=".")` → returns dir contents, LLM summarizes
- Interactive mode: `cozmo run` → user types questions → tool calls work inline

---

### 2026-06-29 — Phase 2: Orchestrator + model routing

**Changes**:
- `core/orchestrator.py` — NEW: hybrid classifier (heuristic + qwen3:0.6b LLM), model router, conversation history manager, fallback chain
- `core/agent.py` — `__init__` takes `model_name: str` param, `run()` accepts pre-built prompt with history
- `cli.py` — creates `Orchestrator` instead of `Agent`
- `config.py` — added `classifier` model to `DEFAULT_CONFIG`
- Models updated to match available Ollama pulls: fast=`phi4-mini:3.8b`, balanced=`qwen3:8b`, heavy=`qwen2.5-coder:14b`, classifier=`qwen3:0.6b`

**Bugs fixed**:
- `orchestrator.py`: Missing comma in `.get("classifier" "qwen3:0.6")` → Python concatenated strings silently. `self.classifier_model` vs `self.classifier` mismatch. `_add_to_hhistory` typo. `tiers[start]` instead of `tiers[start:]`. `"qwuen3.7b"` typo.
- Old `config.toml` missing `classifier` key — regenerated.
- Config models didn't match available Ollama models (`phi3:3.8b` not pulled, `phi-4-mini:latest` not pulled).

**Routing verified**:
- "hello" → heuristic simple → phi4-mini:3.8b ✅
- "list files" → LLK classifier moderate → qwen3:8b ✅
- "write python script..." → heuristic complex (regex match) → qwen2.5-coder:14b ✅

---

### 2026-06-29 — Phase 3: Memory, web search, desktop, Telegram

**Added**:
- `memory/chroma_store.py` — class-based ChromaDB wrapper with embeddings via `nomic-embed-text`
- `memory/manager.py` — `MemoryManager`: short-term buffer (5 turns), auto-summarize via classifier LLM, store summary in Chroma, query past before each turn
- `tools/web_search.py` — `web_search(query)` via `ddgs` (DuckDuckGo)
- `tools/desktop.py` — `screenshot()` + `clipboard_read()`, gated by `desktop.enabled` config flag (default false)
- `cozmo/telegram_bot.py` — async Telegram bot with `/start`, `/help`, text message handler → Orchestrator
- `tools/telegram.py` — `telegram_send(chat_id, message)` tool, registered when bot is active
- `cli.py` — `cozmo telegram` subcommand, `_safe_print()` for Windows console encoding

**Fixed bugs (22 total across 8 files)**:
- `chroma_store.py`: `clinet`→`client` typo, `add()` missing `ids` param
- `manager.py`: `cozmo_memoruies`→`cozmo_memories`, `add_to_short_term`→`add_interaction` mismatch, `assitant`→`assistant`, `self.chroma`→`self.chroma_store`
- `orchestrator.py`: missing `from pathlib import Path`, `_build_prompt(user_input)` → `_build_prompt(user_input, memories)`
- `tools/__init__.py`: missing imports for `web_search`, `desktop`, `telegram`
- `web_search.py`: wrong import (`DuckDuckGoSearch` → `DDGS`), `resutls` typo, switched from `duckduckgo_search` to `ddgs` package (no deprecation warnings)
- `cli.py`: `from.telegram_bot` → `from .telegram_bot` (missing spaces)
- `telegram_bot.py`: `Update.MESSAGE` → `[]` (API change)
- `agent.py`: regex `TOOL:` didn't match `TOOLS:`, follow-up prompt missing original context
- Console: `UnicodeEncodeError` on Windows (emojis) — added UTF-8 reconfigure + `_safe_print()`

**Verified**:
- ChromaStore: add_texts + similarity_search ✅
- MemoryManager: 5-turn auto-summary + cross-session recall ✅
- Calculator: "what is 255 / 5" → 51 ✅
- Web search: "search AI news" → real headlines ✅
- Clipboard: "read clipboard" → returns clipboard content ✅
- Screenshot: gated by config flag ✅
- Telegram: code complete (no token to test)

---

### 2026-06-29 — Specialist model routing refactor

**Changed model tier system (fast/balanced/heavy) to task-specific specialists**:

| Old | New | Model |
|-----|-----|-------|
| fast | chat | phi4-mini:3.8b |
| balanced | research | qwen3:8b |
| heavy | coder | ornith:9b |
| — | vision (new) | qwen2.5vl:7b |
| classifier | classifier | qwen3:0.6b |

**Files changed**:
- `config.py` — replaced `fast`/`balanced`/`heavy` with `chat`/`coder`/`vision`/`research` + `classifier`
- `core/orchestrator.py` — `_classify()` now outputs `chat|coder|vision|research`. Heuristic pre-filter extended with vision keyword matching. `_get_model_name()` maps task type directly.
- `core/agent.py` — added `SPECIALIST_PROMPTS dict` with tailored system prompts per task type. Agent accepts `task_type` param, applies specialist prompt.
- `tools/desktop.py` — `screenshot()` now auto-analyzes via vision model (qwen2.5vl:7b) using Ollama API. Added `analyze_image(path, prompt)` tool. Both return text descriptions, not raw image data.

**New models pulled**: `ornith:9b` (5.6GB), `qwen2.5vl:7b` (6.0GB)

**Design rationale**: paid agents (Claude Code, Cursor) use task-specific models. Cozmo mirrors this locally — each specialist trained/optimized for its domain. Vision analysis happens server-side within the tool, so any agent can describe images without needing multimodal capability itself.

**Verified**:
- "hello" → heuristic chat → phi4-mini ✅
- "write palindrome function" → heuristic coder (regex) → ornith:9b ✅
- Coding output: clean, working Python with explanation ✅
- Config regenerated with all 5 model keys ✅

---

### 2026-06-29 — Phase 4 planning: Cozmo Code, Config CLI, Obsidian, WebUI

**Planning session. No code changes.**

**Decisions**:
- `cozmo code` — separate subcommand, not a flag. Interactive coding session in CWD.
- `code.allow_commands = false` by default. Safe until user opts in.
- Command execution uses OpenCode-style prompt: "Allow Once" / "Allow Always" / "Deny"
- `cozmo code init` walks CWD, respects `.gitignore`, indexes into Chroma `project_index`
- ornith:9b with 256K context — can hold entire small projects. Chunking if needed later.
- Memory shared between `cozmo run` and `cozmo code` (unified Chroma).

**Obsidian memory**: read-only first (index vault `.md` files into Chroma). Bidirectional later (Cozmo writes `.md` files with YAML frontmatter into vault). Config option: `[memory] type = "obsidian"`.

**Config CLI**: `cozmo config set/show/reset` — no manual TOML editing.

**WebUI**: FastAPI + static HTML. `cozmo serve` on localhost:8080. Mobile-responsive. Phone-accessible on same network. After Cozmo Code + Config CLI.

**OpenCode TUI reference** researched for future Cozmo TUI. Key patterns: `@` file search, `!` commands, `/` slash commands, undo/redo, status bar.

**Full roadmap**:
| Phase | What | When |
|-------|------|------|
| 4 | Cozmo Code | Next session |
| 5 | Config CLI | After code |
| 6 | Obsidian read-only | Soon |
| 7 | WebUI | Later |
| 8 | Full desktop, bidirectional Obsidian, PyPI | Eventually |

See [PLAN.md](PLAN.md) for details.

---

### 2026-06-30 — Phase 4: Cozmo Code

**Context**: Dedicated coding session like OpenCode/Claude Code. Started by reviewing PLAN.md, then building incrementally.

**New files**:
- `tools/code_ops.py` — 6 code tools: `write_file`, `edit_file`, `grep_search`, `run_command` (gated), `git_diff`, `git_log`
- `code_indexer.py` — Project walker → chunks → Chroma `project_index` collection. Respects `.gitignore`. 41 files indexed in Cozmo's own repo.
- `core/code_agent.py` — Extends `Agent`: project index context injection, `<tool>` JSON block parsing, 5-turn followup loop, command gating

**Changes**:
- `core/agent.py` — Upgraded from `TOOL: func(arg=val)` regex to `<tool>{"tool":"name","args":{...}}</tool>` JSON block format. Python 3.10-3.12 compat (nested f-string → `.format()`).
- `cli.py` — Added `cozmo code [query] --path --init` subcommand
- `config.py` — Added `[code]` section with `allow_commands` flag
- `tools/__init__.py` — imports `code_ops`

**Architecture decisions**:
- Tool format: `<tool>` JSON blocks (model outputs structured JSON between XML tags → parsed → executed → result fed back)
- Dedicated `project_index` Chroma collection (separate from memory)
- All file types indexed by default (not just source extensions)
- Command gating via `input()`: Allow Once / Allow Always / Deny
- Tool followup loop with max 5 iterations to prevent infinite tool chaining

**Bugs found & fixed during typing**:
- `code_ops.py`: `@register_tool`(no parens) → `@register_tool()` (6 occurrences — without parens, the decorator factory receives the function as `name` param, replaces it with inner `decorator`, never registers)
- `code_ops.py`: `endocoding`→`encoding`, `byters`→`bytes`, `notfoundin`→`not found in`
- `code_ops.py`: `__COMMAND_ALLOWED` vs `_COMMAND_ALLOWED` mismatch
- `code_indexer.py`: reversed method call (`add_document` → `add_texts`), wrong method name (`query` → `similarity_search`), dict access via `.attr` instead of `["key"]`, `collection_name` had trailing colon, `encoding="=utf-8"` extra `=`, `appened` typo
- `code_agent.py`: comma→period in `.resolve()`, `Project`→`ProjectIndex`
- `agent.py`: nested f-strings not supported in Python 3.10-3.11
- `<tool>` regex: `{.*?}` non-greedy stops at first `}`, breaks nested JSON → changed to `(.*?)` capturing everything between tags

**Verified**:
- `cozmo code --init` → Indexed 41 files ✅
- `cozmo code "list python files"` → tool call + directory listing + proper answer ✅
- `cozmo code --path . "line count"` → command gating prompts ✅
- Tool follows up on denied commands gracefully ✅

---

### 2026-06-30 — Phase 5: Quick UX wins

**Context**: Upgrading Cozmo's raw readline loop with OpenCode-inspired UX patterns — no TUI framework yet, just high-impact improvements.

**New file**:
- `config_cli.py` — `cozmo config show` (tree output), `set <dot.key> <value>` (auto-type parsing), `reset` (regenerate defaults)

**Changes**:
- `cli.py` — Full rewrite of `coding_session()`:
  - **`!cmd`** passthrough: lines starting with `!` run as shell command, output prints directly
  - **`/commands`**: `/help`, `/new` (clear session), `/exit`, `/compact`
  - **`@file` autocomplete**: `FileCompleter` class using `prompt_toolkit` — fuzzy-match files on `@` prefix, 20-result limit, caches file list per session
  - **Status bar**: `[model:ornith:9b turns:3]` line before each prompt
  - **`prompt_toolkit`** integration: `FileHistory` persistence, `Completer` subclass, arrow-key history navigation
- `core/code_agent.py` — Added `compact()` method: summarizes conversation history via LLM, clears history, injects summary as `[compacted context]` message
- `pyproject.toml` — Added `prompt-toolkit` dependency

**Design decisions**:
- `prompt_toolkit` over raw `input()` — enables autocomplete, history, and future key binding customizations with zero terminal compatibility issues
- `@file` completer uses `complete_while_typing=True` — shows suggestions as you type after `@`
- `config set` uses dot-notation (`models.coder qwen3:8b`) with auto-type parsing (int → float → str)
- `/compact` runs asynchronously — summarizes what was done, doesn't lose information
- PromptSession only created in interactive mode (single-shot queries skip it to avoid `NoConsoleScreenBufferError`)

**Dependency added**: `prompt-toolkit` (pure Python, no binary deps)

**Verified**:
- `cozmo code "count python files"` — single-shot works ✅
- `cozmo config show` — prints tree ✅
- `cozmo config set display.history 10` — writes to TOML ✅
- `cozmo config reset` — restores defaults ✅
- `cozmo code --help` — new flags shown ✅
- All modules compile clean ✅

---

### 2026-06-30 — Phase 6: Multi-agent system

**Context**: OpenCode-inspired agent switching (Build ↔ Plan) plus custom agents via markdown files. Layered on top of Phase 5 UX improvements.

**New files**:
- `core/agent_registry.py` — AgentRegistry class: loads agent configs from TOML, discovers `.cozmo/agents/*.md`, creates agent instances, provides `switch()`, `current`, `list()` interface
- `core/plan_agent.py` — PlanAgent extends CodeAgent: hard-blocks `write_file`/`edit_file`/`run_command`, overriding `_exec_tool_call` to return `"Plan agent cannot modify files. Only read, search, and analyze."`

**Changes**:
- `cli.py` — Full rewrite of `coding_session()`:
  - Uses AgentRegistry instead of direct CodeAgent instantiation
  - F2 keybinding cycles agents (Build→Plan→Review→Build)
  - Status bar shows active agent name with turn count
  - `/agent` shows current agent, `/agents` lists all with `←` indicator
  - `/new` reinitializes the registry
  - `@file` autocomplete, `!cmd`, `/` commands all work across agents
- `config.py` — Added `[agents]` section to DEFAULT_CONFIG:
  ```toml
  [agents]
  primary = ["build", "plan"]
  [agents.build]
  model = null  # falls back to models.coder
  permissions = {}
  [agents.plan]
  model = null
  permissions = { edit = "deny", bash = "deny" }
  ```
- `core/code_agent.py` — `__init__` now accepts optional `agent_config` dict for per-agent overrides

**Custom markdown agents**:
- `.cozmo/agents/review.md` created as functional test agent
- Frontmatter supports: `name`, `description`, `model`, `permissions`, `---` body becomes system prompt
- Auto-discovered on session start, appended to primary agent list

**Architecture decisions**:
- Agent instances maintain independent `history` — switching agents preserves each conversation
- F2 chosen over Tab to avoid conflict with prompt_toolkit autocomplete
- PlanAgent is a thin override, not a full separate class — inherits all CodeAgent behavior except blocked tools
- Custom agents are always "primary" (Tab-cycleable) — no subagent distinction yet
- The `review` test agent left in place as a real, usable agent

**Verified**:
- Build → Plan → Build cycling via F2 ✅
- PlanAgent blocks write_file: "Plan agent cannot modify files..." ✅
- PlanAgent allows read_file: passes through ✅
- BuildAgent allows write_file: executes ✅
- Custom review agent auto-loaded from `.cozmo/agents/review.md` ✅
- `cozmo code "list files"` — single-shot with Build agent ✅
- All modules compile clean ✅

---

### 2026-06-30 — Phase 7: Permission system

**Context**: Replace ad-hoc `run_command` gating and PlanAgent hardcoded deny with a unified `PermissionResolver` supporting pattern matching, session allowlists, per-agent overrides, and `--auto` non-interactive mode.

**New files**:
- `core/permissions.py` — `PermissionResolver` class:
  - `resolve(tool, args, agent) -> "allow"|"deny"|"ask"`: checks agent overrides -> global rules -> defaults to allow
  - `prompt(tool, args, agent) -> bool`: interactive prompt with once/always/deny; always added to session allowlist
  - Pattern matching via `fnmatch`: `{"run_command": {"git *": "allow", "*": "ask"}}`
  - `_input_key()` maps tool+args to a string key: `run_command` -> command, `write_file`/`edit_file` -> path, others -> tool name
  - `_session_allow: set[str]` persists approved patterns across the session

**Changes**:
- `core/code_agent.py`:
  - `__init__` now creates `PermissionResolver(cfg, auto=self.auto)`
  - `_exec_tool_call` checks `self._perms.resolve()` before executing tool
  - Decision "deny" -> returns `"Error: permission denied — {tool} not allowed for {agent}"`
  - Decision "ask" -> calls `self._perms.prompt()`; user denies -> same error
  - Added `agent_name` property returning `"build"`
  - New `auto` param (from agent_config or caller)
- `core/plan_agent.py`:
  - Simplified: no more hardcoded `_exec_tool_call` override
  - Sets `agent_config["permissions"] = {"write_file":"deny", "edit_file":"deny", "run_command":"deny"}`
  - Permission resolver handles the blocking automatically
  - `agent_name` property returns `"plan"`
- `core/agent_registry.py`:
  - `__init__` now accepts `auto: bool`
  - Passes `auto` to `_create()` and into agent constructors + custom agent agent_config
- `tools/code_ops.py`:
  - Removed `_COMMAND_ALLOWED`, `_COMMAND_WHITELIST` globals
  - `run_command()` no longer gates itself — permission check happens upstream
- `config.py`:
  - Added `[permissions]` section to DEFAULT_CONFIG:
    ```toml
    [permissions]
    write_file = "ask"
    edit_file = "ask"
    [permissions.run_command]
    "*" = "ask"
    "git *" = "allow"
    "dir *" = "allow"
    ```
  - Removed deprecated `code.allow_commands`
  - Updated PlanAgent default permissions with correct tool names (`write_file`, `edit_file`, `run_command`)
- `cli.py`:
  - Added `--auto` flag to `code` subcommand
  - Passes `auto` -> `coding_session()` -> `AgentRegistry` -> agents -> `PermissionResolver`
  - Single-shot queries benefit too — permission prompts suppressed

**Architecture decisions**:
- Permission checks happen at the `CodeAgent._exec_tool_call` layer, not in individual tool functions — one gating point, consistent UX
- `fnmatch` chosen over regex for simplicity — glob patterns like `git *` work naturally
- Prompt UX simplified to 3 options: once / always / deny — "always" adds the full input key to session allowlist (user can always edit config for precise patterns)
- `--auto` converts all "ask" decisions to "allow" — suitable for CI/automation
- PlanAgent permissions set in `__init__` as a config override, not hardcoded in `_exec_tool_call` — permission logic stays in one place

**Verified**:
- All modules compile clean ✅
- `PermissionResolver._input_key` maps tool+args -> correct string for pattern matching ✅
- Denied tool -> returns error message, not executed ✅
- `--auto` skips all prompts ✅

---

### 2026-06-30 — Phase 8: Textual TUI (start)

**Context**: Replace prompt_toolkit interactive loop with full-screen Textual TUI. Started with header + sprite, build step by step to catch Windows rendering issues early.

**New files**:
- `tui/__init__.py` — exports `CozmoApp`
- `tui/app.py` — `CozmoApp(Textual.App)`: minimal shell, TITLE + SUB_TITLE
- `tui/sprite.py` — `render_sprite(width, height) -> rich.Text`: converts 32x32 Cozmo-sprite.png to ANSI half-block art using Pillow (RGBA, NEAREST scaling, half-block chars)
- `tui/widgets/__init__.py`
- `tui/widgets/header.py` — `CozmoHeader(Horizontal)`: docks top, left side sprite + right side "Cozmo v0.1 [model] [agent]" label

**Architecture decisions**:
- Sprite rendered as ANSI half-block art, not Sixel/TGP — works in any terminal, zero extra deps
- Custom header instead of Textual's built-in Header — allows sprite + flexible layout
- Step-by-step build: each widget created in isolation and tested before the next
- Textual v8.2.8 verified rendering clean on Windows Terminal — no longer theoretical

**Verified**:
- Minimal `CozmoApp()` runs and shows clean Textual shell ✅
- `CozmoHeader` with sprite renders 20x4 character sprite + title badge ✅
- Textual v8.2.8 handles Windows Terminal correctly ✅
- Stale `__pycache__` dirs cleaned from tui/ ✅

**Next**: ChatLog widget (RichLog with colored message prefixes), then InputBar with @ autocomplete, then wire AgentRegistry.

---

### 2026-07-01 — CozmoTUI standalone repo

**Context**: Got stuck/overwhelmed building the TUI inside the main project. Stepped away, created a separate repo `rasumeng/CozmoTUI` to build it without the baggage of the full project.

**Built from scratch** (standalone, no Cozmo deps):
- `CozmoTUI/` repo with `cozmo.py` entry point
- `screens/main.py` — MainScreen: grid layout sidebar + main panel + footer
- `screens/settings.py` — Settings modal (theme, model display)
- `widgets/sidebar.py` — Tabbed sidebar with Chat / Collab / Code tabs
- `widgets/footer.py` — Bottom toolbar: Collapse, Settings, Exit buttons
- `widgets/input.py` — ChatInput: message field + send button + file attach placeholder
- `widgets/code_input.py` — CodeInput: Build/Plan mode toggle via Tab key
- `widgets/panels/panel.py` — ChatPanel, CollabPanel, CodePanel with sprite greetings + input
- `widgets/sprite.py` — Cozmo-sprite.png → ANSI half-block art (ported from main project)
- `themes.py` — Custom dark theme with purple accents
- `styles/app.tcss` — Full stylesheet covering all widgets
- `assets/Cozmo-sprite.png` — Logo asset

**Design**: Three-panel concept — Chat (general conversation), Collab (research/collaboration), Code (coding with Build/Plan agents). Sidebar for tab switching and session management. Footer for global actions.

**Status**: Fully functional UI shell. No actual LLM wiring — pure frontend, ready for backend integration.

---

### 2026-07-02 — CozmoTUI merged into main Cozmo project

**Context**: CozmoTUI standalone build was complete. Time to bring it back into the main Cozmo project as `cozmo.tui` package, replacing the partial Phase 8 implementation.

**Merge changes**:
- Replaced old `cozmo/tui/` contents with CozmoTUI files, adapted for package structure
- All imports changed from flat (`from screens.x`, `from widgets.x`) to relative (`from ..screens.x`, `from ..widgets.x`)
- `widgets/sprite.py` path updated from `assets/` to project-root `Cozmo-sprite.png`
- Old files removed: `tui/sprite.py` (superseded), `tui/css/cozmo.tcss` (empty)
- `cozmo tui` CLI subcommand added to `cli.py` → launches `CozmoApp().run()`
- `textual>=8.2` added to `pyproject.toml` dependencies
- `PLAN.md` Phase 8 marked complete
- Kept existing `widgets/header.py` (CozmoHeader with sprite + badges) — available for future use

**Design decisions**:
- UI shell only for now — no LLM wiring yet. Next phase will wire each tab to its specialist model.
- CozmoTUI's sprite renderer kept (default sizing matches source aspect ratio better)
- Old `tui/sprite.py` deleted — single sprite source in `widgets/sprite.py`

**Architecture**:
```
cozmo.tui
├── app.py              ← CozmoApp (Textual App), SCREENS: main, settings
├── themes.py           ← Dark theme definitions
├── screens/
│   ├── main.py         ← MainScreen: sidebar + panels + footer
│   └── settings.py     ← SettingsModal
├── widgets/
│   ├── sidebar.py      ← Sidebar with Chat/Collab/Code tabs
│   ├── footer.py       ← AppFooter toolbar
│   ├── input.py        ← ChatInput
│   ├── code_input.py   ← CodeInput with Build/Plan toggle
│   ├── header.py       ← CozmoHeader (kept from Phase 8)
│   ├── sprite.py       ← ANSI half-block sprite renderer
│   └── panels/
│       └── panel.py    ← ChatPanel, CollabPanel, CodePanel, MainPanel
└── css/
    └── app.tcss        ← Stylesheet
```

**Verified**:
- `cozmo tui` launches CozmoApp with correct theme and screen layout ✅
- Sidebar tab switching works (Chat ↔ Collab ↔ Code) ✅
- CodeInput Tab toggle cycles Build/Plan ✅
- Footer Collapse toggles sidebar visibility ✅
- Settings modal opens and closes ✅
- Old `pyproject.toml` updated ✅
- All `__pycache__` cleaned ✅

**Status**: `cozmo tui` launches full Textual TUI — UI shell complete. Ready for agent wiring in next phase.
