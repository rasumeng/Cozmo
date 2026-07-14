import { useState, useEffect } from 'react'
import { X, Check, ChevronDown, ChevronRight, MessageSquare, Bot, User } from 'lucide-react'

interface Message {
  id: string
  role: string
  content: string
}

interface ConvWithMessages {
  id: string
  title: string
  mode: string
  updatedAt: string
  messages: Message[]
}

interface Props {
  onClose: () => void
  onImport: (ids: string[]) => void
}

const API_BASE = import.meta.env.DEV ? 'http://localhost:8765' : ''

export function ImportFromChatPopup({ onClose, onImport }: Props) {
  const [convs, setConvs] = useState<ConvWithMessages[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetch(`${API_BASE}/api/conversations`)
      .then(r => r.json())
      .then(data => {
        const mapped: ConvWithMessages[] = (data || []).map((c: any) => ({
          id: c.id,
          title: c.title || 'Untitled',
          mode: c.mode || 'chat',
          updatedAt: c.updatedAt || '',
          messages: (c.messages || []).slice(-20),
        }))
        mapped.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
        setConvs(mapped.slice(0, 30))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const toggleExpand = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const MODE_ICONS: Record<string, string> = { chat: '💬', agent: '🤖', code: '💻' }

  const convCount = convs.length
  const selCount = selected.size

  return (
    <div data-modal="true" className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-base-850 border border-base-700 rounded-xl w-[520px] max-h-[80vh] flex flex-col shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-base-700 shrink-0">
          <h3 className="text-sm font-medium text-base-200">Import from Chat</h3>
          <button onClick={onClose} className="text-base-500 hover:text-base-300"><X size={14} /></button>
        </div>

        <p className="text-[11px] text-base-500 px-5 pt-3 pb-1 shrink-0">
          {convCount} conversation{convCount !== 1 ? 's' : ''} loaded. Expand to preview, check to import.
        </p>

        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
          {loading ? (
            <p className="text-[12px] text-base-600 px-2 py-6 text-center">Loading conversations...</p>
          ) : convs.length === 0 ? (
            <p className="text-[12px] text-base-600 px-2 py-6 text-center">No conversations found.</p>
          ) : convs.map(c => {
            const isExpanded = expanded.has(c.id)
            const isSelected = selected.has(c.id)
            return (
              <div key={c.id} className="rounded-lg overflow-hidden">
                <div className="flex items-center gap-1.5 px-1">
                  <button
                    onClick={() => toggleExpand(c.id)}
                    className="p-1 rounded text-base-500 hover:text-base-300 hover:bg-base-800 transition-colors"
                  >
                    {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  </button>
                  <button
                    onClick={() => toggleSelect(c.id)}
                    className="flex items-center gap-2.5 flex-1 py-2 text-left"
                  >
                    <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                      isSelected ? 'bg-accent border-accent' : 'border-base-600'
                    }`}>
                      {isSelected && <Check size={10} className="text-white" />}
                    </div>
                    <span className="text-[13px]">{MODE_ICONS[c.mode] || '💬'}</span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[12px] text-base-200 truncate">{c.title || 'Untitled'}</div>
                      <div className="text-[9px] text-base-500">{c.mode} · {c.messages.length} msgs · {c.updatedAt?.slice(0, 10) || ''}</div>
                    </div>
                  </button>
                </div>
                {isExpanded && (
                  <div className="ml-7 mr-2 pb-2 space-y-1">
                    {c.messages.length === 0 && (
                      <p className="text-[10px] text-base-600 px-2 py-1">No messages</p>
                    )}
                    {c.messages.map(m => (
                      <div key={m.id} className="flex gap-2 px-2 py-1.5 rounded bg-base-900/50">
                        <span className="shrink-0 mt-0.5">{m.role === 'user' ? <User size={10} className="text-base-500" /> : <Bot size={10} className="text-accent" />}</span>
                        <p className="text-[10px] text-base-400 leading-relaxed line-clamp-3">{m.content || '(empty)'}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div className="flex items-center justify-between px-5 py-4 border-t border-base-700 shrink-0">
          <button onClick={onClose} className="px-3 py-1.5 rounded-lg text-[12px] text-base-400 hover:bg-base-800 transition-colors">Cancel</button>
          <button
            onClick={() => { if (selCount > 0) onImport(Array.from(selected)) }}
            disabled={selCount === 0}
            className="px-4 py-1.5 rounded-lg text-[12px] font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-40 transition-colors"
          >
            Import ({selCount}) & Create Project
          </button>
        </div>
      </div>
    </div>
  )
}
