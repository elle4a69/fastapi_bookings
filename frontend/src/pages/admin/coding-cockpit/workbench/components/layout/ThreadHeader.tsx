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
  FolderGit2,
  Cpu,
  ChevronDown,
  Wrench,
  Activity,
  Zap,
  BookOpen,
  Radio
} from 'lucide-react'
import { useWorkbenchStore, getSafeLocalStorage, setSafeLocalStorage } from '../../store/useWorkbenchStore'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger
} from '../ui/dropdown-menu'
import type { AgentStatusData } from '../../../types'

interface ThreadHeaderProps {
  statusData?: AgentStatusData | null
}

const AVAILABLE_MODELS = [
  { value: 'gpt-5.6-sol', label: 'gpt-5.6-sol (Default)' },
  { value: 'gpt-4o', label: 'gpt-4o' },
  { value: 'gpt-4o-mini', label: 'gpt-4o-mini' },
  { value: 'o3-mini', label: 'o3-mini (Reasoning)' },
  { value: 'o1', label: 'o1 (Deep Reasoning)' },
  { value: 'claude-3-5-sonnet', label: 'claude-3-5-sonnet' }
]

export const ThreadHeader: React.FC<ThreadHeaderProps> = ({ statusData }) => {
  const {
    state,
    activeProject,
    activeThread,
    stopActiveTurn,
    renameThread,
    setThreadModel,
    setSidebarOpen,
    setInspectorOpen,
    setInspectorTab,
    toggleBottomDock,
    setDiffStudioOpen,
    setActiveToolModal
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

  const [selectedStickyModel, setSelectedStickyModel] = useState<string>(() =>
    getSafeLocalStorage('codex_last_used_model', 'gpt-5.6-sol')
  )

  const currentModel = activeThread?.model || selectedStickyModel

  const handleSelectModel = (model: string) => {
    setSelectedStickyModel(model)
    setSafeLocalStorage('codex_last_used_model', model)
    if (activeThread) {
      setThreadModel(activeThread.id, model)
    }
  }

  const isStreaming = state.isStreaming
  const hasInProgress = Boolean(activeThread?.turns?.some(t => t.status === 'in_progress'))
  const isAgentWorking = isStreaming || hasInProgress
  const actionText = state.currentActionText || 'Thinking...'
  const elapsed = state.turnElapsedSeconds || 0

  return (
    <header
      className="h-11 px-3 border-b border-border bg-card/95 text-card-foreground flex items-center justify-between shrink-0 w-full max-w-full overflow-hidden select-none z-20 box-border"
      aria-label="Active Agent HUD and Workspace Header"
    >
      {/* 1. Left: Sidebar Toggle, Project & Thread Title, Interactive Model Selector */}
      <div className="flex items-center gap-2 min-w-0 flex-1 mr-2">
        {/* Toggle Left Sidebar */}
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={() => setSidebarOpen(!state.isSidebarOpen)}
          className="h-7 w-7 text-muted-foreground hover:text-foreground hover:bg-muted shrink-0 cursor-pointer"
          aria-label={state.isSidebarOpen ? 'Hide left sidebar' : 'Show left sidebar'}
          title="Toggle Sidebar (Ctrl+B)"
        >
          <Menu className="w-4 h-4 sm:hidden" />
          <PanelLeft className="w-4 h-4 hidden sm:block" />
        </Button>

        {/* Project & Thread Identity */}
        <div className="min-w-0 flex items-center gap-1.5">
          {activeProject && (
            <span className="hidden md:inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground bg-muted/80 px-1.5 py-0.5 rounded shrink-0">
              <FolderGit2 className="w-3 h-3 text-primary" />
              <span className="truncate max-w-[110px]">{activeProject.name}</span>
              <span className="text-muted-foreground/60">/</span>
            </span>
          )}

          {activeThread ? (
            isEditingTitle ? (
              <div className="flex items-center gap-1 flex-1 max-w-xs">
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSaveTitle()}
                  autoFocus
                  className="h-6 text-xs bg-background border border-border rounded px-1.5 text-foreground w-full focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <Button size="icon" variant="ghost" onClick={handleSaveTitle} className="h-6 w-6 text-emerald-500 cursor-pointer">
                  <Check className="w-3.5 h-3.5" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 min-w-0">
                <h1
                  onClick={handleStartEdit}
                  title="Click to rename"
                  className="text-xs sm:text-sm font-semibold text-foreground truncate cursor-pointer hover:text-primary transition-colors m-0 leading-tight"
                >
                  {activeThread.title}
                </h1>
                {activeThread.isPinned && (
                  <Pin className="w-3 h-3 text-amber-500 shrink-0" />
                )}
              </div>
            )
          ) : (
            <span className="text-xs text-muted-foreground font-medium truncate">
              {state.projects.length === 0 ? 'No projects connected' : 'Select or create a conversation'}
            </span>
          )}
        </div>

        {/* Interactive Sticky Model Selector Dropdown */}
        <div className="shrink-0 ml-1">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="inline-flex items-center gap-1.5 h-7 px-2 rounded-md bg-muted/80 hover:bg-muted border border-border text-[11px] font-mono text-foreground transition-colors cursor-pointer select-none"
                aria-label="Select AI Model"
                title="Active AI Model (Sticky)"
              >
                <Cpu className="w-3 h-3 text-primary" />
                <span className="truncate max-w-[90px] sm:max-w-none">{currentModel}</span>
                <ChevronDown className="w-3 h-3 text-muted-foreground opacity-70" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-52 bg-card border-border text-foreground text-xs">
              <DropdownMenuRadioGroup value={currentModel} onValueChange={handleSelectModel}>
                {AVAILABLE_MODELS.map((m) => (
                  <DropdownMenuRadioItem key={m.value} value={m.value} className="cursor-pointer">
                    {m.label}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* 2. Center: Active Agent HUD Pill */}
      <div className="hidden lg:flex items-center justify-center shrink-0 mx-2">
        {isAgentWorking ? (
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs shadow-xs h-7">
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            <span className="font-semibold text-[11px] truncate max-w-[180px]">
              {actionText}
            </span>
            <span className="font-mono text-[10px] opacity-80">
              ({elapsed}s)
            </span>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={stopActiveTurn}
              className="h-4 w-4 rounded-full text-rose-500 hover:text-rose-600 hover:bg-rose-500/20 cursor-pointer"
              title="Stop agent turn"
            >
              <Square className="w-2.5 h-2.5 fill-current" />
            </Button>
          </div>
        ) : activeThread?.status === 'needs_approval' ? (
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-xs h-7">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            <span className="font-semibold text-[11px]">Approval Required</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-muted/60 border border-border text-muted-foreground text-[11px] h-7">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>Agent Ready</span>
          </div>
        )}
      </div>

      {/* 3. Right: Secondary Tools Dropdown, Diffs, Terminal, Inspector */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* Mobile Agent Status indicator when working */}
        {isAgentWorking && (
          <div className="flex lg:hidden items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-[10px]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            <span>{elapsed}s</span>
            <button onClick={stopActiveTurn} className="p-0.5 text-rose-500 cursor-pointer">
              <Square className="w-2.5 h-2.5 fill-current" />
            </button>
          </div>
        )}

        {/* Secondary Engineering Tools Full-Screen Modal Launcher Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 px-2 text-xs gap-1.5 bg-background hover:bg-muted text-foreground border-border cursor-pointer"
              title="Open Secondary Engineering Tools"
            >
              <Wrench className="w-3.5 h-3.5 text-primary" />
              <span className="hidden sm:inline">Tools</span>
              <ChevronDown className="w-3 h-3 text-muted-foreground opacity-70" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56 bg-card border-border text-foreground text-xs">
            <DropdownMenuItem
              onClick={() => setActiveToolModal('health')}
              className="flex items-center justify-between gap-2 cursor-pointer hover:bg-muted py-1.5"
            >
              <span className="flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-emerald-500" />
                <span>SRE Health Sentinels</span>
              </span>
              {statusData && (
                <Badge variant="outline" className="text-[9px] h-4 px-1 border-emerald-500/40 text-emerald-500 bg-emerald-500/10">
                  {statusData.health_score ?? 100}%
                </Badge>
              )}
            </DropdownMenuItem>

            <DropdownMenuItem
              onClick={() => setActiveToolModal('fuzzer')}
              className="flex items-center gap-2 cursor-pointer hover:bg-muted py-1.5"
            >
              <Zap className="w-3.5 h-3.5 text-amber-500" />
              <span>Concurrency Stress Fuzzer</span>
            </DropdownMenuItem>

            <DropdownMenuItem
              onClick={() => setActiveToolModal('issues')}
              className="flex items-center justify-between gap-2 cursor-pointer hover:bg-muted py-1.5"
            >
              <span className="flex items-center gap-2">
                <Wrench className="w-3.5 h-3.5 text-primary" />
                <span>AST Issues Studio</span>
              </span>
              {(statusData?.active_issues?.length ?? 0) > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[9px] font-bold bg-amber-500/20 text-amber-500">
                  {statusData?.active_issues?.length}
                </span>
              )}
            </DropdownMenuItem>

            <DropdownMenuItem
              onClick={() => setActiveToolModal('skills')}
              className="flex items-center gap-2 cursor-pointer hover:bg-muted py-1.5"
            >
              <BookOpen className="w-3.5 h-3.5 text-purple-500" />
              <span>Skills Library</span>
            </DropdownMenuItem>

            <DropdownMenuItem
              onClick={() => setActiveToolModal('stream')}
              className="flex items-center gap-2 cursor-pointer hover:bg-muted py-1.5"
            >
              <Radio className="w-3.5 h-3.5 text-cyan-500" />
              <span>Event Stream</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

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
          className="h-7 px-2 text-xs gap-1.5 bg-background hover:bg-muted text-foreground border-border cursor-pointer"
          title="Review uncommitted diffs"
        >
          <FileCode2 className="w-3.5 h-3.5 text-primary" />
          <span className="hidden sm:inline">Diffs</span>
          {state.diffFiles.length > 0 && (
            <Badge
              variant="secondary"
              className="h-4 px-1 text-[10px] bg-primary/10 text-primary border-primary/20 font-mono"
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
          className={`h-7 w-7 cursor-pointer ${
            state.isBottomDockOpen
              ? 'bg-muted text-primary border border-primary/30'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          }`}
          title="Toggle Bottom Terminal Runner"
        >
          <Terminal className="w-3.5 h-3.5" />
        </Button>

        {/* Toggle Right Inspector */}
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={() => setInspectorOpen(!state.isInspectorOpen)}
          className={`h-7 w-7 cursor-pointer ${
            state.isInspectorOpen
              ? 'bg-muted text-primary border border-primary/30'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          }`}
          title="Toggle Inspector & Changes"
        >
          <SlidersHorizontal className="w-3.5 h-3.5" />
        </Button>
      </div>
    </header>
  )
}
export default ThreadHeader
