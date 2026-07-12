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

## Key Architecture Decisions

1. **Attachments stored on disk**, metadata in conversation messages. No base64 in chat JSON.
2. **Projects are lightweight groupings** — a project is a list of conversation IDs + shared context text. Conversations can belong to 0 or 1 projects.
3. **Skills are SKILL.md files** on disk. The "Skill Creator" skill is just a well-written SKILL.md that tells the agent how to create other skills.
4. **Connectors = MCP servers** already working on backend. Phase 5 is mainly frontend polish.
5. **No database** — everything is file-based: `~/.cozmo/chats/`, `~/.cozmo/projects/`, `~/.cozmo/skills/`, `~/.cozmo/attachments/`.
