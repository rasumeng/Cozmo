import { useCallback, useEffect, useRef, useState } from 'react'
import { Conversation, InlineStep, WorkspaceMode, Attachment, Project, PlanData, AgentTaskCreate, BackgroundRunInfo, BackgroundRunLog, ScheduledTaskInfo, AgentStateInfo, ProgressInfo } from '@/types'
import { CozmoClient, ConnectionState, ServerEvent, fetchConversations, saveConversation, deleteConversationApi, fetchProjects, createProject, updateProject, deleteProjectApi, fetchProjectConversations } from '@/services/cozmo'

export interface PermissionRequest {
  tool: string
  args: Record<string, unknown>
}

let idCounter = 0
const nextId = () => `id-${Date.now()}-${idCounter++}`
const now = () =>
  new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const DRAFT_ID = '__draft__'

export function useCozmoChat() {
  const clientRef = useRef<CozmoClient | null>(null)
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState(() => '')
  const [generating, setGenerating] = useState(false)
  const [inlineSteps, setInlineSteps] = useState<InlineStep[]>([])
  const [permission, setPermission] = useState<PermissionRequest | null>(null)
  const [plan, setPlan] = useState<PlanData | null>(null)
  const [currentDirectory, setCurrentDirectory] = useState('./')
  const [permissionMode, setPermissionMode] = useState('manual')
  const [recentConversations, setRecentConversations] = useState<{ id: string; title: string; mode: string; updatedAt: string }[]>([])
  const [agentTask, setAgentTask] = useState<Project | null>(null)
  const [backgroundRuns, setBackgroundRuns] = useState<BackgroundRunInfo[]>([])
  const [schedules, setSchedules] = useState<ScheduledTaskInfo[]>([])
  const [draftMode, setDraftMode] = useState<WorkspaceMode>('chat')
  const [agentState, setAgentState] = useState<AgentStateInfo | null>(null)
  const [progress, setProgress] = useState<ProgressInfo | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const dirtyRef = useRef(false)

  // Load conversations on mount
  useEffect(() => {
    fetchConversations()
      .then((list) => {
        setConversations(list)
      })
      .catch(() => {
        setConversations([])
      })
    fetchProjects()
      .then((list) => setProjects(list))
      .catch(() => {})
  }, [])

  // Persist when dirty (after message added)
  useEffect(() => {
    if (!dirtyRef.current) return
    dirtyRef.current = false
    const active = conversations.find((c) => c.id === resolvedActiveId)
    if (active && active.id) {
      saveConversation(active).catch(() => {})
    }
  })

  // activeId resolves lazily; fall back to draft
  const resolvedActiveId = activeId || conversations[0]?.id || DRAFT_ID

  const updateActive = useCallback(
    (fn: (c: Conversation) => Conversation) => {
      setConversations((convs) =>
        convs.map((c) => (c.id === resolvedActiveId ? fn(c) : c))
      )
    },
    [resolvedActiveId]
  )

  const appendToken = useCallback(
    (text: string) => {
      updateActive((c) => {
        const msgs = [...c.messages]
        const last = msgs[msgs.length - 1]
        if (last && last.role === 'assistant' && last.streaming) {
          msgs[msgs.length - 1] = { ...last, content: last.content + text }
        } else {
          msgs.push({
            id: nextId(),
            role: 'assistant',
            content: text,
            createdAt: now(),
            streaming: true,
          })
        }
        return { ...c, messages: msgs, updatedAt: 'Just now' }
      })
    },
    [updateActive]
  )

  const finishStreaming = useCallback(() => {
    updateActive((c) => ({
      ...c,
      messages: c.messages.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
    }))
    dirtyRef.current = true
  }, [updateActive])

  const toolLabel = (tool: string, args: Record<string, unknown>): string => {
    const p = args['path'] as string | undefined
    const q = args['query'] as string | undefined
    const pt = args['pattern'] as string | undefined
    const cmd = args['command'] as string | undefined
    const url = args['url'] as string | undefined
    switch (tool) {
      case 'read': return `Reading ${p ?? 'file'}...`
      case 'write_file': return `Writing ${p ?? 'file'}...`
      case 'edit_file': return `Editing ${p ?? 'file'}...`
      case 'glob': return `Finding files${pt ? `: ${pt}` : '...'}`
      case 'grep': return `Searching code${q ? ` for "${q.slice(0, 40)}"` : '...'}`
      case 'bash': return `Running${cmd ? `: ${cmd.slice(0, 50)}` : ' command...'}`
      case 'search_web': return `Searching web${q ? ` for "${q.slice(0, 40)}"` : '...'}`
      case 'web_fetch': return `Fetching ${url ?? 'page'}...`
      default: return `${tool.replace(/_/g, ' ')}...`
    }
  }

  const toolIcon = (tool: string): string => {
    switch (tool) {
      case 'read': case 'write_file': case 'edit_file': return 'FileText'
      case 'glob': case 'grep': return 'Search'
      case 'bash': return 'Terminal'
      case 'search_web': case 'web_fetch': return 'Globe'
      default: return 'Wrench'
    }
  }

  const toolSummary = (tool: string, args: Record<string, unknown>): string | undefined => {
    const p = args['path'] as string | undefined
    const q = args['query'] as string | undefined
    const pt = args['pattern'] as string | undefined
    const cmd = args['command'] as string | undefined
    const url = args['url'] as string | undefined
    switch (tool) {
      case 'read': return `Tool: read — Path: ${p ?? '?'}`
      case 'write_file': return `Tool: write_file — Path: ${p ?? '?'}`
      case 'edit_file': return `Tool: edit_file — Path: ${p ?? '?'}`
      case 'bash': return `Tool: bash — ${cmd ?? '?'}`
      case 'grep': return `Tool: grep — Pattern: ${q ?? pt ?? '?'}`
      case 'glob': return `Tool: glob — Pattern: ${pt ?? '?'}`
      case 'search_web': return `Tool: search_web — Query: ${q ?? '?'}`
      case 'web_fetch': return `Tool: web_fetch — URL: ${url ?? '?'}`
      default: return `Tool: ${tool}`
    }
  }

  const pushStep = useCallback((step: {
    type: 'thinking' | 'tool_call'
    icon: string
    label: string
    detail?: string
    query?: string
    toolCallId?: string
    toolName?: string
    toolCategory?: string
    toolSummary?: string
    status: 'running' | 'completed' | 'error'
  }) => {
    setInlineSteps(prev => {
      const now = Date.now()
      const closed = prev.map(s =>
        s.status === 'running' ? { ...s, status: 'completed' as const, durationMs: now - s.startedAt } : s
      )
      return [...closed, { ...step, id: nextId(), startedAt: now }]
    })
  }, [])

  const pushReasoning = useCallback((text: string) => {
    setInlineSteps(prev => {
      const last = prev[prev.length - 1]
      if (last && last.status === 'running' && last.icon === 'Brain' && last.label === 'Thinking...') {
        return prev.map((s, i) =>
          i === prev.length - 1
            ? { ...s, detail: (s.detail || '') + text }
            : s
        )
      }
      const now = Date.now()
      const closed: InlineStep[] = prev.map(s =>
        s.status === 'running' ? { ...s, status: 'completed' as const, durationMs: now - s.startedAt } : s
      )
      return [...closed, { id: nextId(), type: 'thinking' as const, icon: 'Brain', label: 'Thinking...', detail: text, status: 'running' as const, startedAt: now }]
    })
  }, [])

  const handleEvent = useCallback(
    (ev: ServerEvent) => {
      switch (ev.type) {
        case 'token':
          appendToken(ev.text)
          break
        case 'thinking':
        case 'status':
          pushStep({
            type: 'thinking',
            icon: 'Brain',
            label: ev.text,
            detail: ev.detail,
            query: ev.query,
            status: 'running',
          })
          break
        case 'reasoning':
          pushReasoning(ev.text)
          break
        case 'agent_status':
          pushStep({
            type: 'thinking',
            icon: 'Activity',
            label: ev.text,
            detail: ev.detail,
            query: ev.query,
            status: 'running',
          })
          break
        case 'plan':
          setPlan({ plan: ev.plan, status: 'pending' })
          break
        case 'tool_call':
          pushStep({
            type: 'tool_call',
            icon: toolIcon(ev.tool),
            label: toolLabel(ev.tool, ev.args),
            toolCallId: ev.id,
            toolName: ev.tool,
            toolCategory: ev.category,
            toolSummary: toolSummary(ev.tool, ev.args),
            status: 'running',
          })
          break
        case 'tool_result':
          setInlineSteps(prev => prev.map(s =>
            s.toolCallId === ev.id
              ? { ...s, status: 'completed' as const, durationMs: Date.now() - s.startedAt, result: ev.result, diff: ev.diff }
              : s
          ))
          break
        case 'directory_set':
          setCurrentDirectory(ev.path)
          break
        case 'projects_list':
          setProjects(ev.projects)
          break
        case 'recent_conversations':
          setRecentConversations(ev.conversations)
          break
        case 'project_created':
          setAgentTask(ev.project)
          setProjects(prev => [ev.project, ...prev])
          break
        case 'project_selected':
          setAgentTask(ev.project)
          break
        case 'background_run_update':
          setBackgroundRuns(prev => {
            const idx = prev.findIndex(r => r.run_id === ev.run_id)
            const run: BackgroundRunInfo = {
              run_id: ev.run_id,
              goal: ev.goal ?? '',
              status: ev.status,
              created: prev[idx]?.created ?? new Date().toISOString(),
              ended: ev.status === 'done' || ev.status === 'error' || ev.status === 'cancelled'
                ? new Date().toISOString() : '',
            }
            if (idx >= 0) {
              const next = [...prev]
              next[idx] = run
              return next
            }
            return [run, ...prev]
          })
          break
        case 'background_run_list':
          setBackgroundRuns(ev.runs)
          break
        case 'schedule_list':
          setSchedules(ev.schedules)
          break
        case 'schedule_created':
          setSchedules(prev => [ev.schedule, ...prev])
          break
        case 'schedule_deleted':
          setSchedules(prev => prev.filter(s => s.id !== ev.schedule_id))
          break
        case 'schedule_toggled':
          setSchedules(prev => prev.map(s => s.id === ev.schedule_id ? { ...s, enabled: ev.enabled } : s))
          break
        case 'progress':
          setProgress({ current: ev.current, total: ev.total, label: ev.label })
          break
        case 'agent_state':
          setAgentState({
            current_goal: ev.current_goal,
            status: ev.status,
            tools_used: ev.tools_used,
            error: ev.error,
          })
          break
        case 'permission_request':
          setPermission({ tool: ev.tool, args: ev.args })
          break
        case 'done':
          finishStreaming()
          setGenerating(false)
          setPermission(null)
          setPlan(null)
          setProgress(null)
          setInlineSteps(prev => prev.map(s =>
            s.status === 'running' ? { ...s, status: 'completed' as const, durationMs: Date.now() - s.startedAt } : s
          ))
          break
        case 'error':
          appendToken(`\n\n**Error:** ${ev.text}`)
          setGenerating(false)
          setProgress(null)
          break
      }
    },
    [appendToken, pushStep, pushReasoning, finishStreaming]
  )

  const handleEventRef = useRef(handleEvent)
  handleEventRef.current = handleEvent

  useEffect(() => {
    const client = new CozmoClient()
    client.onEvent = (ev) => handleEventRef.current(ev)
    client.onConnectionChange = setConnection
    client.connect()
    clientRef.current = client
    return () => client.disconnect()
  }, [])

  const sendMessage = useCallback(
    (content: string, attachments?: Attachment[]) => {
      const client = clientRef.current
      if (!client || generating) return
      const trimmed = content.trim()
      if (!trimmed && (!attachments || attachments.length === 0)) return
      const textToSend = trimmed || '(attachment)'

      // Find the project this conversation belongs to
      const convProject = projects.find(p => p.conversationIds.includes(resolvedActiveId))
      const projectId = convProject?.id

      if (resolvedActiveId === DRAFT_ID) {
        const newId = nextId()
        const newConv: Conversation = {
          id: newId,
          title: trimmed.slice(0, 48) || 'Attachments',
          updatedAt: 'Just now',
          pinned: false,
          mode: draftMode,
          messages: [{ id: nextId(), role: 'user', content: textToSend, createdAt: now(), attachments }],
        }
        if (!client.sendChat(textToSend, newId, attachments, projectId, draftMode)) return
        setConversations((convs) => [newConv, ...convs])
        setActiveId(newId)
        dirtyRef.current = true
        setInlineSteps([])
        setGenerating(true)
      } else {
        if (!client.sendChat(textToSend, resolvedActiveId, attachments, projectId, draftMode)) return
        updateActive((c) => ({
          ...c,
          title: c.messages.length === 0 ? (trimmed.slice(0, 48) || 'Attachments') : c.title,
          updatedAt: 'Just now',
          messages: [
            ...c.messages,
            { id: nextId(), role: 'user', content: textToSend, createdAt: now(), attachments },
          ],
        }))
        dirtyRef.current = true
        setInlineSteps([])
        setGenerating(true)
      }
    },
    [generating, updateActive, resolvedActiveId, draftMode, projects]
  )

  const stop = useCallback(() => {
    clientRef.current?.stop()
  }, [])

  const answerPermission = useCallback((allowed: boolean) => {
    clientRef.current?.answerPermission(allowed)
    setPermission(null)
  }, [])

  const answerPlan = useCallback((approved: boolean) => {
    clientRef.current?.answerPlan(approved)
    if (approved) {
      setPlan((p) => p ? { ...p, status: 'approved' } : null)
    } else {
      setPlan(null)
    }
  }, [])

  const setDirectory = useCallback((path: string) => {
    clientRef.current?.setDirectory(path)
  }, [])

  const handleSetPermissionMode = useCallback((mode: string) => {
    setPermissionMode(mode)
    clientRef.current?.setPermissionMode(mode)
  }, [])



  const handleListProjects = useCallback((search?: string) => {
    clientRef.current?.listProjects(search)
  }, [])

  const handleGetRecentConversations = useCallback((mode?: string, limit?: number) => {
    clientRef.current?.getRecentConversations(mode, limit)
  }, [])

  const handleImportFromChat = useCallback((conversationIds: string[]) => {
    clientRef.current?.importFromChat(conversationIds)
  }, [])

  const handleAgentCreateTask = useCallback((data: AgentTaskCreate) => {
    clientRef.current?.createProject(data)
  }, [])

  const handleSelectProject = useCallback((projectId: string) => {
    clientRef.current?.selectProject(projectId)
  }, [])

  const handleStartBackgroundRun = useCallback((goal: string) => {
    if (!goal.trim()) return
    clientRef.current?.startBackgroundRun(goal.trim())
  }, [])

  const handleStopBackgroundRun = useCallback((runId: string) => {
    clientRef.current?.stopBackgroundRun(runId)
  }, [])

  const handleRefreshBackgroundRuns = useCallback(() => {
    clientRef.current?.listBackgroundRuns()
  }, [])

  const handleListSchedules = useCallback(() => {
    clientRef.current?.listSchedules()
  }, [])

  const handleCreateSchedule = useCallback((goal: string, description: string, intervalMinutes: number) => {
    if (!goal.trim()) return
    clientRef.current?.createSchedule(goal.trim(), description, intervalMinutes)
  }, [])

  const handleDeleteSchedule = useCallback((scheduleId: string) => {
    clientRef.current?.deleteSchedule(scheduleId)
  }, [])

  const handleToggleSchedule = useCallback((scheduleId: string) => {
    clientRef.current?.toggleSchedule(scheduleId)
  }, [])

  const newChat = useCallback((mode: WorkspaceMode = 'chat') => {
    if (generating) return
    clientRef.current?.reset()
    setDraftMode(mode)
    setActiveId(DRAFT_ID)
    setInlineSteps([])
    setAgentState(null)
    setProgress(null)
  }, [generating])

  const pinConversation = useCallback((id: string) => {
    setConversations((convs) =>
      convs.map((c) => (c.id === id ? { ...c, pinned: !c.pinned } : c))
    )
  }, [])

  const renameConversation = useCallback((id: string, title: string) => {
    setConversations((convs) =>
      convs.map((c) => (c.id === id ? { ...c, title } : c))
    )
  }, [])

  const deleteConversation = useCallback((id: string) => {
    if (!id) return
    deleteConversationApi(id).catch(() => {})
    setConversations((convs) => convs.filter((c) => c.id !== id))
    setActiveId((prev) => prev === id ? DRAFT_ID : prev)
  }, [])

  const addConversationToProject = useCallback((convId: string, projId: string) => {
    const proj = projects.find(p => p.id === projId)
    if (!proj || proj.conversationIds.includes(convId)) return
    const updated = { ...proj, conversationIds: [...proj.conversationIds, convId] }
    setProjects(prev => prev.map(p => p.id === projId ? updated : p))
    updateProject(projId, { conversationIds: updated.conversationIds }).catch(() => {})
  }, [projects])

  const removeConversationFromProject = useCallback((convId: string, projId: string) => {
    const proj = projects.find(p => p.id === projId)
    if (!proj) return
    const updated = { ...proj, conversationIds: proj.conversationIds.filter(id => id !== convId) }
    setProjects(prev => prev.map(p => p.id === projId ? updated : p))
    updateProject(projId, { conversationIds: updated.conversationIds }).catch(() => {})
  }, [projects])

  const handleCreateProject = useCallback(async (name: string, description?: string, sharedContext?: string) => {
    const p = await createProject({ name, description, sharedContext })
    if (p) setProjects(prev => [p, ...prev])
    return p
  }, [])

  const handleUpdateProject = useCallback(async (id: string, data: Partial<Project>) => {
    const p = await updateProject(id, data)
    if (p) setProjects(prev => prev.map(pr => pr.id === id ? p : pr))
    return p
  }, [])

  const handleDeleteProject = useCallback(async (id: string) => {
    await deleteProjectApi(id)
    setProjects(prev => prev.filter(p => p.id !== id))
    if (activeProjectId === id) setActiveProjectId(null)
  }, [activeProjectId])

  // Resolve project shared context for the active conversation
  const activeProject = activeProjectId
    ? projects.find(p => p.id === activeProjectId) ?? null
    : null

  const active: Conversation = resolvedActiveId === DRAFT_ID
    ? { id: DRAFT_ID, title: 'New chat', updatedAt: '', pinned: false, mode: draftMode, messages: [] }
    : conversations.find((c) => c.id === resolvedActiveId) ?? conversations[0] ?? { id: DRAFT_ID, title: 'New chat', updatedAt: '', pinned: false, mode: draftMode, messages: [] }

  return {
    connection,
    conversations,
    active,
    activeId: resolvedActiveId,
    setActiveId,
    generating,
    inlineSteps,
    agentState,
    progress,
    plan,
    permission,
    currentDirectory,
    permissionMode,
    recentConversations,
    agentTask,
    backgroundRuns,
    schedules,
    sendMessage,
    setPermissionMode: handleSetPermissionMode,
    listProjects: handleListProjects,
    getRecentConversations: handleGetRecentConversations,
    importFromChat: handleImportFromChat,
    agentCreateTask: handleAgentCreateTask,
    selectProject: handleSelectProject,
    startBackgroundRun: handleStartBackgroundRun,
    stopBackgroundRun: handleStopBackgroundRun,
    refreshBackgroundRuns: handleRefreshBackgroundRuns,
    listSchedules: handleListSchedules,
    createSchedule: handleCreateSchedule,
    deleteSchedule: handleDeleteSchedule,
    toggleSchedule: handleToggleSchedule,
    stop,
    answerPermission,
    answerPlan,
    setDirectory,
    newChat,
    pinConversation,
    renameConversation,
    deleteConversation,
    projects,
    activeProjectId,
    setActiveProjectId,
    activeProject,
    addConversationToProject,
    removeConversationFromProject,
    createProject: handleCreateProject,
    updateProject: handleUpdateProject,
    deleteProject: handleDeleteProject,
  }
}
