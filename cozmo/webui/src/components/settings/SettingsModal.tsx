import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Search, Cpu, Brain, Wrench, Puzzle, Cable, Settings, Plus, Trash2, ChevronDown, Upload, Edit3, Sparkles, Plug, Power, PowerOff, FileText, GitBranch, Globe, Database, Lightbulb, Calendar, Mail, MessageSquare, Map, Activity, Image, Server, Cloud, Store, PackagePlus } from 'lucide-react'
import { fetchTools, fetchSkills, createSkill, deleteSkill, uploadSkill, fetchMcpCatalog, fetchMcpStatus, fetchServerDetail } from '@/services/cozmo'
import { Skill, McpCatalogEntry, McpStatusResponse, McpServerStatus, McpServerDetail, McpServerTool } from '@/types'

interface ToolInfo {
  id: string
  name: string
  description: string
  enabled: boolean
}

interface SettingsData {
  models: Record<string, unknown>
  memory: { max_turns_before_summary: number; max_short_term_pairs: number }
  runtime?: { tool_gate?: Record<string, string[]> }
  permissions?: Record<string, unknown>
  mcp?: { servers: Record<string, { command: string; args?: string[]; env?: Record<string, string> }> }
  [key: string]: unknown
}

export type SectionId = 'models' | 'tools' | 'memory' | 'skills' | 'connectors' | 'general'

const SECTIONS: { id: SectionId; label: string; icon: React.ElementType }[] = [
  { id: 'models', label: 'Models', icon: Cpu },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'skills', label: 'Skills', icon: Puzzle },
  { id: 'connectors', label: 'Connectors', icon: Cable },
  { id: 'general', label: 'General', icon: Settings },
]

const API_BASE = import.meta.env.DEV ? 'http://localhost:8765' : ''

async function fetchConfig(): Promise<SettingsData> {
  const r = await fetch(`${API_BASE}/api/config`)
  return r.json()
}

async function saveConfig(patch: Record<string, unknown>) {
  await fetch(`${API_BASE}/api/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
}

async function fetchOllamaModels(): Promise<string[]> {
  try {
    const r = await fetch(`${API_BASE}/api/ollama/models`)
    if (r.ok) return r.json()
  } catch {}
  return []
}

interface Props {
  open: boolean
  onClose: () => void
  initialSection?: SectionId
  onCreateSkill?: () => void
}

export function SettingsModal({ open, onClose, initialSection, onCreateSkill }: Props) {
  const [section, setSection] = useState<SectionId>('models')
  const [search, setSearch] = useState('')
  const [config, setConfig] = useState<SettingsData | null>(null)
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [dirty, setDirty] = useState(false)
  const [lightweight, setLightweight] = useState(false)
  const [skills, setSkills] = useState<Skill[]>([])
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    if (initialSection) setSection(initialSection)
    fetchConfig().then((cfg) => {
      setConfig(cfg)
      setLightweight(!!(cfg as any)?.runtime?.lightweight_mode)
    }).catch(() => {})
    fetchOllamaModels().then(setOllamaModels).catch(() => {})
    fetchTools()
      .then(setTools)
      .catch(() => {})
    fetchSkills()
      .then(setSkills)
      .catch(() => {})
  }, [open, initialSection])

  const updateToolPermission = (toolId: string, mode: string) => {
    if (!config) return
    setConfig({ ...config, permissions: { ...(config.permissions as Record<string, unknown> ?? {}), [toolId]: mode } } as SettingsData)
    setDirty(true)
  }

  const save = () => {
    if (!config) return
    const patch: Record<string, unknown> = { models: config.models }
    if (config.permissions) patch.permissions = config.permissions
    patch.runtime = { ...((config as any).runtime ?? {}), lightweight_mode: lightweight }
    saveConfig(patch).catch(() => {})
    setDirty(false)
  }

  useEffect(() => {
    if (!open) return
    const handleClick = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        if (dirty) save()
        onClose()
      }
    }
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (dirty) save()
        onClose()
      }
    }
    window.addEventListener('mousedown', handleClick)
    window.addEventListener('keydown', handleKey)
    return () => {
      window.removeEventListener('mousedown', handleClick)
      window.removeEventListener('keydown', handleKey)
    }
  }, [open, dirty, onClose])

  const filteredSections = useMemo(() => {
    if (!search) return SECTIONS
    const q = search.toLowerCase()
    return SECTIONS.filter((s) => s.label.toLowerCase().includes(q))
  }, [search])

  const updateModel = (role: string, model: string) => {
    if (!config) return
    setConfig({ ...config, models: { ...config.models, [role]: model } } as SettingsData)
    setDirty(true)
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
        >
          <motion.div
            ref={modalRef}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            className="flex w-[800px] h-[560px] rounded-2xl border border-base-700 bg-base-900 shadow-2xl overflow-hidden"
          >
            <div className="w-48 shrink-0 border-r border-base-800 flex flex-col bg-base-950/50">
              <div className="p-3 border-b border-base-800">
                <div className="flex items-center gap-2 mb-3">
                  <Settings size={16} className="text-accent" />
                  <span className="text-sm font-semibold text-base-100">Settings</span>
                </div>
                <div className="relative">
                  <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-base-500" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search settings..."
                    className="w-full bg-base-800 border border-base-700 rounded-lg pl-7 pr-2.5 py-1.5 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40 transition-colors"
                  />
                </div>
              </div>
              <div className="flex-1 overflow-y-auto py-1">
                {filteredSections.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSection(s.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
                      section === s.id
                        ? 'bg-base-800 text-base-100 border-l-2 border-accent'
                        : 'text-base-400 hover:text-base-200 hover:bg-base-850'
                    }`}
                  >
                    <s.icon size={14} />
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 flex flex-col min-w-0">
              <div className="flex items-center justify-between px-5 h-12 border-b border-base-800 shrink-0">
                <h2 className="text-sm font-semibold text-base-100">
                  {SECTIONS.find((s) => s.id === section)?.label}
                </h2>
                <div className="flex items-center gap-2">
                  {dirty && (
                    <button
                      onClick={save}
                      className="px-3 py-1 text-xs font-medium rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors"
                    >
                      Save
                    </button>
                  )}
                  <button
                    onClick={() => {
                      if (dirty) save()
                      onClose()
                    }}
                    className="p-1.5 rounded-lg text-base-400 hover:text-base-100 hover:bg-base-800 transition-colors"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {section === 'models' && renderModels(config, updateModel, ollamaModels, setConfig, setDirty, lightweight)}
                {section === 'tools' && renderTools(tools, config, updateToolPermission)}
                {section === 'memory' && <MemorySettings config={config} />}
                {section === 'skills' && (
                  <SkillsSection
                    skills={skills}
                    onRefresh={() => fetchSkills().then(setSkills).catch(() => {})}
                    onCreateSkill={onCreateSkill}
                    onClose={onClose}
                  />
                )}
                {section === 'connectors' && <ConnectorsSection config={config} setConfig={setConfig} setDirty={setDirty} />}
                {section === 'general' && renderGeneral(config, setConfig, lightweight, setLightweight, setDirty)}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

const BUILTIN_ROLES = ['chat', 'coder', 'vision', 'research', 'classifier']
const INTERNAL_KEYS = ['max_tokens']

function renderModels(
  config: SettingsData | null,
  updateModel: (role: string, model: string) => void,
  ollamaModels: string[],
  setConfig: (c: SettingsData) => void,
  setDirty: (d: boolean) => void,
  lightweight: boolean,
) {
  const PRESET_META: Record<string, { label: string; desc: string }> = {
    chat: { label: 'Chat', desc: 'General conversation & Q&A' },
    coder: { label: 'Coder', desc: 'Code generation & editing' },
    vision: { label: 'Vision', desc: 'Image analysis & vision tasks' },
    research: { label: 'Research', desc: 'Deep research & search' },
    classifier: { label: 'Classifier', desc: 'Text classification & sentiment analysis' },
  }

  if (!config) return null

  const customEntries = Object.entries(config.models ?? {})
    .filter(([k]) => !BUILTIN_ROLES.includes(k) && !INTERNAL_KEYS.includes(k))
    .map(([key, val]) => ({ key, model: String(val) }))

  const addCustom = () => {
    const key = `preset-${Date.now()}`
    setConfig({ ...config, models: { ...config.models, [key]: '' } })
    setDirty(true)
  }

  const updateCustomModel = (key: string, model: string) => {
    setConfig({ ...config, models: { ...config.models, [key]: model } })
    setDirty(true)
  }

  const renameCustom = (oldKey: string, newKey: string) => {
    if (!newKey.trim() || oldKey === newKey) return
    const { [oldKey]: val, ...rest } = config.models
    setConfig({ ...config, models: { ...rest, [newKey]: val as string } })
    setDirty(true)
  }

  const removeCustom = (key: string) => {
    const { [key]: _, ...rest } = config.models
    setConfig({ ...config, models: rest })
    setDirty(true)
  }

  const isLightweight = lightweight

  return (
    <div className="space-y-5">
      <p className="text-xs text-base-500">Assign models to each preset role. Changes take effect after saving.</p>
      {isLightweight && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-accent/10 border border-accent/30">
          <span className="text-xs text-accent font-medium">Lightweight mode active</span>
          <span className="text-xs text-base-500">— all roles use openbmb/minicpm5</span>
        </div>
      )}
      <div className="space-y-2">
        {BUILTIN_ROLES.map((role) => (
          <div key={role} className="flex items-center justify-between p-3 rounded-xl bg-base-800/50 border border-base-700">
            <div>
              <p className="text-sm text-base-100 font-medium">{PRESET_META[role]?.label ?? role}</p>
              <p className="text-xs text-base-500">{PRESET_META[role]?.desc ?? ''}</p>
            </div>
            <ModelSelect
              value={isLightweight ? 'openbmb/minicpm5' : String(config.models?.[role] ?? '')}
              models={ollamaModels}
              onChange={(v) => updateModel(role, v)}
              disabled={isLightweight}
            />
          </div>
        ))}
      </div>
      <div className="border-t border-base-700 pt-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm text-base-200 font-medium">Custom Presets</p>
          <button
            onClick={addCustom}
            disabled={isLightweight}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg bg-base-800 text-base-300 hover:bg-base-700 hover:text-base-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus size={12} /> Add
          </button>
        </div>
        <div className="space-y-2">
          {customEntries.map(({ key, model }) => (
            <div key={key} className="flex items-center gap-2 p-2 rounded-xl bg-base-800/30 border border-base-700">
              <input
                defaultValue={key}
                onBlur={(e) => renameCustom(key, e.target.value)}
                disabled={isLightweight}
                className="flex-1 bg-base-900 border border-base-700 rounded-lg px-2.5 py-1.5 text-xs text-base-200 outline-none focus:border-accent/40 disabled:opacity-50 disabled:cursor-not-allowed"
                placeholder="Preset name"
              />
              <ModelSelect
                value={model}
                models={ollamaModels}
                onChange={(v) => updateCustomModel(key, v)}
                disabled={isLightweight}
              />
              <button onClick={() => removeCustom(key)} disabled={isLightweight} className="p-1 rounded text-base-500 hover:text-err transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ModelSelect({ value, models, onChange, disabled }: { value: string; models: string[]; onChange: (v: string) => void; disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => !disabled && setOpen((v) => !v)}
        disabled={disabled}
        className={`flex items-center gap-2 w-48 bg-base-900 border border-base-700 rounded-lg px-2.5 py-1.5 text-xs text-base-200 font-mono outline-none transition-colors ${
          disabled
            ? 'opacity-50 cursor-not-allowed'
            : 'hover:border-accent/40'
        }`}
      >
        <span className="flex-1 text-left truncate">{value || 'Select model'}</span>
        <ChevronDown size={12} className="text-base-500 shrink-0" />
      </button>
      {open && (
        <div className="absolute top-full mt-1 left-0 bg-base-850 border border-base-700 rounded-xl overflow-hidden shadow-panel min-w-[200px] z-10 max-h-48 overflow-y-auto">
          {models.length === 0 && (
            <p className="px-3 py-2 text-xs text-base-500">No models found</p>
          )}
          {models.map((m) => (
            <button
              key={m}
              onClick={() => { onChange(m); setOpen(false) }}
              className={`w-full text-left px-3 py-2 text-xs font-mono transition-colors ${
                m === value ? 'bg-accent/20 text-accent' : 'text-base-200 hover:bg-base-800'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const PERM_MODES = ['allow', 'ask', 'deny'] as const

function PermissionSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex rounded-lg overflow-hidden border border-base-700 bg-base-900">
      {PERM_MODES.map((m) => (
        <button
          key={m}
          onClick={() => onChange(m)}
          className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
            value === m
              ? m === 'allow' ? 'bg-emerald-500/20 text-emerald-400'
                : m === 'deny' ? 'bg-red-500/20 text-red-400'
                : 'bg-amber-500/20 text-amber-400'
              : 'text-base-500 hover:text-base-300 hover:bg-base-800'
          }`}
        >
          {m.charAt(0).toUpperCase() + m.slice(1)}
        </button>
      ))}
    </div>
  )
}

function renderTools(
  tools: ToolInfo[],
  config: SettingsData | null,
  updateToolPermission: (toolId: string, mode: string) => void,
) {
  const permissions = (config?.permissions ?? {}) as Record<string, unknown>

  return (
    <div className="space-y-2">
      <p className="text-xs text-base-500 mb-3">Set permission mode per tool. Denied tools won't be available to the agent.</p>
      {tools.map((t) => {
        const raw = permissions[t.id]
        const mode = typeof raw === 'string' ? raw : 'ask'
        return (
          <div key={t.id} className="flex items-center justify-between p-3 rounded-xl bg-base-800/50 border border-base-700">
            <div className="min-w-0 flex-1">
              <p className="text-sm text-base-100">{t.name}</p>
              <p className="text-xs text-base-500 truncate">{t.description}</p>
            </div>
            <PermissionSelect value={mode} onChange={(v) => updateToolPermission(t.id, v)} />
          </div>
        )
      })}
    </div>
  )
}

function MemorySettings({config,}: {config: SettingsData | null}) {

  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [allMemory, setAllMemory] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<'browser' | 'config'>('browser')

  const fetchAll = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/memory/list`)
      const data = await r.json()
      setAllMemory(data)
    } catch {}
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      return
    }
    setLoading(true)
    try {
      const r = await fetch(`${API_BASE}/api/memory/search?q=${encodeURIComponent(searchQuery)}`)
      const data = await r.json()
      setSearchResults(data)
    } catch {}
    setLoading(false)
  }

  const handleDelete = async (id: string) => {
    try {
      await fetch(`${API_BASE}/api/memory/${id}`, { method: 'DELETE' })
      setAllMemory(prev => prev.filter(m => m.id !== id))
      setSearchResults(prev => prev.filter(m => m.id !== id))
    } catch {}
  }

  const openFolder = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/memory/path`)
      const data = await r.json()
      if (data.path) {
        navigator.clipboard.writeText(data.path)
      }
    } catch {}
  }

  useEffect(() => {
    fetchAll()
  }, [])

  return (
    <div className="space-y-4">
      <p className="text-xs text-base-500">Long-term memory stores conversation summaries and learned facts using vector embeddings.</p>

      {/* Tabs */}
      <div className="flex gap-1 p-0.5 bg-base-800 rounded-lg">
        <button
          onClick={() => setTab('browser')}
          className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
            tab === 'browser' ? 'bg-base-700 text-base-100' : 'text-base-400 hover:text-base-200'
          }`}
        >
          Memory Browser
        </button>
        <button
          onClick={() => setTab('config')}
          className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
            tab === 'config' ? 'bg-base-700 text-base-100' : 'text-base-400 hover:text-base-200'
          }`}
        >
          Config
        </button>
      </div>

      {tab === 'browser' && (
        <div className="space-y-3">
          {/* Search */}
          <div className="flex gap-2">
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search memories..."
              className="flex-1 bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40"
            />
            <button
              onClick={handleSearch}
              disabled={loading}
              className="px-3 py-2 text-xs font-medium rounded-lg bg-base-700 text-base-200 hover:bg-base-600 transition-colors disabled:opacity-50"
            >
              {loading ? '...' : 'Search'}
            </button>
          </div>

          {/* Memory path */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-base-800/50 border border-base-700">
            <span className="text-[11px] text-base-400 font-mono">~/.cozmo/memory/</span>
            <button onClick={openFolder} className="text-[11px] text-accent hover:text-accent/80 transition-colors">
              Copy path
            </button>
          </div>

          {/* Results */}
          {searchResults.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[11px] text-base-400 font-medium">Search results ({searchResults.length})</p>
              {searchResults.map((item, i) => (
                <MemoryCard key={item.id || i} item={item} onDelete={handleDelete} />
              ))}
            </div>
          )}

          {/* All memories */}
          <div className="space-y-1.5">
            <p className="text-[11px] text-base-400 font-medium">All memories ({allMemory.length})</p>
            {allMemory.length === 0 && (
              <p className="text-xs text-base-500 py-4 text-center">No memories stored yet. Memories are created automatically from conversations.</p>
            )}
            {allMemory.slice(0, 50).map((item) => (
              <MemoryCard key={item.id} item={item} onDelete={handleDelete} />
            ))}
          </div>
        </div>
      )}

      {tab === 'config' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 rounded-xl bg-base-800/50 border border-base-700">
            <div>
              <p className="text-sm text-base-100">Max turns before summary</p>
              <p className="text-xs text-base-500">Conversation turns before memory is summarized</p>
            </div>
            <span className="text-sm font-mono text-base-200">{config?.memory?.max_turns_before_summary ?? 5}</span>
          </div>
          <div className="flex items-center justify-between p-3 rounded-xl bg-base-800/50 border border-base-700">
            <div>
              <p className="text-sm text-base-100">Max short-term pairs</p>
              <p className="text-xs text-base-500">Recent conversation pairs kept in context</p>
            </div>
            <span className="text-sm font-mono text-base-200">{config?.memory?.max_short_term_pairs ?? 10}</span>
          </div>
        </div>
      )}
    </div>
  )
}

function MemoryCard({ item, onDelete }: { item: any; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const text = item.text || ''
  const preview = text.length > 120 ? text.slice(0, 120) + '...' : text
  const meta = item.metadata || {}
  const distance = item.distance

  return (
    <div className="p-2.5 rounded-lg bg-base-800/30 border border-base-700/50 group">
      <div className="flex items-start justify-between gap-2">
        <div
          className="flex-1 min-w-0 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <p className="text-xs text-base-200 leading-relaxed whitespace-pre-wrap">
            {expanded ? text : preview}
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            {meta.timestamp && (
              <span className="text-[10px] text-base-500">{new Date(meta.timestamp).toLocaleDateString()}</span>
            )}
            {distance != null && (
              <span className="text-[10px] text-base-600">score: {(1 - distance).toFixed(2)}</span>
            )}
            {meta.turns && (
              <span className="text-[10px] text-base-600">{meta.turns} turns</span>
            )}
          </div>
        </div>
        <button
          onClick={() => onDelete(item.id)}
          className="p-1 rounded text-base-600 hover:text-err opacity-0 group-hover:opacity-100 transition-all"
          title="Delete memory"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  )
}

function SkillsSection({ skills, onRefresh, onCreateSkill, onClose }: {
  skills: Skill[]
  onRefresh: () => void
  onCreateSkill?: () => void
  onClose: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [writeOpen, setWriteOpen] = useState(false)
  const [writeName, setWriteName] = useState('')
  const [writeDesc, setWriteDesc] = useState('')
  const [writeContent, setWriteContent] = useState('')
  const [saving, setSaving] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const close = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node))
        setMenuOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menuOpen])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    await uploadSkill(file)
    onRefresh()
    setMenuOpen(false)
  }

  const handleWriteSubmit = async () => {
    if (!writeName.trim()) return
    setSaving(true)
    await createSkill({ name: writeName.trim(), description: writeDesc.trim(), content: writeContent })
    setSaving(false)
    setWriteOpen(false)
    setWriteName('')
    setWriteDesc('')
    setWriteContent('')
    onRefresh()
  }

  const handleDelete = async (name: string) => {
    await deleteSkill(name)
    onRefresh()
  }

  const handleCreateWithCozmo = () => {
    setMenuOpen(false)
    onClose()
    onCreateSkill?.()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-base-500">Skills extend Cozmo with reusable instructions.</p>
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(v => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent hover:bg-accent/90 text-white text-xs font-medium transition-colors"
          >
            <Plus size={14} /> Add
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 bg-base-850 border border-base-700 rounded-xl overflow-hidden shadow-panel min-w-[200px] z-20 py-1">
              <button
                onClick={() => { fileInputRef.current?.click() }}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 text-xs text-base-200 hover:bg-base-800 transition-colors"
              >
                <Upload size={14} /> Upload .md file
              </button>
              <button
                onClick={() => { setMenuOpen(false); setWriteOpen(true) }}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 text-xs text-base-200 hover:bg-base-800 transition-colors"
              >
                <Edit3 size={14} /> Write instructions
              </button>
              <div className="border-t border-base-700 my-1" />
              <button
                onClick={handleCreateWithCozmo}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 text-xs text-accent hover:bg-base-800 transition-colors"
              >
                <Sparkles size={14} /> Create with Cozmo
              </button>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.skill"
            className="hidden"
            onChange={handleUpload}
          />
        </div>
      </div>

      {writeOpen && (
        <div className="p-4 rounded-xl border border-base-700 bg-base-900 space-y-3">
          <input
            value={writeName}
            onChange={(e) => setWriteName(e.target.value)}
            placeholder="Skill name"
            className="w-full bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40"
          />
          <input
            value={writeDesc}
            onChange={(e) => setWriteDesc(e.target.value)}
            placeholder="Short description (optional)"
            className="w-full bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40"
          />
          <textarea
            value={writeContent}
            onChange={(e) => setWriteContent(e.target.value)}
            placeholder="Skill instructions in Markdown..."
            rows={8}
            className="w-full bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40 resize-y font-mono"
          />
          <div className="flex items-center gap-2 justify-end">
            <button
              onClick={() => setWriteOpen(false)}
              className="px-3 py-1.5 rounded-lg text-xs text-base-400 hover:text-base-200 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleWriteSubmit}
              disabled={saving || !writeName.trim()}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving...' : 'Save skill'}
            </button>
          </div>
        </div>
      )}

      {skills.length === 0 ? (
        <div className="flex items-center justify-center h-32 rounded-xl border-2 border-dashed border-base-700 text-base-500 text-sm">
          No skills installed yet
        </div>
      ) : (
        <div className="space-y-2">
          {skills.map((s) => (
            <div key={s.name} className="flex items-center gap-3 px-4 py-3 rounded-xl bg-base-800/50 border border-base-700">
              <Puzzle size={16} className="text-base-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-base-100 font-medium">{s.name}</p>
                {s.description && (
                  <p className="text-xs text-base-500 truncate">{s.description}</p>
                )}
              </div>
              {s.name !== 'skill-creator' && (
                <button
                  onClick={() => handleDelete(s.name)}
                  className="p-1.5 rounded-lg text-base-400 hover:text-err hover:bg-base-800 transition-colors"
                  title="Delete skill"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function formatTimeAgo(ms: number): string {
  const sec = Math.round(ms / 1000)
  if (sec < 60) return `${sec}s ago`
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  return `${hr}h ago`
}

const CAPABILITY_DEFS: Record<string, { label: string; icon: React.ElementType }> = {
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

function ConnectorsSection({
  config,
  setConfig,
  setDirty,
}: {
  config: SettingsData | null
  setConfig: (c: SettingsData) => void
  setDirty: (d: boolean) => void
}) {
  const [addOpen, setAddOpen] = useState(false)
  const [addName, setAddName] = useState('')
  const [addCommand, setAddCommand] = useState('')
  const [addArgs, setAddArgs] = useState('')
  const [addEnv, setAddEnv] = useState<string>('')
  const [testResult, setTestResult] = useState<string | null>(null)
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [catalog, setCatalog] = useState<McpCatalogEntry[]>([])
  const [catalogSearch, setCatalogSearch] = useState('')
  const [selectedCatalog, setSelectedCatalog] = useState<McpCatalogEntry | null>(null)
  const [catalogEnvVars, setCatalogEnvVars] = useState<Record<string, string>>({})
  const [serverStatus, setServerStatus] = useState<McpStatusResponse | null>(null)
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({})
  const [detailName, setDetailName] = useState<string | null>(null)
  const [serverDetail, setServerDetail] = useState<McpServerDetail | null>(null)

  const devMode = !!(config as any)?.devMode
  const servers = (config?.mcp as { servers?: Record<string, { command: string; args?: string[]; env?: Record<string, string>; permissions?: Record<string, boolean> }> })?.servers ?? {}
  const entries = Object.entries(servers)

  // Poll status every 5s
  useEffect(() => {
    const poll = async () => {
      setServerStatus(await fetchMcpStatus())
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [config])

  // ── capabilities from catalog + configured servers ──────────
  const catalogByName = useMemo(() => {
    const map: Record<string, McpCatalogEntry> = {}
    for (const e of catalog) {
      map[e.display_name] = e
      map[e.id] = e
    }
    return map
  }, [catalog])

  const activeCapabilities = useMemo(() => {
    const caps = new Set<string>()
    for (const name of Object.keys(servers)) {
      const entry = catalogByName[name]
      if (entry) {
        for (const c of entry.capabilities) caps.add(c)
      }
    }
    return caps
  }, [servers, catalogByName])

  const serverCapabilities = useMemo(() => {
    const map: Record<string, string[]> = {}
    for (const name of Object.keys(servers)) {
      const entry = catalogByName[name]
      map[name] = entry ? [...entry.capabilities] : []
    }
    return map
  }, [servers, catalogByName])

  // ── handlers ────────────────────────────────────────────────
  const openCatalog = async () => {
    const data = await fetchMcpCatalog()
    setCatalog(data)
    setCatalogSearch('')
    setCatalogOpen(true)
  }

  const pickCatalog = (entry: McpCatalogEntry) => {
    setSelectedCatalog(entry)
    setAddName(entry.display_name || entry.id)
    setAddCommand(entry.command)
    setAddArgs(entry.args.join(', '))
    setCatalogOpen(false)
    const init: Record<string, string> = {}
    for (const ev of entry.env_vars) {
      init[ev.key] = ev.default || ''
    }
    setCatalogEnvVars(init)
  }

  const clearForm = () => {
    setAddName('')
    setAddCommand('')
    setAddArgs('')
    setAddEnv('')
    setSelectedCatalog(null)
    setCatalogEnvVars({})
  }

  const handleAdd = () => {
    if (!addName.trim() || !addCommand.trim() || !config) return
    const args = addArgs.trim() ? addArgs.split(',').map((s) => s.trim()).filter(Boolean) : undefined
    let env: Record<string, string> | undefined
    if (selectedCatalog && Object.keys(catalogEnvVars).length > 0) {
      env = { ...catalogEnvVars }
    }
    if (addEnv.trim()) {
      if (!env) env = {}
      for (const pair of addEnv.split(',')) {
        const eq = pair.indexOf('=')
        if (eq > 0) {
          env[pair.slice(0, eq).trim()] = pair.slice(eq + 1).trim()
        }
      }
    }
    if (env && !Object.keys(env).length) env = undefined
    const mcp = (config.mcp as any) ?? { servers: {} }
    setConfig({
      ...config,
      mcp: { ...mcp, servers: { ...mcp.servers, [addName.trim()]: { command: addCommand.trim(), args, env } } },
    })
    setDirty(true)
    setAddOpen(false)
    clearForm()
  }

  const handleDelete = (name: string) => {
    if (!config) return
    const mcp = (config.mcp as any) ?? { servers: {} }
    const { [name]: _, ...rest } = mcp.servers
    setConfig({ ...config, mcp: { ...mcp, servers: rest } })
    setDirty(true)
  }

  const handleTest = async (name: string) => {
    setTestResult(null)
    try {
      const r = await fetch(`${API_BASE}/api/mcp/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const data = await r.json()
      setTestResult(data.ok ? `Connected — ${data.tools ?? 0} tools` : `Failed: ${data.error}`)
    } catch {
      setTestResult('Connection error')
    }
    setTimeout(() => setTestResult(null), 4000)
  }

  const toggleTools = (name: string) => {
    setExpandedTools((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  const openDetail = async (name: string) => {
    setDetailName(name)
    setServerDetail(await fetchServerDetail(name))
  }

  const closeDetail = () => {
    setDetailName(null)
    setServerDetail(null)
  }

  const setPermission = (serverName: string, permKey: string, value: boolean) => {
    if (!config) return
    const mcp = (config.mcp as any) ?? { servers: {} }
    const server = mcp.servers[serverName] ?? {}
    const perms = { ...server.permissions, [permKey]: value }
    setConfig({
      ...config,
      mcp: { ...mcp, servers: { ...mcp.servers, [serverName]: { ...server, permissions: perms } } },
    })
    setDirty(true)
  }

  const PERMISSION_DEFS: Record<string, { label: string; key: string }[]> = {
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

  // ── catalog overlay state ───────────────────────────────────
  const filteredCatalog = catalogSearch
    ? catalog.filter(
        (e) =>
          e.display_name.toLowerCase().includes(catalogSearch.toLowerCase()) ||
          e.description.toLowerCase().includes(catalogSearch.toLowerCase()) ||
          e.category.toLowerCase().includes(catalogSearch.toLowerCase())
      )
    : catalog

  const catalogGroups: Record<string, McpCatalogEntry[]> = {}
  for (const e of filteredCatalog) {
    if (!catalogGroups[e.category]) catalogGroups[e.category] = []
    catalogGroups[e.category].push(e)
  }

  // ── render ──────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-base-500">MCP (Model Context Protocol) servers extend Cozmo with external tools like databases, APIs, and file systems.</p>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={openCatalog} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-accent/40 text-accent hover:bg-accent/10 text-xs font-medium transition-colors">
            <Store size={14} /> Browse
          </button>
          <button onClick={() => { clearForm(); setAddOpen(true) }} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent hover:bg-accent/90 text-white text-xs font-medium transition-colors">
            <Plug size={14} /> Add
          </button>
        </div>
      </div>

      {/* ── Capabilities summary ── */}
      {entries.length > 0 && (
        <div className="p-4 rounded-xl border border-base-700/60 bg-base-900/30">
          <div className="flex items-center gap-2 mb-3">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-base-400">Capabilities</p>
            <span className="text-[10px] text-base-500">({activeCapabilities.size} enabled)</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(CAPABILITY_DEFS).map(([key, def]) => {
              const enabled = activeCapabilities.has(key)
              const Icon = def.icon
              return (
                <span
                  key={key}
                  className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-colors ${
                    enabled
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-base-800 text-base-500 border border-base-700/50'
                  }`}
                >
                  <Icon size={12} /> {def.label}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Browse catalog (app-store grid) ── */}
      {catalogOpen && (
        <div className="p-4 rounded-xl border border-base-700 bg-base-900">
          <div className="flex items-center gap-2 mb-4">
            <Store size={16} className="text-accent shrink-0" />
            <p className="text-sm font-semibold text-base-100">Connector Store</p>
            <div className="flex-1" />
            <div className="relative max-w-60">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-base-500" />
              <input value={catalogSearch} onChange={(e) => setCatalogSearch(e.target.value)} placeholder="Search connectors..." className="w-full bg-base-800 border border-base-700 rounded-lg pl-7 pr-3 py-1.5 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40" autoFocus />
            </div>
            <button onClick={() => { setCatalogOpen(false); setCatalogSearch('') }} className="p-1.5 rounded-lg text-base-400 hover:text-base-200 hover:bg-base-800 transition-colors"><X size={15} /></button>
          </div>

          {filteredCatalog.length === 0 ? (
            <p className="text-xs text-base-500 text-center py-6">No connectors match your search</p>
          ) : (
            <div className="space-y-5 max-h-96 overflow-y-auto pr-1">
              {Object.entries(catalogGroups).map(([category, entries]) => (
                <div key={category}>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-base-500 mb-2.5">{category}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {entries.map((e) => {
                      const needsToken = e.env_vars.some(ev => !ev.optional)
                      const needsNode = e.command === 'npx'
                      return (
                        <div key={e.id} className="flex flex-col p-3.5 rounded-xl border border-base-700/60 bg-base-800/40 hover:border-accent/30 hover:bg-base-800/70 transition-colors group">
                          <div className="flex items-start gap-2.5 mb-2">
                            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                              <Puzzle size={16} className="text-accent" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-base-100 font-medium">{e.display_name}</p>
                              <p className="text-[11px] text-base-500 line-clamp-2">{e.description}</p>
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-1 mb-2.5">
                            {e.capabilities.map((c) => {
                              const cd = CAPABILITY_DEFS[c]
                              if (!cd) return null
                              const CI = cd.icon
                              return (
                                <span key={c} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-base-800 text-[9px] text-base-400 border border-base-700/40">
                                  <CI size={10} />{cd.label}
                                </span>
                              )
                            })}
                          </div>
                          <div className="flex flex-wrap gap-1.5 mb-3">
                            {needsNode && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 text-[9px] text-amber-400 border border-amber-500/20">
                                Node
                              </span>
                            )}
                            {needsToken && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500/10 text-[9px] text-red-400 border border-red-500/20">
                                Token
                              </span>
                            )}
                            {!needsNode && !needsToken && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-[9px] text-emerald-400 border border-emerald-500/20">
                                Ready
                              </span>
                            )}
                          </div>
                          <button
                            onClick={() => pickCatalog(e)}
                            className="w-full py-1.5 rounded-lg text-xs font-medium bg-accent/80 hover:bg-accent text-white transition-colors mt-auto opacity-0 group-hover:opacity-100 focus:opacity-100"
                          >
                            Install
                          </button>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Add server form ── */}
      {addOpen && (
        <div className="p-4 rounded-xl border border-base-700 bg-base-900 space-y-3">
          {selectedCatalog && <p className="text-[11px] text-accent font-medium">Pre-filled from catalog: {selectedCatalog.display_name}</p>}
          <input value={addName} onChange={(e) => setAddName(e.target.value)} placeholder="Server name (e.g. Filesystem)" className="w-full bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40" />
          <input value={addCommand} onChange={(e) => setAddCommand(e.target.value)} placeholder="Command (e.g. npx)" className="w-full bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40 font-mono" />
          <input value={addArgs} onChange={(e) => setAddArgs(e.target.value)} placeholder="Args (comma-separated, e.g. -y, @modelcontextprotocol/server-filesystem)" className="w-full bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40 font-mono" />
          {selectedCatalog && selectedCatalog.env_vars.length > 0 && (
            <div className="space-y-2">
              <p className="text-[11px] font-medium text-base-400">Environment variables</p>
              {selectedCatalog.env_vars.map((ev) => (
                <div key={ev.key}>
                  <label className="block text-[10px] text-base-500 mb-0.5">{ev.label}</label>
                  <input value={catalogEnvVars[ev.key] ?? ''} onChange={(e) => setCatalogEnvVars({ ...catalogEnvVars, [ev.key]: e.target.value })} placeholder={ev.optional ? `(optional) ${ev.key}` : ev.key} type={ev.secret ? 'password' : 'text'} className="w-full bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40 font-mono" />
                </div>
              ))}
            </div>
          )}
          {!selectedCatalog && <input value={addEnv} onChange={(e) => setAddEnv(e.target.value)} placeholder="Env vars (comma-separated, e.g. KEY=value, FOO=bar)" className="w-full bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 placeholder:text-base-500 outline-none focus:border-accent/40 font-mono" />}
          <div className="flex items-center gap-2 justify-end">
            <button onClick={() => { setAddOpen(false); clearForm() }} className="px-3 py-1.5 rounded-lg text-xs text-base-400 hover:text-base-200 transition-colors">Cancel</button>
            <button onClick={handleAdd} disabled={!addName.trim() || !addCommand.trim()} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-50 transition-colors">Add server</button>
          </div>
        </div>
      )}

      {testResult && (
        <div className={`px-3 py-2 rounded-lg text-xs ${testResult.startsWith('Connected') ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {testResult}
        </div>
      )}

      {entries.length === 0 && !addOpen && !catalogOpen ? (
        <div className="flex flex-col items-center justify-center h-32 rounded-xl border-2 border-dashed border-base-700 text-base-500 text-sm">
          No MCP servers configured
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map(([name, cfg]) => {
            const st = serverStatus?.[name]
            const caps = serverCapabilities[name] ?? []
            const entry = catalogByName[name]
            const desc = entry?.description ?? `${cfg.command}${cfg.args ? ' ' + cfg.args.join(' ') : ''}`
            const needsToken = entry && entry.env_vars.some(ev => !ev.optional) && (!cfg.env || Object.keys(cfg.env).length === 0)
            return (
              <div key={name} className="rounded-xl bg-base-800/40 border border-base-700 overflow-hidden group">
                <div className="px-4 py-3.5">
                  {/* Row 1: status dot + name + status badge */}
                  <div className="flex items-start justify-between mb-1">
                    <div className="flex items-center gap-2.5 min-w-0">
                      {st?.status === 'ok' ? (
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shrink-0 mt-0.5" title="Connected" />
                      ) : st?.status === 'error' ? (
                        <span className="w-2.5 h-2.5 rounded-full bg-red-400 shrink-0 mt-0.5" title="Error" />
                      ) : (
                        <span className="w-2.5 h-2.5 rounded-full bg-base-600 shrink-0 mt-0.5" title="Disconnected" />
                      )}
                      <p className="text-sm text-base-100 font-semibold truncate">{name}</p>
                    </div>
                    {needsToken ? (
                      <span className="shrink-0 text-[10px] font-medium text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">Needs Token</span>
                    ) : st?.status === 'ok' ? (
                      <span className="shrink-0 text-[10px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">Connected</span>
                    ) : st?.status === 'error' ? (
                      <span className="shrink-0 text-[10px] font-medium text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full border border-red-500/20">Error</span>
                    ) : (
                      <span className="shrink-0 text-[10px] font-medium text-base-500 bg-base-800 px-2 py-0.5 rounded-full border border-base-600">Disconnected</span>
                    )}
                  </div>
                  {/* Row 2: description */}
                  <p className="text-[11px] text-base-500 line-clamp-1 ml-[22px] mb-1.5">{desc}</p>
                  {/* Row 3: capabilities + tool count */}
                  <div className="flex items-center gap-1.5 flex-wrap ml-[22px]">
                    {caps.map((c) => {
                      const cd = CAPABILITY_DEFS[c]
                      if (!cd) return null
                      const CI = cd.icon
                      return (
                        <span key={c} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-base-900/60 text-[9px] text-base-400 border border-base-700/40">
                          <CI size={10} />{cd.label}
                        </span>
                      )
                    })}
                    {st && st.tools.length > 0 && (
                      <button onClick={() => toggleTools(name)} className="flex items-center gap-0.5 text-[10px] text-base-500 hover:text-accent transition-colors ml-auto">
                        <ChevronDown size={11} className={`transition-transform ${expandedTools[name] ? 'rotate-180' : ''}`} />
                        {st.tools.length} tool{st.tools.length > 1 ? 's' : ''}
                      </button>
                    )}
                  </div>
                </div>
                {/* Row 4: actions bar */}
                <div className="flex items-center justify-end gap-1 px-4 py-1.5 bg-base-900/30 border-t border-base-700/40 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => openDetail(name)} className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-base-400 hover:text-accent hover:bg-base-800 transition-colors">
                    <Settings size={11} /> Configure
                  </button>
                  <button onClick={() => handleTest(name)} className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-base-400 hover:text-accent hover:bg-base-800 transition-colors">
                    <Power size={11} /> Test
                  </button>
                  <button onClick={() => handleDelete(name)} className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-base-400 hover:text-err hover:bg-base-800 transition-colors">
                    <Trash2 size={11} /> Remove
                  </button>
                </div>
                {/* expanded tool list */}
                {expandedTools[name] && st && st.tools.length > 0 && (
                  <div className="px-4 pb-3 space-y-0.5">
                    {st.tools.map((t) => (
                      <div key={t.name} className="px-3 py-1.5 rounded-lg bg-base-900/50 border border-base-700/50">
                        <p className="text-[11px] text-base-200 font-mono">{t.name}</p>
                        {t.description && <p className="text-[10px] text-base-500 line-clamp-1">{t.description}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
      {entries.length > 0 && (
        <button onClick={openCatalog} className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border-2 border-dashed border-base-700 hover:border-accent/40 text-base-500 hover:text-accent text-xs font-medium transition-colors">
          <PackagePlus size={16} /> Install More Connectors
        </button>
      )}

      {/* ── Connector Detail Panel ── */}
      {detailName && serverDetail && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/40" onClick={closeDetail} />
          <div className="relative w-[26rem] max-w-full h-full bg-base-900 border-l border-base-700 overflow-y-auto">
            <div className="p-5 space-y-5">
              {/* Header */}
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="text-base font-semibold text-base-100">{serverDetail.name}</h2>
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                      serverDetail.status === 'ok' ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20' :
                      serverDetail.status === 'error' ? 'text-red-400 bg-red-500/10 border border-red-500/20' :
                      'text-base-400 bg-base-800 border border-base-600'
                    }`}>
                      {serverDetail.status === 'ok' ? 'Connected' :
                       serverDetail.status === 'error' ? 'Error' :
                       'Disconnected'}
                    </span>
                  </div>
                  {serverDetail.description && (
                    <p className="text-xs text-base-500">{serverDetail.description}</p>
                  )}
                </div>
                <button onClick={closeDetail} className="p-1.5 rounded-lg text-base-400 hover:text-base-200 hover:bg-base-800 transition-colors shrink-0">
                  <X size={16} />
                </button>
              </div>

              {/* Capabilities */}
              {serverDetail.capabilities.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-base-500 mb-2">Capabilities</p>
                  <div className="flex flex-wrap gap-1.5">
                    {serverDetail.capabilities.map((c: string) => {
                      const cd = CAPABILITY_DEFS[c]
                      if (!cd) return null
                      const CI = cd.icon
                      return (
                        <span key={c} className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20">
                          <CI size={12} /> {cd.label}
                        </span>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Tools */}
              {serverDetail.tools.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-base-500 mb-2">{serverDetail.tools.length} Tool{serverDetail.tools.length > 1 ? 's' : ''}</p>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {serverDetail.tools.map((t: McpServerTool) => (
                      <div key={t.name} className="px-3 py-2 rounded-lg bg-base-800/50 border border-base-700/50">
                        <p className="text-[11px] text-base-200 font-mono">{t.name}</p>
                        {t.description && <p className="text-[10px] text-base-500 line-clamp-1">{t.description}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {serverDetail.capabilities.length > 0 && devMode && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-base-500 mb-2">Permissions</p>
                  <div className="space-y-1">
                    {(serverDetail.capabilities.flatMap((c: string) => PERMISSION_DEFS[c] ?? PERMISSION_DEFS._default).filter((p, i, a) => a.findIndex((x) => x.key === p.key) === i)).map((perm) => {
                      const currentPerms = servers[serverDetail.name]?.permissions ?? {}
                      const checked = currentPerms[perm.key] !== false
                      return (
                        <label key={perm.key} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-base-800/30 border border-base-700/50 cursor-pointer hover:bg-base-800/50 transition-colors">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => setPermission(serverDetail.name, perm.key, !checked)}
                            className="accent-accent w-3.5 h-3.5 rounded"
                          />
                          <span className="text-[11px] text-base-300">{perm.label}</span>
                        </label>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Configuration */}
              {serverDetail.config && Object.keys(serverDetail.config.env ?? {}).length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-base-500 mb-2">Configuration</p>
                  <div className="space-y-2">
                    {(Object.entries(serverDetail.config.env) as [string, string][]).map(([key, val]) => (
                      <div key={key}>
                        <label className="block text-[10px] text-base-500 mb-0.5">{key}</label>
                        <input value={val} readOnly type="password" className="w-full bg-base-800 border border-base-700 rounded-lg px-3 py-2 text-xs text-base-200 font-mono outline-none" />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Diagnostics */}
              {serverDetail.diagnostics && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-base-500 mb-2">Diagnostics</p>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: 'Transport', value: serverDetail.diagnostics.transport },
                      { label: 'Response Time', value: serverDetail.diagnostics.response_time_ms != null ? `${serverDetail.diagnostics.response_time_ms}ms` : 'N/A' },
                      { label: 'Startup', value: serverDetail.diagnostics.startup_time_ms != null ? formatTimeAgo(serverDetail.diagnostics.startup_time_ms) : 'N/A' },
                      { label: 'Status', value: serverDetail.status === 'ok' ? 'Healthy' : serverDetail.status === 'error' ? 'Error' : 'Offline' },
                    ].map((d) => (
                      <div key={d.label} className="px-3 py-2 rounded-lg bg-base-800/30 border border-base-700/50">
                        <p className="text-[9px] text-base-500">{d.label}</p>
                        <p className="text-xs text-base-200 font-medium">{d.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {devMode && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-base-500 mb-2">Advanced</p>
                  <div className="space-y-2">
                    <div className="px-3 py-2 rounded-lg bg-base-800/30 border border-base-700/50">
                      <p className="text-[9px] text-base-500">Command</p>
                      <p className="text-[11px] text-base-200 font-mono">{serverDetail.config?.command ?? 'N/A'}</p>
                    </div>
                    {serverDetail.config?.args && serverDetail.config.args.length > 0 && (
                      <div className="px-3 py-2 rounded-lg bg-base-800/30 border border-base-700/50">
                        <p className="text-[9px] text-base-500">Args</p>
                        <p className="text-[11px] text-base-200 font-mono">{serverDetail.config.args.join(' ')}</p>
                      </div>
                    )}
                    <div className="px-3 py-2 rounded-lg bg-base-800/30 border border-base-700/50">
                      <p className="text-[9px] text-base-500">Transport</p>
                      <p className="text-[11px] text-base-200 font-mono">{serverDetail.diagnostics?.transport ?? 'stdio'}</p>
                    </div>
                    <details className="group">
                      <summary className="text-[10px] text-base-500 cursor-pointer hover:text-base-300 transition-colors select-none">Raw Config JSON</summary>
                      <pre className="mt-2 p-3 rounded-lg bg-base-950 border border-base-700/50 text-[10px] text-base-400 font-mono overflow-x-auto max-h-40 overflow-y-auto">{JSON.stringify(serverDetail.config, null, 2)}</pre>
                    </details>
                    <details className="group">
                      <summary className="text-[10px] text-base-500 cursor-pointer hover:text-base-300 transition-colors select-none">Raw Diagnostics Data</summary>
                      <pre className="mt-2 p-3 rounded-lg bg-base-950 border border-base-700/50 text-[10px] text-base-400 font-mono overflow-x-auto max-h-40 overflow-y-auto">{JSON.stringify(serverDetail.diagnostics, null, 2)}</pre>
                    </details>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2 pt-2">
                <button
                  onClick={() => { handleDelete(serverDetail.name); closeDetail() }}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/30 transition-colors"
                >
                  <Trash2 size={13} /> Remove Connector
                </button>
                <button onClick={() => handleTest(serverDetail.name)} className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-base-400 hover:text-base-200 hover:bg-base-800 border border-base-700 transition-colors">
                  <Power size={13} /> Test Connection
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function renderGeneral(
  config: SettingsData | null,
  setConfig: (c: SettingsData) => void,
  lightweight: boolean,
  setLightweight: (v: boolean) => void,
  setDirty: (d: boolean) => void,
) {
  const devMode = !!(config as any)?.devMode
  const toggleDev = () => {
    if (!config) return
    setConfig({ ...config, devMode: !devMode } as SettingsData)
    setDirty(true)
  }
  const toggleLight = () => {
    setLightweight(!lightweight)
    setDirty(true)
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-base-500">General Cozmo settings.</p>
      <div className="space-y-2">
        <div className="flex items-center justify-between p-3 rounded-xl bg-base-800/50 border border-base-700">
          <div>
            <p className="text-sm text-base-100">Lightweight Mode</p>
            <p className="text-xs text-base-500">Use openbmb/minicpm5 for all roles. Lowers RAM usage.</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={lightweight}
            onClick={toggleLight}
            className={`relative inline-flex h-5 w-10 shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
              lightweight ? 'bg-accent' : 'bg-base-700'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-4 w-4 translate-x-0 rounded-full bg-white shadow ring-0 transition-transform duration-200 ${
                lightweight ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
        <div className="flex items-center justify-between p-3 rounded-xl bg-base-800/50 border border-base-700">
          <div>
            <p className="text-sm text-base-100">Developer Mode</p>
            <p className="text-xs text-base-500">Show raw config, transport, and advanced server details in connectors.</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={devMode}
            onClick={toggleDev}
            className={`relative inline-flex h-5 w-10 shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
              devMode ? 'bg-accent' : 'bg-base-700'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-4 w-4 translate-x-0 rounded-full bg-white shadow ring-0 transition-transform duration-200 ${
                devMode ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
        <div className="flex items-center justify-between p-3 rounded-xl bg-base-800/50 border border-base-700">
          <p className="text-sm text-base-100">Version</p>
          <span className="text-xs text-base-500 font-mono">0.1.0</span>
        </div>
      </div>
    </div>
  )
}