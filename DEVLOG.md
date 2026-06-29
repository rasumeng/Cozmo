# Cozmo Devlog

_Chronological development notes. Each entry = date + what changed + why + decisions._

---

### 2025-07-09 — Project inception

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

### 2025-07-09 — Phase 1: Package refactor

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

**Status**: `pip install -e .` → `cozmo init` generates config. `cozmo run "query"` routes to interactive_session stub.

---

### YYYY-MM-DD — Phase 2: Orchestrator

_(TBD)_

---

### YYYY-MM-DD — Phase 3: Memory + Telegram

_(TBD)_
