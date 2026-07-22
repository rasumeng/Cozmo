# Cozmo Development Plan

## Active Roadmap

The vision is three distinct layers:

```
Cozmo Core
   |
Session Manager
   |
├── Chat  → ChatHandler   → LLM (fast path, no tools/plan/memory)
├── Agent → AgentRuntime  → Planner → Tools → Memory → State
└── Code  → CodeRuntime   → FileOps → Terminal → Diff Review
```

Current reality: Chat and Agent share the same monolithic ReAct loop. This plan fixes that.

---

### Phase 1: Separate the Identities (Current)

**Goal:** Make Chat, Agent, and Code actually different.

| # | Task | Why | Files |
|---|------|-----|-------|
| 1.1 | **ChatHandler** — lightweight conversational path | Every chat message pays agent overhead (routing, memory, skills, tool framework). This strips it to: `message → model → stream`. | NEW `core/chat/__init__.py`, NEW `core/chat/handler.py` |
| 1.2 | **AgentRuntime** — refactor runtime into agent directory | `runtime.py` (881 lines) does everything. Extract agent-role logic into `core/agent/runtime.py` with its own state management. | NEW `core/agent/__init__.py`, NEW `core/agent/runtime.py`, EDIT `core/runtime.py` (thin coordinator) |
| 1.3 | **Router decoupling** — extract `_route()` from runtime | Router should be a standalone function, not a method on CozmoRuntime. Repurpose dead `core/router.py`. | REWRITE `core/router.py`, EDIT `core/runtime.py` |
| 1.4 | **AgentState** — persistent cognitive state | Agent loses all state on restart. No goal tracking, no plan progress, no cross-session continuity. | NEW `core/agent/state.py` |
| 1.5 | **Structured Planner** — replace inline plan text | Plans are plain text stuffed into prompts. No step tracking, no dependency resolution, no pause/resume. | NEW `core/agent/planner.py`, EDIT `core/agent/runtime.py` |

---

### Phase 2: Make Agent Actually Agentic

**Goal:** Cognitive continuity — agent maintains goals, learns from failures, adapts plans.

| # | Task | Why |
|---|------|-----|
| 2.1 | **EventBus** — decouple monitoring from yield tuples | UI/logging/tracking coupled to inline yields. Cannot add background monitoring or activity feed without this. |
| 2.2 | **Reflector + LessonStore** — learn from failures | Errors vanish after the turn. No retry strategy, no pattern learning. |
| 2.3 | **PlanExecutor** — step-by-step execution with dependency resolution | Planner generates plans. Executor runs them with retry, partial failure recovery, replanning. |
| 2.4 | **Pause/Resume** — save/restore execution state | Multi-step tasks interrupted by max_steps or session close cannot resume. |

---

### Phase 3: Memory Engine — LanceDB + Sentence Transformers + OKF

**Goal:** LLM reasons, memory engine searches. High-quality persistent memory.

| # | Task | Why |
|---|------|-----|
| 3.1 | **LanceStore** — replace ChromaDB | ChromaDB's client/server overhead. LanceDB is local-first, disk-backed, native hybrid search. |
| 3.2 | **Sentence Transformers** — replace OllamaEmbeddings | Lighter, CPU-friendly, pre-loaded once. 384-dim vectors keep index small. |
| 3.3 | **OKF classification pipeline** | Every stored memory has type, title, tags, importance score, source. Index files enable progressive disclosure. |
| 3.4 | **Knowledge base indexing** | `read_knowledge`/`write_knowledge` files are flat text with no vector search. Index them. |
| 3.5 | **RAG pipeline** — query rewriting, chunking, reranking, citation tracking | Basic vector search is not RAG. |

---

### Phase 4: Advanced Agent Features

| # | Task | Why |
|---|------|-----|
| 4.1 | **Tool Risk Levels** (LOW/MEDIUM/HIGH/CRITICAL) | Flat allow/ask/deny cannot express "auto-allow safe, ask for risky, deny critical." |
| 4.2 | **Agent Router Profiles** | Different tasks need different models/tools/prompts. Profile dispatch within agent mode. |
| 4.3 | **LLM Provider Abstraction** | Ollama lock-in prevents using OpenAI, Anthropic, etc. |
| 4.4 | **Subagent Polish** — recursion limits, shared memory, structured output | `task()` tool spawns naked runtimes. No isolation, no context sharing. |
| 4.5 | **Scheduled Autonomous Runs** | Scheduler exists but not wired to AgentState or Planner. |

---

## Implementation Order (Next Session)

```
PHASE 1 (Current — Separate Identities):
  ├─ 1.1: ChatHandler                    [core/chat/handler.py]
  ├─ 1.2: AgentRuntime + agent/ dir      [core/agent/runtime.py]
  ├─ 1.3: Router decoupling              [core/router.py]
  ├─ 1.4: AgentState                     [core/agent/state.py]
  └─ 1.5: Structured Planner             [core/agent/planner.py]

PHASE 2 (Agentic Agent):
  ├─ 2.1: EventBus                       [core/agent/event_bus.py]
  ├─ 2.2: Reflector + LessonStore        [core/agent/reflector.py]
  ├─ 2.3: PlanExecutor                   [core/agent/planner.py]
  └─ 2.4: Pause/Resume                   [core/agent/state.py]

PHASE 3 (Memory Rewrite):
  ├─ 3.1: LanceStore                     [memory/lancedb_store.py]
  ├─ 3.2: Sentence Transformers          [memory/manager.py]
  ├─ 3.3: OKF pipeline                   [memory/manager.py]
  ├─ 3.4: Knowledge indexing             [tools/file_ops.py]
  └─ 3.5: RAG pipeline                   [memory/rag.py]

PHASE 4 (Advanced):
  ├─ 4.1: Tool Risk Levels               [tools/__init__.py, permissions.py]
  ├─ 4.2: Agent Profiles                 [core/agent/profiles.py]
  ├─ 4.3: LLM Provider ABC               [core/llm.py]
  ├─ 4.4: Subagent polish                [tools/task.py]
  └─ 4.5: Scheduled runs                 [scheduler.py, agent/state.py]
```

---

## Key Architecture Decisions

1. **Chat never pays agent tax** — no routing, no tools, no memory queries, no planning. Pure `model + history → answer`.
2. **Agent owns cognitive state** — goals, plans, observations, failures persisted across sessions.
3. **Planner generates structured plans** — typed Plan/PlanStep dataclasses, not text in prompts.
4. **EventBus decouples monitoring** — runtime emits typed events; WebSocket/TUI/logging subscribe independently.
5. **Reflector learns from failures** — error classification, retry strategies, LessonStore persists patterns.
6. **LanceDB over ChromaDB** — local-first, disk-backed, no daemon. Native hybrid search (vector + FTS).
7. **LLM reasons, memory engine searches** — memory retrieval is a pre-pipeline, not a runtime call.
8. **OKF-classified memories** — type, title, tags, importance, source on every entry.
9. **No database** — everything file-based: `~/.cozmo/chats/`, `~/.cozmo/projects/`, `~/.cozmo/memory/`, `~/.cozmo/agent_state/`.
10. **Three independent modes** — Chat, Agent, Code have separate handlers, not a shared loop with empty tool gates.

---

## Completed

- File & image attachments (upload, paste, drag-drop, thumbnails)
- Projects (CRUD, shared context, conversation linking)
- Skills system (SKILL.md format, CRUD, skill-creator seed)
- Connectors/MCP (config CRUD, catalog, status, tool discovery)
- WebUI Code mode (Terminal panel, Diff panel, DirectoryPicker, RightPanel)
- Per-Mode Input Bars + Collab Project Management
- MCP tool integration (stdio, auto-discovery, health checks)
- Background task queue + scheduler
- Subagent spawning (explore/scout/general + custom agents)
