// WebSocket client for the Cozmo FastAPI backend (cozmo/webui_server.py).
// Reconnects automatically; events are fanned out to a single handler.

import { Conversation, Attachment, Project, Skill, McpCatalogEntry, McpStatusResponse, McpServerDetail, DiffData, CollabProjectCreate } from '@/types'

export type ServerEvent =
  | { type: 'token'; text: string }
  | { type: 'thinking'; text: string; detail?: string; query?: string }
  | { type: 'status'; text: string; detail?: string; query?: string }
  | { type: 'plan'; plan: string }
  | { type: 'tool_call'; tool: string; args: Record<string, unknown>; id: string }
  | { type: 'tool_result'; tool: string; result: string; id: string; diff?: DiffData }
  | { type: 'directory_set'; path: string; indexed: number }
  | { type: 'projects_list'; projects: Project[] }
  | { type: 'recent_conversations'; conversations: { id: string; title: string; mode: string; updatedAt: string }[] }
  | { type: 'project_created'; project: Project; indexed: number }
  | { type: 'project_selected'; project: Project }
  | { type: 'permission_request'; tool: string; args: Record<string, unknown> }
  | { type: 'done' }
  | { type: 'error'; text: string }

export type ConnectionState = 'connecting' | 'open' | 'closed'

const WS_URL =
  import.meta.env.VITE_COZMO_WS_URL ??
  `${location.protocol === 'https:' ? 'wss' : 'ws'}://${
    import.meta.env.DEV ? 'localhost:8765' : location.host
  }/ws/chat`

export const API_BASE = import.meta.env.DEV ? 'http://localhost:8765' : ''

export class CozmoClient {
  private ws: WebSocket | null = null
  private retryMs = 1000
  private closedByUser = false

  onEvent: (ev: ServerEvent) => void = () => {}
  onConnectionChange: (state: ConnectionState) => void = () => {}

  connect() {
    this.closedByUser = false
    this.onConnectionChange('connecting')
    this.ws = new WebSocket(WS_URL)
    this.ws.onopen = () => {
      this.retryMs = 1000
      this.onConnectionChange('open')
    }
    this.ws.onmessage = (e) => {
      try {
        this.onEvent(JSON.parse(e.data) as ServerEvent)
      } catch {
        /* ignore malformed frames */
      }
    }
    this.ws.onclose = () => {
      this.onConnectionChange('closed')
      if (!this.closedByUser) {
        setTimeout(() => this.connect(), this.retryMs)
        this.retryMs = Math.min(this.retryMs * 2, 15000)
      }
    }
  }

  disconnect() {
    this.closedByUser = true
    this.ws?.close()
  }

  private send(payload: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload))
      return true
    }
    return false
  }

  sendChat(content: string, conversationId?: string, attachments?: Attachment[], projectId?: string) {
    const payload: Record<string, unknown> = { type: 'chat', content, conversation_id: conversationId }
    if (attachments?.length) {
      payload.attachments = attachments.map(a => ({ id: a.id, type: a.type, name: a.name, mime: a.mime, size: a.size }))
    }
    if (projectId) payload.project_id = projectId
    return this.send(payload)
  }
  stop() {
    return this.send({ type: 'stop' })
  }
  answerPermission(allowed: boolean) {
    return this.send({ type: 'permission_response', allowed })
  }
  answerPlan(approved: boolean) {
    return this.send({ type: 'plan_response', approved })
  }
  setDirectory(path: string) {
    return this.send({ type: 'set_directory', path })
  }
  setPermissionMode(mode: string) {
    return this.send({ type: 'set_permission_mode', mode })
  }
  listProjects(search?: string) {
    return this.send({ type: 'list_projects', search })
  }
  getRecentConversations(mode?: string, limit?: number) {
    return this.send({ type: 'get_recent_conversations', mode, limit })
  }
  importFromChat(conversationIds: string[]) {
    return this.send({ type: 'import_from_chat', conversation_ids: conversationIds })
  }
  createProject(data: CollabProjectCreate) {
    return this.send({ type: 'create_project', ...data })
  }
  selectProject(projectId: string) {
    return this.send({ type: 'select_project', project_id: projectId })
  }
  reset() {
    return this.send({ type: 'reset' })
  }
}

export async function fetchModels() {
  const r = await fetch(`${API_BASE}/api/models`)
  return r.json() as Promise<{ id: string; name: string; role: string; active: boolean }[]>
}

export async function fetchTools() {
  const r = await fetch(`${API_BASE}/api/tools`)
  return r.json() as Promise<{ id: string; name: string; description: string; enabled: boolean }[]>
}

export async function fetchConversations(): Promise<Conversation[]> {
  const r = await fetch(`${API_BASE}/api/conversations`)
  if (!r.ok) return []
  return r.json()
}

export async function saveConversation(conv: Conversation): Promise<void> {
  await fetch(`${API_BASE}/api/conversations`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: conv.id,
      title: conv.title,
      pinned: conv.pinned,
      mode: conv.mode,
      messages: conv.messages.map((m: { role: string; content: string; attachments?: Attachment[] }) => ({ role: m.role, content: m.content, attachments: m.attachments })),
    }),
  })
}

export async function deleteConversationApi(id: string): Promise<void> {
  await fetch(`${API_BASE}/api/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export async function fetchProjects(): Promise<Project[]> {
  try {
    const r = await fetch(`${API_BASE}/api/projects`)
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return []
}

export async function createProject(data: { name: string; description?: string; sharedContext?: string }): Promise<Project | null> {
  try {
    const r = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return null
}

export async function updateProject(id: string, data: Partial<Project>): Promise<Project | null> {
  try {
    const r = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(id)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return null
}

export async function deleteProjectApi(id: string): Promise<void> {
  await fetch(`${API_BASE}/api/projects/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export async function fetchProjectConversations(id: string): Promise<Conversation[]> {
  try {
    const r = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(id)}/conversations`)
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return []
}

export async function fetchSkills(): Promise<Skill[]> {
  try {
    const r = await fetch(`${API_BASE}/api/skills`)
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return []
}

export async function createSkill(data: { name: string; description?: string; content?: string }): Promise<Skill | null> {
  try {
    const r = await fetch(`${API_BASE}/api/skills`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return null
}

export async function deleteSkill(name: string): Promise<void> {
  await fetch(`${API_BASE}/api/skills/${encodeURIComponent(name)}`, { method: 'DELETE' })
}

export async function uploadSkill(file: File): Promise<Skill | null> {
  const form = new FormData()
  form.append('file', file)
  try {
    const r = await fetch(`${API_BASE}/api/skills/upload`, { method: 'POST', body: form })
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return null
}

export async function uploadFile(file: File): Promise<Attachment | null> {
  const form = new FormData()
  form.append('file', file)
  try {
    const r = await fetch(`${API_BASE}/api/attachments`, { method: 'POST', body: form })
    if (r.ok) {
      const att: Attachment = await r.json()
      att.url = `${API_BASE}${att.url}`
      if (att.thumbnail) att.thumbnail = `${API_BASE}${att.thumbnail}`
      return att
    }
  } catch { /* ignore */ }
  return null
}

export async function deleteAttachment(id: string): Promise<void> {
  await fetch(`${API_BASE}/api/attachments/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export async function fetchServerDetail(name: string): Promise<McpServerDetail | null> {
  try {
    const r = await fetch(`${API_BASE}/api/mcp/servers/${encodeURIComponent(name)}`)
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return null
}

export async function fetchMcpStatus(): Promise<McpStatusResponse> {
  try {
    const r = await fetch(`${API_BASE}/api/mcp/status`)
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return {}
}

export async function fetchMcpCatalog(): Promise<McpCatalogEntry[]> {
  try {
    const r = await fetch(`${API_BASE}/api/mcp/catalog`)
    if (r.ok) return r.json()
  } catch { /* ignore */ }
  return []
}

export { deleteConversationApi as deleteConversation }
