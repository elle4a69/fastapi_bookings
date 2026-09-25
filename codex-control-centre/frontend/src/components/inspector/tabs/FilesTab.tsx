import React, { useState, useEffect } from 'react'
import { FileText, Search, Copy, Check, Loader2, AlertCircle } from 'lucide-react'
import { Input } from '../../ui/input'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { codexApi } from '../../../api/codexApi'

interface FileItem {
  path: string
  size: string
  lines: number
  type: string
}

const MOCK_REPO_FILES: FileItem[] = [
  { path: 'app/main.py', size: '2.4 KB', lines: 78, type: 'python' },
  { path: 'app/services/availability.py', size: '6.8 KB', lines: 210, type: 'python' },
  { path: 'app/services/booking_service.py', size: '12.1 KB', lines: 340, type: 'python' },
  { path: 'app/api/routers/availability.py', size: '4.2 KB', lines: 115, type: 'python' },
  { path: 'alembic/versions/2026_08_add_slot_concurrency_lock.py', size: '1.2 KB', lines: 38, type: 'python' },
  { path: 'tests/test_availability.py', size: '5.1 KB', lines: 160, type: 'python' },
  { path: 'frontend/src/App.tsx', size: '3.3 KB', lines: 95, type: 'typescript' },
  { path: 'frontend/src/lib/api.ts', size: '4.8 KB', lines: 140, type: 'typescript' }
]

export const FilesTab: React.FC = () => {
  const { state, activeProject } = useWorkbenchStore()

  const [liveFiles, setLiveFiles] = useState<FileItem[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (state.appMode === 'demo') {
      setLiveFiles(MOCK_REPO_FILES)
      setSelectedFile(MOCK_REPO_FILES[1] || null)
      setError(null)
      setIsLoading(false)
      return
    }

    if (!activeProject?.id) {
      setLiveFiles([])
      setSelectedFile(null)
      return
    }

    let isMounted = true
    setIsLoading(true)
    setError(null)

    codexApi.getProjectFiles(activeProject.id)
      .then(files => {
        if (!isMounted) return
        const mapped: FileItem[] = Array.isArray(files) ? files : []
        setLiveFiles(mapped)
        setSelectedFile(mapped.length > 0 ? mapped[0] : null)
        setIsLoading(false)
      })
      .catch(err => {
        if (!isMounted) return
        console.warn('Failed to load project files:', err)
        setError(err?.message || 'Unable to read project repository files.')
        setLiveFiles([])
        setSelectedFile(null)
        setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [state.appMode, activeProject?.id, activeProject?.repository])

  const repoFiles = liveFiles
  const filteredFiles = repoFiles.filter(f => 
    f.path.toLowerCase().includes(search.toLowerCase())
  )

  const handleCopyPath = () => {
    if (selectedFile) {
      navigator.clipboard.writeText(selectedFile.path)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (isLoading) {
    return (
      <div className="p-6 flex flex-col items-center justify-center text-xs text-[var(--text-subtle)] space-y-2 h-48">
        <Loader2 className="w-5 h-5 animate-spin text-[var(--accent)]" />
        <p>Scanning workspace repository...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 m-3 rounded bg-[var(--danger-subtle)] border border-[var(--border)] text-xs text-[var(--danger)] space-y-1">
        <div className="flex items-center gap-1.5 font-semibold">
          <AlertCircle className="w-4 h-4" />
          <span>Workspace Inspection Error</span>
        </div>
        <p className="text-[11px] text-[var(--text-secondary)]">{error}</p>
      </div>
    )
  }

  if (state.appMode === 'live' && repoFiles.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-[var(--text-subtle)] mt-6 space-y-2">
        <FileText className="w-8 h-8 mx-auto opacity-40 text-[var(--text-subtle)]" />
        <p className="font-medium text-[var(--text-secondary)]">No workspace files found</p>
        <p className="text-[11px]">No tracked files detected in {activeProject?.name || 'this project'}.</p>
      </div>
    )
  }

  return (
    <div className="p-3 space-y-3 text-xs flex flex-col h-full overflow-hidden">
      {/* Search files */}
      <div className="relative flex-shrink-0">
        <label htmlFor="filter-workspace-files-input" className="sr-only">
          Filter workspace files
        </label>
        <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-subtle)]" aria-hidden="true" />
        <Input
          id="filter-workspace-files-input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter workspace files..."
          className="h-7 pl-8 text-xs bg-[var(--surface-secondary)]"
        />
      </div>

      {/* File Tree List */}
      <div className="space-y-1 max-h-48 overflow-y-auto border border-[var(--border)] rounded-md p-1 bg-[var(--surface-primary)] flex-shrink-0">
        {filteredFiles.map(file => {
          const isSelected = selectedFile && file.path === selectedFile.path
          return (
            <button
              key={file.path}
              type="button"
              onClick={() => setSelectedFile(file)}
              aria-label={`Select file: ${file.path}`}
              className={`w-full flex items-center justify-between p-1.5 rounded cursor-pointer transition-colors font-mono text-[11px] text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
                isSelected
                  ? 'bg-[var(--accent-subtle)] text-[var(--accent)] font-semibold'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]'
              }`}
            >
              <div className="flex items-center gap-1.5 truncate">
                <FileText className="w-3.5 h-3.5 flex-shrink-0" />
                <span className="truncate">{file.path}</span>
              </div>
              <span className="text-[10px] text-[var(--text-subtle)] ml-1 flex-shrink-0">
                {file.lines > 0 ? `${file.lines}L · ` : ''}{file.size}
              </span>
            </button>
          )
        })}
      </div>

      {/* Selected File Details & Preview */}
      {selectedFile ? (
        <div className="flex-1 border border-[var(--border)] rounded-md bg-[var(--surface-primary)] flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--border)] bg-[var(--surface-secondary)]/50">
            <div className="flex items-center gap-2 truncate">
              <FileText className="w-3.5 h-3.5 text-[var(--accent)] flex-shrink-0" />
              <span className="font-mono text-xs font-semibold text-[var(--text-primary)] truncate">{selectedFile.path}</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-[var(--surface-primary)] border border-[var(--border)] text-[var(--text-secondary)] uppercase font-mono">
                {selectedFile.type}
              </span>
            </div>

            <button
              onClick={handleCopyPath}
              className="p-1 rounded text-[var(--text-subtle)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] cursor-pointer"
              title="Copy file path"
              aria-label="Copy file path"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-[var(--success)]" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>

          <div className="p-3 font-mono text-[11px] leading-relaxed bg-[var(--code-bg)] text-[var(--text-primary)] overflow-y-auto flex-1 whitespace-pre">
            {`# ${selectedFile.path}
# Type: ${selectedFile.type} | Size: ${selectedFile.size} | Lines: ${selectedFile.lines}
# Project: ${activeProject?.name || 'Workspace'}

"""
Workspace file inspection preview.
Protected under workspace boundary.
"""`}
          </div>
        </div>
      ) : (
        <div className="flex-1 border border-[var(--border)] rounded-md bg-[var(--surface-primary)] flex items-center justify-center text-xs text-[var(--text-subtle)]">
          Select a file to preview
        </div>
      )}
    </div>
  )
}
