import { useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronDown, Activity } from 'lucide-react'
import { InlineStep, PlanData } from '@/types'
import { InlineTraceStep } from './InlineTraceStep'
import { InlinePlanApproval } from './InlinePlanApproval'

export function InlineTraceTimeline({
  steps,
  plan,
  onApprovePlan,
  onRejectPlan,
  generating,
}: {
  steps: InlineStep[]
  plan: PlanData | null
  onApprovePlan?: () => void
  onRejectPlan?: () => void
  generating: boolean
}) {
  const [collapsed, setCollapsed] = useState(false)
  const hasRunning = steps.some(s => s.status === 'running')
  const totalMs = steps.reduce((sum, s) => sum + (s.durationMs ?? 0), 0)

  if (steps.length === 0 && !plan) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-base-700/50 bg-base-900/50 overflow-hidden"
    >
      <button
        onClick={() => setCollapsed(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-base-800/40 transition-colors"
      >
        <Activity size={13} className="text-accent shrink-0" />
        <span className="text-[12px] font-medium text-base-200">
          {hasRunning ? 'Working...' : `${steps.length} step${steps.length !== 1 ? 's' : ''}`}
        </span>
        {totalMs > 0 && (
          <span className="text-[11px] text-base-500">
            · {(totalMs / 1000).toFixed(1)}s
          </span>
        )}
        {hasRunning && (
          <span className="flex gap-1 ml-1">
            <span className="w-1 h-1 rounded-full bg-accent animate-glow" />
            <span className="w-1 h-1 rounded-full bg-accent animate-glow" style={{ animationDelay: '0.2s' }} />
            <span className="w-1 h-1 rounded-full bg-accent animate-glow" style={{ animationDelay: '0.4s' }} />
          </span>
        )}
        <ChevronDown
          size={12}
          className={`text-base-500 transition-transform shrink-0 ml-auto ${collapsed ? '' : 'rotate-180'}`}
        />
      </button>

      {!collapsed && (
        <div className="px-2 pb-2 space-y-0.5 border-t border-base-800/50 pt-1">
          {plan && (
            <div className="px-1 pb-1">
              <InlinePlanApproval plan={plan} onApprove={onApprovePlan} onReject={onRejectPlan} />
            </div>
          )}
          {steps.map((step, i) => (
            <InlineTraceStep key={step.id} step={step} index={i} />
          ))}
        </div>
      )}
    </motion.div>
  )
}
