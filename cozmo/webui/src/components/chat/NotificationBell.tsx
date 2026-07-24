import { useState, useRef, useEffect } from 'react'
import { Bell, BellDot, Clock, CheckCircle, XCircle, ExternalLink } from 'lucide-react'
import { BackgroundRunInfo } from '@/types'

interface Props {
  runs: BackgroundRunInfo[]
}

interface Notification {
  id: string
  icon: React.ElementType
  text: string
  time: string
  status: 'info' | 'success' | 'error'
}

function toNotifications(runs: BackgroundRunInfo[]): Notification[] {
  const out: Notification[] = []
  for (const r of runs) {
    if (r.status === 'completed' || r.status === 'done') {
      out.push({
        id: `job-${r.run_id}-done`,
        icon: CheckCircle,
        text: `Job completed: ${r.goal.slice(0, 60)}`,
        time: r.ended || 'just now',
        status: 'success',
      })
    }
    if (r.status === 'error') {
      out.push({
        id: `job-${r.run_id}-error`,
        icon: XCircle,
        text: `Job failed: ${r.goal.slice(0, 60)}`,
        time: r.ended || 'just now',
        status: 'error',
      })
    }
  }
  return out.slice(0, 10)
}

export function NotificationBell({ runs }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const notifications = toNotifications(runs)
  const hasUnread = notifications.length > 0

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="relative p-1.5 rounded-lg text-base-400 hover:text-base-100 hover:bg-base-800 transition-colors"
        title="Notifications"
      >
        {hasUnread ? <BellDot size={14} /> : <Bell size={14} />}
        {hasUnread && (
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-accent" />
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 bg-base-850 border border-base-700 rounded-xl shadow-panel overflow-hidden z-50">
          <div className="px-3 py-2 border-b border-base-700 text-[11px] font-medium text-base-300">
            Notifications
          </div>
          {notifications.length === 0 ? (
            <div className="px-3 py-4 text-[12px] text-base-500 text-center">No notifications</div>
          ) : (
            <div className="max-h-64 overflow-y-auto">
              {notifications.map(n => {
                const Icon = n.icon
                return (
                  <div key={n.id} className="flex items-start gap-2.5 px-3 py-2.5 border-b border-base-800/50 last:border-0">
                    <Icon size={13} className={`shrink-0 mt-0.5 ${
                      n.status === 'success' ? 'text-emerald-400' :
                      n.status === 'error' ? 'text-red-400' : 'text-accent'
                    }`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] text-base-200 leading-snug">{n.text}</p>
                      <span className="text-[10px] text-base-500 mt-0.5 block">{n.time}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}