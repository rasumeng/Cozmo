import { Cpu, Wrench, Brain, Puzzle, Cable, Settings, Bot, FileText, GitBranch, Globe, Database, Lightbulb, Calendar, Mail, MessageSquare, Map, Search, Activity, Image, Server, Cloud } from 'lucide-react'
import type { SectionId } from './types'

export const SECTIONS: { id: SectionId; label: string; icon: React.ElementType }[] = [
  { id: 'models', label: 'Models', icon: Cpu },
  { id: 'agent', label: 'Agent', icon: Bot },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'skills', label: 'Skills', icon: Puzzle },
  { id: 'connectors', label: 'Connectors', icon: Cable },
  { id: 'general', label: 'General', icon: Settings },
]

export const BUILTIN_ROLES = ['chat', 'coder', 'vision', 'research', 'classifier', 'agent'] as const

export const INTERNAL_KEYS = ['max_tokens'] as const

export const PRESET_META: Record<string, { label: string; desc: string }> = {
  chat: { label: 'Chat', desc: 'General conversation & Q&A' },
  coder: { label: 'Coder', desc: 'Code generation & editing' },
  vision: { label: 'Vision', desc: 'Image analysis & vision tasks' },
  research: { label: 'Research', desc: 'Deep research & search' },
  classifier: { label: 'Classifier', desc: 'Text classification & sentiment analysis' },
  agent: { label: 'Agent', desc: 'Autonomous multi-step task execution' },
}

export const PERM_MODES = ['allow', 'ask', 'deny'] as const

export const CAPABILITY_DEFS: Record<string, { label: string; icon: React.ElementType }> = {
  files: { label: "Files", icon: FileText },
  git: { label: "Git", icon: GitBranch },
  github: { label: "GitHub", icon: GitBranch },
  browser: { label: "Browser Automation", icon: Globe },
  database: { label: "Databases", icon: Database },
  memory: { label: "Long-term Memory", icon: Brain },
  reasoning: { label: "Reasoning", icon: Lightbulb },
  calendar: { label: "Calendar", icon: Calendar },
  email: { label: "Email", icon: Mail },
  communication: { label: "Communication", icon: MessageSquare },
  maps: { label: "Maps", icon: Map },
  "web-search": { label: "Web Search", icon: Search },
  monitoring: { label: "Monitoring", icon: Activity },
  "image-generation": { label: "Image Generation", icon: Image },
  infrastructure: { label: "Infrastructure", icon: Server },
  "cloud-storage": { label: "Cloud Storage", icon: Cloud },
}

export const PERMISSION_DEFS: Record<string, { label: string; key: string }[]> = {
  files: [
    { label: 'Read & Search', key: 'read' },
    { label: 'Write Files', key: 'write' },
    { label: 'Delete Files', key: 'delete' },
  ],
  git: [
    { label: 'Read Repos', key: 'read' },
    { label: 'Commit & Push', key: 'write' },
  ],
  github: [
    { label: 'Read Issues & PRs', key: 'read' },
    { label: 'Create & Edit', key: 'write' },
    { label: 'Merge & Approve', key: 'approve' },
    { label: 'Delete Branches', key: 'delete' },
  ],
  database: [
    { label: 'Read Queries', key: 'read' },
    { label: 'Write Queries', key: 'write' },
  ],
  browser: [
    { label: 'Navigate', key: 'navigate' },
    { label: 'Get Content', key: 'read' },
    { label: 'Interact (click, type)', key: 'interact' },
  ],
  _default: [
    { label: 'Allow Execution', key: 'execute' },
  ],
}
