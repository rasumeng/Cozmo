export type SectionId = 'models' | 'tools' | 'memory' | 'skills' | 'connectors' | 'general' | 'agent'

export interface ToolInfo {
  id: string
  name: string
  description: string
  enabled: boolean
}

export interface SettingsData {
  models: Record<string, unknown>
  memory: { max_turns_before_summary: number; max_short_term_pairs: number }
  runtime?: { tool_gate?: Record<string, string[]> }
  permissions?: Record<string, unknown>
  mcp?: { servers: Record<string, { command: string; args?: string[]; env?: Record<string, string> }> }
  [key: string]: unknown
}
