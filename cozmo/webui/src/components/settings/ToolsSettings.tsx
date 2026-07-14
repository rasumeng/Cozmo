import { PermissionSelect } from './PermissionSelect'
import type { ToolInfo, SettingsData } from './types'

interface Props {
  tools: ToolInfo[]
  config: SettingsData | null
  updateToolPermission: (toolId: string, mode: string) => void
}

export function ToolsSettings({ tools, config, updateToolPermission }: Props) {
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
