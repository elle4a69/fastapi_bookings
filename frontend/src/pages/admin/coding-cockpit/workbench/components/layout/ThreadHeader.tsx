import React, { useState } from 'react'
import {
  Menu,
  PanelLeft,
  SlidersHorizontal,
  FileCode2,
  Terminal,
  Square,
  Check,
  Pin,
  FolderGit2
} from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'

export const ThreadHeader: React.FC = () => {
  const {
    state,
    activeProject,
    activeThread,
    stopActiveTurn,
    renameThread,
    setSidebarOpen,
    setInspectorOpen,
    setInspectorTab,
    toggleBottomDock,
    setDiffStudioOpen
  } = useWorkbenchStore()

  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editedTitle, setEditedTitle] = useState('')

  const handleStartEdit = () => {
    if (activeThread) {
      setEditedTitle(activeThread.title)
      setIsEditingTitle(true)
    }
  }

  const handleSaveTitle = () => {
    if (activeThread && editedTitle.trim()) {
      renameThread(activeThread.id, editedTitle.trim())
    }
    setIsEditingTitle(false)
  }

  const isStreaming = state.isStreaming
  const hasInProgress = Boolean(activeThread?.turns?.some(t => t.status === 'in_progress'))
  const isAgentWorking = isStreaming || hasInProgress
  const actionText = state.currentActionText || 'Thinking...'
  const elapsed = state.turnElapsedSeconds || 0

  return (
    <header
      className="flex items-center justify-between px-2.5 sm:px-4 py-2 border-b border-slate-800 bg-slate-900 text-slate-100 shrink-0 min-h-[50px] w-full max-w-full overflow-hidden select-none z-20"
      aria-label="Active Agent HUD and Workspace Header"
    >
      {/* 1. Left: Sidebar Toggle, Project & Thread Title */}
      <div className="flex items-center gap-2 min-w-0 flex-1 mr-2">
        {/* Toggle Left Sidebar */}
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={() => setSidebarOpen(!state.isSidebarOpen)}
          className="min-h-[44px] min-w-[44px] sm:h-8 sm:w-8 text-slate-300 hover:text-white hover:bg-slate-800 shrink-0"
          aria-label={state.isSidebarOpen ? 'Hide left sidebar' : 'Show left sidebar'}
          title="Toggle Sidebar (Ctrl+B)"
        >
          <Menu className="w-5 h-5 sm:hidden" />
          <PanelLeft className="w-4 h-4 hidden sm:block" />
        </Button>

        {/* Project & Thread Identity */}
        <div className="min-w-0 flex-1 flex items-center gap-1.5">
          {activeProject && (
            <span className="hidden md:inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded shrink-0">
              <FolderGit2 className="w-3 h-3 text-indigo-400" />
              <span className="truncate max-w-[120px]">{activeProject.name}</span>
              <span className="text-slate-600">/</span>
            </span>
          )}

          {activeThread ? (
            isEditingTitle ? (
              <div className="flex items-center gap-1 flex-1 max-w-sm">
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSaveTitle()}
                  autoFocus
                  className="h-7 text-xs bg-slate-950 border border-slate-700 rounded px-2 text-white w-full focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
                <Button size="icon" variant="ghost" onClick={handleSaveTitle} className="h-7 w-7 text-emerald-400">
                  <Check className="w-3.5 h-3.5" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 min-w-0">
                <h1
                  onClick={handleStartEdit}
                  title="Click to rename"
                  className="text-xs sm:text-sm font-semibold text-slate-100 truncate cursor-pointer hover:text-indigo-300 transition-colors m-0 leading-tight"
                >
                  {activeThread.title}
                </h1>
                {activeThread.isPinned && (
                  <Pin className="w-3 h-3 text-amber-400 shrink-0" />
                )}
                <span className="hidden lg:inline text-[10px] font-mono text-slate-400 px-1.5 py-0.2 rounded bg-slate-800 border border-slate-700">
                  {activeThread.model}
                </span>
              </div>
            )
          ) : (
            <span className="text-xs text-slate-400 font-medium truncate">
              {state.projects.length === 0 ? 'No projects connected' : 'Select or create a conversation'}
            </span>
          )}
        </div>
      </div>

      {/* 2. Center: Active Agent HUD Pill */}
      <div className="hidden sm:flex items-center justify-center shrink-0 mx-2">
        {isAgentWorking ? (
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs shadow-xs">
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            <span className="font-semibold text-[11px] truncate max-w-[220px]">
              {actionText}
            </span>
            <span className="font-mono text-[10px] text-emerald-400/80">
              ({elapsed}s)
            </span>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={stopActiveTurn}
              className="h-5 w-5 rounded-full text-rose-400 hover:text-rose-300 hover:bg-rose-500/20"
              title="Stop agent turn"
            >
              <Square className="w-2.5 h-2.5 fill-current" />
            </Button>
          </div>
        ) : activeThread?.status === 'needs_approval' ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-950/60 border border-amber-500/40 text-amber-300 text-xs">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="font-semibold text-[11px]">Approval Required</span>
          </div>
        ) : (
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-slate-800/60 border border-slate-700/60 text-slate-400 text-[11px]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>Agent Ready</span>
          </div>
        )}
      </div>

      {/* 3. Right: Action Buttons (Diffs, Dock, Inspector) */}
      <div className="flex items-center gap-1 shrink-0">
        {/* Mobile Agent Status indicator when working */}
        {isAgentWorking && (
          <div className="flex sm:hidden items-center gap-1 px-2 py-1 rounded bg-emerald-950 border border-emerald-500/40 text-emerald-300 text-[10px] mr-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            <span>{elapsed}s</span>
            <button onClick={stopActiveTurn} className="p-0.5 text-rose-400">
              <Square className="w-2.5 h-2.5 fill-current" />
            </button>
          </div>
        )}

        {/* Diff Review Studio Launcher */}
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            if (state.diffFiles.length > 0) {
              setDiffStudioOpen(true)
            } else {
              setInspectorTab('changes')
            }
          }}
          className="min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 sm:h-8 px-2 sm:px-2.5 text-xs gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 hover:text-white"
          title="Review uncommitted diffs"
        >
          <FileCode2 className="w-3.5 h-3.5 text-indigo-400" />
          <span className="hidden sm:inline">Diffs</span>
          {state.diffFiles.length > 0 && (
            <Badge
              variant="secondary"
              className="h-4 px-1 text-[10px] bg-indigo-500/20 text-indigo-300 border-indigo-500/30 font-mono"
            >
              {state.diffFiles.length}
            </Badge>
          )}
        </Button>

        {/* Toggle Bottom Console Dock */}
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={toggleBottomDock}
          className={`min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 sm:h-8 sm:w-8 ${
            state.isBottomDockOpen
              ? 'bg-slate-800 text-indigo-400 border border-indigo-500/30'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
          title="Toggle Bottom Console Dock"
        >
          <Terminal className="w-4 h-4" />
        </Button>

        {/* Toggle Right Inspector */}
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={() => setInspectorOpen(!state.isInspectorOpen)}
          className={`min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 sm:h-8 sm:w-8 ${
            state.isInspectorOpen
              ? 'bg-slate-800 text-indigo-400 border border-indigo-500/30'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
          title="Toggle Inspector & Changes"
        >
          <SlidersHorizontal className="w-4 h-4" />
        </Button>
      </div>
    </header>
  )
}
export default ThreadHeader
