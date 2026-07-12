import { motion } from 'framer-motion'
import { Check, X, FileText } from 'lucide-react'
import { ActivityStep, PlanData } from '@/types'
import { ActivityCard } from './ActivityCard'

export function ActivityPanel({
  steps,
  plan,
  onApprovePlan,
  onRejectPlan,
}: {
  steps: ActivityStep[]
  plan: PlanData | null
  onApprovePlan?: () => void
  onRejectPlan?: () => void
}) {
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
        {plan && plan.status === 'pending' && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 overflow-hidden"
          >
            <div className="flex items-center gap-2.5 px-3 py-2.5 border-b border-emerald-500/10">
              <FileText size={14} className="text-emerald-400 shrink-0" />
              <span className="text-[13px] font-medium text-emerald-300">Proposed Plan</span>
            </div>
            <div className="px-3 py-2.5 text-[12px] text-base-300 whitespace-pre-wrap font-mono leading-relaxed max-h-[300px] overflow-y-auto">
              {plan.plan}
            </div>
            <div className="flex gap-2 px-3 pb-3">
              <button
                onClick={onApprovePlan}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 py-2 text-[13px] font-medium text-emerald-300 transition-colors"
              >
                <Check size={14} />
                Approve
              </button>
              <button
                onClick={onRejectPlan}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 py-2 text-[13px] font-medium text-red-400 transition-colors"
              >
                <X size={14} />
                Reject
              </button>
            </div>
          </motion.div>
        )}
        {plan && plan.status === 'approved' && (
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2.5 flex items-center gap-2.5">
            <Check size={14} className="text-emerald-400 shrink-0" />
            <span className="text-[13px] text-emerald-300">Plan approved — executing...</span>
          </div>
        )}
        {steps.length === 0 && !plan && (
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
