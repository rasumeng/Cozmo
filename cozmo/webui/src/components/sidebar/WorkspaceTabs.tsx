import clsx from 'clsx'
import { MessageSquare, Bot, Code2 } from 'lucide-react'
import { WorkspaceMode } from './workspaceModes'

const TABS: { id: WorkspaceMode; label: string; icon: React.ElementType }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'agent', label: 'Agent', icon: Bot },
  { id: 'code', label: 'Code', icon: Code2 },
]

export function WorkspaceTabs({
  active,
  onChange,
  collapsed,
}: {
  active: WorkspaceMode
  onChange: (mode: WorkspaceMode) => void
  collapsed: boolean
}) {
  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            title={t.label}
            className={clsx(
              'p-1.5 rounded-lg transition-colors',
              active === t.id ? 'bg-base-800 text-accent' : 'text-base-500 hover:text-base-100 hover:bg-base-800'
            )}
          >
            <t.icon size={15} />
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-0.5 p-1 rounded-xl bg-base-850 border border-base-800">
      {TABS.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={clsx(
            'flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-medium transition-colors',
            active === t.id ? 'bg-base-750 text-base-100 shadow-panel' : 'text-base-400 hover:text-base-200'
          )}
        >
          <t.icon size={13} />
          {t.label}
        </button>
      ))}
    </div>
  )
}
