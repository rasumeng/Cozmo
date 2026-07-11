import clsx from 'clsx'
import { ActivityStatus } from '@/types'

const COLORS: Record<ActivityStatus, string> = {
  running: 'bg-secondary animate-pulse shadow-sm shadow-secondary/30',
  completed: 'bg-ok shadow-sm shadow-ok/30',
  error: 'bg-err shadow-sm shadow-err/30',
}

export function StatusIndicator({ status }: { status: ActivityStatus }) {
  return <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', COLORS[status])} />
}
