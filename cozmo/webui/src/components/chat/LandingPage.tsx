import { MessageSquare, Users, Code2, Sparkles, FileText, GitBranch, Globe, Search, PenTool, Braces, Bug, Workflow, Lightbulb, BookOpen, BarChart3, Mail, FileSymlink } from 'lucide-react'
import { WorkspaceMode } from '@/components/sidebar/workspaceModes'

interface Props {
  mode: WorkspaceMode
  onSuggestion?: (text: string) => void
}

interface SuggestionItem {
  icon: React.ElementType
  label: string
  prompt: string
}

const SUGGESTIONS: Record<WorkspaceMode, SuggestionItem[]> = {
  chat: [
    { icon: Globe, label: 'Research a topic', prompt: 'Research the topic of ' },
    { icon: FileSymlink, label: 'Summarize this article', prompt: 'Summarize this article: ' },
    { icon: Mail, label: 'Draft an email', prompt: 'Draft an email about ' },
    { icon: BarChart3, label: 'Analyze this data', prompt: 'Analyze this data: ' },
  ],
  collab: [
    { icon: Lightbulb, label: 'Brainstorm features', prompt: 'Help me brainstorm feature ideas for ' },
    { icon: Workflow, label: 'Plan architecture', prompt: 'Plan the architecture for ' },
    { icon: BookOpen, label: 'Write documentation', prompt: 'Write documentation for ' },
    { icon: PenTool, label: 'Draft a spec', prompt: 'Draft a specification for ' },
  ],
  code: [
    { icon: FileText, label: 'Explain this code', prompt: 'Explain this code: ' },
    { icon: Search, label: 'Find a bug', prompt: 'Find bugs in this code: ' },
    { icon: GitBranch, label: 'Review my PR', prompt: 'Review this pull request: ' },
    { icon: Braces, label: 'Refactor a module', prompt: 'Refactor this code: ' },
    { icon: Bug, label: 'Debug an error', prompt: 'Help me debug this error: ' },
    { icon: Sparkles, label: 'Write unit tests', prompt: 'Write unit tests for ' },
  ],
}

const HEADINGS: Record<WorkspaceMode, { title: string; subtitle: string; icon: React.ElementType }> = {
  chat: { icon: MessageSquare, title: 'Ask Cozmo anything', subtitle: 'Research, summarize, draft, and analyze.' },
  collab: { icon: Users, title: 'Start a collaborative task', subtitle: 'Brainstorm, plan, write, and create together.' },
  code: { icon: Code2, title: 'Begin a coding session', subtitle: 'Explain, debug, refactor, review, and test code.' },
}

export function LandingPage({ mode, onSuggestion }: Props) {
  const h = HEADINGS[mode]
  const suggestions = SUGGESTIONS[mode]
  const HI = h.icon

  const modeColors: Record<WorkspaceMode, string> = {
    chat: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
    collab: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    code: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  }
  const modeRing: Record<WorkspaceMode, string> = {
    chat: 'hover:border-indigo-500/30',
    collab: 'hover:border-emerald-500/30',
    code: 'hover:border-amber-500/30',
  }
  const modeIconBg: Record<WorkspaceMode, string> = {
    chat: 'bg-indigo-500/15',
    collab: 'bg-emerald-500/15',
    code: 'bg-amber-500/15',
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 py-16">
      <div className={`w-14 h-14 rounded-2xl ${modeIconBg[mode]} flex items-center justify-center mb-5`}>
        <HI size={28} className="text-base-100" />
      </div>
      <h1 className="text-xl font-semibold text-base-100 mb-1">{h.title}</h1>
      <p className="text-sm text-base-500 mb-8">{h.subtitle}</p>

      <div className="grid grid-cols-2 gap-3 max-w-md">
        {suggestions.map((s) => {
          const SI = s.icon
          return (
            <button
              key={s.label}
              onClick={() => onSuggestion?.(s.prompt)}
              className={`flex items-center gap-2.5 px-4 py-3 rounded-xl bg-base-800/40 border border-base-700/60 ${modeRing[mode]} text-base-400 hover:text-base-200 text-xs font-medium transition-all text-left`}
            >
              <div className={`w-7 h-7 rounded-lg ${modeColors[mode]} flex items-center justify-center shrink-0`}>
                <SI size={14} />
              </div>
              {s.label}
            </button>
          )
        })}
      </div>

      <div className="mt-8 flex items-center gap-2 text-[11px] text-base-600">
        <div className={`w-1.5 h-1.5 rounded-full ${modeColors[mode].split(' ')[0]}`} />
        Connected and ready
      </div>
    </div>
  )
}
