# Cozmo Feature Implementation Plan

## Current State

- **Attachments**: "+" menu stubbed (4 buttons, no handlers). No file input, paste, or drag-drop.
- **ChatMessage type**: Only `content` (string). No attachments/images field.
- **Backend**: Only `/api/transcribe` handles uploads. No file upload endpoint, no attachment storage.
- **Sidebar**: Filters by workspace mode (chat/collab/code). No project grouping.
- **Settings > Skills**: "No skills installed yet" placeholder.
- **Settings > Connectors**: Reads MCP server list from config, display-only.
- **Conversation persistence**: `.md` files store text only.
- **WebSocket protocol**: No file-related message types.

---

## Phase 1: File & Image Attachments

### Frontend — types/index.ts

```typescript
// Add to ChatMessage
export interface Attachment {
  id: string
  type: 'image' | 'file'
  name: string
  mime: string
  size: number
  url: string      // /api/attachments/{id}/file
  thumbnail?: string // /api/attachments/{id}/thumb (for images)
}
// Add to ChatMessage:
//   attachments?: Attachment[]
```

### Frontend — services/cozmo.ts

- Add `uploadFile(file: File): Promise<Attachment>` — POST `/api/attachments` with `FormData`
- Add `deleteAttachment(id: string): Promise<void>` — DELETE `/api/attachments/{id}`

### Frontend — PromptInput.tsx

1. **File input**: Hidden `<input type="file" multiple accept="image/*,.pdf,.txt,.py,.js,.ts,.md,.json,.csv,.docx,.xlsx">`
2. **"+ Attach files or photos"** handler: triggers hidden file input, uploads files, stores `Attachment[]` in local state above the textarea (rendered as chips with name + remove button)
3. **Paste handler** (`onPaste` on textarea): `clipboardData.items` → detect `image/png`, `image/jpeg` → `FileReader` → upload → add as attachment chip
4. **Attachment chips**: rendered between textarea and button bar, show icon + filename + remove X
5. **Send**: On submit, pass attachments up via `onSend(content, attachments)`
6. **Drag-drop**: Optional — handle `onDragOver`/`onDrop` on the input container

### Frontend — Conversation.tsx

- `onSend` signature changes to `(content: string, attachments?: Attachment[])` → pass through to `chat.sendMessage`
- If `conversation` has no messages (draft state), show attachment chips if present

### Frontend — MessageBubble.tsx

- Render `message.attachments`:
  - Images: `<img>` with lightbox on click
  - Files: download link with icon + filename + size

### Frontend — useCozmoChat.ts

- `sendMessage(content, attachments?)`: If draft, create `newConv` with attachments on the user message. If existing, `updateActive` to add user message with attachments. Send via WebSocket with `attachments` metadata in the `chat` message.

### Backend — webui_server.py

- Add `ATTACHMENTS_DIR = Path.home() / ".cozmo" / "attachments"`
- Add `POST /api/attachments` endpoint:
  - Accept `UploadFile`, generate UUID filename, save to `ATTACHMENTS_DIR`
  - For images, generate a thumbnail (128px width) with PIL
  - Return `{ id, type, name, mime, size, url, thumbnail? }`
- Add `GET /api/attachments/{id}/file` — serve raw file
- Add `GET /api/attachments/{id}/thumb` — serve thumbnail
- Add `DELETE /api/attachments/{id}` — remove file
- Conversation save/load: store attachment metadata alongside messages in the `.md` file (YAML frontmatter for attachments per message, or JSON block)
- WebSocket `chat` message: accept optional `attachments` array

### WebSocket Protocol Change

client → server:
```json
{"type": "chat", "content": "...", "conversation_id": "...", "attachments": [{"id": "...", "type": "file", "name": "..."}]}
```

Server passes attachments info to runtime so tools can access uploaded files.

---

## Phase 2: Image Paste Directly Into Input

(Subset of Phase 1, but specifically)

### PromptInput.tsx

```typescript
// onPaste handler on textarea:
const handlePaste = (e: React.ClipboardEvent) => {
  const items = e.clipboardData.items
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const file = item.getAsFile()
      if (file) handleAttachFiles([file])
      break
    }
  }
}
```

Image paste === same upload + chip flow as Phase 1. No extra backend work.

---

## Phase 3: Projects

### Backend — Project persistence

- `PROJECTS_DIR = Path.home() / ".cozmo" / "projects"`
- Project schema (in `index.json`):
  ```json
  {
    "id": "proj-xxx",
    "name": "My Feature",
    "description": "Working on authentication",
    "conversationIds": ["conv-aaa", "conv-bbb"],
    "sharedContext": "## Project context\nThis project is about...",
    "createdAt": "...",
    "updatedAt": "..."
  }
  ```
- REST endpoints:
  - `GET /api/projects` — list projects
  - `POST /api/projects` — create project
  - `PUT /api/projects/{id}` — update (name, desc, sharedContext, add/remove convos)
  - `DELETE /api/projects/{id}` — delete project (doesn't delete conversations)
  - `GET /api/projects/{id}/conversations` — list conversations in project

### Frontend — Project types (types/index.ts)

```typescript
export interface Project {
  id: string
  name: string
  description: string
  conversationIds: string[]
  sharedContext: string
  createdAt: string
  updatedAt: string
}
```

### Frontend — Project screen

New component tree:
```
src/components/projects/
  ProjectsPanel.tsx       # Main screen: list of projects + "New Project" button
  ProjectDetail.tsx       # Single project view: name, description, shared context editor, linked conversations list
  ProjectForm.tsx         # Create/edit form (name, description, shared context)
```

- Accessible from the "+" menu "Add to project" button
- Also accessible from Sidebar as a 4th tab or a separate toggle below workspace tabs
- A project detail page shows:
  - Project name + description (editable)
  - Shared context textarea (editable, this gets injected as system context)
  - List of linked conversations (clickable to navigate)
  - "Add conversation to project" — from sidebar context menu or from within the conversation

### Frontend — Sidebar changes

- Sidebar gets a "Projects" toggle option (maybe a 4th tab or a smaller link below chat/collab/code)
- When in project view, sidebar shows conversations belonging to that project
- "Add to project" appears in conversation context menu (SidebarItem)
- "+ New Chat" within a project creates a conversation auto-linked to the project

### Frontend — useCozmoChat.ts

- Add `projects` state + CRUD callbacks
- `sendMessage` — if active conversation belongs to a project, include project's `sharedContext` when sending to the runtime

### Backend — Project context injection

- When WebSocket receives a `chat` message with a `project_id`, prepend the project's `sharedContext` to the system prompt or as a user message

---

## Phase 4: Skills System

### Backend — Skills directory

- `SKILLS_DIR = Path.home() / ".cozmo" / "skills"`
- Each skill is a folder with `SKILL.md` (name + description frontmatter, instructions body)
- Optional subfolders: `scripts/`, `references/`, `assets/`
- REST endpoints:
  - `GET /api/skills` — list installed skills (name + description)
  - `GET /api/skills/{name}` — get full SKILL.md
  - `POST /api/skills/{name}` — create/update skill from uploaded `.skill` package (zip)
  - `DELETE /api/skills/{name}` — uninstall

### Frontend — Settings > Skills

- Replace empty placeholder with list of installed skills
- Each skill shows: name, description, install/remove button
- "Install Skill" button → file picker for `.skill` package

### Frontend — Skill Creator skill

The massive spec the user provided IS the Skill Creator skill implementation. It doesn't need frontend UI — it's a skill installed on the backend that guides the agent through creating other skills.

Steps to implement:
1. Create `~/.cozmo/skills/skill-creator/SKILL.md` with the full spec the user provided
2. Add a `POST /api/skills` endpoint that accepts SKILL.md content
3. Frontend: Skills menu in "+" button shows installed skills as quick-trigger prompts
4. Frontend: "Skills" menu opens a skill picker → clicking a skill populates the input with a trigger prompt

### Frontend — "+ Skills" menu

- Opens a submenu/panel showing installed skills
- Clicking a skill inserts a trigger prompt into the input or opens the skill in a new chat
- Skills section in settings shows installed skills with remove option

---

## Phase 5: Connectors (MCP)

### Current State

- Backend already has `MCPHost` (`core/mcp_host.py`) that connects to MCP servers
- Config stores MCP server definitions under `mcp.servers`
- Settings > Connectors reads config and displays servers
- **Missing**: UI to add/edit/remove MCP servers, tool discovery display, enable/disable per-server

### Frontend — Settings > Connectors

- "Add MCP Server" button → form modal:
  - Server name
  - Command (e.g. `npx`, `uvx`)
  - Arguments (e.g. `-y @modelcontextprotocol/server-filesystem ./data`)
  - Environment variables (key-value pairs)
- List servers with enable/disable toggle
- Each server shows its available tools (from `tools.json` discovery)
- Remove server button

### Frontend — "+ Connectors" menu

- Quick-toggle to enable/disable connectors
- Maybe show connected server status (green dot / red dot)
- For now, clicking opens Settings > Connectors

### Backend — MCP enhancements

- MCPHost already connects to servers and discovers tools. Ensure `get_tools()` API endpoint includes MCP tools alongside built-in tools.
- MCP server start/stop lifecycle tied to config changes.
- New REST endpoints if needed:
  - `POST /api/mcp/servers` — add server (update config + restart MCPHost)
  - `DELETE /api/mcp/servers/{name}` — remove server
---

## Phase 6: Wire Up "+" Menu — Step-by-Step Per File

### 6A. "+ Add to project"

**Goal:** clicking "+ Add to project" shows a project picker; selecting one adds the current conversation to that project.

| Step | File | Change |
|------|------|--------|
| 1 | `PromptInput.tsx` | Add props: `activeId?: string`, `projects: Project[]`, `onAddToProject: (convId: string, projId: string) => void`. "Add to project" button gets `onClick` → open submenu dropdown listing `projects`. Click project calls `onAddToProject(activeId, project.id)`. If `!activeId` (draft) → gray out + tooltip "Send a message first". If `projects.length === 0` → show "No projects — create one" with link to toggle project panel. |
| 2 | `Conversation.tsx` | Pass `activeId`, `projects`, `onAddToProject` through to `<PromptInput>`. Source from existing props (already drilling from App/chat hook). |
| 3 | `App.tsx` | Pass `chat.activeId`, `chat.projects`, `chat.addConversationToProject` to `<Conversation>`. |
| 4 | `PromptInput.tsx` | Add project picker submenu state (`showProjectSubmenu`). Render as a nested dropdown with search filter. On select, call `onAddToProject(activeId, id)`, close menu, show toast/snackbar confirmation. |

### 6B. "+ Skills"

**Goal:** full-stack skills feature — backend CRUD, settings UI, and skill picker in "+" menu.

**Step 6B-1: Backend API**

| File | Change |
|------|--------|
| `webui_server.py` | Add `SKILLS_DIR = Path.home() / ".cozmo" / "skills"` at module level. Create dir on startup. Add endpoints: `GET /api/skills` → list `{name, description}[]` from `SKILLS_DIR/*/SKILL.md` frontmatter, `POST /api/skills` → accept `{name, description, content}` → write `SKILLS_DIR/{name}/SKILL.md`, `DELETE /api/skills/{name}` → rmtree. Add `GET /api/skills/{name}` → return full SKILL.md content. |

**Step 6B-2: Frontend types + services**

| File | Change |
|------|--------|
| `types/index.ts` | Add `export interface Skill { name: string; description: string }`. |
| `services/cozmo.ts` | Add `fetchSkills(): Promise<Skill[]>`, `createSkill(data: {name, description, content}): Promise<Skill|null>`, `deleteSkill(name: string): Promise<void>`. |

**Step 6B-3: Settings > Skills**

| File | Change |
|------|--------|
| `SettingsModal.tsx` | Replace `renderSkills()` placeholder. New: fetch skills on mount → list cards with name, description, delete button. "Install Skill" button → opens a form panel (inline or modal) with name + description + content textarea fields. Calls `createSkill()`, refreshes list. Loading/error states. |

**Step 6B-4: "+" menu skill picker**

| File | Change |
|------|--------|
| `PromptInput.tsx` | "+ Skills" button `onClick` → open submenu listing `skills` (fetched on mount). Each skill shows `name`. On click: insert trigger prompt `@skill {name}` into textarea, close menu. Fetch skills on mount via `fetchSkills()`. |

**Step 6B-5: skill-creator seed**

| File | Change |
|------|--------|
| `webui_server.py` | **Startup**: if `SKILLS_DIR/skill-creator` doesn't exist, create it with the SKILL.md spec from user docs. This seeds the first skill. |

### 6C. "+ Connectors"

**Goal:** full-stack MCP connector management — backend config CRUD, settings UI with add/edit/remove/toggle, status in "+" menu.

**Step 6C-1: Backend API endpoints**

| File | Change |
|------|--------|
| `webui_server.py` | Add `GET /api/mcp/servers` → return `{name, command, args, env, enabled}[]` from `config.mcp.servers`. Add `POST /api/mcp/servers` → accept `{name, command, args?, env?, enabled?}`, write to config, restart MCPHost if running. Add `PUT /api/mcp/servers/{name}` → update server config fields. Add `DELETE /api/mcp/servers/{name}` → remove from config, kill MCP process. Add `POST /api/mcp/servers/{name}/toggle` → flip enabled flag, start/stop MCP process. Add `GET /api/mcp/servers/{name}/tools` → return discovered tool list from the MCP server (if connected). |

**Step 6C-2: Frontend types + services**

| File | Change |
|------|--------|
| `types/index.ts` | Add `export interface McpServer { name: string; command: string; args: string[]; env: Record<string,string>; enabled: boolean; tools?: ToolInfo[] }`. |
| `services/cozmo.ts` | Add `fetchMcpServers(): Promise<McpServer[]>`, `addMcpServer(data): Promise<McpServer|null>`, `updateMcpServer(name, data): Promise<McpServer|null>`, `removeMcpServer(name): Promise<void>`, `toggleMcpServer(name): Promise<McpServer|null>`, `fetchMcpTools(name): Promise<ToolInfo[]>`. |

**Step 6C-3: Settings > Connectors**

| File | Change |
|------|--------|
| `SettingsModal.tsx` | Upgrade `renderConnectors()`. New: fetch MCP servers on mount. "Add MCP Server" button → opens a modal with fields: name (text), command (text, e.g. `npx`), args (tags input, e.g. `-y @modelcontextprotocol/server-filesystem ./data`), env vars (key-value rows). List each server as a card with: status dot (green=enabled/connected, gray=disabled, red=error), name, command, tools count. Toggle switch for enabled/disabled. Delete button. "Tools" expand → fetch and show tool list with name + description. |

**Step 6C-4: "+" menu connector status**

| File | Change |
|------|--------|
| `PromptInput.tsx` | "+ Connectors" button `onClick` → open submenu listing active MCP servers with status dots. Quick-toggle each on/off. Clicking a server name opens Settings > Connectors section. Fetch status on mount via `fetchMcpServers()`. |

### 6D. Cross-Cutting: PromptInput Prop Plumbing

PromptInput needs new props for all three features:

```typescript
interface Props {
  generating: boolean
  disabled: boolean
  onSend: (content: string, attachments?: Attachment[]) => void
  onStop: () => void
  // + Add to project:
  activeId?: string
  projects: Project[]
  onAddToProject: (convId: string, projId: string) => void
  // + Connectors quick-toggle:
  mcpServers: McpServer[]
  onToggleMcpServer: (name: string) => void
}
```

All three bubble through `Conversation.tsx` → `App.tsx` → `useCozmoChat`.

---

## Implementation Order

```
SPRINT 1: "+ Add to project" (∼½ day)
  ├─ PromptInput.tsx         — project picker submenu + props
  ├─ Conversation.tsx        — pass new props through
  └─ App.tsx                 — pass chat state down

SPRINT 2: Skills backend (∼½ day)
  ├─ webui_server.py         — /api/skills endpoints + SKILLS_DIR
  ├─ types/index.ts          — Skill interface
  ├─ services/cozmo.ts       — fetchSkills, createSkill, deleteSkill
  └─ webui_server.py         — seed skill-creator SKILL.md on startup

SPRINT 3: Skills frontend (∼½ day)
  ├─ SettingsModal.tsx        — real skills list + install form
  ├─ PromptInput.tsx         — skills picker submenu
  └─ Conversation.tsx        — pass fetchSkills down (or fetch inline)

SPRINT 4: Connectors backend (∼½ day)
  ├─ webui_server.py         — /api/mcp/servers CRUD + toggle
  ├─ types/index.ts          — McpServer interface
  └─ services/cozmo.ts       — fetchMcpServers, addMcpServer, removeMcpServer, toggleMcpServer

SPRINT 5: Connectors frontend (∼1 day)
  ├─ SettingsModal.tsx        — add/edit/remove MCP form + tool discovery
  ├─ PromptInput.tsx         — connectors status submenu + quick-toggle
  └─ Conversation.tsx        — pass mcpServers + onToggleMcpServer through
```

---

---

## Phase 7: Code Mode UI Redesign — Coding Agent Aesthetic

### Goal

Make Code mode feel like a proper coding agent (Claude Code, Cursor, Windsurf) in the browser. The key gap: currently Code mode is Chat mode with different labels. No file visibility, no diff tracking, no command output panel.

### Design Principles

1. **Right panel is the hub** — Terminal, Diff, and Trace all live as tabs in the right panel. User chooses what to look at.
2. **No file explorer** — replaced by a directory picker button above the input. Simple: pick a project directory, agent indexes it.
3. **Lang-agnostic terminal** — all command output (bash, python, node, cargo, etc.) shows in the Terminal tab equally. `execute_python` is just another tool call.
4. **Inline file change cards** — when agent edits a file, a small `> path (+X/-Y)` card appears in the chat message AND in the Diff tab. Expandable to full diff in both places.
5. **Diffs scoped to current session** — Diff tab shows agent-made changes this session. Git history is accessible via `git_diff`/`git_log` tools.

### Target Layout (Code Mode Only)

```
┌──────────┬──────────────────────────────────────┬──────────────────┐
│          │                                      │                  │
│ Sidebar  │         Main Chat Area               │  Right Panel     │
│          │                                      │  (320px)         │
│  Mode    │  messages + code blocks              │                  │
│  Tabs    │  file change cards inline            │ [Term][Diff]     │
│          │  (expandable `> path (+X/-Y)`)       │ [Trace]          │
│  Conv    │                                      │                  │
│  List    │                                      │  Terminal:       │
│          │                                      │  all tool output │
│          │                                      │  color-coded     │
│          │                                      │  filter chips    │
│          │                                      │  auto-scroll     │
│          │                                      │                  │
│          │                                      │  Diff:           │
│          │                                      │  `> path(+X -Y)` │
│          │                                      │  expand→full diff│
│          │                                      │  session-scoped  │
│          │                                      │                  │
│          │                                      │  Trace:          │
│          │                                      │  activity steps  │
│          ├──────────────────────────────────────┤  (existing UI)   │
│          │  📁 ./my-project        [Change]     │                  │
│          │  Input: Ask Cozmo anything...        │                  │
│          └──────────────────────────────────────┘                  │
└──────────┴──────────────────────────────────────┴──────────────────┘
```

### Backend Changes

#### 1. `cozmo/core/runtime.py` — Emit structured tool events

In `run_stream()`, after each `_exec_tool()` call, yield structured events:

```python
# Before tool execution:
yield ("tool_call", tool_name, tool_args, call_id)

# After tool execution, compute diff for file ops:
if name in ("edit_file", "write_file"):
    diff = _compute_diff(name, args)  # unified diff text + added/removed counts
yield ("tool_result", tool_name, result_text, call_id, diff)
```

Add `_compute_diff()`:
```python
def _compute_diff(name: str, args: dict) -> dict | None:
    if name == "edit_file":
        old = args.get("old_text", "").splitlines(keepends=True)
        new = args.get("new_text", "").splitlines(keepends=True)
        diff = list(difflib.unified_diff(old, new, fromfile=args["path"], tofile=args["path"], n=3))
        text = "".join(diff[2:]) if len(diff) > 2 else ""
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        return {"text": text, "added": added, "removed": removed}
    if name == "write_file":
        new = args.get("content", "").splitlines()
        return {"text": "\n".join(f"+{l}" for l in new), "added": len(new), "removed": 0}
    return None
```

#### 2. `cozmo/webui_server.py` — Forward events + directory handler

**New WebSocket events (server → client):**
```json
{"type": "tool_call", "tool": "edit_file", "args": {"path": "src/app.ts", ...}, "id": "call-0-edit"}
{"type": "tool_result", "tool": "edit_file", "result": "Edited src/app.ts", "id": "call-0-edit", "diff": {"text": "@@ -1 +1 @@\n-old\n+new", "added": 1, "removed": 1}}
{"type": "directory_set", "path": "/home/user/project", "indexed": 42}
```

**New WebSocket handler (client → server):**
```python
elif mtype == "set_directory":
    path = msg.get("path", "")
    session.runtime.set_project_context(path)
    n = session.runtime.project_index.index_all() if session.runtime.project_index else 0
    await ws.send_text(json.dumps({"type": "directory_set", "path": path, "indexed": n}))
```

ChatSession gets `_emit_tool_call()` and `_emit_tool_result()` wrappers.

### Frontend Types

#### `types/index.ts` additions:

```typescript
export interface DiffData {
  text: string     // unified diff text (minus ---/+++ headers)
  added: number
  removed: number
}

export interface TerminalEntry {
  id: string
  tool: string
  args: Record<string, unknown>
  result: string
  diff?: DiffData
  timestamp: number
}

export interface DiffEntry {
  id: string
  path: string
  added: number
  removed: number
  diff: DiffData
  timestamp: number
}
```

#### `services/cozmo.ts` — ServerEvent additions:

```typescript
| { type: 'tool_call'; tool: string; args: Record<string, unknown>; id: string }
| { type: 'tool_result'; tool: string; result: string; id: string; diff?: DiffData }
| { type: 'directory_set'; path: string; indexed: number }
```

### Components (New)

#### `FileChangeCard.tsx`

Reusable component for showing a file change inline. Used in both chat messages and Diff tab.

```
> src/app.ts (+12 -3)             ← collapsed state (default)
  ┌─ unified diff ────────────┐
  │ @@ -1,3 +1,4 @@           │  ← expanded state
  │  import { foo }           │     syntax-highlighted
  │ +import { bar }           │     green/red lines
  │  export const x = ...     │
  └───────────────────────────┘
```

Props:
```typescript
interface FileChangeCardProps {
  path: string
  added: number
  removed: number
  diff: DiffData
}
```

#### `TerminalPanel.tsx`

Scrollable list of all tool output with filter chips.

```
┌─ Terminal ─────────────────────────────────┐
│ [All] [Shell] [Python] [Files] [Search]    │
│ ────────────────────────────────────────── │
│ > edit_file src/app.ts                     │
│   Edited 3 lines in src/app.ts             │
│                                            │
│ > run_command python -m py_compile app.ts  │
│   OK                                       │
│                                            │
│ > grep_search "TODO" .                     │
│   src/utils.ts:42: TODO: optimize          │
│                                            │
│ ~ auto-scroll ▼  [Clear]                   │
└────────────────────────────────────────────┘
```

- Filter chips: All, Shell, Python, Files, Search
- Color-coded by tool type (shell=green, file ops=blue, search=yellow, git=purple)
- Each entry: `> tool_name args` on one line, result below (truncated)
- Right-click/copy on result text
- Auto-scroll to bottom on new entry; manual scroll pauses auto-scroll
- "Clear" button in bottom bar
- Max scrollback: unbounded (clearable)

#### `DiffPanel.tsx`

Cumulative file changes from current session.

```
┌─ Diff ─────────────────────────────────────┐
│ > src/app.ts (+12 -3)                      │
│ > src/utils.ts (+5 -1)                     │
│ > assets/image.png (+0 -0)                 │
│                                            │
│ (click any → expand full diff inline)      │
└────────────────────────────────────────────┘
```

- Uses same `FileChangeCard` component as chat inline cards
- Sorted by path, grouped by session (one session per message)
- Auto-opens when new file change arrives (auto-switch tab)
- Click to expand/collapse full diff

#### `DirectoryPicker.tsx`

Small bar above the input area.

```
📁 ./my-project                               [Change]
```

- Shows current working directory (shortened)
- "Change" button → opens a modal with:
  - Text input for path (with validation)
  - Basic directory browser (read-only, expand folders)
  - "Set Directory" button → sends `set_directory` WebSocket message
  - Cancels closes modal
- Backend auto-indexes on set, response shows `indexed: N` count

#### `RightPanel.tsx`

Tabbed container holding Terminal, Diff, and Trace.

```
┌─ RightPanel ───────────────────────────────┐
│ [Terminal] [Diff]  [Trace]                 │
│ ───────────────────────────────────────── │
│ <active tab content>                        │
└────────────────────────────────────────────┘
```

Props:
```typescript
interface RightPanelProps {
  activeTab: 'terminal' | 'diff' | 'trace'
  onTabChange: (tab: 'terminal' | 'diff' | 'trace') => void
  terminalEntries: TerminalEntry[]
  diffEntries: DiffEntry[]
  activitySteps: ActivityStep[]
  plan: PlanData | null
  onApprovePlan: () => void
  onRejectPlan: () => void
  onClearTerminal: () => void
}
```

**Auto-switch behavior:**
- New `tool_call` received → if tab is Trace, switch to Terminal
- New `edit_file`/`write_file` result received → if tab is Trace, switch to Diff
- User manually switches tabs → stays on chosen tab until next message
- On new message start → reset to Trace tab

### Hook Changes (`useCozmoChat.ts`)

New state:
```typescript
const [terminalEntries, setTerminalEntries] = useState<TerminalEntry[]>([])
const [diffEntries, setDiffEntries] = useState<DiffEntry[]>([])
const [currentDirectory, setCurrentDirectory] = useState<string>('./')
```

New event handlers:
```typescript
case 'tool_call':
  setTerminalEntries(prev => [...prev, { id: ev.id, tool: ev.tool, args: ev.args, result: '', timestamp: Date.now() }])
  break
case 'tool_result':
  setTerminalEntries(prev => prev.map(e =>
    e.id === ev.id ? { ...e, result: ev.result, diff: ev.diff } : e
  ))
  if ((ev.tool === 'edit_file' || ev.tool === 'write_file') && ev.diff) {
    setDiffEntries(prev => [...prev, {
      id: ev.id,
      path: (ev.args as any).path || 'unknown',
      added: ev.diff!.added,
      removed: ev.diff!.removed,
      diff: ev.diff!,
      timestamp: Date.now()
    }])
  }
  break
case 'directory_set':
  setCurrentDirectory(ev.path)
  break
```

New methods:
```typescript
const setDirectory = useCallback((path: string) => {
  clientRef.current?.send({ type: 'set_directory', path })
}, [])
const clearTerminal = useCallback(() => {
  setTerminalEntries([])
}, [])
```

### Layout Changes

#### `App.tsx`

New state:
```typescript
const [rightTab, setRightTab] = useState<'terminal' | 'diff' | 'trace'>('trace')
```

Code mode renders RightPanel instead of ActivityPanel:
```tsx
{mode === 'code' && activityOpen && !showProjects ? (
  <RightPanel
    activeTab={rightTab}
    onTabChange={setRightTab}
    terminalEntries={chat.terminalEntries}
    diffEntries={chat.diffEntries}
    activitySteps={chat.activity}
    plan={chat.plan}
    onApprovePlan={() => chat.answerPlan(true)}
    onRejectPlan={() => chat.answerPlan(false)}
    onClearTerminal={chat.clearTerminal}
  />
) : activityOpen && !showProjects ? (
  <ActivityPanel steps={chat.activity} plan={chat.plan} ... />
)}
```

#### `Conversation.tsx`

Add DirectoryPicker above PromptInput:
```tsx
{mode === 'code' && (
  <DirectoryPicker path={chat.currentDirectory} onChange={chat.setDirectory} />
)}
<PromptInput ... />
```

#### `MessageBubble.tsx`

After markdown content, render FileChangeCards for tool calls:
```tsx
{message.toolCalls?.filter(tc => ['edit_file', 'write_file'].includes(tc.tool)).map(tc => {
  const tr = message.toolResults?.find(r => r.id === tc.id)
  if (!tr?.diff) return null
  return (
    <FileChangeCard
      key={tc.id}
      path={(tc.args as any).path || 'unknown'}
      added={tr.diff.added}
      removed={tr.diff.removed}
      diff={tr.diff}
    />
  )
})}
```

### Implementation Order

| Step | Files | What | Effort |
|------|-------|------|--------|
| 1 | `runtime.py` | Emit `tool_call`/`tool_result` with call_id + diff computation | Small |
| 2 | `webui_server.py` | Forward tool events, add `set_directory`/`directory_set` handlers | Small |
| 3 | `types/index.ts`, `cozmo.ts` | Add types + ServerEvent union members | Small |
| 4 | `useCozmoChat.ts` | Handle new events, track terminal/diff state | Medium |
| 5 | `FileChangeCard.tsx` | New component — expandable diff card | Small |
| 6 | `TerminalPanel.tsx` | New component — filtered tool output list | Medium |
| 7 | `DiffPanel.tsx` | New component — cumulative session diffs | Small |
| 8 | `DirectoryPicker.tsx` | New component — cwd bar + change modal | Small |
| 9 | `RightPanel.tsx` | New component — tabbed container with auto-switch | Small |
| 10 | `App.tsx` | Layout: RightPanel vs ActivityPanel per mode | Small |
| 11 | `Conversation.tsx` | Add DirectoryPicker above input | Small |
| 12 | `MessageBubble.tsx` | Render FileChangeCards inline | Small |

### Questions Before Implementation

- [x] Diffs scoped to current session? **Yes**
- [x] Terminal accumulates with Clear? **Yes**
- [x] Auto-index on directory set? **Yes**
- [x] File cards in both chat + diff tab? **Yes** — same component
- [x] `> path (+X -Y)` format? **Yes**
- [x] All tool output in terminal, not just commands? **Yes**
- [x] Auto-switch tab based on event type? **Yes**

---

---

## Phase 8: Per-Mode Input Bars + Collab Project Management

### Goal

Give each workspace mode its own tailored input bar instead of a one-size-fits-all PromptInput. Collab mode gets project management (create, import, select folder). Code mode keeps directory picker + permission mode (already built). Chat mode stays minimal.

### Current Problem

- `PromptInput` is a single component shared by all 3 modes
- Directory picker + permission mode buttons appear in all modes (they should be code-only)
- Collab mode has no project/folder awareness at all
- No way to create projects from within the UI

### Target Per-Mode Input Bars

#### Chat Mode (no change from current)

```
┌──────────────────────────────────────┐
│ textarea                              │
├──────────────────────────────────────┤
│ + (attach)              mic  send    │
└──────────────────────────────────────┘
```

#### Code Mode (already implemented)

```
┌──────────────────────────────────────┐
│ textarea                              │
├──────────────────────────────────────┤
│ + (attach)  [📁 path]  [🔒 Manual]  │
│                          mic  send    │
└──────────────────────────────────────┘
```

#### Collab Mode (new)

```
┌──────────────────────────────────────┐
│ textarea                              │
├──────────────────────────────────────┤
│ + (attach)  [📁 Project Name]        │
│                          mic  send    │
└──────────────────────────────────────┘
```

The `[📁 Project Name]` button opens a project management popup.

### Collab Project Management Popup

```
┌─ Work in a Project Folder ─────────────────┐
│ 🔍 Search projects...                       │
│ ─────────────────────────────────────────── │
│                                             │
│ MyAuthenticationSystem                      │
│ ├── Description: Auth system for web app    │
│ ├── Updated: 2h ago                         │
│ └── [Select]                                │
│                                             │
│ BlogPlatform API                            │
│ ├── Description: REST API for blog          │
│ ├── Updated: 1d ago                         │
│ └── [Select]                                │
│                                             │
│ ─────────────────────────────────────────── │
│ [📁 Create New Project]                     │
│ [💬 Import from Chat]                       │
│ [📂 Use Existing Folder]                    │
└─────────────────────────────────────────────┘
```

Three action buttons at the bottom:

#### Action 1: Create New Project

Multi-step wizard modal (like a 3-step form with Back/Next):

```
Step 1: Project Details
┌──────────────────────────────────────┐
│ Project Name *              [____]   │
│ Instructions for Cozmo      [____]   │
│   (how to work in this project)      │
│ Brief description           [____]   │
├──────────────────────────────────────┤
│              [Cancel]  [Next →]      │
└──────────────────────────────────────┘

Step 2: Add Files
┌──────────────────────────────────────┐
│ Drag & drop files here or click to   │
│ browse                               │
│                                      │
│ 📄 requirements.txt        [Remove]  │
│ 📄 main.py                 [Remove]  │
│ 📄 README.md               [Remove]  │
├──────────────────────────────────────┤
│          [← Back]  [Next →]         │
└──────────────────────────────────────┘

Step 3: Choose Location
┌──────────────────────────────────────┐
│ Project folder will be created at:   │
│ [______________________________]     │
│                                      │
│ [Browse Folder]                      │
│                                      │
│ Will create: /path/to/projects/      │
│              my-project-name/        │
├──────────────────────────────────────┤
│          [← Back]  [✨ Create]       │
└──────────────────────────────────────┘
```

**Backend behavior:**
1. Receives `create_project` WebSocket message with: `{name, instructions, files[], location}`
2. Creates directory at `{location}/{name}`
3. Saves uploaded files into the directory
4. Creates a `.cozmo/project.json` metadata file
5. Returns project metadata + triggers indexing
6. Sets the new project as the current collab session context

#### Action 2: Import from Chat

```
┌─ Import from Chat ────────────────────┐
│ Select conversations to import context │
│ from:                                 │
│                                      │
│ ☐ "Help me brainstorm a business..." │
│   2h ago - Collab                    │
│ ☐ "Write a marketing plan for..."    │
│   5h ago - Chat                      │
│ ☐ "Research competitors in..."       │
│   1d ago - Chat                      │
│                                      │
│ Preview imported context:            │
│ ┌──────────────────────────────┐    │
│ │ Business idea: local coffee  │    │
│ │ shop app. Key features:      │    │
│ │ loyalty program, mobile      │    │
│ │ ordering, rewards tracking.  │    │
│ └──────────────────────────────┘    │
│                                      │
│ [Cancel]  [Import & Create Project]  │
└──────────────────────────────────────┘
```

**Backend behavior:**
1. Receives `import_from_chat` with `{conversation_ids[]}`
2. Extracts key messages/context from each conversation
3. Creates a new project with the extracted context as instructions
4. Returns project metadata

#### Action 3: Use Existing Folder

```
┌─ Use Existing Folder ────────────────┐
│ Point Cozmo to an existing project    │
│ directory:                           │
│                                      │
│ [______________________________]     │
│ [Browse Folder]                      │
│                                      │
│ Recent:                              │
│ /home/user/projects/my-app      [X] │
│ /home/user/projects/blog-api    [X] │
│                                      │
│ Cozmo will index the project files   │
│ and make them available as context.  │
│                                      │
│ [Cancel]  [Use This Folder]          │
└──────────────────────────────────────┘
```

**Backend behavior:**
1. Same as `set_directory` in code mode
2. Creates a project record linked to the folder
3. Indexes the folder
4. Returns project metadata

### Frontend Files

| File | New/Change | Purpose |
|------|-----------|---------|
| `PromptInput.tsx` | **Change** | Accept `mode` prop; conditionally render mode-specific extensions in toolbar. Chat=none, Code=dir+permission, Collab=project button |
| `CollabProjectPopup.tsx` | **New** | Main popup: search + project list + 3 action buttons |
| `CreateProjectWizard.tsx` | **New** | 3-step wizard modal (details, files, location) |
| `ImportFromChatPopup.tsx` | **New** | List recent conversations, select to import |
| `Conversation.tsx` | **Change** | Pass `mode` to PromptInput |
| `App.tsx` | **Change** | Pass collab project state through |

### Backend Changes

**WebSocket messages (client → server):**

| Message Type | Payload | Purpose |
|-------------|---------|---------|
| `create_project` | `{name, instructions, files[], location}` | Create new project folder + index |
| `import_from_chat` | `{conversation_ids[]}` | Extract context from past convos |
| `list_projects` | `{search?}` | List/search projects |
| `get_recent_conversations` | `{mode?, limit?}` | Get recent convos for import |
| `use_folder` | `{path}` | Same as `set_directory` but creates project record |

**WebSocket messages (server → client):**

| Message Type | Payload | Purpose |
|-------------|---------|---------|
| `project_created` | `{id, name, path, indexed}` | Confirm project creation |
| `projects_list` | `{projects[]}` | Project search results |
| `recent_conversations` | `{conversations[]}` | For import picker |
| `import_context` | `{text}` | Extracted context from selected convos |

**File: `webui_server.py`**

- Add handler for `create_project`:
  ```python
  elif mtype == "create_project":
      name = msg["name"]
      location = Path(msg["location"]) / name
      location.mkdir(parents=True, exist_ok=True)
      # Save instructions as .cozmo/project.json
      # Save uploaded files
      # Index the project directory
      await ws.send_text(json.dumps({"type": "project_created", ...}))
  ```

- Add handler for `import_from_chat`:
  ```python
  elif mtype == "import_from_chat":
      conv_ids = msg.get("conversation_ids", [])
      # Read each conversation .md file
      # Extract key messages
      # Return combined context
  ```

- Add handler for `list_projects` (uses existing `_projects_idx()`)
- Add handler for `get_recent_conversations` (uses existing `_conversations_idx()`)

### Implementation Order

| Step | Files | What | Effort |
|------|-------|------|--------|
| 1 | `webui_server.py` | Add `create_project`, `import_from_chat`, `list_projects`, `get_recent_conversations` handlers | Medium |
| 2 | `types/index.ts`, `cozmo.ts` | Add new ServerEvent + message types | Small |
| 3 | `useCozmoChat.ts` | Add project state, handler methods | Medium |
| 4 | `PromptInput.tsx` | Add `mode` prop, conditionally render extensions | Small |
| 5 | `CollabProjectPopup.tsx` | New: popup with search + project list + 3 actions | Medium |
| 6 | `CreateProjectWizard.tsx` | New: 3-step wizard (details, files, location) | Large |
| 7 | `ImportFromChatPopup.tsx` | New: recent conversation picker + context preview | Medium |
| 8 | `App.tsx` + `Conversation.tsx` | Wire new props through | Small |
| 9 | Full integration test | Verify all 3 modes have correct input bars | Small |

### Component Tree (Collab Mode)

```
Conversation
└── PromptInput (mode='collab')
    ├── textarea
    ├── attachment chips
    └── toolbar
        ├── + menu (existing)
        ├── [📁 Project Name] button
        │   └── CollabProjectPopup
        │       ├── search input
        │       ├── project list
        │       ├── [Create New Project]
        │       │   └── CreateProjectWizard (3-step modal)
        │       ├── [Import from Chat]
        │       │   └── ImportFromChatPopup
        │       └── [Use Existing Folder]
        │           └── DirectoryPicker inline
        ├── mic button (existing)
        └── send button (existing)
```

### Questions

- [ ] Should project files uploaded during creation be stored server-side (in `~/.cozmo/projects/`) or on the user's chosen path?
  → **Chosen path**. The location step lets user pick where the folder lives on their system.
- [ ] Should "Import from Chat" create a project or just set context for the current session?
  → **Create a project**. The imported context becomes the project instructions.
- [ ] How do uploaded files in Step 2 of creation get saved?
  → Files are uploaded via REST API (`POST /api/project-files`), stored in `~/.cozmo/temp-uploads/`, then moved to the new project directory on creation.
- [ ] Should the collab project be persisted across sessions?
  → **Yes**. Project metadata + indexed files persist in the chosen location.

---

## Key Architecture Decisions (Updated)

1. **Attachments stored on disk**, metadata in conversation messages. No base64 in chat JSON.
2. **Projects are lightweight groupings** — a project is a list of conversation IDs + shared context text. Conversations can belong to 0 or 1 projects.
3. **Skills are SKILL.md files** on disk. The "Skill Creator" skill is just a well-written SKILL.md that tells the agent how to create other skills.
4. **Connectors = MCP servers** already working on backend. Phase 5 is mainly frontend polish.
5. **No database** — everything is file-based: `~/.cozmo/chats/`, `~/.cozmo/projects/`, `~/.cozmo/skills/`, `~/.cozmo/attachments/`.
6. **Code mode diffs are session-scoped** — computed from tool args on the backend (Python `difflib.unified_diff`), not from git history. Git tools exist separately.
7. **Terminal is lang-agnostic** — `execute_python` is just another tool call alongside `run_command`, `npm test`, `cargo build`, etc. No special treatment.
8. **Collab project files live on the user's chosen path** — not in `~/.cozmo/`. The user picks where the project folder goes on their system.
9. **Per-mode input bars share a single PromptInput component** with conditional rendering based on `mode` prop, rather than 3 separate components.
