import { MessageSquare, FolderKanban, PlayCircle, Settings, LucideIcon } from 'lucide-react'

export type NavItemId = 'conversations' | 'projects' | 'jobs' | 'settings'

export interface NavItemConfig {
  label: string
  icon: LucideIcon
}

export const NAV_ITEMS: Record<NavItemId, NavItemConfig> = {
  conversations: { label: 'Conversations', icon: MessageSquare },
  projects: { label: 'Projects', icon: FolderKanban },
  jobs: { label: 'Jobs', icon: PlayCircle },
  settings: { label: 'Settings', icon: Settings },
}

export const NAV_ORDER: NavItemId[] = ['conversations', 'projects', 'jobs', 'settings']
