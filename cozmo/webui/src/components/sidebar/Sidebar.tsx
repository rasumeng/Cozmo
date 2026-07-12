import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { PanelLeftClose, PanelLeftOpen, Plus, Search, Settings, FolderKanban, MessageSquare } from 'lucide-react'
import { Conversation, Project } from '@/types'
import { SidebarItem } from './SidebarItem'
import { WorkspaceTabs } from './WorkspaceTabs'
import { WORKSPACE_MODE_CONFIG, WorkspaceMode } from './workspaceModes'
import { SearchModal } from '@/components/search/SearchModal'

interface Props {
  collapsed: boolean
  onToggleCollapse: () => void
  conversations: Conversation[]
  activeId: string
  onSelect: (id: string) => void
  onNewChat: (mode?: WorkspaceMode) => void
  onTabChange: (mode: WorkspaceMode) => void
  onPin: (id: string) => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
  projects?: Project[]
  showProjects?: boolean
  onToggleProjects?: () => void
  onAddToProject?: (convId: string, projId: string) => void
  settingsOpen?: boolean
  onOpenSettings?: () => void
  onCloseSettings?: () => void
}

export function Sidebar({ collapsed, onToggleCollapse, conversations, activeId, onSelect, onNewChat, onTabChange, onPin, onRename, onDelete, projects, showProjects, onToggleProjects, onAddToProject, settingsOpen, onOpenSettings, onCloseSettings }: Props) {
  const [mode, setMode] = useState<WorkspaceMode>('chat')
  const [searchOpen, setSearchOpen] = useState(false)
  const modeConfig = WORKSPACE_MODE_CONFIG[mode]

  const handleModeChange = (m: WorkspaceMode) => {
    if (m === mode) return
    setMode(m)
    onTabChange(m)
  }
  const modeConversations = useMemo(() => conversations.filter((c) => c.mode === mode), [conversations, mode])

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 264 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="h-full flex flex-col border-r border-base-800 bg-base-900 shrink-0"
    >
      <div className="flex items-center justify-between px-3 h-14 shrink-0">
        <div className="flex items-center gap-2.5">
          <img src="/assets/Cozmo-sprite.svg" alt="Cozmo" className="w-auto h-8" style={{ imageRendering: 'pixelated' }} />
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-semibold tracking-tight text-base-100 leading-tight">Cozmo</span>
              <span className="text-[10px] text-base-500 tracking-wide">AI coding assistant</span>
            </div>
          )}
        </div>
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-lg text-base-400 hover:text-base-100 hover:bg-base-800 transition-colors"
        >
          {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
        </button>
      </div>

      <div className="px-2 space-y-2">
        <WorkspaceTabs active={mode} onChange={handleModeChange} collapsed={collapsed} />

        <button
          onClick={() => onNewChat(mode)}
          className="w-full flex items-center gap-2 px-2.5 py-2 rounded-xl bg-accent/90 hover:bg-accent text-white text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          {!collapsed && modeConfig.createLabel}
        </button>
        {!collapsed && (
          <button onClick={() => setSearchOpen(true)} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-xl text-base-300 hover:bg-base-800 text-sm transition-colors">
            <Search size={15} />
            {modeConfig.searchLabel}
          </button>
        )}
        <button
          onClick={onToggleProjects}
          className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-xl text-sm transition-colors ${
            showProjects ? 'bg-accent/15 text-accent' : 'text-base-300 hover:bg-base-800 hover:text-base-100'
          }`}
        >
          <FolderKanban size={15} />
          {!collapsed && 'Projects'}
        </button>
      </div>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto mt-4 px-2 space-y-1">
          {(() => {
            const pinned = modeConversations.filter((c) => c.pinned)
            const recent = modeConversations.filter((c) => !c.pinned)
            return (
              <>
                {pinned.length > 0 && (
                  <>
                    <p className="px-2.5 text-[11px] uppercase tracking-wider text-accent mb-1">Pinned</p>
                    {pinned.map((c) => (
                      <SidebarItem key={c.id} conversation={c} active={c.id === activeId} onClick={() => onSelect(c.id)} onPin={onPin} onRename={onRename} onDelete={onDelete} projects={projects} onAddToProject={onAddToProject} />
                    ))}
                    <div className="h-2" />
                  </>
                )}
                <p className="px-2.5 text-[11px] uppercase tracking-wider text-base-500 mb-1">{modeConfig.emptyRecentLabel}</p>
                {recent.map((c) => (
                  <SidebarItem key={c.id} conversation={c} active={c.id === activeId} onClick={() => onSelect(c.id)} onPin={onPin} onRename={onRename} onDelete={onDelete} projects={projects} onAddToProject={onAddToProject} />
                ))}
              </>
            )
          })()}
        </div>
      )}

      <div className="mt-auto px-2 py-3 space-y-0.5 border-t border-base-800">
        <SidebarFooterItem icon={<Settings size={15} />} label="Settings" collapsed={collapsed} onClick={() => onOpenSettings?.()} />
      </div>
      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} onSelect={onSelect} />
    </motion.aside>
  )
}

function SidebarFooterItem({ icon, label, collapsed, onClick }: { icon: React.ReactNode; label: string; collapsed: boolean; onClick?: () => void }) {
  return (
    <button onClick={onClick} className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-base-400 hover:text-base-100 hover:bg-base-800 text-sm transition-colors">
      {icon}
      {!collapsed && label}
    </button>
  )
}
