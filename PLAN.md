# Cozmo Development Plan

## Architecture v3 — Task-Based Execution

Cozmo transitions from a **mode-based multi-assistant** (Chat/Agent/Code with separate pipelines)
to a **task-based single intelligent system**. Every user request becomes a `Task`.
The system determines intent, complexity, strategy, tools, and model — the user never chooses a mode.

```
                        ┌──────────────────┐
                        │   Event Bus      │
                        │  (central pub/sub)│
                        └──────────────────┘
                               │
User Message → Orchestrator → JobManager → Engine (stateless)
                    │              │
               IntentDetector  Job lifecycle
               GoalExtractor   (pause/resume/
               PolicyEngine     cancel/retry/
               Complexity       checkpoint)
               CapabilityReg
               ModelRouter
```

### Core Concepts

| Concept | Role |
|---------|------|
| **Task** | Universal currency. Every request creates one. Has id, goal, status, execution history. |
| **Goal** | What to accomplish. Extracted from user message, resolved via memory for continuations. |
| **Intent** | Kind of work (CODING, RESEARCH, CONVERSATION, PLANNING, VISION). |
| **Job** | Execution instance of a Task. Stateless Engine receives a Job and streams events. |
| **Capability** | Declarative unit of functionality (tools, models, permissions, planner strategy). |
| **WorkspaceContext** | Active project state: directory, files, git status, current objectives. |

### Architecture Principles

1. **Task is universal currency** — not conversations, not messages, not modes.
2. **Orchestrator is thin** — coordinates, does NOT execute. Delegates everything.
3. **Engine is stateless** — pure ReAct loop. No knowledge of modes, tasks, or intents.
4. **Everything speaks through events** — components subscribe to EventBus.
5. **Policy gates all action** — no destructive operation bypasses policy check.
6. **Memory enriches early** — context resolution precedes planning.
7. **Capabilities are composable** — each has tools, permissions, model needs, risk.
8. **Model routing is resource-aware** — considers VRAM, loaded models, latency.

---

## Migration Plan (6 Phases)

### Phase 0: Foundation (COMPLETE)
**No behavior change.** Restructure directories, create dataclass types, set up aliases.

Create:
- `cozmo/runtime/` — core execution (engine.py, event_bus.py, session.py, model_router.py, resources.py, etc.)
- `cozmo/orchestrator/` — task_types.py (Task, Goal, TaskProfile, ExecutionPlan, ExecutionHistory)
- `cozmo/jobs/` — job.py (Job, JobStatus, Checkpoint)
- `cozmo/capabilities/` — registry.py, base.py, builtin.py
- `cozmo/planner/` — llm_planner.py (moved from core/agent/)
- `cozmo/runtime/workspace.py` — WorkspaceContext (active project state)

Keep:
- `cozmo/core/` as alias → `cozmo/runtime/` (all existing imports work)
- `force_mode` as developer debugging compatibility layer
- All existing agent/ files in place (will be migrated in Phase 1-4)

Add:
- `force_capability` / `force_model` parameters (developer override, not user-facing)

### Phase 1: Unified Pipeline
**Core migration.** The ReAct loop no longer branches on mode.

- Replace `core/router.py` with `orchestrator/intent.py` (IntentDetector)
- Build `orchestrator/complexity.py` (ComplexityEstimator)
- Build `orchestrator/orchestrator.py` (lightweight coordinator, ~150 lines)
- Remove mode branching from `engine.py` (`_MODE_DISCIPLINE`, `_tool_gate`, per-mode temps)
- Remove `force_mode` from pipeline (keep as deprecated compat for 1 release)
- Build `runtime/model_router.py` (capability-based model selection)
- Build `capabilities/builtin.py` (Python-based capability definitions)
- Unify `webui_server.py` pipeline (no more force_mode passthrough)

### Phase 2: Job Manager + Pause/Resume
**Long-running tasks become proper Job objects.**

- `jobs/manager.py` — JobManager (submit, pause, resume, cancel, retry)
- `jobs/persistence.py` — save/load Jobs and Checkpoints
- Engine yields checkpoint events periodically
- Continuation ("keep going") loads Task + last Job checkpoint
- Background runs unified with foreground JobManager

### Phase 3: Safety + Awareness
**Policy gates all tasks. Resource tracking.**

- `orchestrator/policy.py` — PolicyEngine (permission mode, destructive patterns, workspace trust)
- `runtime/resources.py` — ResourceManager (VRAM, loaded models, concurrency)
- ModelRouter consults ResourceManager before selecting model

### Phase 4: Capability-Based Tool Selection
**Tools driven by capability resolution, not mode gating.**

- `capabilities/registry.py` — resolves task profile → capability list → tool set
- Remove `_tool_gate` completely
- Any tool available to any task if capability supports it

### Phase 5: Frontend Redesign (COMPLETE)
**No mode tabs. Workspace navigation.**

- Removed `WorkspaceMode`, `WorkspaceTabs`, `workspaceModes.ts`
- Built `WorkspaceNav`: Conversations | Projects | Memory | Knowledge | Settings
- Unified LandingPage (no per-mode colors/logos)
- Simplified PromptInput (no mode-conditioned UI)
- Removed mode from WebSocket protocol, conversation persistence

### Phase 6: Polish + Data Migration (COMPLETE)
**Clean up. Migrate. Release.**

- `cozmo migrate v1-to-v2` — strips `mode` from persisted conversations
- Deleted `cozmo/core/`, `cozmo/core/agent/`, `cozmo/core/chat/`
- Removed old sidebar components (WorkspaceTabs.tsx)
- Updated docs, bumped version to 0.2.0

---

## Directory Structure (Target)

```
cozmo/
├── orchestrator/       # Coordination — thin, delegates everything
│   ├── orchestrator.py # Event stitcher
│   ├── intent.py       # IntentDetector + GoalExtractor
│   ├── complexity.py   # ComplexityEstimator
│   ├── policy.py       # PolicyEngine
│   └── task_types.py   # Task, Goal, TaskProfile, ExecutionPlan, ExecutionHistory
│
├── capabilities/       # Declarative capability system (Python first → TOML)
│   ├── registry.py     # CapabilityRegistry
│   ├── base.py         # Capability dataclass
│   ├── builtin.py      # Built-in capabilities
│   └── reflection.py   # Per-capability lesson stores
│
├── planner/            # Hybrid planning
│   ├── planner.py      # HybridPlanner (dispatcher)
│   ├── templates.py    # Level 1: template plans
│   ├── heuristics.py   # Level 2: workflow patterns
│   ├── llm_planner.py  # Level 3: LLM plans (moved from core/agent/)
│   └── plan.py         # Plan, PlanStep dataclasses
│
├── jobs/               # Job lifecycle
│   ├── manager.py      # JobManager
│   ├── job.py          # Job, JobStatus, Checkpoint
│   └── persistence.py  # Checkpoint persistence
│
├── runtime/            # Execution fundamentals
│   ├── engine.py       # Stateless ReAct loop
│   ├── event_bus.py    # Central pub/sub
│   ├── session.py      # SessionState (generalized from AgentState)
│   ├── workspace.py    # WorkspaceContext (active project state)
│   ├── model_router.py # Cost-aware model selection
│   ├── resources.py    # VRAM/model/concurrency tracking
│   ├── prompts.py      # System prompt builder
│   ├── context.py      # Token estimation
│   ├── tool_registry.py
│   ├── tool_risk.py
│   ├── permissions.py
│   └── reflection.py   # Error reflection (always on)
│
├── providers/          # LLM providers
├── memory/             # Memory (knowledge + retrieval)
├── tools/              # Tool implementations
├── webui/              # React frontend
├── config.py           # Config
└── cli.py              # CLI entry point
```

---

## Completed

- Phase 0 architecture restructuring
- Task/Goal/Job dataclass types
- WorkspaceContext, EventBus, Session
- Runtime/Engine/ModelRouter/ResourceManager skeletons
- Backward-compat core/ → runtime/ stubs
- force_capability / force_model config params
- **Phase 1: Unified pipeline**
  - `orchestrator/intent.py` — IntentDetector + GoalExtractor (replaces core/router.py)
  - `orchestrator/complexity.py` — ComplexityEstimator (heuristic-based)
  - `orchestrator/orchestrator.py` — lightweight coordinator (~150 lines)
  - `runtime/runtime.py` — removed `_MODE_DISCIPLINE`, `_tool_gate`, per-mode temps
  - `runtime/runtime.py` — unified ReAct loop (no agent/research mode branching)
  - `runtime/runtime.py` — `force_mode` deprecated (logged, ignored for routing)
  - `webui_server.py` — removed `force_mode` passthrough, unify pipeline
  - `core/router.py` — deprecated re-export stub
- **Phase 2: Job Manager + Pause/Resume**
  - `jobs/manager.py` — JobManager (submit, pause, resume, cancel, retry, start, complete)
  - `jobs/persistence.py` — JobStore (JSON file persistence for jobs and checkpoints)
  - `runtime/engine.py` — checkpoint_interval + Checkpoint events + resume support
  - `orchestrator/continuation.py` — ContinuationHandler (continue task, retry job, build EngineContext)
  - `core/` — backward-compat stubs for JobManager, JobStore, ContinuationHandler

- **Phase 3: Safety + Awareness**
  - `orchestrator/policy.py` — PolicyEngine with 3 modes (relaxed/normal/strict)
  - Policy: destructive command detection (rm -rf, format, sudo rm, batch delete)
  - Policy: workspace trust evaluation (git repo, package.json, etc.)
  - Policy: risk-based decisions (LOW auto-allow, CRITICAL deny, MEDIUM/HIGH ask)
  - `runtime/resources.py` — full ResourceManager with concurrency gating
  - ResourceManager: VRAM tracking, model load/unload with OOM prevention
  - ResourceManager: LRU eviction, `best_available()` ranking
  - ResourceManager: job reservation (`reserve_job` / `release_job`)
  - `runtime/model_router.py` — consults ResourceManager for VRAM/loaded status
  - ModelRouter: prefers loaded models, falls back through capability chain
  - `core/policy.py` — backward-compat stub

- **Phase 4: Capability-Based Tool Selection**
  - `runtime/runtime.py` — `_tools_for_mode` accepts `allowed_tools` list from capability resolution
  - `runtime/runtime.py` — `run_stream` resolves capabilities via `CapabilityRegistry.get_tool_names()`
  - `runtime/runtime.py` — `run_stream` selects model via `ModelRouter.resolve()` using capability
  - `runtime/runtime.py` — `_INTENT_TO_CAP_IDS` maps intent strings to capability IDs
  - `runtime/model_manager.py` — `bind_model()` and `client_for_model()` bypass role-based model selection
  - `runtime/model_manager.py` — `_get_provider_for_model()` creates provider for explicit model name
   - Pipeline: intent → capability IDs → tool names → filtered tools → model name → execution

- **Phase 5: Frontend Redesign**
  - Removed `WorkspaceMode`, `WorkspaceTabs`, `workspaceModes.ts`
  - Built `WorkspaceNav`: Conversations | Projects | Memory | Knowledge | Settings
  - Unified LandingPage, simplified PromptInput
  - Removed mode from WebSocket protocol, conversation persistence
  - Stripped mode from all frontend files (types, hooks, services, components, fixtures)
  - TypeScript compiles clean with zero mode references

- **Phase 6: Polish + Data Migration**
  - Deleted `cozmo/core/` (all backward-compat stubs + old agent/chat/providers code)
  - Updated `cli.py` imports from `cozmo.core.*` → `cozmo.runtime.*`
  - `cozmo migrate v1-to-v2` — strips `mode` from persisted conversations
  - Bumped version to 0.2.0
