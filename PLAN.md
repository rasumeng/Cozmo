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

### Phase 4: Subagent System (Medium Priority)

**Problem:** No subagent/task spawning capability. `.cozmo/agents/` directory exists with `review.md` but isn't wired into runtime.

**Changes:**
- `core/runtime.py`: Load custom agents from `.cozmo/agents/*.md` files
- New tool `task(description, prompt, subagent_type)` that spawns sub-CozmoRuntime instances
- Subagent types: `@general` (full agent), `@explore` (read-only), `@scout` (external research)
- `webui_server.py`: Handle subagent events in WebSocket stream
- Frontend: Show subagent progress in activity panel

**Files:** `cozmo/core/runtime.py`, `cozmo/tools/` (new task tool), `cozmo/webui_server.py`

---

### Phase 5: Collab Polish + Async Workflow (Low Priority)

**Current state:** Collab mode has plan generation → approval → execution. Projects CRUD exists. Missing: async background tasks, error recovery, progress tracking.

**Changes:**
- Improve collab mode error recovery and step progress reporting
- Add background task queue with status persistence
- Add task resume capability after session restart
- Add guided workflows for common collab tasks

**Files:** `cozmo/core/runtime.py`, `cozmo/webui_server.py`

---

### Phase 6: Diagnostics + Sourcegraph (Low Priority)

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
PHASE 4 (Subagents):                    [runtime.py, tools/]
PHASE 5 (Collab):                       [runtime.py, webui_server.py]
PHASE 6 (Diagnostics):                  [tools/]
```

---

## Key Architecture Decisions

1. **Attachments stored on disk**, metadata in conversation messages. No base64 in chat JSON.
2. **Projects are lightweight groupings** — a project is a list of conversation IDs + shared context text.
3. **Skills are SKILL.md files** on disk. The "Skill Creator" skill guides the agent through creating other skills.
4. **Connectors = MCP servers** on backend. Settings UI manages them.
5. **No database** — everything is file-based: `~/.cozmo/chats/`, `~/.cozmo/projects/`, `~/.cozmo/skills/`, `~/.cozmo/attachments/`, `~/.cozmo/memory/`.
6. **Code mode diffs are session-scoped** — computed from tool args on the backend (`difflib.unified_diff`).
7. **Terminal is lang-agnostic** — all tool output shows equally.
8. **Per-mode input bars share a single PromptInput** with conditional rendering by `mode` prop.

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
