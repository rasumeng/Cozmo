import type { SettingsData } from './types'

interface Props {
  config: SettingsData | null
  setConfig: (c: SettingsData) => void
  lightweight: boolean
  setLightweight: (v: boolean) => void
  setDirty: (d: boolean) => void
}

export function GeneralSettings({ config, setConfig, lightweight, setLightweight, setDirty }: Props) {
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
