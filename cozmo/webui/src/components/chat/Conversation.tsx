import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import { Conversation as ConversationType, Attachment, Project, AgentTaskFile, InlineStep, PlanData } from '@/types'
import { ConnectionState } from '@/services/cozmo'
import type { SectionId } from '@/components/settings/SettingsModal'
import { MessageBubble } from './MessageBubble'
import { InlineTraceTimeline } from './InlineTraceTimeline'
import { PromptInput } from './PromptInput'
import { LandingPage } from './LandingPage'

interface Props {
  conversation: ConversationType
  connection: ConnectionState
  generating: boolean
  inlineSteps: InlineStep[]
  plan: PlanData | null
  onSend: (content: string, attachments?: Attachment[]) => void
  onStop: () => void
  onApprovePlan: () => void
  onRejectPlan: () => void
  activeConversationId?: string
  projects?: Project[]
  onAddToProject?: (convId: string, projId: string) => void
  onOpenProjectPanel?: () => void
  onOpenSettings?: (section: SectionId) => void
  onCreateSkillTrigger?: () => void
  pendingSkillTrigger?: boolean
  onConsumeSkillTrigger?: () => void
  currentDirectory?: string
  onSetDirectory?: (path: string) => void
  permissionMode?: string
  onSetPermissionMode?: (mode: string) => void
  agentTask?: Project | null
  onListProjects?: (search?: string) => void
  onSelectProject?: (id: string) => void
  onCreateTask?: (data: { name: string; description: string; instructions: string; files: AgentTaskFile[]; location: string }) => void
  onImportChat?: (ids: string[]) => void
}

const CONNECTION_LABEL: Record<ConnectionState, { text: string; dot: string }> = {
  connecting: { text: 'Connecting…', dot: 'bg-amber-400' },
  open: { text: 'Connected', dot: 'bg-emerald-400' },
  closed: { text: 'Disconnected — retrying', dot: 'bg-red-400' },
}

export function Conversation({
  conversation,
  connection,
  generating,
  inlineSteps,
  plan,
  onSend,
  onStop,
  onApprovePlan,
  onRejectPlan,
  activeConversationId,
  projects,
  onAddToProject,
  onOpenProjectPanel,
  onOpenSettings,
  onCreateSkillTrigger,
  pendingSkillTrigger,
  onConsumeSkillTrigger,
  currentDirectory,
  onSetDirectory,
  permissionMode,
  onSetPermissionMode,
  agentTask,
  onListProjects,
  onSelectProject,
  onCreateTask,
  onImportChat,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [suggestionText, setSuggestionText] = useState('')

  // stick to bottom as tokens stream in
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [conversation.messages])

  const conn = CONNECTION_LABEL[connection]

  return (
    <main className="flex-1 flex flex-col min-w-0 bg-base-950">
      <header className="h-14 shrink-0 flex items-center justify-between px-5 border-b border-base-800">
        <div className="flex items-center gap-2.5 text-sm text-base-300">
          <div className="w-5 h-5 rounded-md bg-accent/15 flex items-center justify-center">
            <Sparkles size={12} className="text-accent" />
          </div>
          <span className="text-base-100 font-medium">{conversation.title}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[11px] text-base-500">
            <span className={`w-1.5 h-1.5 rounded-full ${conn.dot}`} />
            {conn.text}
          </div>
        </div>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
          {conversation.messages.length === 0 ? (
            <LandingPage mode={conversation.mode} onSuggestion={setSuggestionText} />
          ) : (
            conversation.messages.map((m, i, arr) => (
              <div key={m.id}>
                <MessageBubble message={m} />
                {m.role === 'user' && (i === arr.length - 1 || i === arr.length - 2) && (generating || inlineSteps.length > 0) && (
                  <div className="mt-3">
                    {inlineSteps.length === 0 ? (
                      <motion.div
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex items-center gap-2 px-1"
                      >
                        <div className="flex gap-1">
                          <span className="w-2 h-2 rounded-full bg-accent/70 animate-glow" />
                          <span className="w-2 h-2 rounded-full bg-accent/70 animate-glow" style={{ animationDelay: '0.2s' }} />
                          <span className="w-2 h-2 rounded-full bg-accent/70 animate-glow" style={{ animationDelay: '0.4s' }} />
                        </div>
                        <span className="text-[12px] text-base-500">Thinking...</span>
                      </motion.div>
                    ) : (
                      <InlineTraceTimeline
                        steps={inlineSteps}
                        plan={plan}
                        onApprovePlan={onApprovePlan}
                        onRejectPlan={onRejectPlan}
                        generating={generating}
                      />
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      <div className="border-t border-base-800 bg-base-950/80 backdrop-blur px-6 py-4">
        <div className="max-w-3xl mx-auto">
          <PromptInput
            generating={generating}
            disabled={connection !== 'open'}
            onSend={(content, attachments) => { setSuggestionText(''); onSend(content, attachments) }}
            onStop={onStop}
            activeConversationId={activeConversationId}
            mode={conversation.mode}
            projects={projects}
            onAddToProject={onAddToProject}
            onOpenProjectPanel={onOpenProjectPanel}
            onOpenSettings={onOpenSettings}
            onCreateSkillTrigger={onCreateSkillTrigger}
            pendingSkillTrigger={pendingSkillTrigger}
            onConsumeSkillTrigger={onConsumeSkillTrigger}
            suggestion={suggestionText}
            currentDirectory={currentDirectory}
            onSetDirectory={onSetDirectory}
            permissionMode={permissionMode}
            onSetPermissionMode={onSetPermissionMode}
            agentTask={agentTask}
            onListProjects={onListProjects}
            onSelectProject={onSelectProject}
            onCreateTask={onCreateTask}
            onImportChat={onImportChat}
          />
        </div>
      </div>
    </main>
  )
}
