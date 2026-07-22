import { useState } from 'react'
import { motion } from 'framer-motion'
import * as Icons from 'lucide-react'
import { ChevronDown, Check, X } from 'lucide-react'
import { InlineStep } from '@/types'

export function InlineTraceStep({ step, index }: { step: InlineStep; index: number }) {
  const [open, setOpen] = useState(false)
  const Icon = (Icons as any)[step.icon] ?? Icons.Circle
  const isRunning = step.status === 'running'
  const hasExpandable = step.detail || step.query || step.toolSummary || step.result || step.diff

  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.03 }}
      className="overflow-hidden"
    >
      <div className="flex items-start gap-2 py-1.5 px-1">
        <div className="mt-0.5 shrink-0">
          {isRunning ? (
            <span className="block w-3.5 h-3.5 rounded-full bg-accent/30 animate-pulse" />
          ) : step.status === 'error' ? (
            <X size={14} className="text-red-400" />
          ) : (
            <Check size={14} className="text-emerald-400" />
          )}
        </div>

        {hasExpandable ? (
          <button
            onClick={() => setOpen(v => !v)}
            className="flex-1 flex items-center gap-1.5 text-left group min-w-0"
          >
            <Icon size={13} className="text-accent shrink-0" />
            <span className={`text-[13px] truncate ${isRunning ? 'text-base-100' : 'text-base-300'}`}>
              {step.label}
            </span>
            {step.durationMs !== undefined && step.durationMs > 0 && (
              <span className="text-[11px] text-base-500 shrink-0">
                {(step.durationMs / 1000).toFixed(1)}s
              </span>
            )}
            <ChevronDown
              size={11}
              className={`text-base-500 transition-transform shrink-0 ml-auto ${open ? 'rotate-180' : 'opacity-0 group-hover:opacity-100'}`}
            />
          </button>
        ) : (
          <div className="flex-1 flex items-center gap-1.5 min-w-0">
            <Icon size={13} className="text-accent shrink-0" />
            <span className={`text-[13px] truncate ${isRunning ? 'text-base-100' : 'text-base-300'}`}>
              {step.label}
            </span>
            {step.durationMs !== undefined && step.durationMs > 0 && (
              <span className="text-[11px] text-base-500 shrink-0">
                {(step.durationMs / 1000).toFixed(1)}s
              </span>
            )}
          </div>
        )}
      </div>

      {open && hasExpandable && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="pl-7 pr-2 pb-2"
        >
          <div className="text-[12px] text-base-400 space-y-1.5">
            {step.detail && (
              <p className="text-base-500">{step.detail}</p>
            )}
            {step.toolSummary && (
              <p className="font-mono text-base-400 bg-base-800/50 rounded px-2 py-1">
                {step.toolSummary}
              </p>
            )}
            {step.query && (
              <p><span className="text-base-500">Query: </span><span className="text-base-300 font-mono">{step.query}</span></p>
            )}
            {step.result && (
              <div>
                <span className="text-base-500">Result: </span>
                <pre className="text-base-300 text-[11px] mt-0.5 bg-base-800/30 rounded px-2 py-1 max-h-24 overflow-y-auto whitespace-pre-wrap">
                  {step.result.length > 300 ? step.result.slice(0, 300) + '...' : step.result}
                </pre>
              </div>
            )}
            {step.diff && step.diff.text && (
              <pre className="text-[11px] leading-relaxed font-mono overflow-x-auto bg-base-800/30 rounded p-2 max-h-40 overflow-y-auto">
                {step.diff.text.split('\n').map((line, li) => {
                  const cls = line.startsWith('+') ? 'text-green-400' : line.startsWith('-') ? 'text-red-400' : line.startsWith('@@') ? 'text-accent' : 'text-base-500'
                  return <div key={li} className={cls}>{line || ' '}</div>
                })}
              </pre>
            )}
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
