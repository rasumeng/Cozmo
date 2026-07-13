import { useRef, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Terminal, FileText, Search, GitBranch, Calculator, Trash2 } from 'lucide-react'
import { TerminalEntry } from '@/types'

type ToolFilter = 'all' | 'shell' | 'files' | 'search' | 'git'

const TOOL_CATEGORIES: Record<string, ToolFilter> = {
  run_command: 'shell',
  execute_python: 'shell',
  write_file: 'files',
  edit_file: 'files',
  read_file: 'files',
  list_directory: 'files',
  grep_search: 'search',
  git_diff: 'git',
  git_log: 'git',
}

const CATEGORY_ICONS: Record<ToolFilter, React.ElementType> = {
  all: Terminal,
  shell: Terminal,
  files: FileText,
  search: Search,
  git: GitBranch,
}

const CATEGORY_COLORS: Record<ToolFilter, string> = {
  all: 'text-base-300',
  shell: 'text-green-400',
  files: 'text-blue-400',
  search: 'text-yellow-400',
  git: 'text-purple-400',
}

function toolFilter(entry: ToolFilter, t: TerminalEntry): boolean {
  if (entry === 'all') return true
  return (TOOL_CATEGORIES[t.tool] || 'shell') === entry
}

export function TerminalPanel({
  entries,
  onClear,
}: {
  entries: TerminalEntry[]
  onClear: () => void
}) {
  const [filter, setFilter] = useState<ToolFilter>('all')
  const bottomRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  const filtered = entries.filter(t => toolFilter(filter, t))

  useEffect(() => {
    if (autoScroll) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [filtered.length, autoScroll])

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
    if (!atBottom) setAutoScroll(false)
    else setAutoScroll(true)
  }

  const FILTERS: { key: ToolFilter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'shell', label: 'Shell' },
    { key: 'files', label: 'Files' },
    { key: 'search', label: 'Search' },
    { key: 'git', label: 'Git' },
  ]

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-1 px-3 py-2 border-b border-base-800 shrink-0">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => { setFilter(f.key); setAutoScroll(true) }}
            className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
              filter === f.key ? 'bg-base-700 text-base-200' : 'text-base-500 hover:text-base-300'
            }`}
          >
            {f.label}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={onClear}
          className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-base-500 hover:text-base-300 hover:bg-base-800 transition-colors"
        >
          <Trash2 size={11} />
          Clear
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5" onScroll={handleScroll}>
        {filtered.length === 0 && (
          <p className="text-[11px] text-base-600 px-1 pt-2">No tool calls yet.</p>
        )}
        {filtered.map(entry => {
          const cat = TOOL_CATEGORIES[entry.tool] || 'shell'
          const Icon = CATEGORY_ICONS[cat]
          const color = CATEGORY_COLORS[cat]
          return (
            <motion.div
              key={entry.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-[11px] font-mono leading-relaxed"
            >
              <div className="flex items-start gap-1.5">
                <Icon size={12} className={`shrink-0 mt-0.5 ${color}`} />
                <span className="text-base-400">&gt;</span>
                <span className="text-base-200">{entry.tool}</span>
                <span className="text-base-500 truncate min-w-0">{JSON.stringify(entry.args).slice(0, 120)}</span>
              </div>
              {entry.result && (
                <div className="pl-6 text-base-400 whitespace-pre-wrap break-all">
                  {entry.result.length > 300 ? entry.result.slice(0, 300) + '…' : entry.result}
                </div>
              )}
              {!entry.result && (
                <div className="pl-6 text-base-600 italic">running…</div>
              )}
            </motion.div>
          )
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
