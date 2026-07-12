import { useEffect, useState, useRef, useCallback } from 'react'
import { Paperclip, ArrowUp, Square, Mic, Plus, Folder, Puzzle, Cable, X, ChevronRight, Settings } from 'lucide-react'
import { Attachment, Project, Skill } from '@/types'
import { fetchSkills } from '@/services/cozmo'
import type { SectionId } from '@/components/settings/SettingsModal'

const API_BASE = import.meta.env.DEV ? 'http://localhost:8765' : ''

interface SpeechRecognition extends EventTarget {
  continuous: boolean
  interimResults: boolean
  lang: string
  start(): void
  stop(): void
  onstart: (() => void) | null
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onend: (() => void) | null
  onerror: ((event: { error: string }) => void) | null
}

interface SpeechRecognitionEvent {
  resultIndex: number
  results: SpeechRecognitionResultList
}

interface SpeechRecognitionResultList {
  length: number
  item(index: number): SpeechRecognitionResult
  [index: number]: SpeechRecognitionResult
}

interface SpeechRecognitionResult {
  isFinal: boolean
  [index: number]: { transcript: string }
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognition
  prototype: SpeechRecognition
}

declare global {
  interface Window {
    webkitSpeechRecognition: SpeechRecognitionConstructor
    SpeechRecognition?: SpeechRecognitionConstructor
  }
}

interface Props {
  generating: boolean
  disabled: boolean
  onSend: (content: string, attachments?: Attachment[]) => void
  onStop: () => void
  activeConversationId?: string
  projects?: Project[]
  onAddToProject?: (convId: string, projId: string) => void
  onOpenProjectPanel?: () => void
  onOpenSettings?: (section: SectionId) => void
  onCreateSkillTrigger?: () => void
  pendingSkillTrigger?: boolean
  onConsumeSkillTrigger?: () => void
  suggestion?: string
}

export function PromptInput({
  generating,
  disabled,
  onSend,
  onStop,
  activeConversationId,
  projects = [],
  onAddToProject,
  onOpenProjectPanel,
  onOpenSettings,
  onCreateSkillTrigger,
  pendingSkillTrigger,
  onConsumeSkillTrigger,
  suggestion,
}: Props) {
  const [value, setValue] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [activeSubmenu, setActiveSubmenu] = useState<string | null>(null)
  const [micState, setMicState] = useState<'idle' | 'listening' | 'recording'>('idle')
  const micStateRef = useRef<'idle' | 'listening' | 'recording'>('idle')
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const valueRef = useRef('')
  const prefixRef = useRef('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [uploading, setUploading] = useState(false)
  const [skills, setSkills] = useState<Skill[]>([])
  const submenuTimerRef = useRef<number | null>(null)

  const transcribeAudio = useCallback(async (blob: Blob): Promise<string | null> => {
    const form = new FormData()
    form.append('file', blob, 'audio.webm')
    try {
      const r = await fetch(`${API_BASE}/api/transcribe`, { method: 'POST', body: form })
      if (r.ok) {
        const { text } = await r.json()
        return text ?? null
      }
    } catch { /* ignore */ }
    return null
  }, [])

  const lastTextRef = useRef('')

  const sendAccumulated = useCallback(async (isFinal: boolean) => {
    const all = audioChunksRef.current
    if (all.length === 0) return
    const blob = new Blob(all, { type: mediaRecorderRef.current?.mimeType ?? 'audio/webm' })
    const text = await transcribeAudio(blob)
    if (!text) return
    const prev = lastTextRef.current
    if (text.startsWith(prev)) {
      const novel = text.slice(prev.length).trim()
      if (novel) {
        setValue((v) => v + (v ? ' ' : '') + novel)
      }
    } else {
      const pfx = prefixRef.current
      setValue(pfx + (pfx && text ? ' ' : '') + text)
    }
    lastTextRef.current = text
    if (isFinal) lastTextRef.current = ''
  }, [transcribeAudio])

  // poll accumulated audio every 2s during recording
  useEffect(() => {
    if (micState !== 'recording') return
    let cancelled = false
    const poll = async () => {
      if (cancelled) return
      await sendAccumulated(false)
      if (!cancelled) setTimeout(poll, 1000)
    }
    poll()
    return () => { cancelled = true }
  }, [micState, sendAccumulated])

  const startFallbackRecording = useCallback(async () => {
    let stream: MediaStream | null = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      micStateRef.current = 'idle'
      setMicState('idle')
      return
    }
    prefixRef.current = valueRef.current
    audioChunksRef.current = []
    const recorder = new MediaRecorder(stream)
    mediaRecorderRef.current = recorder
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunksRef.current.push(e.data)
    }
    recorder.onstop = async () => {
      stream?.getTracks().forEach((t) => t.stop())
      await sendAccumulated(true)
    }
    recorder.start(1000)
    micStateRef.current = 'recording'
    setMicState('recording')
  }, [transcribeAudio])

  const trySpeechRecognition = useCallback(() => {
    const SR = window.webkitSpeechRecognition || (window as any).SpeechRecognition
    if (!SR) {
      startFallbackRecording()
      return
    }
    const recognition = new SR()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = 'en-US'

    recognition.onstart = () => {
      micStateRef.current = 'listening'
      setMicState('listening')
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          setValue((prev) => prev + event.results[i][0].transcript)
        }
      }
    }

    recognition.onend = () => {
      if (micStateRef.current === 'listening') {
        trySpeechRecognition()
      } else {
        setMicState('idle')
      }
    }

    recognition.onerror = () => {
      if (micStateRef.current === 'idle') return
      micStateRef.current = 'idle'
      recognitionRef.current = null
      startFallbackRecording()
    }

    recognitionRef.current = recognition
    recognition.start()
  }, [startFallbackRecording])

  const handleAttachFiles = useCallback(async (files: FileList | File[]) => {
    setUploading(true)
    const uploaded: Attachment[] = []
    for (const file of Array.from(files)) {
      const form = new FormData()
      form.append('file', file)
      try {
        const r = await fetch(`${API_BASE}/api/attachments`, { method: 'POST', body: form })
        if (r.ok) {
          const att: Attachment = await r.json()
          att.url = `${API_BASE}${att.url}`
          if (att.thumbnail) att.thumbnail = `${API_BASE}${att.thumbnail}`
          uploaded.push(att)
        }
      } catch { /* ignore */ }
    }
    setAttachments(prev => [...prev, ...uploaded])
    setUploading(false)
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      handleAttachFiles(e.target.files)
      e.target.value = ''
    }
  }, [handleAttachFiles])

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData.items
    const imageFiles: File[] = []
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) imageFiles.push(file)
      }
    }
    if (imageFiles.length > 0) {
      e.preventDefault()
      handleAttachFiles(imageFiles)
    }
  }, [handleAttachFiles])

  const removeAttachment = useCallback((id: string) => {
    setAttachments(prev => prev.filter(a => a.id !== id))
    fetch(`${API_BASE}/api/attachments/${id}`, { method: 'DELETE' }).catch(() => {})
  }, [])

  const toggleMic = useCallback(() => {
    if (micStateRef.current === 'idle') {
      micStateRef.current = 'listening'
      trySpeechRecognition()
    } else {
      const prev = micStateRef.current
      micStateRef.current = 'idle'
      setMicState('idle')
      if (prev === 'listening') {
        recognitionRef.current?.stop()
        recognitionRef.current = null
      } else if (prev === 'recording') {
        mediaRecorderRef.current?.stop()
        mediaRecorderRef.current = null
      }
    }
  }, [trySpeechRecognition])

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop()
      mediaRecorderRef.current?.stop()
    }
  }, [])

  useEffect(() => {
    if (!menuOpen) return
    const close = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
        setActiveSubmenu(null)
      }
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menuOpen])

  useEffect(() => {
    fetchSkills().then(setSkills).catch(() => {})
  }, [])

  useEffect(() => {
    if (pendingSkillTrigger) {
      setValue((prev) => {
        const prefix = prev ? prev + ' ' : ''
        return prefix + '@skill skill-creator'
      })
      onConsumeSkillTrigger?.()
      textareaRef.current?.focus()
    }
  }, [pendingSkillTrigger, onConsumeSkillTrigger])

  useEffect(() => {
    if (suggestion) {
      setValue(suggestion)
      textareaRef.current?.focus()
    }
  }, [suggestion])

  const autoResize = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }, [])

  useEffect(() => { autoResize() }, [value, autoResize])

  const submit = () => {
    if (generating) {
      onStop()
      return
    }
    if ((!value.trim() && attachments.length === 0) || disabled) return
    onSend(value, attachments.length > 0 ? attachments : undefined)
    setValue('')
    setAttachments([])
  }

  return (
    <div className="rounded-2xl border border-base-700 bg-base-900 shadow-panel focus-within:border-base-600 transition-colors">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => { setValue(e.target.value); valueRef.current = e.target.value }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
        onPaste={handlePaste}
        placeholder={disabled ? 'Connecting to Cozmo…' : 'Message Cozmo...'}
        rows={1}
        disabled={disabled}
        className="w-full resize-none bg-transparent px-4 pt-3.5 pb-2 text-[15px] text-base-100 placeholder:text-base-500 focus:outline-none disabled:opacity-60 max-h-[200px] overflow-y-auto"
      />
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 px-4 pb-2">
          {attachments.map(att => (
            <span key={att.id} className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-base-800 text-xs text-base-200">
              {att.type === 'image' ? (
                <img
                  src={att.thumbnail || att.url}
                  alt={att.name}
                  className="w-6 h-6 rounded object-cover"
                />
              ) : (
                <Paperclip size={12} />
              )}
              <span className="truncate max-w-[120px]">{att.name}</span>
              <button onClick={() => removeAttachment(att.id)} className="text-base-400 hover:text-base-100 ml-0.5">
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex items-center justify-between px-2.5 pb-2.5">
        <div className="flex items-center gap-1">
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="p-2 rounded-lg text-base-400 hover:text-base-100 hover:bg-base-800 transition-colors"
            >
              <Plus size={16} />
            </button>
            {menuOpen && (
              <div
                className="absolute bottom-full mb-1 left-0 bg-base-850 border border-base-700 rounded-xl overflow-visible shadow-panel min-w-[180px] z-10 py-1"
                onMouseLeave={() => setActiveSubmenu(null)}
              >
                <button
                  onClick={() => { setMenuOpen(false); fileInputRef.current?.click() }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-base-200 hover:bg-base-800 transition-colors"
                >
                  <Paperclip size={13} /> Attach files or photos
                </button>

                <div
                  className="relative"
                  onMouseEnter={() => { if (submenuTimerRef.current) clearTimeout(submenuTimerRef.current); setActiveSubmenu('project') }}
                  onMouseLeave={() => { submenuTimerRef.current = window.setTimeout(() => setActiveSubmenu(null), 150) }}
                >
                  <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-base-200 hover:bg-base-800 transition-colors">
                    <Folder size={13} /> Add to project <ChevronRight size={12} className="ml-auto" />
                  </button>
                  {activeSubmenu === 'project' && (
                    <div
                      className="absolute left-full top-0 bg-base-850 border border-base-700 rounded-xl overflow-hidden shadow-panel min-w-[170px] z-20 py-1"
                      onMouseEnter={() => { if (submenuTimerRef.current) clearTimeout(submenuTimerRef.current); setActiveSubmenu('project') }}
                      onMouseLeave={() => { submenuTimerRef.current = window.setTimeout(() => setActiveSubmenu(null), 150) }}
                    >
                      {projects.length === 0 ? (
                        <div className="px-3 py-2 text-xs text-base-500">No projects yet</div>
                      ) : (
                        projects.map((p) => (
                          <button
                            key={p.id}
                            onClick={() => {
                              if (activeConversationId && onAddToProject) {
                                onAddToProject(activeConversationId, p.id)
                              }
                              setMenuOpen(false)
                              setActiveSubmenu(null)
                            }}
                            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-base-200 hover:bg-base-800 transition-colors text-left"
                          >
                            <Folder size={12} className="text-accent shrink-0" />
                            <span className="truncate">{p.name}</span>
                          </button>
                        ))
                      )}
                      <div className="border-t border-base-700 my-1" />
                      <button
                        onClick={() => {
                          setMenuOpen(false)
                          setActiveSubmenu(null)
                          onOpenProjectPanel?.()
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-accent hover:bg-base-800 transition-colors"
                      >
                        <Plus size={12} /> Start a new project
                      </button>
                    </div>
                  )}
                </div>

                <div className="border-t border-base-700 my-1" />

                <div
                  className="relative"
                  onMouseEnter={() => { if (submenuTimerRef.current) clearTimeout(submenuTimerRef.current); setActiveSubmenu('skills') }}
                  onMouseLeave={() => { submenuTimerRef.current = window.setTimeout(() => setActiveSubmenu(null), 150) }}
                >
                  <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-base-200 hover:bg-base-800 transition-colors">
                    <Puzzle size={13} /> Skills <ChevronRight size={12} className="ml-auto" />
                  </button>
                  {activeSubmenu === 'skills' && (
                    <div
                      className="absolute left-full top-0 bg-base-850 border border-base-700 rounded-xl overflow-hidden shadow-panel min-w-[170px] z-20 py-1"
                      onMouseEnter={() => { if (submenuTimerRef.current) clearTimeout(submenuTimerRef.current); setActiveSubmenu('skills') }}
                      onMouseLeave={() => { submenuTimerRef.current = window.setTimeout(() => setActiveSubmenu(null), 150) }}
                    >
                      {skills.length === 0 ? (
                        <div className="px-3 py-2 text-xs text-base-500">No skills installed</div>
                      ) : (
                        skills.map((s) => (
                          <button
                            key={s.name}
                            onClick={() => {
                              setValue((prev) => prev + (prev ? ' ' : '') + `@skill ${s.name}`)
                              setMenuOpen(false)
                              setActiveSubmenu(null)
                            }}
                            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-base-200 hover:bg-base-800 transition-colors text-left"
                          >
                            <Puzzle size={12} className="text-base-400 shrink-0" />
                            <span className="truncate">{s.name}</span>
                          </button>
                        ))
                      )}
                      <div className="border-t border-base-700 my-1" />
                      <button
                        onClick={() => {
                          setMenuOpen(false)
                          setActiveSubmenu(null)
                          onOpenSettings?.('skills')
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-base-300 hover:bg-base-800 transition-colors"
                      >
                        <Settings size={12} /> Manage skills
                      </button>
                    </div>
                  )}
                </div>

                <div
                  className="relative"
                  onMouseEnter={() => { if (submenuTimerRef.current) clearTimeout(submenuTimerRef.current); setActiveSubmenu('connectors') }}
                  onMouseLeave={() => { submenuTimerRef.current = window.setTimeout(() => setActiveSubmenu(null), 150) }}
                >
                  <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-base-200 hover:bg-base-800 transition-colors">
                    <Cable size={13} /> Connectors <ChevronRight size={12} className="ml-auto" />
                  </button>
                  {activeSubmenu === 'connectors' && (
                    <div
                      className="absolute left-full top-0 bg-base-850 border border-base-700 rounded-xl overflow-hidden shadow-panel min-w-[170px] z-20 py-1"
                      onMouseEnter={() => { if (submenuTimerRef.current) clearTimeout(submenuTimerRef.current); setActiveSubmenu('connectors') }}
                      onMouseLeave={() => { submenuTimerRef.current = window.setTimeout(() => setActiveSubmenu(null), 150) }}
                    >
                      <div className="px-3 py-2 text-xs text-base-500">
                        Manage MCP server connections
                      </div>
                      <div className="border-t border-base-700 my-1" />
                      <button
                        onClick={() => {
                          setMenuOpen(false)
                          setActiveSubmenu(null)
                          onOpenSettings?.('connectors')
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-base-300 hover:bg-base-800 transition-colors"
                      >
                        <Settings size={12} /> Manage connectors
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,.pdf,.txt,.py,.js,.ts,.md,.json,.csv,.docx,.xlsx"
            className="hidden"
            onChange={handleFileSelect}
          />
          <button
            onClick={toggleMic}
            className={`relative p-2 rounded-lg transition-colors ${
              micState === 'idle'
                ? 'text-base-400 hover:text-base-100 hover:bg-base-800'
                : 'text-red-400 bg-red-500/10 shadow-[0_0_10px_rgba(239,68,68,0.35)]'
            }`}
            title={
              micState === 'idle' ? 'Voice input' :
              micState === 'listening' ? 'Stop listening' : 'Stop recording'
            }
          >
            <Mic size={16} className={micState !== 'idle' ? 'animate-pulse' : ''} />
            {micState === 'recording' && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-400" />
            )}
          </button>
        </div>

        <button
          onClick={submit}
          disabled={disabled || (!value.trim() && attachments.length === 0 && !generating)}
          className="p-2 rounded-full bg-accent hover:bg-accent/90 disabled:bg-base-700 disabled:text-base-500 text-white transition-colors"
        >
          {generating ? <Square size={14} /> : <ArrowUp size={16} />}
        </button>
      </div>
    </div>
  )
}