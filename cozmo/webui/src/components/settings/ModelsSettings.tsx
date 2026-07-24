import { Plus, Trash2, Server, KeyRound, Brain } from 'lucide-react'
import { BUILTIN_ROLES, PRESET_META } from './constants'
import type { SettingsData } from './types'

interface Props {
  config: SettingsData | null
  ollamaModels: string[]
  availableModels: { name: string; provider: string }[]
  setConfig: (c: SettingsData) => void
  setDirty: (d: boolean) => void
  lightweight: boolean
}

const allModelOptions = (models: { name: string; provider: string }[]): string[] => {
  const seen = new Set<string>()
  const out: string[] = []
  for (const m of models) {
    if (!seen.has(m.name)) {
      seen.add(m.name)
      out.push(m.name)
    }
  }
  return out
}

export function ModelsSettings({ config, ollamaModels, availableModels, setConfig, setDirty, lightweight }: Props) {
  if (!config) return null

  const llm = (config as any).llm || {}
  const defaultModel = llm.default_model || ''
  const llmRoles: Record<string, any> = llm.roles || {}

  const modelOptions = allModelOptions(availableModels)
  const modelSet = new Set(modelOptions)

  const setDefaultModel = (model: string) => {
    setConfig({ ...config, llm: { ...llm, default_model: model } } as any)
    setDirty(true)
  }

  const setRoleModel = (role: string, model: string) => {
    const newRoles = { ...llmRoles }
    if (model) {
      newRoles[role] = { model }
    } else {
      delete newRoles[role]
    }
    setConfig({ ...config, llm: { ...llm, roles: newRoles }, models: { ...config.models, [role]: model } } as any)
    setDirty(true)
  }

  const setOllamaUrl = (url: string) => {
    setConfig({
      ...config,
      ollama: { ...(config.ollama || {}), url },
      providers: { ...(config.providers || {}), default: config.providers?.default || 'ollama', ollama: { ...((config.providers as any)?.ollama || {}), url } },
    } as any)
    setDirty(true)
  }

  const setOpenaiKeyEnv = (env: string) => {
    setConfig({
      ...config,
      providers: { ...(config.providers || {}), default: config.providers?.default || 'ollama', openai: { api_key_env: env } },
    } as any)
    setDirty(true)
  }

  const setDefaultProvider = (provider: string) => {
    setConfig({
      ...config,
      providers: { ...(config.providers || {}), default: provider },
    } as any)
    setDirty(true)
  }

  const providers = (config as any).providers || {}
  const ollamaUrl = providers.ollama?.url || config.ollama?.url || 'http://localhost:11434'
  const openaiKeyEnv = providers.openai?.api_key_env || 'OPENAI_API_KEY'
  const ollamaReasoning = providers.ollama?.reasoning !== false

  const setOllamaReasoning = (enabled: boolean) => {
    setConfig({
      ...config,
      providers: { ...(config.providers || {}), default: config.providers?.default || 'ollama', ollama: { ...((config.providers as any)?.ollama || {}), url: ollamaUrl, reasoning: enabled } },
    } as any)
    setDirty(true)
  }

  return (
    <div className="space-y-6">
      {/* Default Model */}
      <div>
        <p className="text-sm text-base-100 font-medium mb-1">Default Model</p>
        <p className="text-xs text-base-500 mb-2">Used for all roles unless overridden below.</p>
        <select
          value={defaultModel}
          onChange={(e) => setDefaultModel(e.target.value)}
          disabled={lightweight}
          className="w-full bg-base-900 border border-base-700 rounded-lg px-3 py-2 text-sm text-base-200 outline-none focus:border-accent/40 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <option value="">Select a model...</option>
          {modelOptions.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
          {defaultModel && !modelSet.has(defaultModel) && (
            <option value={defaultModel}>{defaultModel} (not found)</option>
          )}
        </select>
      </div>

      {/* Providers */}
      <div>
        <p className="text-sm text-base-100 font-medium mb-1">Providers</p>
        <p className="text-xs text-base-500 mb-2">Configure model backends.</p>
        <div className="space-y-2">
          {/* Default provider selector */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-base-800/50 border border-base-700">
            <span className="text-sm text-base-200">Default Provider</span>
            <select
              value={providers.default || 'ollama'}
              onChange={(e) => setDefaultProvider(e.target.value)}
              className="bg-base-900 border border-base-700 rounded-lg px-2.5 py-1.5 text-xs text-base-200 outline-none focus:border-accent/40"
            >
              {Object.keys(providers).filter(k => k !== 'default').map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
              {!Object.keys(providers).some(k => k !== 'default') && (
                <option value="ollama">ollama</option>
              )}
            </select>
          </div>

          {/* Ollama */}
          <div className="space-y-2 p-3 rounded-xl bg-base-800/50 border border-base-700">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server size={14} className="text-base-500" />
                <span className="text-sm text-base-200">Ollama</span>
              </div>
              <input
                value={ollamaUrl}
                onChange={(e) => setOllamaUrl(e.target.value)}
                placeholder="http://localhost:11434"
                className="w-56 bg-base-900 border border-base-700 rounded-lg px-2.5 py-1.5 text-xs text-base-200 font-mono outline-none focus:border-accent/40"
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain size={14} className="text-base-500" />
                <span className="text-xs text-base-400">Reasoning (thinking tokens)</span>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={ollamaReasoning}
                onClick={() => setOllamaReasoning(!ollamaReasoning)}
                className={`relative inline-flex h-4 w-8 shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 ${
                  ollamaReasoning ? 'bg-accent' : 'bg-base-700'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-3 w-3 translate-x-0 rounded-full bg-white shadow ring-0 transition-transform duration-200 ${
                    ollamaReasoning ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* OpenAI */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-base-800/50 border border-base-700">
            <div className="flex items-center gap-2">
              <KeyRound size={14} className="text-base-500" />
              <span className="text-sm text-base-200">OpenAI</span>
            </div>
            <input
              value={openaiKeyEnv}
              onChange={(e) => setOpenaiKeyEnv(e.target.value)}
              placeholder="OPENAI_API_KEY"
              className="w-56 bg-base-900 border border-base-700 rounded-lg px-2.5 py-1.5 text-xs text-base-200 font-mono outline-none focus:border-accent/40"
            />
          </div>
        </div>
      </div>

      {/* Per-Role Overrides */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <p className="text-sm text-base-100 font-medium">Per-Role Overrides</p>
          <span className="text-xs text-base-500">Optional — leave as "Use default" to inherit</span>
        </div>
        <p className="text-xs text-base-500 mb-2">Pin specific models to roles when needed.</p>
        <div className="space-y-1.5">
          {BUILTIN_ROLES.map((role) => {
            const roleSpec = llmRoles[role]
            const currentModel = roleSpec?.model || roleSpec || ''
            return (
              <div key={role} className="flex items-center justify-between p-2.5 rounded-xl bg-base-800/30 border border-base-700">
                <div>
                  <p className="text-sm text-base-100">{PRESET_META[role]?.label ?? role}</p>
                  <p className="text-xs text-base-500">{PRESET_META[role]?.desc ?? ''}</p>
                </div>
                <select
                  value={currentModel}
                  onChange={(e) => setRoleModel(role, e.target.value)}
                  disabled={lightweight}
                  className="min-w-[180px] bg-base-900 border border-base-700 rounded-lg px-2.5 py-1.5 text-xs text-base-200 font-mono outline-none focus:border-accent/40 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <option value="">Use default</option>
                  {modelOptions.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}