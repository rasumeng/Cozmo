import { useState, useEffect, useRef } from 'react'
import { Folder, History, X } from 'lucide-react'

const RECENT_KEY = 'cozmo_recent_dirs'
const MAX_RECENT = 5

function loadRecents(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveRecents(dirs: string[]) {
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(dirs)) } catch {}
}

function addRecent(path: string) {
  const recents = loadRecents().filter(d => d !== path)
  recents.unshift(path)
  saveRecents(recents.slice(0, MAX_RECENT))
}

export function DirectoryPicker({
  path,
  onChange,
}: {
  path: string
  onChange: (path: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState(path)
  const [recents, setRecents] = useState<string[]>([])
  const pickerRef = useRef<HTMLInputElement>(null)
  const popupRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) {
      setInput(path)
      setRecents(loadRecents())
    }
  }, [open])

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      setTimeout(() => document.addEventListener('click', handleClick), 0)
    }
    return () => document.removeEventListener('click', handleClick)
  }, [open])

  const handleSubmit = () => {
    const val = input.trim()
    if (val) {
      addRecent(val)
      onChange(val)
      setOpen(false)
    }
  }

  const handleBrowse = () => {
    pickerRef.current?.click()
  }

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    // Extract directory prefix from webkitRelativePath
    const dirName = files[0].webkitRelativePath?.split('/')[0]
    if (dirName) {
      setInput(dirName)
    }
    // Reset so same folder can be picked again
    e.target.value = ''
  }

  const displayName = path === './' || path === '.' ? 'Open Folder' : path.length > 30 ? `…${path.slice(-27)}` : path

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-[11px] font-medium text-base-400 hover:text-base-200 hover:bg-base-800 transition-colors"
        title="Set project directory"
      >
        <Folder size={13} className="text-accent" />
        <span className="max-w-[120px] truncate">{displayName}</span>
      </button>

      <input ref={pickerRef} type="file" {...({ webkitdirectory: '' } as any)} className="hidden" onChange={handleFiles} />

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setOpen(false)}>
          <div ref={popupRef} className="bg-base-850 border border-base-700 rounded-xl p-4 w-[400px] shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-base-200">Project Directory</h3>
              <button onClick={() => setOpen(false)} className="text-base-500 hover:text-base-300">
                <X size={14} />
              </button>
            </div>
            <p className="text-[11px] text-base-500 mb-3">
              Set the project directory Cozmo will index and work with.
            </p>

            {recents.length > 0 && (
              <div className="mb-3">
                <div className="flex items-center gap-1.5 text-[11px] text-base-500 mb-1.5">
                  <History size={11} />
                  Recent
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {recents.map(d => (
                    <button
                      key={d}
                      onClick={() => { addRecent(d); onChange(d); setOpen(false) }}
                      className="px-2 py-1 rounded-md bg-base-800 text-[11px] text-base-300 hover:text-base-100 hover:bg-base-700 transition-colors"
                    >
                      {d.length > 40 ? `…${d.slice(-37)}` : d}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-2 mb-3">
              <input
                autoFocus
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleSubmit() }}
                placeholder="/home/user/projects/my-app"
                className="flex-1 px-3 py-2 rounded-lg bg-base-900 border border-base-700 text-[13px] text-base-200 placeholder:text-base-600 outline-none focus:border-accent"
              />
              <button
                onClick={handleBrowse}
                className="shrink-0 px-3 py-2 rounded-lg bg-base-800 border border-base-700 text-[12px] text-base-300 hover:text-base-100 hover:bg-base-700 transition-colors"
              >
                Browse
              </button>
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setOpen(false)}
                className="px-3 py-1.5 rounded-lg text-[12px] text-base-400 hover:bg-base-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!input.trim()}
                className="px-3 py-1.5 rounded-lg text-[12px] font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-40 transition-colors"
              >
                Set Directory
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
