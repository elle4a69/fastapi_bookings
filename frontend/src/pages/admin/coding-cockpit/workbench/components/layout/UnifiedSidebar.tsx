import React, { useState } from 'react'
import {
  FolderGit2,
  FolderPlus,
  Plus,
  Search,
  ChevronDown,
  ChevronRight,
  Sparkles,
  Settings,
  Trash2,
  Pin,
  RefreshCw,
  Loader2,
  PanelLeftClose,
  MoreVertical,
  Headphones,
  X
} from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import type { Thread } from '../../types/workbench'
import {
  CODEX_MODELS,
  getLastUsedCodexModel,
  setLastUsedCodexModel,
} from '../../modelCatalog'

interface UnifiedSidebarProps {
  onSelectThreadMobile?: () => void
}

export const UnifiedSidebar: React.FC<UnifiedSidebarProps> = ({ onSelectThreadMobile }) => {
  const {
    state,
    selectProject,
    selectThread,
    createProject,
    createThread,
    deleteThread,
    renameThread,
    pinThread,
    archiveThread,
    setSidebarOpen,
    setThreadSearchQuery,
    setAppMode,
    retryConnection,
    fetchBoundaries,
    addBoundary,
    removeBoundary,
    fetchTelemetrySettings,
    updateTelemetrySettings,
    testTelemetry,
    setActiveToolModal
  } = useWorkbenchStore()

  // Expanded project tree items in local state (active project always expanded by default)
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {}
    state.projects.forEach(p => {
      init[p.id] = true
    })
    if (state.activeProjectId) {
      init[state.activeProjectId] = true
    }
    return init
  })

  // Modals state
  const [isNewProjectOpen, setIsNewProjectOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectRepo, setNewProjectRepo] = useState('')
  const [newProjectError, setNewProjectError] = useState('')

  const [isNewThreadOpen, setIsNewThreadOpen] = useState(false)
  const [targetProjectIdForThread, setTargetProjectIdForThread] = useState<string>('')
  const [newThreadTitle, setNewThreadTitle] = useState('')
  const [newThreadModel, setNewThreadModel] = useState(getLastUsedCodexModel)
  const [newThreadError, setNewThreadError] = useState('')

  const [isRenameThreadOpen, setIsRenameThreadOpen] = useState(false)
  const [threadToRename, setThreadToRename] = useState<Thread | null>(null)
  const [renameTitle, setRenameTitle] = useState('')

  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [settingsTab, setSettingsTab] = useState<'boundaries' | 'telemetry' | 'system'>('boundaries')
  const [newBoundaryPath, setNewBoundaryPath] = useState('')
  const [newBoundaryName, setNewBoundaryName] = useState('')
  const [boundaryError, setBoundaryError] = useState('')
  const [telemetrySignoz, setTelemetrySignoz] = useState('')
  const [telemetryOtlp, setTelemetryOtlp] = useState('')
  const [isTestingTelemetry, setIsTestingTelemetry] = useState(false)
  const [telemetryFeedback, setTelemetryFeedback] = useState<string | null>(null)

  const toggleProject = (projectId: string) => {
    setExpandedProjects(prev => ({
      ...prev,
      [projectId]: !prev[projectId]
    }))
  }

  const handleOpenNewThread = (projectId: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    setTargetProjectIdForThread(projectId)
    setNewThreadTitle('')
    setNewThreadModel(getLastUsedCodexModel())
    setNewThreadError('')
    setIsNewThreadOpen(true)
  }

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newProjectName.trim()) {
      setNewProjectError('Project name is required')
      return
    }
    try {
      const proj = await createProject(newProjectName.trim(), newProjectRepo.trim())
      setExpandedProjects(prev => ({ ...prev, [proj.id]: true }))
      setIsNewProjectOpen(false)
      setNewProjectName('')
      setNewProjectRepo('')
      setNewProjectError('')
    } catch (err: any) {
      setNewProjectError(err.message || 'Failed to create project')
    }
  }

  const handleCreateThread = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newThreadTitle.trim()) {
      setNewThreadError('Thread title is required')
      return
    }
    const projId = targetProjectIdForThread || state.activeProjectId || state.projects[0]?.id
    if (!projId) {
      setNewThreadError('A project must be selected first')
      return
    }
    try {
      selectProject(projId)
      const thread = await createThread(newThreadTitle.trim(), newThreadModel)
      if (thread && thread.id) {
        selectThread(thread.id)
      }
      setIsNewThreadOpen(false)
      setNewThreadTitle('')
      setNewThreadError('')
      onSelectThreadMobile?.()
    } catch (err: any) {
      setNewThreadError(err.message || 'Failed to create thread')
    }
  }

  const handleOpenRename = (thread: Thread, e?: React.MouseEvent) => {
    e?.stopPropagation()
    setThreadToRename(thread)
    setRenameTitle(thread.title)
    setIsRenameThreadOpen(true)
  }

  const handleSaveRename = (e: React.FormEvent) => {
    e.preventDefault()
    if (threadToRename && renameTitle.trim()) {
      renameThread(threadToRename.id, renameTitle.trim())
      setIsRenameThreadOpen(false)
      setThreadToRename(null)
    }
  }

  // Filter threads by search query
  const query = state.threadSearchQuery.trim().toLowerCase()
  const getFilteredThreadsForProject = (projId: string) => {
    const threads = state.threads.filter(t => t.projectId === projId)
    if (!query) return threads
    return threads.filter(t =>
      t.title.toLowerCase().includes(query) ||
      t.model.toLowerCase().includes(query) ||
      t.status.toLowerCase().includes(query)
    )
  }

  // Telemetry modal helpers
  const handleOpenSettings = async () => {
    setIsSettingsOpen(true)
    await fetchBoundaries()
    await fetchTelemetrySettings()
    if (state.telemetrySettings) {
      setTelemetrySignoz(state.telemetrySettings.signoz_url)
      setTelemetryOtlp(state.telemetrySettings.otlp_endpoint)
    }
  }

  const handleAddBoundary = async () => {
    if (!newBoundaryPath.trim()) {
      setBoundaryError('Filesystem path is required')
      return
    }
    setBoundaryError('')
    await addBoundary(newBoundaryPath.trim(), newBoundaryName.trim() || undefined)
    setNewBoundaryPath('')
    setNewBoundaryName('')
  }

  const handleTestTelemetry = async () => {
    setIsTestingTelemetry(true)
    setTelemetryFeedback(null)
    try {
      const res = await testTelemetry(telemetryOtlp || undefined)
      if (res.connected) {
        setTelemetryFeedback(`Connected to SigNoz (${res.latency_ms}ms latency)`)
      } else {
        setTelemetryFeedback(`Connection failed: ${(res as any).error || (res as any).status || 'Endpoint unreachable'}`)
      }
    } catch (err: any) {
      setTelemetryFeedback(`Error testing telemetry: ${err.message}`)
    } finally {
      setIsTestingTelemetry(false)
    }
  }

  const handleSaveTelemetry = async () => {
    await updateTelemetrySettings({
      signoz_url: telemetrySignoz || 'http://localhost:3301',
      otlp_endpoint: telemetryOtlp || 'http://localhost:4318',
      enabled: true
    })
    setIsSettingsOpen(false)
  }

  return (
    <aside
      className="flex flex-col h-full w-full bg-card border-r border-border text-card-foreground select-none overflow-hidden"
      aria-label="Unified Project and Thread Workspace"
    >
      {/* 1. Header: Brand, Connection & + New Project (Standardized h-11 slim header) */}
      <div className="h-11 px-3 border-b border-border bg-card/95 backdrop-blur-xs flex items-center justify-between gap-2 shrink-0 box-border">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-md bg-primary/10 text-primary border border-primary/20 flex items-center justify-center shrink-0">
            <FolderGit2 className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-semibold text-foreground truncate flex items-center gap-1.5 m-0 leading-tight">
              <span>Projects & Threads</span>
            </h2>
            <div className="flex items-center gap-1.5 text-[9px] text-muted-foreground font-mono leading-none">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  state.connectionStatus === 'connected'
                    ? 'bg-emerald-400'
                    : state.connectionStatus === 'connecting'
                    ? 'bg-amber-400 animate-pulse'
                    : 'bg-rose-400'
                }`}
              />
              <span className="capitalize">{state.connectionStatus}</span>
              {state.appMode === 'demo' && (
                <span className="px-1 py-0.2 rounded bg-blue-500/20 text-blue-300 text-[8px] uppercase font-semibold">
                  Demo
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              setNewProjectName('')
              setNewProjectRepo('')
              setNewProjectError('')
              setIsNewProjectOpen(true)
            }}
            className="h-7 px-2 text-xs gap-1 bg-slate-800 hover:bg-slate-700 text-foreground border-border hover:text-white cursor-pointer"
            title="Register a new engineering project target"
          >
            <Plus className="w-3.5 h-3.5 text-primary" />
            <span className="hidden sm:inline">Project</span>
          </Button>

          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setActiveToolModal('support_tickets')}
            className="h-7 px-2 text-xs gap-1 bg-slate-800 hover:bg-slate-700 text-foreground border-border hover:text-white cursor-pointer"
            title="Open Inbound Support Tickets Review Queue"
          >
            <Headphones className="w-3.5 h-3.5 text-emerald-400" />
            <span className="hidden sm:inline">Tickets</span>
          </Button>

          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => setSidebarOpen(false)}
            className="h-7 w-7 text-muted-foreground hover:text-foreground hover:bg-muted hidden md:flex cursor-pointer"
            aria-label="Collapse Left Sidebar"
            title="Collapse sidebar (Ctrl+B)"
          >
            <PanelLeftClose className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* 2. Search & Filter Bar */}
      <div className="p-2.5 border-b border-border bg-muted/20 shrink-0">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <Input
            value={state.threadSearchQuery}
            onChange={(e) => setThreadSearchQuery(e.target.value)}
            placeholder="Search conversations & threads..."
            className="h-8 pl-8 pr-7 text-xs bg-slate-950/60 border-border text-foreground placeholder:text-muted-foreground focus-visible:ring-indigo-500"
          />
          {state.threadSearchQuery && (
            <button
              onClick={() => setThreadSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5"
              aria-label="Clear search"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* 3. Nested Tree of Projects & Conversations */}
      <ScrollArea className="flex-1 overflow-y-auto">
        <div className="p-2 space-y-1">
          {state.projects.length === 0 ? (
            <div className="p-6 text-center text-xs text-muted-foreground space-y-3">
              <FolderGit2 className="w-8 h-8 text-muted-foreground/60 mx-auto" />
              <p className="font-medium text-foreground">No Projects Registered</p>
              <p className="text-[11px] text-muted-foreground max-w-[200px] mx-auto">
                Add an engineering project repository target to begin autonomous agent work.
              </p>
              <Button
                size="sm"
                onClick={() => setIsNewProjectOpen(true)}
                className="w-full text-xs bg-indigo-600 hover:bg-indigo-500 text-white"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                New Project
              </Button>
            </div>
          ) : (
            state.projects.map((proj) => {
              const isExpanded = Boolean(expandedProjects[proj.id])
              const isProjActive = state.activeProjectId === proj.id
              const projThreads = getFilteredThreadsForProject(proj.id)

              return (
                <Collapsible
                  key={proj.id}
                  open={isExpanded}
                  onOpenChange={() => toggleProject(proj.id)}
                  className="rounded-lg border border-border/80 bg-slate-950/40 overflow-hidden"
                >
                  {/* Project Row Header */}
                  <div
                    onClick={() => selectProject(proj.id)}
                    className={`group flex items-center justify-between px-2.5 py-2 cursor-pointer transition-colors ${
                      isProjActive
                        ? 'bg-indigo-950/30 border-l-2 border-indigo-500 text-foreground'
                        : 'hover:bg-muted/60 text-foreground'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <CollapsibleTrigger asChild onClick={(e) => e.stopPropagation()}>
                        <button
                          className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-transform"
                          aria-label={isExpanded ? 'Collapse project' : 'Expand project'}
                        >
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </CollapsibleTrigger>

                      <FolderGit2
                        className={`w-4 h-4 shrink-0 ${
                          isProjActive ? 'text-primary' : 'text-muted-foreground'
                        }`}
                      />

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-semibold truncate leading-tight">
                            {proj.name}
                          </span>
                        </div>
                        <p className="text-[10px] text-muted-foreground truncate font-mono">
                          {proj.repo_path || proj.repository}
                        </p>
                      </div>
                    </div>

                    {/* Right actions on project header */}
                    <div className="flex items-center gap-1 shrink-0 ml-1">
                      <Badge
                        variant="secondary"
                        className="text-[10px] h-5 px-1.5 font-mono bg-slate-800 text-foreground border-border"
                      >
                        {projThreads.length}
                      </Badge>

                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              onClick={(e) => handleOpenNewThread(proj.id, e)}
                              className="w-7 h-7 flex items-center justify-center rounded hover:bg-indigo-600/20 text-muted-foreground hover:text-primary opacity-80 group-hover:opacity-100 transition-opacity"
                              aria-label="New thread in this project"
                            >
                              <Plus className="w-3.5 h-3.5" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top">New Conversation Thread</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                  </div>

                  {/* Expandable Nested Threads Tree */}
                  <CollapsibleContent>
                    <div className="pl-6 pr-2 py-1 space-y-0.5 border-t border-border/60 bg-slate-950/70">
                      {projThreads.length === 0 ? (
                        <div className="py-2.5 px-2 text-[11px] text-muted-foreground flex items-center justify-between">
                          <span>No threads matching filter</span>
                          <button
                            onClick={() => handleOpenNewThread(proj.id)}
                            className="text-primary hover:underline text-[11px]"
                          >
                            + Start one
                          </button>
                        </div>
                      ) : (
                        projThreads.map((thread) => {
                          const isThreadActive = state.activeThreadId === thread.id
                          const isStreaming = state.streamingTurnIdByThread[thread.id]

                          return (
                            <div
                              key={thread.id}
                              onClick={() => {
                                selectProject(proj.id)
                                selectThread(thread.id)
                                onSelectThreadMobile?.()
                              }}
                              className={`group relative flex items-center justify-between px-2 py-1.5 rounded-md cursor-pointer text-xs transition-all ${
                                isThreadActive
                                  ? 'bg-indigo-600/20 text-foreground border border-indigo-500/40 shadow-xs'
                                  : 'hover:bg-muted/60 text-foreground hover:text-white'
                              }`}
                            >
                              {/* Left status & title */}
                              <div className="flex items-center gap-2 min-w-0 flex-1">
                                {isStreaming ? (
                                  <span className="relative flex h-2 w-2 shrink-0">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                                  </span>
                                ) : thread.status === 'needs_approval' ? (
                                  <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
                                ) : thread.isPinned ? (
                                  <Pin className="w-3 h-3 text-amber-400 shrink-0" />
                                ) : (
                                  <span className="w-1.5 h-1.5 rounded-full bg-slate-600 shrink-0 group-hover:bg-slate-400" />
                                )}

                                <div className="min-w-0 flex-1">
                                  <span className="truncate block font-medium leading-tight">
                                    {thread.title}
                                  </span>
                                  <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mt-0.5">
                                    <span>{thread.model}</span>
                                    <span>•</span>
                                    <span>{thread.turns?.length || 0} turns</span>
                                  </div>
                                </div>
                              </div>

                              {/* Right Dropdown Menu for Thread Actions */}
                              <div
                                className="shrink-0 ml-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <button
                                      className="w-6 h-6 flex items-center justify-center rounded hover:bg-slate-700 text-muted-foreground hover:text-foreground"
                                      aria-label="Thread actions"
                                    >
                                      <MoreVertical className="w-3 h-3" />
                                    </button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end" className="w-44 bg-card border-border text-foreground text-xs">
                                    <DropdownMenuItem onClick={() => handleOpenRename(thread)}>
                                      Rename conversation
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => pinThread(thread.id)}>
                                      {thread.isPinned ? 'Unpin thread' : 'Pin thread'}
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => archiveThread(thread.id)}>
                                      {thread.isArchived ? 'Unarchive thread' : 'Archive thread'}
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator className="bg-slate-800" />
                                    <DropdownMenuItem
                                      onClick={() => deleteThread(thread.id)}
                                      className="text-rose-400 focus:text-rose-400"
                                    >
                                      Delete conversation
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </div>
                            </div>
                          )
                        })
                      )}
                    </div>
                  </CollapsibleContent>
                </Collapsible>
              )
            })
          )}
        </div>
      </ScrollArea>

      {/* 4. Footer: Settings, App Mode & Status */}
      <div className="p-3 border-t border-border bg-card/90 backdrop-blur-xs flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={handleOpenSettings}
            className="h-8 px-2.5 text-xs gap-1.5 text-foreground hover:text-white hover:bg-muted"
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Settings</span>
          </Button>

          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setAppMode(state.appMode === 'live' ? 'demo' : 'live')}
            className={`h-8 px-2 text-[11px] font-mono border ${
              state.appMode === 'demo'
                ? 'border-blue-500/40 text-blue-300 bg-blue-500/10 hover:bg-blue-500/20'
                : 'border-border text-foreground hover:bg-muted'
            }`}
          >
            {state.appMode === 'demo' ? 'DEMO' : 'LIVE'}
          </Button>
        </div>

        {state.connectionStatus !== 'connected' && (
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={retryConnection}
            className="h-8 w-8 text-amber-400 hover:text-amber-300 hover:bg-muted"
            title="Reconnect to event stream"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        )}
      </div>

      {/* Dialog 1: Register New Project */}
      <Dialog open={isNewProjectOpen} onOpenChange={setIsNewProjectOpen}>
        <DialogContent className="max-w-md bg-card border-border text-foreground p-6">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold flex items-center gap-2">
              <FolderPlus className="w-5 h-5 text-primary" />
              <span>Register Engineering Project</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Attach a local repository path or worktree root for autonomous agent tasks and AST supervision.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateProject} className="space-y-4 py-2">
            <div>
              <label className="text-xs font-medium text-foreground block mb-1">
                Project Name
              </label>
              <Input
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="e.g. FastAPI Bookings"
                className="bg-background border-border text-foreground text-xs"
                autoFocus
              />
            </div>

            <div>
              <label className="text-xs font-medium text-foreground block mb-1">
                Repository / Workspace Directory
              </label>
              <Input
                value={newProjectRepo}
                onChange={(e) => setNewProjectRepo(e.target.value)}
                placeholder="e.g. F:\Projects\fastapi_bookings"
                className="bg-background border-border text-foreground text-xs font-mono"
              />
              <p className="text-[11px] text-muted-foreground mt-1">
                Target worktree for isolated branches, tool executions, and diff proposals.
              </p>
            </div>

            {newProjectError && (
              <p className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 p-2 rounded">
                {newProjectError}
              </p>
            )}

            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setIsNewProjectOpen(false)}
                className="text-xs text-muted-foreground hover:text-white"
              >
                Cancel
              </Button>
              <Button type="submit" className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white">
                Register Target
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Dialog 2: Create New Thread */}
      <Dialog open={isNewThreadOpen} onOpenChange={setIsNewThreadOpen}>
        <DialogContent className="max-w-md bg-card border-border text-foreground p-6">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary" />
              <span>New Autonomous Thread</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Launch a new reasoning and coding turn under the selected project worktree.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateThread} className="space-y-4 py-2">
            <div>
              <label className="text-xs font-medium text-foreground block mb-1">
                Conversation / Task Title
              </label>
              <Input
                value={newThreadTitle}
                onChange={(e) => setNewThreadTitle(e.target.value)}
                placeholder="e.g. Implement OTel distributed tracing for SMS webhooks"
                className="bg-background border-border text-foreground text-xs"
                autoFocus
              />
            </div>

            <div>
              <label className="text-xs font-medium text-foreground block mb-1">
                Language Model
              </label>
              <select
                value={newThreadModel}
                onChange={(e) => setNewThreadModel(setLastUsedCodexModel(e.target.value))}
                className="w-full h-9 rounded-md bg-slate-950 border border-border text-foreground text-xs px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {CODEX_MODELS.map(model => (
                  <option key={model.id} value={model.id}>{model.label} — {model.description}</option>
                ))}
              </select>
            </div>

            {newThreadError && (
              <p className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 p-2 rounded">
                {newThreadError}
              </p>
            )}

            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setIsNewThreadOpen(false)}
                className="text-xs text-muted-foreground hover:text-white"
              >
                Cancel
              </Button>
              <Button type="submit" className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white">
                Start Conversation
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Dialog 3: Rename Thread */}
      <Dialog open={isRenameThreadOpen} onOpenChange={setIsRenameThreadOpen}>
        <DialogContent className="max-w-md bg-card border-border text-foreground p-6">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold">Rename Conversation</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSaveRename} className="space-y-4 py-2">
            <Input
              value={renameTitle}
              onChange={(e) => setRenameTitle(e.target.value)}
              className="bg-background border-border text-foreground text-xs"
              autoFocus
            />
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setIsRenameThreadOpen(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button type="submit" className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white">
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Dialog 4: Cockpit Settings (Boundaries & Telemetry) */}
      <Dialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
        <DialogContent className="max-w-lg bg-card border-border text-foreground p-6">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold flex items-center gap-2">
              <Settings className="w-5 h-5 text-primary" />
              <span>Cockpit Settings & Boundaries</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Manage filesystem boundary access controls and SigNoz OpenTelemetry tracing sentinels.
            </DialogDescription>
          </DialogHeader>

          {/* Settings Tabs */}
          <div className="flex border-b border-border gap-4 mt-2">
            <button
              onClick={() => setSettingsTab('boundaries')}
              className={`pb-2 text-xs font-medium border-b-2 transition-colors ${
                settingsTab === 'boundaries'
                  ? 'border-indigo-500 text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              Workspace Boundaries
            </button>
            <button
              onClick={() => setSettingsTab('telemetry')}
              className={`pb-2 text-xs font-medium border-b-2 transition-colors ${
                settingsTab === 'telemetry'
                  ? 'border-indigo-500 text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              OTel Telemetry
            </button>
          </div>

          <div className="py-4">
            {settingsTab === 'boundaries' ? (
              <div className="space-y-4">
                <p className="text-xs text-foreground leading-relaxed">
                  Workspace boundaries restrict Codex mutations and file reads strictly to authorized paths.
                </p>

                <div className="space-y-2">
                  {state.boundaries.map((b) => (
                    <div
                      key={b.id}
                      className="p-2.5 rounded-lg border border-border bg-slate-950/60 flex items-center justify-between text-xs"
                    >
                      <div className="min-w-0 flex-1 pr-2">
                        <div className="font-medium text-foreground truncate">{b.name}</div>
                        <div className="text-[11px] font-mono text-muted-foreground truncate">{b.path}</div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {b.is_default && (
                          <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-400">
                            Default
                          </Badge>
                        )}
                        {!b.is_default && (
                          <button
                            onClick={() => removeBoundary(b.id)}
                            className="p-1 text-muted-foreground hover:text-rose-400"
                            title="Remove boundary"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="pt-2 border-t border-border space-y-2">
                  <div className="text-xs font-medium text-foreground">Add Authorized Boundary Path</div>
                  <Input
                    value={newBoundaryPath}
                    onChange={(e) => setNewBoundaryPath(e.target.value)}
                    placeholder="Path, e.g. F:\Projects\fastapi_bookings"
                    className="h-8 text-xs bg-background border-border text-foreground font-mono"
                  />
                  <div className="flex gap-2">
                    <Input
                      value={newBoundaryName}
                      onChange={(e) => setNewBoundaryName(e.target.value)}
                      placeholder="Display label (optional)"
                      className="h-8 text-xs bg-background border-border text-foreground flex-1"
                    />
                    <Button
                      size="sm"
                      onClick={handleAddBoundary}
                      className="h-8 text-xs bg-indigo-600 hover:bg-indigo-500 text-white"
                    >
                      Add
                    </Button>
                  </div>
                  {boundaryError && <p className="text-xs text-rose-400">{boundaryError}</p>}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">
                    SigNoz UI Dashboard URL
                  </label>
                  <Input
                    value={telemetrySignoz}
                    onChange={(e) => setTelemetrySignoz(e.target.value)}
                    placeholder="http://localhost:3301"
                    className="h-8 text-xs bg-background border-border text-foreground font-mono"
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">
                    OTLP Collector Endpoint
                  </label>
                  <Input
                    value={telemetryOtlp}
                    onChange={(e) => setTelemetryOtlp(e.target.value)}
                    placeholder="http://localhost:4318"
                    className="h-8 text-xs bg-background border-border text-foreground font-mono"
                  />
                </div>

                {telemetryFeedback && (
                  <p className="text-xs p-2 rounded bg-slate-950 border border-border text-foreground">
                    {telemetryFeedback}
                  </p>
                )}

                <div className="flex justify-between items-center pt-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={handleTestTelemetry}
                    disabled={isTestingTelemetry}
                    className="text-xs border-border text-foreground hover:bg-muted"
                  >
                    {isTestingTelemetry ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
                    Test Sentinel Connectivity
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleSaveTelemetry}
                    className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white"
                  >
                    Save Telemetry Config
                  </Button>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsSettingsOpen(false)}
              className="text-xs text-muted-foreground"
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  )
}
