import { motion } from 'framer-motion'
import { ActivityStep } from '@/types'
import { ActivityCard } from './ActivityCard'

export function ActivityPanel({ steps }: { steps: ActivityStep[] }) {
  return (
    <motion.aside
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className="w-[320px] shrink-0 h-full border-l border-base-800 bg-base-900 flex flex-col"
    >
      <div className="h-14 shrink-0 flex items-center gap-2 px-4 border-b border-base-800">
        <div className="w-5 h-5 rounded-md bg-accent/15 flex items-center justify-center">
          <span className="text-accent text-[10px] font-bold">~</span>
        </div>
        <span className="text-sm font-medium text-base-100">Trace</span>
        <span className="text-[11px] text-base-500">agent execution</span>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {steps.length === 0 && (
          <p className="text-xs text-base-500 px-2 py-3">
            Agent steps show up here while Cozmo works.
          </p>
        )}
        {steps.map((step, i) => (
          <ActivityCard key={step.id} step={step} index={i} />
        ))}
      </div>
    </motion.aside>
  )
}
