import { useState, useRef } from 'react'
import { X, Plus, Trash2, Folder } from 'lucide-react'
import { CollabProjectFile } from '@/types'

interface Props {
  onClose: () => void
  onCreate: (data: { name: string; description: string; instructions: string; files: CollabProjectFile[]; location: string }) => void
}

const API_BASE = import.meta.env.DEV ? 'http://localhost:8765' : ''

export function CreateProjectWizard({ onClose, onCreate }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [instructions, setInstructions] = useState('')
  const [files, setFiles] = useState<CollabProjectFile[]>([])
  const [location, setLocation] = useState('')
  const [picking, setPicking] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleAddFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files
    if (!fileList) return
    const remaining = Array.from(fileList)
    const results: CollabProjectFile[] = []

    const readNext = () => {
      if (remaining.length === 0) {
        setFiles(prev => [...prev, ...results])
        return
      }
      const f = remaining.shift()!
      const r = new FileReader()
      r.onload = () => {
        results.push({ name: f.name, content: r.result as string })
        readNext()
      }
      r.readAsText(f)
    }
    readNext()
    e.target.value = ''
  }

  const removeFile = (name: string) => setFiles(prev => prev.filter(f => f.name !== name))

  const handleBrowseLocation = async () => {
    setPicking(true)
    try {
      const r = await fetch(`${API_BASE}/api/directory-picker`, { method: 'POST' })
      const data = await r.json()
      if (data.path) setLocation(data.path)
    } catch { /* ignore */ }
    setPicking(false)
  }

  const canSubmit = name.trim().length > 0 && location.trim().length > 0

  return (
    <div data-modal="true" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-base-850 border border-base-700 rounded-xl w-[540px] max-h-[85vh] flex flex-col shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-base-700 shrink-0">
          <h3 className="text-sm font-medium text-base-200">Create New Project</h3>
          <button onClick={onClose} className="text-base-500 hover:text-base-300"><X size={14} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          <div>
            <label className="text-[12px] text-base-400 mb-1 block">Project Name *</label>
            <input autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="My Project" className="w-full px-3 py-2 rounded-lg bg-base-900 border border-base-700 text-[13px] text-base-200 placeholder:text-base-600 outline-none focus:border-accent" />
          </div>

          <div>
            <label className="text-[12px] text-base-400 mb-1 block">Description</label>
            <input value={description} onChange={e => setDescription(e.target.value)} placeholder="Brief description of the project" className="w-full px-3 py-2 rounded-lg bg-base-900 border border-base-700 text-[13px] text-base-200 placeholder:text-base-600 outline-none focus:border-accent" />
          </div>

          <div>
            <label className="text-[12px] text-base-400 mb-1 block">Instructions for Cozmo</label>
            <textarea value={instructions} onChange={e => setInstructions(e.target.value)} placeholder="How should Cozmo work in this project? Coding style, conventions, goals..." rows={3} className="w-full px-3 py-2 rounded-lg bg-base-900 border border-base-700 text-[13px] text-base-200 placeholder:text-base-600 outline-none focus:border-accent resize-none" />
          </div>

          <div>
            <label className="text-[12px] text-base-400 mb-1 block">Seed Files (optional)</label>
            <div className="border-2 border-dashed border-base-700 rounded-xl p-4 text-center hover:border-base-600 transition-colors cursor-pointer" onClick={() => fileInputRef.current?.click()}>
              <Plus size={18} className="mx-auto text-base-500 mb-1.5" />
              <p className="text-[11px] text-base-500">Click to browse files</p>
            </div>
            <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleAddFiles} />
            {files.length > 0 && (
              <div className="mt-2 space-y-1 max-h-[140px] overflow-y-auto">
                {files.map(f => (
                  <div key={f.name} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-base-900 text-[11px] text-base-300">
                    <span className="flex-1 truncate">{f.name}</span>
                    <button onClick={() => removeFile(f.name)} className="text-base-500 hover:text-red-400"><Trash2 size={11} /></button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="text-[12px] text-base-400 mb-1 block">Location *</label>
            <div className="flex gap-2">
              <div className="flex-1 px-3 py-2 rounded-lg bg-base-900 border border-base-700 text-[13px] text-base-500 truncate">
                {location || 'No folder selected'}
              </div>
              <button onClick={handleBrowseLocation} disabled={picking} className="shrink-0 px-4 py-2 rounded-lg bg-base-800 border border-base-700 text-[12px] text-base-300 hover:text-base-100 hover:bg-base-700 disabled:opacity-40 transition-colors flex items-center gap-1.5">
                <Folder size={13} /> {picking ? 'Opening...' : 'Browse'}
              </button>
            </div>
            {name && location && (
              <div className="mt-1.5 px-3 py-1.5 rounded-lg bg-base-900 text-[11px] text-base-500">
                Will create: <span className="text-base-300 font-mono">{location}/{name}/</span>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between px-5 py-4 border-t border-base-700 shrink-0">
          <button onClick={onClose} className="px-3 py-1.5 rounded-lg text-[12px] text-base-400 hover:bg-base-800 transition-colors">Cancel</button>
          <button onClick={() => onCreate({ name, description, instructions, files, location })} disabled={!canSubmit} className="px-4 py-1.5 rounded-lg text-[12px] font-medium bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-40 transition-colors flex items-center gap-1.5">
            ✨ Create Project
          </button>
        </div>
      </div>
    </div>
  )
}
