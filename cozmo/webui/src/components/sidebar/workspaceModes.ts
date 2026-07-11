import { MessageSquare, Users2, TerminalSquare, LucideIcon } from 'lucide-react'

export type WorkspaceMode = 'chat' | 'collab' | 'code'

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
  collab: {
    createLabel: 'New Task',
    icon: Users2,
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
