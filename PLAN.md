# Cozmo Development Plan

## Roadmap: Next Phase

This is the active development roadmap. Items are grouped by priority phase.

---

### Phase 1: UX Polish + Prompt Generalization (High Priority)

#### 1A. Lightweight Mode Lock

**Problem:** Backend forces lightweight model for all roles when enabled, but UI ModelSelect dropdowns remain interactive — misleading.

**Current state:**
- `config.py:37` — `lightweight_mode: False` in runtime config
- `model_manager.py:29-33` — `_model_name()` returns lightweight model unconditionally when set
- `SettingsModal.tsx:293-298` — Shows banner but dropdowns stay editable

**Changes:**
- `SettingsModal.tsx`: Add `disabled` prop to `ModelSelect`. When `isLightweight=true`, disable all model dropdowns, apply `opacity-50` + `cursor-not-allowed`
- No backend changes needed

**Files:** `cozmo/webui/src/components/settings/SettingsModal.tsx`

#### 1B. Memory UI

**Problem:** Settings > Memory shows only two read-only config values. No way to browse, search, or view stored memories. No visibility into storage location.

**Changes:**
- Backend: Add `GET /api/memory/search?q=...` and `DELETE /api/memory/{id}` endpoints to `webui_server.py`
- Backend: Add `list_all()` and `delete(id)` methods to `memory/chroma_store.py`
- Frontend: Add "Memory Browser" panel in Settings > Memory with search box, results list (timestamp, text preview, distance), delete button per entry
- Frontend: Add "Open memory folder" button that reveals `~/.cozmo/memory/`
- Frontend: Add info panel explaining what memory does and where data lives

**Files:** `cozmo/webui_server.py`, `cozmo/memory/chroma_store.py`, `cozmo/memory/manager.py`, `cozmo/webui/src/components/settings/SettingsModal.tsx`

#### 1C. Prompt Generalization

**Problem:** Prompts hardcoded for specific use cases (gaming, coding). Route prompt has game-specific keywords. Identity prompt describes Cozmo as only a coding agent.

**Changes:**
- `runtime.py`: Remove game-specific keywords from `_RESEARCH_KEYWORDS` ("wuthering waves", "genshin", "gacha", "banner", "tier list")
- `runtime.py`: Make `_IDENTITY` more general — describe Cozmo as a general-purpose assistant
- `runtime.py`: Add diverse examples to `_ROUTE_PROMPT` covering general use cases
- `config.py`: Add optional `personality` config field for user-defined instructions
- `runtime.py`: Inject user personality into system prompt if configured

**Files:** `cozmo/core/runtime.py`, `cozmo/config.py`

---

### Phase 2: Core Tools + Open Folder (High Priority)

#### 2A. Open Folder Fix

**Problem:** `_safe_path()` in `file_ops.py` restricts reads to `Path.cwd()` only. When user sets a project directory, reads should work from that directory. Also, `ProjectIndex` reads entire files into ChromaDB upfront — wasteful.

**Changes:**
- `file_ops.py`: Add `set_allowed_root(root)` function to update `ALLOWED_ROOT` at runtime
- `webui_server.py`: Call `set_allowed_root()` when `set_directory` is handled
- `code_indexer.py`: Add lazy loading — index file metadata upfront, read content only on query. Use file modification times to detect stale entries.

**Files:** `cozmo/tools/file_ops.py`, `cozmo/webui_server.py`, `cozmo/code_indexer.py`

#### 2B. Add `glob` Tool

**Problem:** No pattern-based file discovery. Agent can only `list_directory` or `grep_search`.

**Changes:**
- New tool `glob_search(pattern, path=".")` using Python `fnmatch` or `wcmatch`
- Register in `tools/__init__.py`
- Add to `_tool_gate` for work/collab modes

**Files:** `cozmo/tools/file_ops.py` (add function), `cozmo/tools/__init__.py`

#### 2C. Upgrade `read_file` → `read` with Offset/Limit

**Problem:** `read_file` has 5000 char hard cap, no line range support. Claude Code's `read` supports offset/limit.

**Changes:**
- Rename `read_file` → `read` (keep `read_file` as alias for backwards compat)
- Add `offset` (line number, 1-indexed) and `limit` (max lines) parameters
- Remove 5000 char hard cap — use configurable max from `runtime.max_tool_output_chars`
- Return line-numbered output like `1: content\n2: content`

**Files:** `cozmo/tools/file_ops.py`

#### 2D. Add `webfetch` Tool

**Problem:** No URL fetching capability. Listed in roadmap as a general skill.

**Changes:**
- New tool `webfetch(url, format="markdown")` using `trafilatura` (already in dependencies) or `httpx`
- Return page content in markdown/text/html format
- Add timeout and size limits
- Register in tools

**Files:** `cozmo/tools/web_search.py` (add function), `cozmo/tools/__init__.py`

---

### Phase 3: Memory OKF + RAG Enhancement (Medium Priority)

**Current state:** ChromaDB + Ollama embeddings work. OKF frontmatter only on knowledge base writes, not conversation memories. No hybrid search. No memory types.

**Changes:**
- `memory/manager.py`: Add OKF metadata (type, title, tags) to conversation summaries stored in ChromaDB
- `memory/chroma_store.py`: Add hybrid search (combine ChromaDB similarity with keyword matching)
- `memory/manager.py`: Add memory types — separate metadata tags for conversation summaries, user preferences, project context, learned facts
- `memory/manager.py`: Add importance scoring (recency + relevance + frequency)
- `memory/manager.py`: Add consolidation — periodically merge similar/duplicate memories
- `memory/manager.py`: Add user preference detection and storage

**Files:** `cozmo/memory/manager.py`, `cozmo/memory/chroma_store.py`, `cozmo/core/runtime.py`

---

### Phase 4: Autonomous Agent Core (High Priority)

Port autonomous agentic features from CozmoBrain into Cozmo. These components exist in the CozmoBrain prototype but are missing or simplified in Cozmo.

Target architecture:

```
User Input
    |
CozmoRuntime (upgraded)
    |
Cognitive Loop
 ├── Think/Route
 ├── Plan (structured with Planner)
 ├── Execute (with Reflector error recovery)
 ├── Reflect (learn from failures)
 ├── Update State (persistent AgentState)
 └── Continue
    |
EventBus → UI / logging / monitoring (decoupled)
```

---

#### 4A. Persistent AgentState + StateStore

Port `CozmoBrain/agent/state.py` → `cozmo/core/agent_state.py`

**Purpose:** Track persistent cognitive state across sessions — goals, status, plan progress, observations, failures, tool history.

**Dataclasses to port:**
- `AgentStatus` — state enum: IDLE, THINKING, PLANNING, EXECUTING, REFLECTING, WAITING, COMPLETE, ERROR
- `Observation` — source, content, timestamp
- `AgentEvent` — event_type, description, data, timestamp
- `AgentState` — current_goal, status, active_plan, observations, events, tools_used, failures, scratchpad
- `StateStore` — JSON persistence to `~/.cozmo/agent_state.json`

**Integration:**
- `CozmoRuntime.__init__()` loads state on startup
- `run_stream()` tracks state transitions through lifecycle
- `_remember()` saves state after each turn
- State summary injected into system prompt for context
- Config: `agent_state_path` in config.toml

**Files:**
- NEW `cozmo/core/agent_state.py`
- EDIT `cozmo/core/runtime.py`
- EDIT `cozmo/config.py`

---

#### 4B. EventBus

Port `CozmoBrain/agent/events.py` → `cozmo/core/event_bus.py`

**Purpose:** Decouple monitoring, logging, and UI updates from runtime. Everything becomes observable.

**Event types:** goal_started, goal_completed, plan_created, tool_failed, step_completed, reflection_completed, state_changed, error, warning, info

**Integration:**
- `CozmoRuntime.__init__()` creates EventBus
- `run_stream()` emits events alongside yield tuples
- WebSocket server subscribes and forwards to frontend
- Enables future: background monitoring, autonomous task scheduling, activity feed

**Files:**
- NEW `cozmo/core/event_bus.py`
- EDIT `cozmo/core/runtime.py` (emit events)
- EDIT `cozmo/webui_server.py` (forward events to WebSocket)

---

#### 4C. Planner + TaskQueue + PlanExecutor

Port `CozmoBrain/agent/planner.py` → `cozmo/core/planner.py`

**Purpose:** Replace inline `_generate_plan()` with a structured planner that generates, validates, executes, and replans.

**Components to port:**
- `Plan` — goal, steps (PlanStep list), context, timestamp, `to_text()`
- `PlanStep` — id, description, tool, args, depends_on, status (PENDING/READY/RUNNING/DONE/FAILED/SKIPPED)
- `TaskQueue` — dependency resolution state machine: `get_ready()`, `mark_done()`, `mark_failed()`, `all_done()`
- `PlanExecutor` — execute steps with retry loop, integrates with Reflector
- `Planner` — LLM-based plan generation, JSON parsing, validation (tool names exist, no cycles, max steps), `replan()` on failure

**Integration:**
- Replace `_generate_plan()` with `Planner.create_plan()`
- Replace `_gather_agent_context()` with `Planner` using tool descriptions
- Agent mode uses `PlanExecutor.execute_plan()` with step-by-step progress
- Replan on partial failure in agent mode
- Plan validation prevents hallucinated tool names

**Files:**
- NEW `cozmo/core/planner.py`
- EDIT `cozmo/core/runtime.py` (swap inline plan gen for Planner)
- EDIT `cozmo/core/llm.py` (add `StatelessLLM` wrapper for one-shot LLM calls)

---

#### 4D. Reflector + LessonStore

Port `CozmoBrain/agent/reflector.py` → `cozmo/core/reflector.py`

**Purpose:** Analyze tool failures, classify errors, recommend recovery strategies, store lessons for future reference. Currently Cozmo has no error learning — errors vanish after the turn.

**Components to port:**
- `ErrorType` — enum: TIMEOUT, AUTH, NOT_FOUND, PARSE, RATE_LIMIT, VALIDATION, LOGIC, UNKNOWN
- `RetryStrategy` — enum: RETRY, MODIFY_PARAMS, CHANGE_TOOL, DECOMPOSE, ABORT
- `ReflectionResult` — success, error_type, retry_strategy, suggestion, modified_args, confidence
- `LessonStore` — persists failure patterns with match scoring, `format_for_prompt()` surfaces relevant lessons
- `Reflector` — `before_step()`/`after_step()` hooks, error classification, strategy recommendation, param fixes, optional LLM-powered deep analysis

**Integration:**
- `PlanExecutor` calls `Reflector.before_step()`/`after_step()` each step
- On failure, Reflector suggests modified args or alternative approach
- `LessonStore` persists to `~/.cozmo/lessons.json`
- Lessons injected into system prompt after repeated failures
- Config: `reflection.llm_enabled` in config.toml

**Files:**
- NEW `cozmo/core/reflector.py`
- EDIT `cozmo/core/planner.py` (PlanExecutor uses Reflector)
- EDIT `cozmo/config.py` (add `[reflection]` section)

---

#### 4E. Tool Risk Levels

Port `CozmoBrain/agent/tool_registry.py` (RiskLevel + ToolSpec) into Cozmo's tool registry.

**Purpose:** Enable nuanced permission gating — "allow LOW risk, ask for HIGH, deny CRITICAL". Currently Cozmo has flat allow/ask/deny.

**Changes:**
- Add `RiskLevel` enum to `cozmo/tools/__init__.py` (LOW/MEDIUM/HIGH/CRITICAL)
- Add `risk_level` field to tool registration (decorator param: `@register_tool(risk="medium")`)
- Add `category` field for tool classification
- Permission system uses risk level: e.g. "allow LOW/MEDIUM without asking, ask for HIGH, deny CRITICAL"
- Add `by_risk(max_risk)` filter for mode-based tool gating

**Files:**
- EDIT `cozmo/tools/__init__.py` (RiskLevel, decorator upgrade)
- EDIT existing tool files (add risk/category metadata)
- EDIT `cozmo/core/permissions.py` (risk-aware resolution)
- EDIT `cozmo/core/runtime.py` (risk-based tool gate)

---

#### 4F. Agent Router Profiles

Port `CozmoBrain/agent/agent_router.py` → `cozmo/core/agent_router.py`

**Purpose:** Route queries to specialized agent profiles (coder/researcher/writer) with different models, tool sets, and system prompts. Currently Cozmo has mode dispatch (chat/work/research/agent/vision) but no profile-based specialization.

**Components to port:**
- `AgentProfile` — name, description, model, allowed tool categories, system prompt override, risk max
- `AgentRouter` — register profiles, route queries via keyword + LLM fallback

**Integration:**
- Router runs after mode dispatch, selects profile within mode
- Profile model overrides mode model in ModelManager
- Profile tool categories filter available tools
- Config: `[agents.profiles]` in config.toml

**Files:**
- NEW `cozmo/core/agent_router.py`
- EDIT `cozmo/core/runtime.py` (profile-aware tool selection)
- EDIT `cozmo/core/model_manager.py` (model override per profile)
- EDIT `cozmo/config.py` (profile config section)

---

### Phase 5: Subagent System Polish (Medium Priority)

**Current state:** `.cozmo/agents/` directory exists with `review.md`. `task()` tool implemented with explore/scout/general + custom agent loading from `.md` files. Wiring into runtime is partial.

**Remaining changes:**
- `core/runtime.py`: Load custom agents from `.cozmo/agents/*.md` directly in runtime (not just task tool)
- `webui_server.py`: Handle subagent events in WebSocket stream
- Frontend: Show subagent progress in activity panel
- Add `builder` (surgical edit) and `reviewer` (diff review) built-in subagent types
- Structured output contracts for subagents (parseable formats)

**Files:** `cozmo/core/runtime.py`, `cozmo/tools/task.py`, `cozmo/webui_server.py`

---

### Phase 6: Collab Polish + Async Workflow (Low Priority)

**Current state:** Collab mode has plan generation → approval → execution. Projects CRUD exists. Missing: async background tasks, error recovery, progress tracking.

**Changes:**
- Integrate Planner + TaskQueue for structured plan execution in collab mode
- Add background task queue with status persistence (uses EventBus + AgentState)
- Add task resume capability after session restart
- Add guided workflows for common collab tasks

**Files:** `cozmo/core/runtime.py`, `cozmo/core/planner.py`, `cozmo/core/event_bus.py`, `cozmo/webui_server.py`

---

### Phase 7: Diagnostics + Sourcegraph (Low Priority)

**Changes:**
- Add `diagnostics(path)` tool — stub for LSP error retrieval (can be enhanced later)
- Add `sourcegraph(query)` tool — search public repos (requires API config)

**Files:** `cozmo/tools/` (new files)





---

## Implementation Order

```
PHASE 1 (UX Polish):
  ├─ 1A: Lightweight mode lock          [SettingsModal.tsx]
  ├─ 1B: Memory UI                      [webui_server.py, chroma_store.py, SettingsModal.tsx]
  └─ 1C: Prompt generalization          [runtime.py, config.py]

PHASE 2 (Core Tools):
  ├─ 2A: Open Folder fix                [file_ops.py, webui_server.py, code_indexer.py]
  ├─ 2B: Add glob tool                  [file_ops.py]
  ├─ 2C: Upgrade read with offset/limit [file_ops.py]
  └─ 2D: Add webfetch tool              [web_search.py]

PHASE 3 (Memory):                       [manager.py, chroma_store.py]

PHASE 4 (Autonomous Agent Core):
  ├─ 4A: AgentState + StateStore        [agent_state.py NEW, runtime.py, config.py]
  ├─ 4B: EventBus                       [event_bus.py NEW, runtime.py, webui_server.py]
  ├─ 4C: Planner + TaskQueue            [planner.py NEW, runtime.py, llm.py]
  ├─ 4D: Reflector + LessonStore        [reflector.py NEW, planner.py, config.py]
  ├─ 4E: Tool Risk Levels               [tools/__init__.py, permissions.py, runtime.py]
  └─ 4F: Agent Router Profiles          [agent_router.py NEW, runtime.py, model_manager.py, config.py]

PHASE 5 (Subagents):                    [runtime.py, tools/task.py, webui_server.py]
PHASE 6 (Collab):                       [runtime.py, planner.py, event_bus.py, webui_server.py]
PHASE 7 (Diagnostics):                  [tools/]
```

---

## Key Architecture Decisions

1. **Attachments stored on disk**, metadata in conversation messages. No base64 in chat JSON.
2. **Projects are lightweight groupings** — a project is a list of conversation IDs + shared context text.
3. **Skills are SKILL.md files** on disk. The "Skill Creator" skill guides the agent through creating other skills.
4. **Connectors = MCP servers** on backend. Settings UI manages them.
5. **No database** — everything is file-based: `~/.cozmo/chats/`, `~/.cozmo/projects/`, `~/.cozmo/skills/`, `~/.cozmo/attachments/`, `~/.cozmo/memory/`, `~/.cozmo/agent_state/`.
6. **Code mode diffs are session-scoped** — computed from tool args on the backend (`difflib.unified_diff`).
7. **Terminal is lang-agnostic** — all tool output shows equally.
8. **Per-mode input bars share a single PromptInput** with conditional rendering by `mode` prop.
9. **Autonomous agent state is persistent** — `AgentState` saves goals/observations/failures to `agent_state.json`. Survives restarts. Loaded on CozmoRuntime init.
10. **EventBus decouples monitoring** — runtime emits typed events; WebSocket / TUI / logging subscribe independently. No hardcoded yield tuples for status.
11. **Planner replaces inline plan gen** — structured plan with dependency resolution, validation, retry, and replanning. TaskQueue manages step state machine.
12. **Reflector learns from failures** — error classification, recovery strategies, LessonStore persists patterns. LLM-powered root cause analysis optional.
13. **Tool risk levels replace flat permission gating** — LOW/MEDIUM/HIGH/CRITICAL tiers enable nuanced auto-allow/ask/deny per mode.
14. **Agent profiles specialize behavior** — AgentRouter routes to coder/researcher/writer profiles with different models, tool sets, and system prompts within the existing mode system.

---

## Completed Phases (v0.1.0)

The following features are implemented and working:

- **Phase 1-2:** File & image attachments (upload, paste, drag-drop, thumbnails)
- **Phase 3:** Projects (CRUD, shared context, conversation linking)
- **Phase 4:** Skills system (SKILL.md format, CRUD, skill-creator seed)
- **Phase 5:** Connectors/MCP (config CRUD, catalog, status, tool discovery)
- **Phase 6:** "+" Menu wiring (project picker, skill picker, connector status)
- **Phase 7:** Code Mode UI (Terminal panel, Diff panel, DirectoryPicker, RightPanel)
- **Phase 8:** Per-Mode Input Bars + Collab Project Management (create/import/use-folder wizards)


## Overall assessment

From what I can see, SettingsModal.tsx is feature-rich but trying to do too much. The strongest architectural issues are:

1. SettingsModal is far too large (should be broken into smaller section/components).
  * This is probably the biggest issue I noticed.
    Everything lives inside one file.

    You have

    SettingsModal
    ModelSelect
    PermissionSelect
    MemorySettings
    MemoryCard
    SkillsSection
    ConnectorsSection
    ConnectorDetail

    and probably over 2000 lines.

    That makes it difficult to maintain.

    I'd split it into

    settings/

        SettingsModal.tsx

        sections/
            ModelsSection.tsx
            MemorySection.tsx
            SkillsSection.tsx
            ConnectorsSection.tsx
            GeneralSection.tsx
            ToolsSection.tsx

        components/
            ModelSelect.tsx
            PermissionSelect.tsx
            MemoryCard.tsx
            ConnectorCard.tsx
            ConnectorDetail.tsx

That alone would massively improve maintainability.
2. Skills lack parity with Connectors—there's no search, categories, metadata, or marketplace.
3. The roadmap never actually includes a Skill Marketplace, so your inability to find one is expected; it hasn't been designed or implemented.
4. Memory UI depends on backend APIs that must exist for it to work.
5. The Connector experience feels like a polished "app store," while the Skills experience still feels like a simple CRUD file manager.
