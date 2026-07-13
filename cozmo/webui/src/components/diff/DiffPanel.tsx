import { motion } from 'framer-motion'
import { DiffEntry } from '@/types'
import { FileChangeCard } from '@/components/chat/FileChangeCard'

export function DiffPanel({ entries }: { entries: DiffEntry[] }) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-base-800 shrink-0">
        <span className="text-[12px] font-medium text-base-200">File Changes</span>
        <span className="text-[11px] text-base-500">this session</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {entries.length === 0 && (
          <p className="text-[11px] text-base-600 px-1 pt-2">No file changes yet.</p>
        )}
        {entries.map((entry, i) => (
          <motion.div
            key={entry.id}
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.15, delay: i * 0.02 }}
          >
            <FileChangeCard
              path={entry.path}
              added={entry.added}
              removed={entry.removed}
              diff={entry.diff}
            />
          </motion.div>
        ))}
      </div>
    </div>
  )
}
