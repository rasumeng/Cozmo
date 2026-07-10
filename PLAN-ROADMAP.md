# Cozmo Development Roadmap

## Current State (July 2026)

- **Backend**: Fully functional Python agent (ReAct loop, tools, memory, MCP, WebSocket)
- **WebUI**: Core chat works, many UI elements dead (settings, search, attach, mic)
- **TUI**: Chat/Collab/Code tabs work with real agent, no differentiation between modes

---

## Phase 0: Foundation (Current P0)

### 0.1 Chat Persistence (Backend Save)

Save conversations to `~/.cozmo/chats/` as `.md` files with YAML frontmatter (OKF standard). WebSocket backend already writes `.md` for TUI; extend to WebUI via REST API.

**Endpoints needed:**
- `GET /api/conversations` — list all conversations
- `GET /api/conversations/:id` — load single conversation
- `POST /api/conversations` — save/create
- `DELETE /api/conversations/:id` — delete
- `POST /api/conversations/:id/pin` — toggle pin

**Frontend:**
- `Conversation` type gets `mode: WorkspaceMode` field
- `useCozmoChat` loads from API on mount, saves on new/update/delete
- Backend WebSocket event includes conversation `id` for matching

**Files:** `webui_server.py`, `useCozmoChat.ts`, `types/index.ts`, `cozmo.ts`

### 0.2 Per-Mode Recent Lists

**Current:** Flat `Conversation[]` array, no mode filter.
**Fix:** Add `mode: WorkspaceMode` to `Conversation`. Sidebar filters by active tab. `onNewChat(mode)` creates conversation with mode tag.

**Files:** `Sidebar.tsx`, `useCozmoChat.ts`, `types/index.ts`

---

## Phase 1: Core UX (P1)

### 1.1 Settings Screen (Modal Overlay)

Full-screen sized modal overlay with:
- **Left sidebar**: sections list with search bar at top
- **Right panel**: section content
- Sections: Models, Tools, Memory, Skills, Connectors, General

**Config CRUD backend:** `GET /api/config`, `PUT /api/config`

**Files:** New `components/settings/SettingsModal.tsx`, `Sidebar.tsx` (wire up footer icons), `webui_server.py`

### 1.2 Input Bar + Menu

- Paperclip → `+` button opens dropdown menu
- Menu items: Attach files, Add to Project (stub), Skills > submenu, Connectors > submenu
- Model selector stays, defaults to `qwen3:8b`

**Files:** `PromptInput.tsx`

---

## Phase 2: Deep Features (P2)

### 2.1 Model Presets Editor

Settings > Models section:
- List of presets (Chat, Coder, Vision, Research) with model dropdown each
- Add custom preset (name + model)
- Delete custom presets
- Backend: update `config.toml` models section

### 2.2 Tools Section

Settings > Tools section:
- List of tools with name, description, enabled toggle
- Permission mode selector per tool (allow/ask/deny)
- Uses existing `fetchTools()` endpoint

### 2.3 Search Chats

- Search bar in sidebar triggers overlay
- Backend search endpoint: `GET /api/chats/search?q=...`
- Searches title + full content of `.md` files
- Frontend: debounced input, results list

---

## Phase 3: Power User (P3)

### 3.1 MCP Connectors Section

Settings > Connectors:
- Add/edit/remove MCP server entries
- Fields: name, command, args, env vars
- Backend: writes to `config.toml` `[mcp.servers]`

### 3.2 Skills Section

Settings > Skills:
- List installed skills (from `~/.cozmo/skills/` or `.cozmo/skills/`)
- Trigger: "Create Skill" opens skill-creator workflow
- Skills stored as `SKILL.md` per the Agent Skills standard
- Discovered during session start, injected into system prompt based on description matching

**Skill format (Agent Skills open standard):**
```
skill-name/
├── SKILL.md
│   ├── name: kebab-case
│   ├── description: trigger description (~100 words)
│   └── markdown instructions
├── scripts/
├── references/
└── assets/
```

### 3.3 Microphone / Speech-to-Text

- Browser `webkitSpeechRecognition` → fills input textarea
- Voice mode (empty input + mic used → voice conversation with TTS) → defer to P4

---

## Phase 4: Future (P4)

### 4.1 Voice Mode (Conversational)

- Two-way voice: STT + browser `SpeechSynthesis` or Ollama TTS
- Send button becomes "talk" when input empty

### 4.2 Collab: Repository-Aware Mode

- Auto-index opened repo via `ProjectIndex` (ChromaDB)
- Collab agent prompt includes: "you can search the repo with code_indexer"
- UI shows "Repo indexed" badge

### 4.3 Memory Viewer

- Settings > Memory section
- Browse/delete memory summaries from ChromaDB
- View embeddings stats

---

## Architecture Notes

### Backend Save Flow
```
WebUI → WS /ws/chat (real-time) | REST /api/conversations (persistence)
                            ↓
                    webui_server.py
                            ↓
              ChatManager (TUI reuse!)
              writes ~/.cozmo/chats/{id}.md
              + updates ~/.cozmo/chats/index.json
```

### Memory Flow (Already Implemented)
```
User message → ChromaStore.query() → top-k memories injected
Every N turns → LLM summarizes → ChromaStore.add() embedding
```

### Skill Integration
```
~/.cozmo/skills/{name}/SKILL.md
  → loaded at CozmoRuntime init
  → name+description added to system prompt
  → body loaded when LLM routes to skill
```

---

## Quick Reference: Config Sections in config.toml

| Section | Purpose | Settings UI |
|---------|---------|-------------|
| `[models]` | Role→model mapping | Model presets editor |
| `[permissions]` | Tool→allow/ask/deny | Tools section |
| `[mcp.servers]` | MCP connections | Connectors section |
| `[memory]` | Chunk sizes, thresholds | Memory section |
| `[runtime.tool_gate]` | Role→allowed tools | Tools section |
| `[search]` | SearXNG URL | General section |