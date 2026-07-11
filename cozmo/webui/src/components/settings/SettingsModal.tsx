import { useState, useEffect, useMemo, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Search, Cpu, Brain, Wrench, Puzzle, Cable, Settings, Plus, Trash2, ChevronDown } from 'lucide-react'
import { fetchTools } from '@/services/cozmo'

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

type SectionId = 'models' | 'tools' | 'memory' | 'skills' | 'connectors' | 'general'

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
}

export function SettingsModal({ open, onClose }: Props) {
  const [section, setSection] = useState<SectionId>('models')
  const [search, setSearch] = useState('')
  const [config, setConfig] = useState<SettingsData | null>(null)
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [dirty, setDirty] = useState(false)
  const [lightweight, setLightweight] = useState(false)
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    fetchConfig().then((cfg) => {
      setConfig(cfg)
      setLightweight(!!(cfg as any)?.runtime?.lightweight_mode)
    }).catch(() => {})
    fetchOllamaModels().then(setOllamaModels).catch(() => {})
    fetchTools()
      .then(setTools)
      .catch(() => {})
  }, [open])

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
                {section === 'memory' && renderMemory(config)}
                {section === 'skills' && renderSkills()}
                {section === 'connectors' && renderConnectors(config)}
                {section === 'general' && renderGeneral(config, lightweight, setLightweight, setDirty)}
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
              value={String(config.models?.[role] ?? '')}
              models={ollamaModels}
              onChange={(v) => updateModel(role, v)}
            />
          </div>
        ))}
      </div>
      <div className="border-t border-base-700 pt-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm text-base-200 font-medium">Custom Presets</p>
          <button
            onClick={addCustom}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg bg-base-800 text-base-300 hover:bg-base-700 hover:text-base-100 transition-colors"
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
                className="flex-1 bg-base-900 border border-base-700 rounded-lg px-2.5 py-1.5 text-xs text-base-200 outline-none focus:border-accent/40"
                placeholder="Preset name"
              />
              <ModelSelect
                value={model}
                models={ollamaModels}
                onChange={(v) => updateCustomModel(key, v)}
              />
              <button onClick={() => removeCustom(key)} className="p-1 rounded text-base-500 hover:text-err transition-colors">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ModelSelect({ value, models, onChange }: { value: string; models: string[]; onChange: (v: string) => void }) {
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
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 w-48 bg-base-900 border border-base-700 rounded-lg px-2.5 py-1.5 text-xs text-base-200 font-mono outline-none hover:border-accent/40 transition-colors"
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

function renderMemory(config: SettingsData | null) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-base-500">Configure long-term memory behavior.</p>
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
    </div>
  )
}

function renderSkills() {
  return (
    <div className="space-y-4">
      <p className="text-xs text-base-500">Skills extend Cozmo with reusable instructions. Create with skill-creator.</p>
      <div className="flex items-center justify-center h-32 rounded-xl border-2 border-dashed border-base-700 text-base-500 text-sm">
        No skills installed yet
      </div>
    </div>
  )
}

function renderConnectors(config: SettingsData | null) {
  const servers = (config?.mcp as { servers?: Record<string, { command: string; args?: string[] }> })?.servers ?? {}
  const entries = Object.entries(servers)

  return (
    <div className="space-y-4">
      <p className="text-xs text-base-500">MCP (Model Context Protocol) servers extend Cozmo with external tools like databases, APIs, and file systems.</p>
      {entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-32 rounded-xl border-2 border-dashed border-base-700 text-base-500 text-sm">
          No MCP servers connected
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map(([name, cfg]) => (
            <div key={name} className="p-3 rounded-xl bg-base-800/50 border border-base-700">
              <p className="text-sm text-base-100 font-medium">{name}</p>
              <p className="text-xs text-base-500 font-mono">{cfg.command}{cfg.args ? ' ' + cfg.args.join(' ') : ''}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function renderGeneral(
  config: SettingsData | null,
  lightweight: boolean,
  setLightweight: (v: boolean) => void,
  setDirty: (d: boolean) => void,
) {
  const toggle = () => {
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
            onClick={toggle}
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
          <p className="text-sm text-base-100">Version</p>
          <span className="text-xs text-base-500 font-mono">0.1.0</span>
        </div>
      </div>
    </div>
  )
}