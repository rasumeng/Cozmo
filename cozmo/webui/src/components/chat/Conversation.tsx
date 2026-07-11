import { useEffect, useRef } from 'react'
import { Sparkles, PanelRightClose, PanelRightOpen } from 'lucide-react'
import { Conversation as ConversationType, Attachment } from '@/types'
import { ConnectionState } from '@/services/cozmo'
import { MessageBubble } from './MessageBubble'
import { PromptInput } from './PromptInput'

interface Props {
  conversation: ConversationType
  connection: ConnectionState
  generating: boolean
  activityOpen: boolean
  onSend: (content: string, attachments?: Attachment[]) => void
  onStop: () => void
  onToggleActivity: () => void
}

const CONNECTION_LABEL: Record<ConnectionState, { text: string; dot: string }> = {
  connecting: { text: 'Connecting…', dot: 'bg-amber-400' },
  open: { text: 'Connected', dot: 'bg-emerald-400' },
  closed: { text: 'Disconnected — retrying', dot: 'bg-red-400' },
}

export function Conversation({
  conversation,
  connection,
  generating,
  activityOpen,
  onSend,
  onStop,
  onToggleActivity,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // stick to bottom as tokens stream in
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [conversation.messages])

  const conn = CONNECTION_LABEL[connection]

  return (
    <main className="flex-1 flex flex-col min-w-0 bg-base-950">
      <header className="h-14 shrink-0 flex items-center justify-between px-5 border-b border-base-800">
        <div className="flex items-center gap-2.5 text-sm text-base-300">
          <div className="w-5 h-5 rounded-md bg-accent/15 flex items-center justify-center">
            <Sparkles size={12} className="text-accent" />
          </div>
          <span className="text-base-100 font-medium">{conversation.title}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[11px] text-base-500">
            <span className={`w-1.5 h-1.5 rounded-full ${conn.dot}`} />
            {conn.text}
          </div>
          <button
            onClick={onToggleActivity}
            className="p-1.5 rounded-lg text-base-400 hover:text-base-100 hover:bg-base-800 transition-colors"
            title="Toggle activity panel"
          >
            {activityOpen ? <PanelRightClose size={17} /> : <PanelRightOpen size={17} />}
          </button>
        </div>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
          {conversation.messages.length === 0 && (
            <div className="flex flex-col items-center justify-center pt-24 text-center">
              <img src="/assets/Cozmo-sprite.svg" alt="" className="w-auto h-20" style={{ imageRendering: 'pixelated' }} />              
              <p className="text-base-300 text-sm">
                Ask Cozmo anything — code, files, research.
              </p>
            </div>
          )}
          {conversation.messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
        </div>
      </div>

      <div className="border-t border-base-800 bg-base-950/80 backdrop-blur px-6 py-4">
        <div className="max-w-3xl mx-auto">
          <PromptInput
            generating={generating}
            disabled={connection !== 'open'}
            onSend={onSend}
            onStop={onStop}
          />
        </div>
      </div>
    </main>
  )
}
