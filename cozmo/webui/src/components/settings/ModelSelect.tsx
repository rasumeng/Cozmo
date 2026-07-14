import { useState, useEffect, useRef } from 'react'
import { ChevronDown } from 'lucide-react'

interface Props {
  value: string
  models: string[]
  onChange: (v: string) => void
  disabled?: boolean
}

export function ModelSelect({ value, models, onChange, disabled }: Props) {
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
