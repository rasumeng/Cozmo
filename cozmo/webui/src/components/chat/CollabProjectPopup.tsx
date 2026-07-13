import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Folder, FolderOpen, Plus, MessageSquare, Search, Check } from 'lucide-react'
import { Project, CollabProjectFile } from '@/types'
import { CreateProjectWizard } from './CreateProjectWizard'
import { ImportFromChatPopup } from './ImportFromChatPopup'

const API_BASE = import.meta.env.DEV ? 'http://localhost:8765' : ''

interface Props {
  collabProject: Project | null
  projects: Project[]
  onClose: () => void
  onSelectProject: (id: string) => void
  onListProjects: (search?: string) => void
  onCreateProject: (data: { name: string; description: string; instructions: string; files: CollabProjectFile[]; location: string }) => void
  onImportChat: (ids: string[]) => void
  onSetDirectory: (path: string) => void
}

export function CollabProjectPopup({
  collabProject,
  projects,
  onClose,
  onSelectProject,
  onListProjects,
  onCreateProject,
  onImportChat,
  onSetDirectory,
}: Props) {
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [pickingDir, setPickingDir] = useState(false)
  const popupRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    onListProjects('')
  }, [])

  useEffect(() => {
    const close = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (popupRef.current && !popupRef.current.contains(target) && !target.closest('[data-modal="true"]')) onClose()
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [onClose])

  const filtered = search
    ? projects.filter(p => p.name.toLowerCase().includes(search.toLowerCase()) || p.description?.toLowerCase().includes(search.toLowerCase()))
    : projects

  return (
    <>
      <div ref={popupRef} className="absolute bottom-full mb-1 left-0 bg-base-850 border border-base-700 rounded-xl overflow-visible shadow-panel min-w-[340px] z-50 py-1">
        <div className="px-3 pt-2 pb-1">
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-base-500" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search projects..."
              className="w-full pl-7 pr-2.5 py-1.5 rounded-lg bg-base-900 border border-base-700 text-[12px] text-base-200 placeholder:text-base-600 outline-none focus:border-accent"
            />
          </div>
        </div>

        <div className="max-h-[220px] overflow-y-auto px-1.5 py-1 space-y-0.5">
          {filtered.length === 0 && (
            <p className="text-[11px] text-base-600 px-2 py-3 text-center">No projects yet</p>
          )}
          {filtered.map(p => {
            const active = collabProject?.id === p.id
            return (
              <button
                key={p.id}
                onClick={() => { onSelectProject(p.id); onClose() }}
                className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left transition-colors ${
                  active ? 'bg-base-800 ring-1 ring-accent' : 'hover:bg-base-800/50'
                }`}
              >
                <FolderOpen size={14} className={`shrink-0 ${active ? 'text-accent' : 'text-base-500'}`} />
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-medium text-base-200 truncate">{p.name}</div>
                  {p.description && <div className="text-[9px] text-base-500 truncate">{p.description}</div>}
                </div>
                {active && <Check size={12} className="text-accent shrink-0" />}
              </button>
            )
          })}
        </div>

        <div className="border-t border-base-700 mx-1.5 my-1" />

        <div className="px-1.5 pb-1.5 space-y-0.5">
          <button onClick={() => setShowCreate(true)} className="w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[11px] text-base-300 hover:bg-base-800 transition-colors">
            <Plus size={13} className="text-emerald-400" />
            Create New Project
          </button>
          <button onClick={() => setShowImport(true)} className="w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[11px] text-base-300 hover:bg-base-800 transition-colors">
            <MessageSquare size={13} className="text-blue-400" />
            Import from Chat
          </button>
          <button
            onClick={async () => {
              setPickingDir(true)
              try {
                const r = await fetch(`${API_BASE}/api/directory-picker`, { method: 'POST' })
                const data = await r.json()
                if (data.path) { onSetDirectory(data.path); onClose() }
              } catch { /* ignore */ }
              setPickingDir(false)
            }}
            disabled={pickingDir}
            className="w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[11px] text-base-300 hover:bg-base-800 disabled:opacity-40 transition-colors"
          >
            <Folder size={13} className="text-amber-400" />
            {pickingDir ? 'Opening folder picker...' : 'Use Existing Folder'}
          </button>
        </div>
      </div>

      {showCreate && createPortal(
        <CreateProjectWizard
          onClose={() => setShowCreate(false)}
          onCreate={(data) => { onCreateProject(data); setShowCreate(false); onClose() }}
        />,
        document.body
      )}

      {showImport && createPortal(
        <ImportFromChatPopup
          onClose={() => setShowImport(false)}
          onImport={(ids) => { onImportChat(ids); setShowImport(false); onClose() }}
        />,
        document.body
      )}
    </>
  )
}
