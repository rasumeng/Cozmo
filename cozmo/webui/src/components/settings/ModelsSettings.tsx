import { Plus, Trash2 } from 'lucide-react'
import { ModelSelect } from './ModelSelect'
import { BUILTIN_ROLES, PRESET_META } from './constants'
import type { SettingsData } from './types'

interface Props {
  config: SettingsData | null
  updateModel: (role: string, model: string) => void
  ollamaModels: string[]
  setConfig: (c: SettingsData) => void
  setDirty: (d: boolean) => void
  lightweight: boolean
}

export function ModelsSettings({ config, updateModel, ollamaModels, setConfig, setDirty, lightweight }: Props) {
  if (!config) return null

  const customEntries = Object.entries(config.models ?? {})
    .filter(([k]) => !BUILTIN_ROLES.includes(k as any) && k !== 'max_tokens')
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

  return (
    <div className="space-y-5">
      <p className="text-xs text-base-500">Assign models to each preset role. Changes take effect after saving.</p>
      {lightweight && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-accent/10 border border-accent/30">
          <span className="text-xs text-accent font-medium">Lightweight mode active</span>
          <span className="text-xs text-base-500">— single model used for all roles</span>
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
              disabled={lightweight}
            />
          </div>
        ))}
      </div>
      <div className="border-t border-base-700 pt-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm text-base-200 font-medium">Custom Presets</p>
          <button
            onClick={addCustom}
            disabled={lightweight}
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
                disabled={lightweight}
                className="flex-1 bg-base-900 border border-base-700 rounded-lg px-2.5 py-1.5 text-xs text-base-200 outline-none focus:border-accent/40 disabled:opacity-50 disabled:cursor-not-allowed"
                placeholder="Preset name"
              />
              <ModelSelect
                value={model}
                models={ollamaModels}
                onChange={(v) => updateCustomModel(key, v)}
                disabled={lightweight}
              />
              <button onClick={() => removeCustom(key)} disabled={lightweight} className="p-1 rounded text-base-500 hover:text-err transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
