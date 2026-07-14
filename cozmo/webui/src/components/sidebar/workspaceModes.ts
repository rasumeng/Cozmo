import { MessageSquare, Bot, TerminalSquare, LucideIcon } from 'lucide-react'

export type WorkspaceMode = 'chat' | 'agent' | 'code'

interface ModeConfig {
  createLabel: string
  icon: LucideIcon
  searchLabel: string
  emptyRecentLabel: string
}

export const WORKSPACE_MODE_CONFIG: Record<WorkspaceMode, ModeConfig> = {
  chat: {
    createLabel: 'New Chat',
    icon: MessageSquare,
    searchLabel: 'Search chats',
    emptyRecentLabel: 'Recent',
  },
  agent: {
    createLabel: 'New Task',
    icon: Bot,
    searchLabel: 'Search tasks',
    emptyRecentLabel: 'Recent Tasks',
  },
  code: {
    createLabel: 'New Session',
    icon: TerminalSquare,
    searchLabel: 'Search sessions',
    emptyRecentLabel: 'Recent Sessions',
  },
}
