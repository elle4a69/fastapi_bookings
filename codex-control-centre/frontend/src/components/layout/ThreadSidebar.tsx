import React, { useState } from 'react'
import { 
  Plus, 
  Search, 
  Filter, 
  ChevronLeft, 
  Layers, 
  AlertTriangle, 
  Pin, 
  ChevronRight, 
  FolderGit2 
} from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { ThreadRow } from './ThreadRow'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { ScrollArea } from '../ui/scroll-area'
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuRadioGroup, 
  DropdownMenuRadioItem, 
  DropdownMenuTrigger 
} from '../ui/dropdown-menu'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog'

export const ThreadSidebar: React.FC = () => {
  const { 
    state, 
    activeProject, 
    projectThreads, 
    createThread, 
    setSidebarOpen, 
    setThreadSearchQuery, 
    setThreadStatusFilter 
  } = useWorkbenchStore()

  const [isNewThreadOpen, setIsNewThreadOpen] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newModel, setNewModel] = useState('gpt-4o')
  const [titleError, setTitleError] = useState('')

  if (!state.isSidebarOpen) {
    return (
      <div className="h-full border-r border-[var(--border)] bg-[var(--surface-primary)] flex items-center justify-center p-1">
        <button
          onClick={() => setSidebarOpen(true)}
          className="p-1.5 rounded-md hover:bg-[var(--surface-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
          aria-label="Expand Thread Sidebar"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    )
  }

  // Filter threads
  const filteredThreads = projectThreads.filter(thread => {
    // Search query filter
    if (state.threadSearchQuery) {
      const q = state.threadSearchQuery.toLowerCase()
      const matchesTitle = thread.title.toLowerCase().includes(q)
      const matchesModule = thread.module.toLowerCase().includes(q)
      const matchesBranch = thread.branch.toLowerCase().includes(q)
      if (!matchesTitle && !matchesModule && !matchesBranch) return false
    }

    // Status filter
    if (state.threadStatusFilter === 'needs_approval') {
      return thread.approvalCount > 0 || thread.status === 'needs_approval'
    }
    if (state.threadStatusFilter === 'active') {
      return thread.status === 'active'
    }
    if (state.threadStatusFilter === 'pinned') {
      return !!thread.isPinned
    }
    if (state.threadStatusFilter === 'archived') {
      return !!thread.isArchived || thread.status === 'archived'
    }
    if (state.threadStatusFilter === 'failed') {
      return thread.status === 'failed' || thread.status === 'interrupted'
    }

    // Default: hide archived unless viewing archived
    return !thread.isArchived
  })

  // Groupings
  const needsApprovalThreads = filteredThreads.filter(t => t.approvalCount > 0 || t.status === 'needs_approval')
  const pinnedThreads = filteredThreads.filter(t => t.isPinned && !needsApprovalThreads.includes(t))
  const activeThreads = filteredThreads.filter(t => t.status === 'active' && !needsApprovalThreads.includes(t) && !pinnedThreads.includes(t))
  const otherThreads = filteredThreads.filter(t => !needsApprovalThreads.includes(t) && !pinnedThreads.includes(t) && !activeThreads.includes(t))

  return (
    <>
      {/* Mobile backdrop for small viewport drawer */}
      <div 
        className="fixed inset-0 bg-black/50 z-30 md:hidden transition-opacity" 
        onClick={() => setSidebarOpen(false)} 
        aria-hidden="true" 
      />

      <nav
        style={{ width: `${state.sidebarWidth}px` }}
        className="fixed md:relative inset-y-0 left-0 z-40 flex flex-col h-full bg-[var(--surface-primary)] border-r border-[var(--border)] max-w-[85vw] sm:max-w-xs shadow-2xl md:shadow-none flex-shrink-0 overflow-hidden"
        aria-label="Threads Navigation"
      >
        {/* Header */}
        <div className="p-3 border-b border-[var(--border)] flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-1.5 min-w-0 font-semibold text-xs text-[var(--text-primary)] m-0">
              <FolderGit2 className="w-4 h-4 text-[var(--accent)] flex-shrink-0" />
              <span className="truncate">
                {activeProject?.name || 'Project Threads'}
              </span>
            </h2>

            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="secondary"
                className="h-7 px-2 text-xs gap-1 font-medium text-[var(--accent)]"
                onClick={() => setIsNewThreadOpen(true)}
              >
                <Plus className="w-3.5 h-3.5" />
                New
              </Button>
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-1 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                aria-label="Collapse sidebar"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Search & Filter bar */}
          <div className="flex items-center gap-1.5">
            <div className="relative flex-1">
              <label htmlFor="thread-search-input" className="sr-only">
                Search threads and branches
              </label>
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-subtle)]" aria-hidden="true" />
              <Input
                id="thread-search-input"
                value={state.threadSearchQuery}
                onChange={(e) => setThreadSearchQuery(e.target.value)}
                placeholder="Search threads, branches..."
                className="h-7 pl-8 text-xs bg-[var(--surface-secondary)] border-transparent focus:border-[var(--border)] focus:bg-[var(--surface-primary)]"
              />
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button 
                  size="sm" 
                  variant="ghost" 
                  className="h-7 w-7 p-0 text-[var(--text-secondary)]"
                  aria-label="Filter threads by status"
                >
                  <Filter className="w-3.5 h-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44 text-xs">
                <DropdownMenuRadioGroup
                  value={state.threadStatusFilter}
                  onValueChange={(val) => setThreadStatusFilter(val)}
                >
                  <DropdownMenuRadioItem value="all">All Threads</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="active">Active Only</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="needs_approval">Needs Approval</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="pinned">Pinned</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="failed">Failed / Interrupted</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="archived">Archived</DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* Thread list grouped */}
        <ScrollArea className="flex-1 px-2 py-2">
          {filteredThreads.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-6 text-center text-xs text-[var(--text-subtle)]">
              <Layers className="w-6 h-6 mb-2 stroke-1" />
              <p className="font-medium text-[var(--text-secondary)]">No threads found</p>
              <p className="text-[11px] mt-1">Try adjusting your search or filters.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Needs Approval Group */}
              {needsApprovalThreads.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-1 px-1 mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--warning)] m-0">
                    <AlertTriangle className="w-3 h-3" />
                    Needs Approval ({needsApprovalThreads.length})
                  </h3>
                  {needsApprovalThreads.map(thread => (
                    <ThreadRow
                      key={thread.id}
                      thread={thread}
                      isActive={thread.id === state.activeThreadId}
                    />
                  ))}
                </div>
              )}

              {/* Pinned Group */}
              {pinnedThreads.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-1 px-1 mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--accent)] m-0">
                    <Pin className="w-3 h-3" />
                    Pinned ({pinnedThreads.length})
                  </h3>
                  {pinnedThreads.map(thread => (
                    <ThreadRow
                      key={thread.id}
                      thread={thread}
                      isActive={thread.id === state.activeThreadId}
                    />
                  ))}
                </div>
              )}

              {/* Active Group */}
              {activeThreads.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-1 px-1 mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] m-0">
                    Active ({activeThreads.length})
                  </h3>
                  {activeThreads.map(thread => (
                    <ThreadRow
                      key={thread.id}
                      thread={thread}
                      isActive={thread.id === state.activeThreadId}
                    />
                  ))}
                </div>
              )}

              {/* Other / Recent Group */}
              {otherThreads.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-1 px-1 mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-subtle)] m-0">
                    Recent ({otherThreads.length})
                  </h3>
                  {otherThreads.map(thread => (
                    <ThreadRow
                      key={thread.id}
                      thread={thread}
                      isActive={thread.id === state.activeThreadId}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </ScrollArea>

        {/* New Thread Dialog */}
        <Dialog 
          open={isNewThreadOpen} 
          onOpenChange={(open) => {
            setIsNewThreadOpen(open)
            if (!open) {
              setTitleError('')
              setNewTitle('')
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>New Engineering Thread</DialogTitle>
              <DialogDescription>
                Start a new focused investigation, refactor, or test cycle with Codex.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2">
              {titleError && (
                <div className="p-2 rounded bg-[var(--danger-subtle)] text-[var(--danger)] text-xs font-medium">
                  {titleError}
                </div>
              )}
              <div>
                <label 
                  htmlFor="new-thread-title-input" 
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
                >
                  Thread Title / Objective *
                </label>
                <Input
                  id="new-thread-title-input"
                  placeholder="e.g. Refactor availability service locking"
                  value={newTitle}
                  onChange={(e) => {
                    setNewTitle(e.target.value)
                    if (titleError) setTitleError('')
                  }}
                  className="mt-1"
                  autoFocus
                />
              </div>
              <div>
                <label 
                  htmlFor="new-thread-model-select" 
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
                >
                  Model & Reasoning
                </label>
                <select
                  id="new-thread-model-select"
                  value={newModel}
                  onChange={(e) => setNewModel(e.target.value)}
                  className="w-full mt-1 h-9 rounded-md border border-[var(--border)] bg-[var(--surface-primary)] px-3 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                >
                  <option value="gpt-4o">gpt-4o (High capability & tool orchestration)</option>
                  <option value="o3-mini">o3-mini (Deep algorithmic reasoning)</option>
                  <option value="o1">o1 (Full complex code synthesis)</option>
                </select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="secondary" onClick={() => setIsNewThreadOpen(false)}>Cancel</Button>
              <Button
                onClick={() => {
                  if (!newTitle.trim()) {
                    setTitleError('Please enter a thread title or objective.')
                    return
                  }
                  createThread(newTitle.trim(), newModel)
                  setIsNewThreadOpen(false)
                  setNewTitle('')
                  setTitleError('')
                }}
              >
                Start Thread
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </nav>
    </>
  )
}
