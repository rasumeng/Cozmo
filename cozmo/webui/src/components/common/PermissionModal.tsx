import { motion } from 'framer-motion'
import { ShieldAlert } from 'lucide-react'
import { PermissionRequest } from '@/hooks/useCozmoChat'

interface Props {
  request: PermissionRequest
  onAnswer: (allowed: boolean) => void
}

export function PermissionModal({ request, onAnswer }: Props) {
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.15 }}
        className="w-[420px] rounded-2xl border border-base-700 bg-base-900 p-5 shadow-panel"
      >
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
            <ShieldAlert size={16} className="text-amber-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-base-100">Permission required</p>
            <p className="text-[11px] text-base-500">Cozmo wants to run a tool</p>
          </div>
        </div>
        <div className="rounded-xl bg-base-850 border border-base-800 p-3 mb-4">
          <p className="text-xs text-accent font-mono mb-1.5">{request.tool}</p>
          <pre className="text-[11px] text-base-300 whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
            {JSON.stringify(request.args, null, 2)}
          </pre>
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={() => onAnswer(false)}
            className="px-3.5 py-1.5 rounded-lg text-sm text-base-300 hover:bg-base-800 transition-colors"
          >
            Deny
          </button>
          <button
            onClick={() => onAnswer(true)}
            className="px-3.5 py-1.5 rounded-lg text-sm bg-accent hover:bg-accent/90 text-white transition-colors"
          >
            Allow
          </button>
        </div>
      </motion.div>
    </div>
  )
}
