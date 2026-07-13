import { useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronDown, FileText } from 'lucide-react'
import { DiffData } from '@/types'

export function FileChangeCard({ path, added, removed, diff }: { path: string; added: number; removed: number; diff: DiffData }) {
  const [open, setOpen] = useState(false)
  const isBinary = added === 0 && removed === 0 && diff.text === ''

  return (
    <div className="rounded-lg border border-base-700 overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-base-800/60 transition-colors"
      >
        <FileText size={13} className="text-accent shrink-0" />
        <span className="flex-1 text-[12px] font-mono text-base-200 truncate">{(path.length > 50 ? path.slice(-47) : path).padStart(1)}</span>
        <span className="text-[11px] shrink-0">
          <span className="text-green-400">+{added}</span>
          <span className="text-base-600 mx-0.5">/</span>
          <span className="text-red-400">-{removed}</span>
        </span>
        {!isBinary && (
          <ChevronDown size={12} className={`text-base-500 transition-transform shrink-0 ${open ? 'rotate-180' : ''}`} />
        )}
      </button>
      {open && !isBinary && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="border-t border-base-700"
        >
          <pre className="text-[11px] leading-relaxed font-mono overflow-x-auto p-3 bg-base-900/50">
            {diff.text.split('\n').map((line, i) => {
              const cls = line.startsWith('+') ? 'text-green-400' : line.startsWith('-') ? 'text-red-400' : line.startsWith('@@') ? 'text-accent' : 'text-base-500'
              return <div key={i} className={cls}>{line}</div>
            })}
          </pre>
        </motion.div>
      )}
    </div>
  )
}
