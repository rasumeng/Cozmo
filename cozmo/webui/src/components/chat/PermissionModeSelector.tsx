import { useState, useEffect, useRef } from 'react'
import { Shield, Check, ChevronDown } from 'lucide-react'

export interface PermissionMode {
  id: string
  label: string
  description: string
}

export const PERMISSION_MODES: PermissionMode[] = [
  { id: 'manual', label: 'Manual', description: 'Review every edit and command before execution' },
  { id: 'plan', label: 'Plan', description: 'Generate a plan with no file changes or commands' },
  { id: 'accept-edits', label: 'Accept edits', description: 'Auto-accept file edits, still ask for commands' },
  { id: 'auto', label: 'Auto', description: 'Auto-approve safe changes, ask for risky operations' },
  { id: 'bypass', label: 'Bypass', description: 'Skip all approval prompts (dangerous)' },
]

export function PermissionModeSelector({
  mode,
  onChange,
}: {
  mode: string
  onChange: (mode: string) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      setTimeout(() => document.addEventListener('click', handleClick), 0)
    }
    return () => document.removeEventListener('click', handleClick)
  }, [open])

  const current = PERMISSION_MODES.find(m => m.id === mode) || PERMISSION_MODES[0]

  const COLORS: Record<string, string> = {
    manual: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    plan: 'text-violet-400 border-violet-500/30 bg-violet-500/10',
    'accept-edits': 'text-blue-400 border-blue-500/30 bg-blue-500/10',
    auto: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    bypass: 'text-red-400 border-red-500/30 bg-red-500/10',
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium border transition-colors ${COLORS[mode] || COLORS.manual}`}
      >
        <Shield size={11} />
        {current.label}
        <ChevronDown size={10} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute bottom-full mb-1 left-0 bg-base-850 border border-base-700 rounded-xl overflow-hidden shadow-panel min-w-[220px] z-20 py-1">
          {PERMISSION_MODES.map(pm => {
            const active = pm.id === mode
            return (
              <button
                key={pm.id}
                onClick={() => { onChange(pm.id); setOpen(false) }}
                className={`w-full flex items-start gap-2.5 px-3 py-2.5 text-left transition-colors ${
                  active ? 'bg-base-800' : 'hover:bg-base-800/50'
                }`}
              >
                <div className="shrink-0 mt-0.5">
                  {active ? <Check size={13} className="text-accent" /> : <div className="w-[13px]" />}
                </div>
                <div className="min-w-0">
                  <div className={`text-[12px] font-medium ${active ? 'text-base-100' : 'text-base-300'}`}>{pm.label}</div>
                  <div className="text-[10px] text-base-500 mt-0.5 leading-snug">{pm.description}</div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
