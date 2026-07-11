import { useState } from 'react'
import { Sidebar } from '@/components/sidebar/Sidebar'
import { Conversation } from '@/components/chat/Conversation'
import { ActivityPanel } from '@/components/activity/ActivityPanel'
import { PermissionModal } from '@/components/common/PermissionModal'
import { ProjectsPanel } from '@/components/projects/ProjectsPanel'
import { useCozmoChat } from '@/hooks/useCozmoChat'
import { WorkspaceMode } from '@/types'

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [activityOpen, setActivityOpen] = useState(true)
  const [showProjects, setShowProjects] = useState(false)
  const chat = useCozmoChat()

  return (
    <div className="h-screen w-screen flex bg-base-950 text-base-100 overflow-hidden relative">
      <div className="absolute inset-0 pointer-events-none z-0" />
      <div className="relative z-10 flex flex-1">
        <Sidebar
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed((v) => !v)}
          conversations={chat.conversations}
          activeId={chat.activeId}
          onSelect={chat.setActiveId}
          onNewChat={(mode?: WorkspaceMode) => chat.newChat(mode)}
          onPin={chat.pinConversation}
          onRename={chat.renameConversation}
          onDelete={chat.deleteConversation}
          projects={chat.projects}
          showProjects={showProjects}
          onToggleProjects={() => setShowProjects(v => !v)}
          onAddToProject={chat.addConversationToProject}
        />
        {showProjects ? (
          <ProjectsPanel
            projects={chat.projects}
            conversations={chat.conversations}
            onCreateProject={chat.createProject}
            onUpdateProject={chat.updateProject}
            onDeleteProject={chat.deleteProject}
            onSelectConversation={(id) => { chat.setActiveId(id); setShowProjects(false) }}
            onRemoveConversation={chat.removeConversationFromProject}
            onSelectProject={chat.setActiveProjectId}
          />
        ) : (
          <Conversation
            conversation={chat.active}
            connection={chat.connection}
            generating={chat.generating}
            onSend={chat.sendMessage}
            onStop={chat.stop}
            onToggleActivity={() => setActivityOpen((v) => !v)}
            activityOpen={activityOpen}
          />
        )}
        {activityOpen && !showProjects && <ActivityPanel steps={chat.activity} />}
      </div>
      {chat.permission && (
        <PermissionModal request={chat.permission} onAnswer={chat.answerPermission} />
      )}
    </div>
  )
}
