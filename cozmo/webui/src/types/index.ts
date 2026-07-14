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

export type WorkspaceMode = 'chat' | 'agent' | 'code'

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

export type PlanStepStatus = 'pending' | 'approved' | 'rejected'

export interface PlanData {
  plan: string
  status: PlanStepStatus
}

export interface DiffData {
  text: string
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

export interface ToolInfo {
  id: string
  name: string
  description: string
  enabled: boolean
}

export interface Skill {
  name: string
  description: string
}

export interface McpServer {
  name: string
  command: string
  args: string[]
  env: Record<string, string>
  enabled: boolean
  tools?: ToolInfo[]
}

export interface McpCatalogEnvVar {
  key: string
  label: string
  secret: boolean
  optional: boolean
  default: string
}

export interface McpCatalogEntry {
  id: string
  display_name: string
  description: string
  command: string
  args: string[]
  transport: string
  tags: string[]
  category: string
  capabilities: string[]
  env_vars: McpCatalogEnvVar[]
  homepage: string
}

export interface McpServerTool {
  name: string
  description: string
}

export interface McpServerStatus {
  status: 'ok' | 'error' | 'disconnected'
  tools: McpServerTool[]
}

export interface McpStatusResponse {
  [serverName: string]: McpServerStatus
}

export interface AgentTaskFile {
  name: string
  content: string
}

export interface AgentTaskCreate {
  name: string
  description?: string
  instructions?: string
  files?: AgentTaskFile[]
  location: string
}

export type AgentStatus = 'idle' | 'planning' | 'executing' | 'waiting' | 'done' | 'error'

export interface AgentToolCall {
  id: string
  tool: string
  args: Record<string, unknown>
  result: string
  timestamp: number
}

export interface AgentConfig {
  model?: string
  system_prompt?: string
  max_steps?: number
  temperature?: number
}

export interface TaskData {
  id: string
  description: string
  prompt: string
  agent_type: string
  status: string
  created: string
  result: string
  error: string
  goal?: string
  mode?: string
}

export interface BackgroundRunInfo {
  run_id: string
  goal: string
  status: string
  created: string
  ended: string
}

export interface BackgroundRunLog {
  log_type: 'tool_call' | 'tool_result'
  tool?: string
  args?: Record<string, unknown>
  result?: string
  call_id?: string
}

export interface ScheduledTaskInfo {
  id: string
  goal: string
  description: string
  interval_minutes: number
  next_run: string
  enabled: boolean
  created: string
  last_run: string
}

export interface McpServerDetail {
  name: string
  status: 'ok' | 'error' | 'disconnected' | 'connecting'
  description?: string
  capabilities: string[]
  tools: McpServerTool[]
  config: {
    command: string
    args: string[]
    env: Record<string, string>
  }
  diagnostics: {
    transport: string
    startup_time_ms: number | null
    last_connected: string | null
    last_ping: string | null
    response_time_ms: number | null
  }
  permissions?: Record<string, boolean>
  source: 'catalog' | 'custom'
  category?: string
  homepage?: string
}
