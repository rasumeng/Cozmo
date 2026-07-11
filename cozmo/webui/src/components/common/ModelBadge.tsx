import clsx from 'clsx'

const MODEL_COLORS: Record<string, string> = {
  coder: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
  chat: 'bg-accent/10 text-accent border-accent/20',
  vision: 'bg-secondary/10 text-secondary border-secondary/20',
  research: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  classifier: 'bg-base-600/10 text-base-400 border-base-600/20',
}

export function ModelBadge({ model }: { model: string }) {
  const key = model.split(':')[0]?.split('-')[0] ?? model
  const known = Object.keys(MODEL_COLORS).find((k) => key.includes(k))
  const colorClass = known ? MODEL_COLORS[known] : 'bg-base-700/10 text-base-400 border-base-700/20'

  return (
    <span className={clsx('inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-md border', colorClass)}>
      {model}
    </span>
  )
}
