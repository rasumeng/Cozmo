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
