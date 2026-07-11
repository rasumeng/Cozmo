export interface Attachment {
  id: string
  type: 'image' | 'file'
  name: string
  mime: string
  size: number
  url: string
  thumbnail?: string
}

export type Role = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: Role
  content: string
  createdAt: string
  model?: string
  citations?: string[]
  streaming?: boolean
  attachments?: Attachment[]
}

export type WorkspaceMode = 'chat' | 'collab' | 'code'

export interface Conversation {
  id: string
  title: string
  updatedAt: string
  pinned: boolean
  mode: WorkspaceMode
  messages: ChatMessage[]
}

export type ActivityStatus = 'running' | 'completed' | 'error'

export interface ActivityStep {
  id: string
  icon: string // lucide icon name
  label: string
  detail?: string
  query?: string
  durationMs?: number
  status: ActivityStatus
  startedAt: string
}

export interface ModelInfo {
  id: string
  name: string
  role: 'chat' | 'coder' | 'vision' | 'research' | 'classifier'
  sizeGb: number
  active: boolean
}

export interface MemoryItem {
  id: string
  summary: string
  createdAt: string
  tags: string[]
}

export interface Project {
  id: string
  name: string
  description: string
  conversationIds: string[]
  sharedContext: string
  createdAt: string
  updatedAt: string
}

export interface ToolInfo {
  id: string
  name: string
  description: string
  enabled: boolean
}
