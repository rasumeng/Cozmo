import { useState, useCallback, useEffect, useRef } from 'react'
import { Sidebar } from '@/components/sidebar/Sidebar'
import { Conversation } from '@/components/chat/Conversation'
import { ActivityPanel } from '@/components/activity/ActivityPanel'
import { RightPanel } from '@/components/activity/RightPanel'
import { PermissionModal } from '@/components/common/PermissionModal'
import { ProjectsPanel } from '@/components/projects/ProjectsPanel'

import { SettingsModal, SectionId } from '@/components/settings/SettingsModal'
import { useCozmoChat } from '@/hooks/useCozmoChat'
import { WorkspaceMode } from '@/types'

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [activityOpen, setActivityOpen] = useState(true)
  const [showProjects, setShowProjects] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsSection, setSettingsSection] = useState<SectionId>('models')
  const [pendingSkillTrigger, setPendingSkillTrigger] = useState(false)
  const [rightTab, setRightTab] = useState<'terminal' | 'diff' | 'trace'>('trace')
  const prevTermLen = useRef(0)
  const prevDiffLen = useRef(0)
  const chat = useCozmoChat()

  useEffect(() => {
    if (chat.active.mode !== 'code') return
    if (chat.terminalEntries.length > prevTermLen.current && rightTab !== 'terminal') {
      setRightTab('terminal')
    } else if (chat.diffEntries.length > prevDiffLen.current && rightTab !== 'diff') {
      setRightTab('diff')
    }
    prevTermLen.current = chat.terminalEntries.length
    prevDiffLen.current = chat.diffEntries.length
  }, [chat.terminalEntries.length, chat.diffEntries.length, chat.active.mode])

  const handleOpenSettings = useCallback((section?: SectionId) => {
    if (section) setSettingsSection(section)
    setSettingsOpen(true)
  }, [])

  const handleCreateSkill = useCallback(() => {
    setPendingSkillTrigger(true)
  }, [])

  const handleTabChange = useCallback((mode: WorkspaceMode) => {
    chat.newChat(mode)
    setShowProjects(false)
  }, [chat])

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
          onTabChange={handleTabChange}
          onPin={chat.pinConversation}
          onRename={chat.renameConversation}
          onDelete={chat.deleteConversation}
          projects={chat.projects}
          showProjects={showProjects}
          onToggleProjects={() => setShowProjects(v => !v)}
          onAddToProject={chat.addConversationToProject}
          settingsOpen={settingsOpen}
          onOpenSettings={() => handleOpenSettings()}
          onCloseSettings={() => setSettingsOpen(false)}
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
            activeConversationId={chat.activeId && chat.activeId !== '__draft__' ? chat.activeId : undefined}
            projects={chat.projects}
            onAddToProject={chat.addConversationToProject}
            onOpenProjectPanel={() => setShowProjects(true)}
            onOpenSettings={handleOpenSettings}
            onCreateSkillTrigger={() => setPendingSkillTrigger(true)}
            pendingSkillTrigger={pendingSkillTrigger}
            onConsumeSkillTrigger={() => setPendingSkillTrigger(false)}
            currentDirectory={chat.currentDirectory}
            onSetDirectory={chat.setDirectory}
            permissionMode={chat.permissionMode}
            onSetPermissionMode={chat.setPermissionMode}
            diffEntries={chat.diffEntries}
            agentTask={chat.agentTask}
            onListProjects={chat.listProjects}
            onSelectProject={chat.selectProject}
            onCreateTask={chat.agentCreateTask}
            onImportChat={chat.importFromChat}
          />
        )}
        {activityOpen && !showProjects && chat.active.mode === 'code' && (
          <RightPanel
            activeTab={rightTab}
            onTabChange={setRightTab}
            terminalEntries={chat.terminalEntries}
            diffEntries={chat.diffEntries}
            activitySteps={chat.activity}
            plan={chat.plan}
            onApprovePlan={() => chat.answerPlan(true)}
            onRejectPlan={() => chat.answerPlan(false)}
            onClearTerminal={chat.clearTerminal}
          />
        )}
        {activityOpen && !showProjects && chat.active.mode !== 'code' && (
          <ActivityPanel
            steps={chat.activity}
            plan={chat.plan}
            onApprovePlan={() => chat.answerPlan(true)}
            onRejectPlan={() => chat.answerPlan(false)}
          />
        )}
      </div>
      {chat.permission && (
        <PermissionModal request={chat.permission} onAnswer={chat.answerPermission} />
      )}
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        initialSection={settingsSection}
        onCreateSkill={handleCreateSkill}
      />
    </div>
  )
}
