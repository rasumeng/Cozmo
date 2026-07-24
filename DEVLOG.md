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

---

### 2026-07-03 — Model selector + Agent harness wiring

**Context**: Two major features in one session — (1) model selector UI for switching Ollama models per-chat, (2) wiring the existing agent harness (CodeAgent, PlanAgent, PermissionResolver) into the TUI with specialized agents for each tab.

---

#### Part 1: Model Selector

**New files**:
- `tui/screens/model_selector.py` — ModalScreen: queries Ollama `/api/tags` for downloaded models, shows clickable list with checkmark on current

**Changes**:
- `ollama_util.py` — Added `get_ollama_models()` using `/api/tags` endpoint
- `tui/widgets/input.py` — Added `#model-selector-btn` Static to toolbar (between spacer and send), `ModelLabelClicked` message, `update_model_label()` method
- `tui/widgets/panels/panel.py` — `selected_model` attribute (default from config), `set_model()` method, per-chat model used in streaming worker
- `tui/screens/main.py` — Register ModelSelectorScreen, wire `ModelLabelClicked` → push modal, `ModelSelected` → `ChatPanel.set_model()`
- `tui/css/app.tcss` — Model button + modal styling

**Layout**: `[+ ] [spacer] [phi4-mini:3.8b >] [▶]` — model label sits right next to send button.

**Bug fixed**: Model names with colons (`gemma3:4b`) are invalid Textual IDs. Fixed by sanitizing IDs (`:` → `_`) and mapping back to real names via dict.

**Design**: Per-chat model selection. Default `phi4-mini:3.8b`. Switching persists for that chat. Future settings will allow customizable default.

---

#### Part 2: Agent Harness Research

**Researched**:
- Claude Code architecture: ReAct while-loop, 7-stage permission pipeline, sub-agents, context compaction
- Claude Cowork architecture: Observe-Plan-Act-Reflect, VM isolation, folder-scoped permissions, human-in-loop
- Karpathy's insights: Loop Engineering > Prompt Engineering, Generator/Evaluator separation, "Iron Man suit" (augmentation + agent), state in persistent files

**Key findings**:
- Existing `CodeAgent` already had 5-turn ReAct loop + permissions — just not wired to TUI
- `PlanAgent` existed but was read-only — needed full CollabAgent for collaborative work
- `PermissionResolver` worked but used CLI `input()` — needed TUI modal
- `web_search` only returned links, not content — needed `web_fetch` tool

---

#### Part 3: Specialized Agents

**New files**:
- `tools/web_fetch.py` — Fetch URL content (HTML → stripped text, truncated). Unlike `web_search` which only returns title + snippet + URL.
- `core/chat_agent.py` — ChatAgent: smart chat, minimal tools (calculator, web_search, web_fetch), simple ReAct loop (max 3 turns), streaming
- `core/collab_agent.py` — CollabAgent: Observe-Plan-Act-Reflect loop (max 7 turns), all tools, project context observation (file listing + git status), permission callback support, streaming
- `tui/screens/permission.py` — PermissionModal (ModalScreen) + PermissionBridge (threading bridge between agent callback and TUI modal)

**Changes**:
- `core/code_agent.py` — Added `run_stream()` method yielding `(kind, text)` tuples during 5-turn loop, added `set_permission_callback()` for TUI integration
- `tui/widgets/panels/panel.py` — Complete rewrite of all three panels:
  - ChatPanel → ChatAgent (minimal tools, streaming)
  - CollabPanel → CollabAgent (all tools, Observe-Plan-Act-Reflect, permission modal)
  - CodePanel → CodeAgent (all tools, 5-turn ReAct, permission modal)
  - All panels show thinking status ("Using calculator...", "Reading file...") during tool execution
- `tui/widgets/code_input.py` — Added `MessageSent` message for code input submission
- `tui/screens/main.py` — Wires orchestrator + chat_manager to all panels, handles PermissionModal results
- `tui/css/app.tcss` — Permission modal + thinking status styling
- `tools/__init__.py` — Registered `web_fetch`

**Architecture**:
```
Chat tab   → ChatAgent    (minimal tools, simple ReAct, max 3 turns)
Collab tab → CollabAgent   (all tools, Observe-Plan-Act-Reflect, max 7 turns, confirms destructive ops)
Code tab   → CodeAgent     (all tools, 5-turn ReAct, permissions)
```

**Streaming format**: All agents yield `(kind, text)` tuples:
- `[token]` — response chunk for live UI update
- `[thinking]` — status update shown in thinking indicator

**Permission flow**:
```
Agent thread calls permission_callback(tool, args, agent)
  → PermissionBridge.ask() blocks via threading.Event
  → bridge calls app.call_from_thread(_show_modal)
  → TUI pushes PermissionModal (Allow Once / Always / Deny)
  → User clicks button → modal posts PermissionResult
  → MainScreen handler calls app._perm_callback(event)
  → PermissionBridge._event.set() → agent thread unblocks
```

**Verified**:
- All imports clean ✅
- `cozmo tui --help` works ✅
- Model selector renders with sanitized IDs ✅

**Status**: Agent harness fully wired into TUI. Chat, Collab, and Code tabs each use specialized agents with streaming + thinking status + permission modals.

---

### 2026-07-03 — Comprehensive audit + Phase 1 fixes

**Context**: Deep audit of entire codebase as Senior AI Agent Engineer. Identified fragmented architecture, dead code, security issues, and missing features. Created `AUDIT.md` with full critique and prioritized improvement plan.

---

#### Audit Findings

**Critical bugs found**:
- `q` key exits app from input fields (both `app.py` and `main.py` had `exit()` on `q`)
- Permission modal hangs for 120s if user presses Escape (no signal on dismiss)
- Sidebar typo: "Sessoions" → "Sessions"
- Model selector only worked for ChatPanel, not Collab/Code
- ChatAgent had no history persistence (each message independent)
- CollabAgent history grew unbounded (no limit/compaction)
- CodeInput ToggleMode message never handled (dead toggle)

**Security issues found**:
- `eval(expression)` in calculator — arbitrary code execution
- `subprocess.run(command, shell=True)` in code_ops — shell injection
- File path traversal via symlinks in file_ops

**Architecture issues found**:
- Two parallel systems (CLI Orchestrator vs TUI direct-agent) that don't talk
- Orchestrator's classification, memory, routing completely bypassed by TUI
- `_parse_tool_call`, `_build_system` duplicated across 4 agent files
- Panel helpers (`_add_message`, `_show_thinking`, etc.) copy-pasted across 3 panels (~250 lines)

---

#### Phase 1 Fixes Implemented

**Bug fixes**:
- `app.py` + `main.py` — Changed `q` → `Ctrl+Q` for exit
- `permission.py` — Added `on_key` handler for Escape → signals `False` immediately
- `sidebar.py` — Fixed typo
- `main.py` — Model selector now tracks which panel opened it, routes selection correctly

**Security fixes**:
- `calculator.py` — Replaced `eval()` with safe AST parser (`_safe_eval`). Only supports math operators (+, -, *, /, //, %, **). No code execution.
- `code_ops.py` — Replaced `shell=True` with `shlex.split()` + argument list. Added blocked command list (rm, del, format, shutdown, etc.)
- `file_ops.py` — Added `realpath()` check to prevent symlink traversal

**Architecture cleanup**:
- Created `core/base_agent.py` — Shared utilities: `parse_tool_call()`, `build_tool_schema()`, `exec_tool_call()`, `BaseAgent` class with history, compaction, permission callback
- Refactored `chat_agent.py` — Now extends `BaseAgent`, has history persistence (max 20 turns)
- Refactored `collab_agent.py` — Now extends `BaseAgent`, history capped at 30 turns
- Refactored `code_agent.py` — Now extends `BaseAgent`, extracted `_run_loop()` shared by `run()` and `run_stream()`
- Simplified `agent.py` — Now uses shared utilities, kept as legacy for Orchestrator path
- Simplified `plan_agent.py` — Clean 19-line extension of CodeAgent

**TUI deduplication**:
- Created `tui/widgets/panels/chat_mixin.py` — `ChatMixin` class with all shared panel helpers
- Rewrote `panel.py` — All three panels now extend `ChatMixin`. ~250 lines of duplication eliminated.

**Files created**: `AUDIT.md`, `core/base_agent.py`, `tui/widgets/panels/chat_mixin.py`
**Files modified**: `core/agent.py`, `core/chat_agent.py`, `core/collab_agent.py`, `core/code_agent.py`, `core/plan_agent.py`, `tools/calculator.py`, `tools/code_ops.py`, `tools/file_ops.py`, `tui/app.py`, `tui/screens/main.py`, `tui/screens/permission.py`, `tui/widgets/panels/panel.py`, `tui/widgets/sidebar.py`

**Verified**:
- All imports clean ✅
- `cozmo tui --help` works ✅

---

#### Remaining (from AUDIT.md)

**Phase 2** (next session):
- Wire Orchestrator into TUI (classification + memory)
- Context compaction for all agents
- Markdown rendering in responses
- @ file attachment in TUI
- Keyboard shortcuts
- Token/cost display

**Status**: Phase 1 complete. AUDIT.md serves as reference for remaining work.

---

### 2026-07-03 — Phase 2 Complete

**Context**: All Phase 2 tasks from AUDIT.md implemented in this session.

---

#### Phase 2 Changes

**Orchestrator integration**:
- Added classification display in thinking area (`"Classified: chat"`)
- Added memory context to all agent prompts (via `orchestrator.memory.query()`)
- Added history/memory persistence after each interaction
- All three panels now use Orchestrator for classification + memory

**Context compaction**:
- Added `self.compact()` call to ChatAgent, CollabAgent, CodeAgent after history append
- Compaction triggers when history exceeds 6 turns (summarizes to 3-4 sentences)

**Markdown rendering**:
- Assistant messages now render via `textual.widgets.Markdown`
- User messages remain as plain text with colored labels

**File attachment**:
- Created `tui/screens/file_picker.py` — ModalScreen with directory navigation
- Directory browsing with backspace to go up
- Escape to cancel, click to select
- File content inserted with `@filename: ```content``` ` syntax
- Wired to ChatPanel and CollabPanel attach buttons

**Keyboard shortcuts**:
- `Ctrl+Q` — Exit app
- `Ctrl+L` — Clear/reset chat panel

**Token display**:
- Added `update_tokens()` method to `AppFooter`
- Token count displayed in footer: `Tokens: 1234`
- Updated from `_stream_worker` every 10 tokens

**Files created**: `tui/screens/file_picker.py`
**Files modified**: `tui/widgets/panels/panel.py`, `tui/widgets/panels/chat_mixin.py`, `tui/widgets/footer.py`, `tui/screens/main.py`, `core/chat_agent.py`, `core/collab_agent.py`, `core/code_agent.py`

**Verified**:
- All imports clean ✅
- `cozmo tui --help` works ✅

---

#### Remaining (from AUDIT.md)

**Phase 3** (future):
- Fix CodeInput ToggleMode (dead toggle)
- Consolidate CLI/TUI paths
- Remove dead code (Orchestrator legacy)
- Add token/cost estimation per model
- Fix model selector routing for CodePanel default model

**Status**: Phase 2 complete. All high/medium priority AUDIT.md items resolved.

---

### 2026-07-03 — Bug fixes + Phase 3

**Context**: Fixed runtime errors and completed remaining Phase 3 items.

---

#### Bug Fixes

**ModelLabelClicked error**:
- `ChatInput.ModelLabelClicked` message had no `widget` attribute
- Fixed by passing `model_name` in message constructor
- Updated `on_chat_input_model_label_clicked` to use `event.control` for panel detection
- Model selector now works correctly from all panels

---

#### Phase 3 Changes

**CodeInput ToggleMode**:
- `ToggleMode` message was posted but never handled
- Added `on_code_input_toggle_mode` handler to `CodePanel`
- `CodePanel._mode` tracks current mode ("Build" / "Plan")
- Agent recreated on mode switch (`CodeAgent` ↔ `PlanAgent`)
- Added `set_mode()` and `_update_mode_label()` to `CodeInput`
- `reset()` now restores default "Build" mode

**Context window % display**:
- `AppFooter` now shows `Tokens: 1234 (12%)` instead of just count
- `_get_context_window()` estimates window size from model name
- `update_model()` called when model changes
- Default 4096 tokens, scaled for known models (qwen3, llama3, gemma, etc.)

**CLI deprecation**:
- `run` and `code` subcommands marked `[DEPRECATED: use 'tui']`
- `tui` subcommand marked as primary interface
- CLI code retained for backward compatibility

**Files modified**: `tui/widgets/input.py`, `tui/screens/main.py`, `tui/widgets/code_input.py`, `tui/widgets/panels/panel.py`, `tui/widgets/footer.py`, `cli.py`

**Verified**:
- All imports clean ✅
- `cozmo tui --help` works ✅

---

#### Remaining

**Phase 4** (future):
- Remove dead code (Orchestrator legacy, AgentRegistry)
- Consolidate CLI/TUI paths
- Add custom agent support in TUI
- Add @ file autocomplete

**Status**: Phase 3 complete. TUI is now primary interface.

---

### 2026-07-03 — Web search fix

**Context**: Fixed web search returning outdated information. LLM was relying on training data instead of web results.

---

#### Changes

**ChatAgent system prompt**:
- Added explicit instructions to use `web_search` for time-sensitive information
- Model now forced to verify current events with web search
- Added note to flag outdated results in answers

**Web tool consolidation**:
- Moved `web_fetch` into `web_search.py` (single file for web tools)
- Deleted `tools/web_fetch.py`
- Updated `tools/__init__.py` imports
- Both `web_search` and `web_fetch` still registered in `TOOL_REGISTRY`

**Files modified**: `core/chat_agent.py`, `tools/web_search.py`, `tools/__init__.py`
**Files deleted**: `tools/web_fetch.py`

**Verified**:
- All imports clean ✅
- `cozmo tui --help` works ✅

---

### 2026-07-08 — CozmoBrain integration

**Context**: Merged the standalone [CozmoBrain](https://github.com/rasumeng/CozmoBrain) repo into main Cozmo codebase. Brain had a more sophisticated tool routing system (keyword + domain priority + LLM fallback), MCP server support, context management utilities, date-aware prompt builder, and additional tools (execute_python sandbox, knowledge CRUD with OKF frontmatter, date-stamped web search).

**New files** (per [IMPLEMENT_PLAN.md](https://github.com/rasumeng/CozmoBrain/blob/main/IMPLEMENT_PLAN.md)):
- `cozmo/core/mcp_host.py` — MCPHost: stdio sessions, connect/disconnect, tool wrapper factory
- `cozmo/core/router.py` — ToolRouter: keyword → domain priority → LLM fallback classification, 10 categories inlined
- `cozmo/core/context.py` — `trim_history`, `truncate_tool_responses`, `compact_messages`, `estimate_tokens`
- `cozmo/core/prompts.py` — `build_system_prompt()` with live tool list + date injection
- `cozmo/docker/sandbox.Dockerfile` — sandboxed Python execution via Docker

**Modified files**:
- `cozmo/core/__init__.py` — exports MCPHost, ToolRouter, StatelessLLM, build_system_prompt, context utils
- `cozmo/core/llm.py` — added `StatelessLLM` (langchain-based, for ToolRouter classifier)
- `cozmo/tools/code_ops.py` — added `execute_python` with Docker → subprocess fallback
- `cozmo/tools/web_search.py` — added `fetch_url`, date-stamped `web_search` results
- `cozmo/tools/file_ops.py` — added `read_knowledge` / `write_knowledge` with OKF frontmatter
- `cozmo/cli.py` — added `cozmo mcp connect|list|disconnect` subcommand
- `cozmo/config.py` — added `router`, `workspace`, `search`, `mcp`, `context` config sections
- `pyproject.toml` — added `mcp>=1.0`, `pyyaml` dependencies
- `.gitignore` — added `.cozmo/`, `workspace/`, `knowledge/`, `test_brain_integration.py`

**Design decisions**:
- `rules.yaml` → inlined as `ToolRouter.CATEGORIES` class dict (no YAML at runtime)
- Brain's `pydantic_ai` → Cozmo's `OllamaModel` via `StatelessLLM` wrapper (no new framework)
- `config.yaml` → merged into TOML defaults in `config.py`
- All new tools use existing `@register_tool()` decorator → auto-in `TOOL_REGISTRY`
- Docker fallback: if Docker unavailable or sandbox build fails, falls through to subprocess

**Verified** (14/14 tests pass):
- All imports resolve ✅
- 20 tools in TOOL_REGISTRY (4 new) ✅
- ToolRouter classify returns matching categories ✅
- ToolRouter no-match returns None (safe) ✅
- build_system_prompt injects date + tool list ✅
- context utils (trim, truncate, estimate) work ✅
- StatelessLLM instantiates cleanly ✅
- Config defaults include new sections ✅
- MCPHost instantiates cleanly ✅
- execute_python("print('hello')") → "hello" ✅
- fetch_url("http://example.com") → page text ✅
- read_knowledge missing file → error (safe) ✅
- write_knowledge writes OKF file ✅
- MCP connect/disconnect works ✅
- MCP tool wrappers call through to registered tools ✅
- All original Cozmo tests still pass ✅

---

### 2026-07-09 — WebUI color scheme refresh

**Context**: Changed WebUI color palette from teal/amber to purple theme matching TUI (`themes.py`). Replaced sparkle icons with Cozmo pixel-art sprite.

**Files changed**:
- `cozmo/webui/tailwind.config.js` — accent → purple (`#7A6EE0`), secondary → gold (`#E8C868`), ok/warn/err → TUI palette
- `cozmo/webui/src/styles/globals.css` — selection highlight + body gradients updated
- `cozmo/tui/widgets/panels/chat_mixin.py` — user msg color neon blue → purple
- `cozmo/webui/public/assets/Cozmo-sprite.svg` — new pixel-art SVG (converted from PNG)
- `cozmo/webui/src/components/sidebar/Sidebar.tsx` — logo "C" → sprite image
- `cozmo/webui/src/components/chat/Conversation.tsx` — sparkle icons → Cozmo sprite

---

### 2026-07-09 — WebUI sidebar pin/rename/delete

**Context**: Added conversation management to sidebar — pin convos to separate "Pinned" section, inline rename, delete.

**Files changed**:
- `cozmo/webui/src/types/index.ts` — pinned made required
- `cozmo/webui/src/hooks/useCozmoChat.ts` — added pinConversation, renameConversation, deleteConversation
- `cozmo/webui/src/components/sidebar/SidebarItem.tsx` — full rewrite: pin icon on hover, ⋮ menu (pin/unpin, rename, delete), inline rename input
- `cozmo/webui/src/components/sidebar/Sidebar.tsx` — Pinned + Recents sections; Pinned hides when empty
- `cozmo/webui/src/App.tsx` — wired new callbacks
- `cozmo/webui/src/data/mock.ts` — added pinned field to mock data

---

### 2026-07-09 — WebUI: Search chats (Phase 2.3)

**Context**: Added full-text search across all conversations — searches both title and `.md` content, returns matching context snippet.

**New files**:
- `cozmo/webui/src/components/search/SearchModal.tsx` — Overlay modal with debounced input (200ms), results list with mode icons, click-outside close, Escape close, Enter to select first result

**Changes**:
- `cozmo/webui_server.py` — Added `GET /api/conversations/search?q=` endpoint: reads `index.json` + `.md` files, searches title + content, returns `snippet` (~120 chars around keyword match). Fixed route ordering (search before `/{conv_id}` delete). Fixed `KeyError 'conversations'` in `_conversations_idx()` when TUI writes index with `"chats"` key.
- `cozmo/webui/src/components/sidebar/Sidebar.tsx` — Wired search button → SearchModal, passes `onSelect` (sets `chat.activeId`) + `onClose`
- `cozmo/webui/src/hooks/useCozmoChat.ts` — Search expects only content matches (no title-only), returns keyword context ±60 chars

**Design decisions**:
- Content-only search (title-only excluded to avoid redundant results)
- Snippet extracted from raw `.md` text, not message-parsed — simpler, captures more context
- Debounce 200ms prevents excessive API calls during typing
- Results capped at 20

---

### 2026-07-09 — WebUI: Settings modal + Input bar menu (Phase 1)

**Context**: Full Settings modal with 6 sections (Models, Tools, Memory, Skills, Connectors, General) and input bar `+` menu with stub actions.

**Changes**:
- `cozmo/webui/src/components/settings/SettingsModal.tsx` — New: left sidebar (searchable), right panel section content, dirty state tracking, click-outside save+close. Models section: dropdowns for chat/coder/vision/research from Ollama list. Config CRUD via `GET/PUT /api/config`. Tools toggle, memory display, skills/connectors/general stubs.
- `cozmo/webui/src/components/chat/PromptInput.tsx` — `+` button opens dropdown (Attach files, Add to project, Skills, Connectors — all stubs). Model selector with role badges. Send/stop button.
- `cozmo/webui_server.py` — Added `GET /api/config`, `PUT /api/config` (deep-merge + tomli_w write). Added `GET /api/ollama/models` (proxies Ollama `/api/tags`).
- `cozmo/config.py` — Default `chat` model set to `qwen3:8b`

**Model sync**: Settings save calls `onModelChange` → updates `useCozmoChat.setChatModel` → PromptInput re-selects matching model from dropdown.

---

### 2026-07-09 — WebUI: Model presets editor (Phase 2.1)

**Context**: Upgrade Settings > Models from flat dropdowns to a proper preset editor — add/delete custom presets, built-in roles preserved.

**Changes**:
- `cozmo/webui_server.py` — `put_config` now full-replaces `models` key instead of deep-merge, so deleted custom presets are actually removed from config
- `cozmo/webui/src/components/settings/SettingsModal.tsx` — Removed separate `customPresets` local state. Custom presets now live in `config.models` directly. Derived from `Object.entries(config.models).filter()` excluding built-in roles (`chat`/`coder`/`vision`/`research`) and internal keys (`classifier`/`max_tokens`). Add creates `preset-{timestamp}` key, rename updates key, delete removes key. Save sends full `config.models` dict — backend persists to `config.toml`.

**Flow**: Add → empty model entry created → user names it → selects model from dropdown → Save → persists to `[models]` section. Survives modal close/reopen.

---

### 2026-07-09 — WebUI: Tools permission mode (Phase 2.2)

**Context**: Each tool in Settings > Tools now has Allow/Ask/Deny 3-mode selector instead of just an enabled toggle. Permission saved to `config.toml [permissions]`.

**Changes**:
- `cozmo/webui/src/components/settings/SettingsModal.tsx` — Added `PermissionSelect` component (3-button group: Allow/Ask/Deny, color-coded green/amber/red). `renderTools` now reads permissions from `config.permissions`, writes back on change via `updateToolPermission`. Save sends `{ permissions: config.permissions }` alongside models.
- Backend unchanged — `deep_merge` handles permissions recursively, preserving complex entries like `run_command` patterns.

---

### 2026-07-09 — WebUI: Microphone STT (Phase 3.3)

**Context**: Cross-browser speech-to-text input. Chrome uses native `webkitSpeechRecognition` (streaming, per-word). Other browsers (Brave, Firefox, Edge, VS Code WebView) fall back to MediaRecorder + backend transcription via Google Speech API.

**Multiple iterations during development**:

**Iteration 1** — `webkitSpeechRecognition` only:
- Frontend: Added `onstart`/`onresult`/`onend`/`onerror` handlers. `onstart` sets listening state (fixes brief flash on unsupported browsers). `continuous: true` + `interimResults: true`. Text appended to input on final results.
- Problem: Brave/VS Code had `webkitSpeechRecognition` but it failed immediately (shields/permissions). Button flashed then turned off.

**Iteration 2** — Whisper fallback (removed):
- Backend: Added `POST /api/transcribe` using `openai-whisper` with `tiny` model. Cached model instance via `nonlocal`. Frontend: Added MediaRecorder fallback when SpeechRecognition fails.
- Problem: Whisper model ~1.5GB download, slow transcription per request. Removed and replaced.

**Iteration 3** — SpeechRecognition library + Google API:
- Backend: `pip install SpeechRecognition pydub`. `/api/transcribe` now converts WebM → WAV via pydub+ffmpeg, transcribes via Google's free Speech API (`recognize_google()`). No model download, fast.
- Frontend: Dual path — try SpeechRecognition first, fall back to MediaRecorder on error. Recording saves chunks, sends blob on stop.

**Iteration 4** — Progressive transcription during recording:
- Added polling (every 2s) during recording that sends accumulated audio to backend. Full audio sent each poll for context. Diffs against previous transcription, appends only new words. Poll interval reduced to 1s for snappier feel.
- Uses `prefixRef` to preserve user-typed text before recording started. `lastTextRef` tracks previous transcription for diffing.

**Files changed**:
- `cozmo/webui/src/components/chat/PromptInput.tsx` — Full STT logic: type declarations for SpeechRecognition API, `micState` (idle/listening/recording), `recognitionRef`, `mediaRecorderRef`, `audioChunksRef`, `transcribeAudio`, `sendAccumulated` (diff-based append), polling effect, `onstop` handler. Mic button styled with red glow + pulse when active, red dot when recording. `recorder.start(1000)` for 1s chunk intervals.
- `cozmo/webui_server.py` — `POST /api/transcribe`: receives UploadFile, converts via pydub, transcribes via `speech_recognition.recognize_google()`. Returns `{"text":"..."}`.
- `pyproject.toml` — added `SpeechRecognition`, `pydub` (transitive via pip install)

**Dependencies**: `SpeechRecognition`, `pydub`, `ffmpeg` (required for audio conversion)

**Behavior by browser**:
| Browser | Path | UX |
|---------|------|----|
| Chrome | `webkitSpeechRecognition` | Streaming per-word |
| Brave/Edge/Opera | SpeechRecognition fails → MediaRecorder fallback | Record → 1s poll → progressive text |
| Firefox/Safari | No SpeechRecognition → MediaRecorder | Same fallback |
| VS Code WebView | No mic access → button behaves as expected | Graceful no-op |

---

### 2026-07-10 — File/image attachments, vision routing, projects

**Context**: Three phases implemented from PLAN.md — file/image attachment support in WebUI, vision model routing for image analysis, and project grouping system.

---

#### Phase 1: File & Image Attachments

**Backend** (`webui_server.py`):
- `POST/GET/DELETE /api/attachments` endpoints — upload to `~/.cozmo/attachments/`, thumbnail gen via PIL (128px width), serve raw files
- `@attachments` JSON marker in `.md` conversation persistence — round-trips attachment metadata through save/load
- WS handler accepts `attachments` array in `chat` messages (metadata only, files stay on disk)

**Frontend types** (`types/index.ts`):
- `Attachment` interface: `{id, type, name, mime, size, url, thumbnail}`
- `attachments?: Attachment[]` on `ChatMessage`

**Frontend services** (`services/cozmo.ts`):
- `uploadFile()`, `deleteAttachment()` — REST wrappers with `API_BASE` prefix
- `sendChat()` accepts attachments (sends `{id, type, name, mime, size}` to WS)
- `saveConversation()` includes attachments in message payload

**PromptInput** (`PromptInput.tsx`):
- Hidden `<input type=file multiple accept="image/*,.pdf,.txt,...">` triggered by "+ Attach" button
- `handlePaste` on textarea — detects clipboard images, uploads, shows as chip
- Attachment chips between textarea and button bar — thumbnail for images, Paperclip icon for files, X to remove
- Submit passes `attachments` up via `onSend(content, attachments)`

**MessageBubble** (`MessageBubble.tsx`):
- Image attachments render as `<img>` with thumbnail, click to open full image
- File attachments render as download link with icon + file size

**Props/state chain**:
- `Conversation.onSend` → `(content, attachments?)` (was `(content)`)
- `useCozmoChat.sendMessage` → `(content, attachments?)` — stores on ChatMessage, sends via WS

---

#### Phase 2: Vision Model Routing

**Runtime** (`runtime.py`):
- `run_stream(user_input, attachments?)` — accepts attachment list with resolved file paths
- `_build_multimodal_content()` — base64-encodes image files, builds `HumanMessage(content=[{type:"text"}, {type:"image_url"}])` for langchain `ChatOllama`
- When images present → forces `"vision"` mode (bypasses `_route()`), uses `qwen2.5vl:7b` from config
- `_system_prompt` includes attachment metadata + file paths for tools
- Added `"vision"` to `self.temps` and `self._tool_gate` defaults

**Server** (`webui_server.py`):
- `ChatSession._resolve_attachments()` — matches UUID -> file path on disk
- `start_run()` passes resolved attachments + project context to runtime
- WS handler reads `project_id` field, injects project `sharedContext` into runtime

---

#### Phase 3: Projects

**Backend** (`webui_server.py`):
- `GET/POST/PUT/DELETE /api/projects` — CRUD persisted to `~/.cozmo/projects/index.json`
- `GET /api/projects/{id}/conversations` — returns full conversation objects
- Project schema: `{id, name, description, conversationIds[], sharedContext, createdAt, updatedAt}`

**Frontend types + services**:
- `Project` interface in `types/index.ts`
- `fetchProjects()`, `createProject()`, `updateProject()`, `deleteProjectApi()`, `fetchProjectConversations()` in `cozmo.ts`

**Project components** (`components/projects/`):
- `ProjectsPanel` — list view with "New Project" button, delete per project
- `ProjectDetail` — shared context editor, linked conversations list with navigate + remove
- `ProjectForm` — create/edit form (name, description, shared context)

**Sidebar integration**:
- "Projects" toggle button in sidebar (below workspace tabs, between search and + buttons)
- `SidebarItem` context menu — "Add to project" submenu listing available projects
- `Sidebar` passes `projects` + `onAddToProject` down to each item

**App view switching**:
- `App.tsx` — `showProjects` state toggles between `Conversation` and `ProjectsPanel`
- `ActivityPanel` hidden during project view

**Project context injection**:
- `useCozmoChat.sendMessage` auto-detects project via `conversationIds.includes(activeId)`
- Sends `project_id` in WS payload → server looks up `sharedContext` → injects into `_system_prompt`

---

**Files created**: `ProjectForm.tsx`, `ProjectDetail.tsx`, `ProjectsPanel.tsx`
**Files modified**: `types/index.ts`, `webui_server.py`, `cozmo.ts`, `runtime.py`, `PromptInput.tsx`, `MessageBubble.tsx`, `Conversation.tsx`, `useCozmoChat.ts`, `App.tsx`, `Sidebar.tsx`, `SidebarItem.tsx`

**Verified**: TypeScript compiles clean, Python syntax + imports OK.

---

### 2026-07-10 — Routing fix: game/meta queries misclassified as chat

**Context**: Queries about game updates ("who should I pull in wuwa update") classified as `chat` (no tools) instead of `research` (web search). Small router LLM (MiniCPM5-1B) didn't know gaming terms like "wuwa", "pull", "banner".

**Root cause**: `_route()` in `cozmo/core/runtime.py:255-265` used a 1B router LLM with prompt covering news/sports/weather but zero gaming keywords. Query fell through to `chat` → model refused ("I can't search live info").

**Changes** (`cozmo/core/runtime.py`):

| Change | What |
|--------|------|
| Expanded `_ROUTE_PROMPT` | Added keywords: `game banners`, `character tiers`, `gacha pulls`, `who to pull`, `what to build` + 5 explicit examples |
| Added `_RESEARCH_KEYWORDS` | Pre-pass list: `"who should"`, `"pull"`, `"banner"`, `"tier list"`, `"meta"`, `"new character"`, `"gacha"`, `"game update"`, etc. |
| Keyword pre-pass in `_route()` | Scans query before LLM call → any match returns `"research"` immediately |
| Fallback default | `"chat"` → `"research"` (matches prompt rule: "when unsure, pick research") |

**Why it works**:
- "who should I pull in wuwa" → keyword pre-pass catches `"who should"` + `"pull"` → `research` mode
- "latest genshin banners" → `"banner"` → `research`
- New examples in prompt help the router LLM learn patterns
- Fallback defaults to research (safe: web search vs. silent hallucination)

**Files changed**: `cozmo/core/runtime.py`

---

### 2026-07-12 — WebUI: Code Mode redesign + Collab mode + Project management

**Context**: Three major phases: (1) Code Mode UI overhaul with tool events, terminal/diff/trace panels, inline diffs, directory picker, permission modes. (2) Collab mode runtime + frontend (plan approval flow). (3) Collab Project Management — create, import, select projects with full wizard UI.

---

#### Part 1: Code Mode — Tool events + Panels

**Backend** (`runtime.py`):
- `_compute_diff()` — line-by-line diff from old/new file content
- `run_stream()` now yields `tool_call`/`tool_result` events with diffs
- `_check_permission()` — 5 permission modes: `manual`, `plan`, `accept-edits`, `auto`, `bypass`

**Server** (`webui_server.py`):
- Forwards `tool_call`/`tool_result` events to WebSocket
- `set_directory` handler — accepts path, creates `ProjectIndex`, sets runtime context
- `set_permission_mode` handler — sets runtime permission mode

**Frontend types** (`types/index.ts`):
- `DiffData`, `TerminalEntry`, `DiffEntry` — panel data structures

**Frontend services** (`services/cozmo.ts`):
- `tool_call`, `tool_result`, `directory_set` server events
- `setDirectory()`, `setPermissionMode()` client methods

**Hook** (`useCozmoChat.ts`):
- `terminalEntries`, `diffEntries`, `currentDirectory`, `permissionMode` state
- Auto-switch right panel tab on new terminal/diff activity

**New components**:
- `FileChangeCard.tsx` — Expandable diff view (+/- lines, syntax highlighted)
- `TerminalPanel.tsx` — Filtered tool output list with colored badges per tool type
- `DiffPanel.tsx` — Cumulative session file changes, collapsed list with expand
- `RightPanel.tsx` — Tabbed container (Terminal / Diff / Trace)
- `DirectoryPicker.tsx` — Button with popup: recent directories (localStorage), Browse via `webkitdirectory`, manual path input
- `PermissionModeSelector.tsx` — 5-mode dropdown (Manual / Plan / Accept edits / Auto / Bypass)

**Updated**:
- `App.tsx` — RightPanel wired for code mode, auto-tab-switch
- `Conversation.tsx` — Passes new props, shows FileChangeCards on last assistant message
- `PromptInput.tsx` — Directory + PermissionMode controls visible in code mode

---

#### Part 2: Collab mode

**Backend** (`runtime.py`):
- `run_stream()` yields `plan` event with text + `plan_request` flag
- `answer_plan(approved)` — resumes or aborts the run

**Server** (`webui_server.py`):
- Forwards `plan` events, handles `plan_response` WS messages

**Frontend**:
- `PlanCard` rendered in activity panel with approve/reject buttons
- `useCozmoChat` — plan state + `answerPlan()` callback

---

#### Part 3: Collab Project Management

**Backend** (`webui_server.py`):
- `list_projects` — search/filter projects from `~/.cozmo/projects/index.json`
- `get_recent_conversations` — recent conversations by mode, sorted by updatedAt
- `import_from_chat` — extracts context from `.md` files, creates project directly (title from first conv, instructions from content, indexes files)
- `create_project` — validates name+location, creates dir, saves instructions+seed files, indexes via `ProjectIndex`, stores project record, sets as active context
- `select_project` — looks up project by id, injects `sharedContext` into runtime
- `POST /api/directory-picker` — opens native OS folder dialog via `tkinter.filedialog.askdirectory()`, returns real filesystem path
- Protocol doc: 6 new server events (`projects_list`, `recent_conversations`, `project_created`, `project_selected`)

**Frontend types** (`types/index.ts`):
- `CollabProjectFile`, `CollabProjectCreate` interfaces

**Frontend services** (`services/cozmo.ts`):
- 6 new client methods (`listProjects`, `getRecentConversations`, `importFromChat`, `createProject`, `selectProject`)
- 5 new server event union members

**Hook** (`useCozmoChat.ts`):
- `collabProject`, `recentConversations` state
- `collabCreateProject`, `selectProject`, `listProjects`, `importFromChat` handlers
- `project_created` handler updates both `collabProject` and `projects` list

**New components**:
- `CollabProjectPopup.tsx` — Dropdown positioned above toolbar button: search projects, select existing, or choose action
- `CreateProjectWizard.tsx` — Single-page modal: name, description, instructions, seed files (dropzone), location (Browse via server dialog). Preview shows `{path}/{name}/`
- `ImportFromChatPopup.tsx` — Fetches all conversations from `GET /api/conversations`, shows expandable items (▶ toggle), message previews with user/assistant icons, checkbox per conversation

**Wiring** (`PromptInput.tsx`, `Conversation.tsx`, `App.tsx`):
- Collab mode shows `[📁 Project Name]` button in toolbar
- Click opens dropdown, wrapped in `relative` container for absolute positioning
- Create + Import modals portaled to `document.body` via `createPortal` for true `fixed` centering
- `data-modal` attribute on modals prevents click-outside-close from closing the dropdown

**Bug fixes in this session**:
- `project_created` sent partial fields → now sends full project object
- "Import from Chat" went nowhere → backend now creates project directly in one step
- `_conversations_idx()` called N times in loop → moved outside with lookup map
- Modals clipped by parent stacking context → portaled to `document.body`
- CollabProjectPopup was full-screen modal → converted to dropdown (absolute, no backdrop, click-outside-close)
- Mousedown on portaled modals closed the dropdown → `data-modal` attribute filter added
- Browse buttons used `webkitdirectory` (folder name only) → replaced with server-side `tkinter.filedialog.askdirectory()` returning real path

**Files created**: `RightPanel.tsx`, `TerminalPanel.tsx`, `DiffPanel.tsx`, `FileChangeCard.tsx`, `DirectoryPicker.tsx`, `PermissionModeSelector.tsx`, `CollabProjectPopup.tsx`, `CreateProjectWizard.tsx`, `ImportFromChatPopup.tsx`

**Files modified**: `runtime.py`, `webui_server.py`, `types/index.ts`, `cozmo.ts`, `useCozmoChat.ts`, `App.tsx`, `Conversation.tsx`, `PromptInput.tsx`, `PLAN.md`

**Verified**: TypeScript compiles clean, Vite build succeeds, Python syntax OK.

---

### 2026-07-21 — v2 Architecture migration: Phase 0-6 (mode-based → task-based)

**Context**: Complete rewrite of Cozmo's internal architecture. Replaced mode-based multi-assistant (Chat/Agent/Code/Collab) with task-based single intelligent system. Every request becomes a `Task`; system determines intent, complexity, tools, model without user mode selection. Three parallel sessions across ~6 hours of work.

**Architecture v3**: Task is universal currency; Orchestrator is thin (~150 lines, delegates); Engine is stateless; EventBus for pub/sub events; direct calls for sync queries.

**Key architectural components**:

| Component | File | Purpose |
|-----------|------|---------|
| `runtime/` | `runtime.py`, `engine.py` | Unified `CozmoRuntime.run_stream()` — production execution loop |
| `orchestrator/` | `orchestrator.py`, `intent.py`, `complexity.py`, `policy.py`, `continuation.py` | Intent → plan → execute |
| `jobs/` | `manager.py`, `job.py`, `persistence.py` | Long-running job lifecycle (submit/pause/resume/cancel/retry) |
| `capabilities/` | `registry.py`, `builtin.py`, `base.py` | Resolvable capability definitions with tool lists |
| `planner/` | `planner.py` | Step-by-step execution plan generation |

**Phase 0** — Created directory structure + backward-compat stubs. `config.py` added `force_capability`/`force_model`.

**Phase 1** — `orchestrator/intent.py` (IntentDetector replaces `core/router.py`), `orchestrator/complexity.py`, `orchestrator/orchestrator.py` (~130 lines). `runtime/runtime.py` stripped of `_MODE_DISCIPLINE`, `_tool_gate`, per-mode temps. `run_stream()` unified. `force_mode` deprecated (logged, ignored).

**Phase 2** — `jobs/manager.py` (JobManager: submit/pause/resume/cancel/retry/start/complete, thread-safe). `jobs/persistence.py` (JSON store). `runtime/engine.py` (checkpoint_interval, Checkpoint events, resume). `orchestrator/continuation.py` (ContinuationHandler).

**Phase 3** — `orchestrator/policy.py` (PolicyEngine: relaxed/normal/strict modes, destructive command detection). `runtime/resources.py` (ResourceManager: VRAM tracking, LRU eviction, model ranking). `runtime/model_router.py` (capability-based model selection with resource awareness).

**Phase 4** — `runtime/runtime.py` wired to CapabilityRegistry for tool resolution, ModelRouter for model selection. `runtime/model_manager.py`: `bind_model()`, `client_for_model()`.

**Phase 5 (Frontend)** — Removed `WorkspaceMode` type, `Conversation.mode` field. Deleted `WorkspaceTabs.tsx`, created `WorkspaceNav.tsx` (5 nav items). Updated `Sidebar.tsx`, `App.tsx`, `useCozmoChat.ts`, `Conversation.tsx`, `LandingPage.tsx`, `PromptInput.tsx`, `services/cozmo.ts`, `SearchModal.tsx`, `ImportFromChatPopup.tsx`, `mock.ts`. All mode references stripped. TypeScript zero errors.

**Phase 6** — Deleted `cozmo/core/` entirely. Fixed `cli.py` imports. Re-restored `core/agent/`, `core/chat/`, `core/providers/` from git (11 files) because `webui_server.py` was never migrated. Added `cozmo migrate v1-to-v2` CLI command. `core/` backward-compat stubs re-created. Bumped version to `0.2.0`. Bare `cozmo` defaults to webui.

**WebUI server migration** — Replaced `ChatSession` with `Session`. Replaced old `ChatHandler`/`AgentRuntime`/`EventBus` imports with new `Orchestrator`/`CozmoRuntime`/`JobManager`/`ModelRouter`/`CapabilityRegistry`. `get_backend()` now returns new components. `build_runtime()` returns `(runtime, orchestrator, job_manager, event_bus)`. Session bridges new EventBus events to WebSocket via `on_any()` subscriber. `_start_background_run()` and `/api/tasks/{id}/run` both updated for new return signatures.

**Migration CLI**: `cozmo migrate v1-to-v2` strips `mode` from `~/.cozmo/conversations/*.json`.

**Integration tests** (27 tests): Orchestrator (intent detection, capability resolution, tool selection), JobManager (full lifecycle), Runtime stream (events, stop flag), Pipeline integration (plan → job → stream), Session class (event bus bridging, permission/plan approval flow).

**Remaining gap**: `core/agent/runtime.py` (AgentRuntime), `core/chat/handler.py` (ChatHandler), old `EventBus`, old `Reflector`, `core/providers/` remain as fallback stubs for `webui_server.py` imports that use `MCPManager` and `catalog` — these are the only old-architecture files. `runtime/engine.py` `Engine.run()` is a scaffolding stub — no real model/tool invocation yet.

**Files created**: `runtime/runtime.py`, `runtime/engine.py`, `runtime/event_bus.py`, `runtime/model_manager.py`, `runtime/model_router.py`, `runtime/resources.py`, `runtime/llm.py`, `runtime/tool_risk.py`, `runtime/mcp_host.py`, `orchestrator/orchestrator.py`, `orchestrator/intent.py`, `orchestrator/complexity.py`, `orchestrator/policy.py`, `orchestrator/continuation.py`, `orchestrator/task_types.py`, `orchestrator/__init__.py`, `jobs/manager.py`, `jobs/job.py`, `jobs/persistence.py`, `jobs/__init__.py`, `capabilities/registry.py`, `capabilities/builtin.py`, `capabilities/base.py`, `capabilities/__init__.py`, `planner/planner.py`, `planner/__init__.py`, `migrate.py`, `__init__.py`, `tests/test_v2_pipeline.py`

**Verified**: Python imports clean from root package, TypeScript zero errors, 27 integration tests pass.

### 2026-07-22 � Engine activation + Cognitive Layer (v2 completion)

**Context**: Two final pushes to complete v2 architecture migration: (1) activate execution layer with real Engine.run_stream(), wire CapabilityRegistry, remove core/ entirely. (2) Add Cognitive Layer � memory context assembly, complexity-aware model routing, reflection lessons, background scheduler via Job system.

---

#### Execution Layer Activation

**runtime/engine.py** � Real ReAct loop:
- Static generator run_stream(model_fn, execute_tool, tools, ...) yields (kind, ...) tuples + final ("__result__", EngineResult) sentinel
- Model invocation ? tool call extraction (native + JSON text fallback) ? execute_tool callback ? feed ToolMessage ? next iteration
- Duplicate call detection via seen_calls set (exact sig match)
- Checkpoint emission at interval, resume from Checkpoint
- Synchronous Engine.run() wrapper iterates generator and returns result

**CozmoRuntime.run_stream()** � now accepts execution_plan parameter. When provided, uses plan.tools / plan.model_spec / plan.temperature / plan.max_steps directly, skipping re-resolution.

**Session.start_run()** � passes plan from Orchestrator.plan() ? runtime.run_stream(execution_plan=plan).

**core/ removed** � zero remaining references in cozmo/ package. All imports route through runtime/, orchestrator/, jobs/, capabilities/. ProfileRouter, Reflector, old EventBus fallback removed. tools/task.py and webui_server.py imports updated.

**Job manager wiring** � _start_background_run() accepts optional job_manager, submits/removes Job on start/error/done.

---

#### Cognitive Layer

**Memory context assembly** � _query_memory() rewritten:
- Intent-based type filtering (_memory_types_for_intent)
- Recency/frequency/distance ranking (_rank_memories)
- Section-labeled output, injected into system prompt

**Complexity-aware ModelRouter** � resolve() accepts complexity_score; _complexity_tier() upgrades capability when score >= 4. Orchestrator.plan() passes complexity via ModelRequirement.

**Reflection lessons** � runtime/lessons.py: LessonStore records tool success/failure patterns, persists to ~/.cozmo/lessons/lessons.json. CozmoRuntime._exec_tool() records every result. Lesson context injected into system prompt.

**Scheduler via Job system** � _ensure_scheduler() now gets job_manager from backend, passes it to _start_background_run().

**New tests** � tests/test_cognitive.py (22 tests): memory assembly, complexity routing, lesson store, scheduler integration.

**Test results**: 64 tests, 0 failures (42 v2 pipeline + 15 execution + 22 cognitive).

**Files created**: tests/test_cognitive.py, cozmo/runtime/lessons.py

**Files modified**: cozmo/webui_server.py (_ensure_scheduler passes job_manager), cozmo/runtime/engine.py (real ReAct loop), cozmo/runtime/runtime.py (execution_plan support, memory context, lesson recording), cozmo/runtime/model_router.py (complexity_score param), cozmo/orchestrator/orchestrator.py (complexity to ModelRouter)

**Verified**: 64 tests pass, imports clean, lint clean.
