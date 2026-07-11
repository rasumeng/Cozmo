import { useState } from 'react'
import { motion } from 'framer-motion'
import * as Icons from 'lucide-react'
import { ChevronDown } from 'lucide-react'
import { ActivityStep } from '@/types'
import { StatusIndicator } from '@/components/common/StatusIndicator'

export function ActivityCard({ step, index }: { step: ActivityStep; index: number }) {
  const [open, setOpen] = useState(false)
  const Icon = (Icons as any)[step.icon] ?? Icons.Circle

  return (
    <motion.div
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2, delay: index * 0.04 }}
      className="rounded-xl border border-base-800 bg-base-850 overflow-hidden"
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left hover:bg-base-800/60 transition-colors"
      >
        <Icon size={14} className="text-accent shrink-0" />
        <span className="flex-1 text-[13px] text-base-200 truncate">{step.label}</span>
        {step.durationMs !== undefined && step.durationMs > 0 && (
          <span className="text-[11px] text-base-500 shrink-0">{(step.durationMs / 1000).toFixed(1)}s</span>
        )}
        <StatusIndicator status={step.status} />
        <ChevronDown
          size={13}
          className={`text-base-500 transition-transform shrink-0 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (step.detail || step.query) && (
        <div className="px-3 pb-2.5 pt-0.5 text-[12px] text-base-400 space-y-1 border-t border-base-800/60">
          {step.query && (
            <div>
              <span className="text-base-500">Query: </span>
              <span className="text-base-300 font-mono">{step.query}</span>
            </div>
          )}
          {step.detail && (
            <div>
              <span className="text-base-500">Detail: </span>
              <span className="text-base-300">{step.detail}</span>
            </div>
          )}
          <div>
            <span className="text-base-500">Status: </span>
            <span className="text-base-300 capitalize">{step.status}</span>
          </div>
        </div>
      )}
    </motion.div>
  )
}
