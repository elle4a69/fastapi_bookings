import React, { useState } from 'react'
import { 
  GitBranch, 
  Cpu, 
  Shield, 
  Sparkles, 
  Users, 
  SlidersHorizontal, 
  FileCode2, 
  ChevronRight, 
  Check, 
  Edit2, 
  MoreVertical, 
  Pin, 
  Archive,
  Layers,
  Menu
} from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip'
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from '../ui/dropdown-menu'
import { cn } from '../../lib/utils'

export const ThreadHeader: React.FC = () => {
  const { 
    activeProject, 
    activeThread, 
    activeSubAgents, 
    renameThread, 
    pinThread, 
    archiveThread, 
    compactThread, 
    setInspectorTab, 
    setDiffStudioOpen, 
    state, 
    setInspectorOpen,
    setSidebarOpen 
  } = useWorkbenchStore()

  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editedTitle, setEditedTitle] = useState(activeThread?.title || '')

  if (!activeThread) {
    return (
      <header className="min-h-[48px] border-b border-[var(--border)] bg-[var(--surface-primary)] px-2 sm:px-4 flex items-center justify-between text-xs text-[var(--text-subtle)] w-full max-w-full overflow-hidden flex-shrink-0">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <button
            onClick={() => setSidebarOpen(!state.isSidebarOpen)}
            className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md md:hidden text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] flex-shrink-0 cursor-pointer"
            aria-label="Toggle navigation sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h1 className="text-xs font-medium text-[var(--text-subtle)] truncate m-0">
            {state.appMode === 'live' && state.projects.length === 0 ? 'No projects connected — Register a project or switch to Demo Mode' : 'No active thread selected'}
          </h1>
        </div>
      </header>
    )
  }

  const handleSaveTitle = () => {
    if (editedTitle.trim()) {
      renameThread(activeThread.id, editedTitle.trim())
    }
    setIsEditingTitle(false)
  }

  const getCompactionBadge = () => {
    switch (activeThread.contextCompactionState) {
      case 'compacted':
        return (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="success" className="h-6 px-1.5 text-[10px] gap-1 cursor-pointer flex items-center">
                <Sparkles className="w-2.5 h-2.5" /> <span className="hidden sm:inline">Compacted</span>
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <div>Context Compacted</div>
              <div className="text-[10px] text-[var(--text-subtle)]">Earlier history condensed to free token capacity.</div>
            </TooltipContent>
          </Tooltip>
        )
      case 'approaching':
        return (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="warning" className="h-6 px-1.5 text-[10px] gap-1 cursor-pointer flex items-center">
                <Sparkles className="w-2.5 h-2.5" /> <span className="hidden sm:inline">82% Context</span><span className="sm:hidden">82%</span>
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <div>Approaching Compaction Limit</div>
              <div className="text-[10px] text-[var(--text-subtle)]">Codex will automatically summarize older turns.</div>
            </TooltipContent>
          </Tooltip>
        )
      default:
        return (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="secondary" className="h-6 px-1.5 text-[10px] gap-1 text-[var(--text-subtle)] cursor-pointer flex items-center">
                <Sparkles className="w-2.5 h-2.5" /> <span className="hidden sm:inline">27% Token Budget</span><span className="sm:hidden">27%</span>
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <div>Token Window Healthy</div>
              <div className="text-[10px] text-[var(--text-subtle)]">
                {activeThread.tokenBudget ? `${activeThread.tokenBudget.used.toLocaleString()} / ${activeThread.tokenBudget.limit.toLocaleString()} tokens` : 'Plenty of context remaining.'}
              </div>
            </TooltipContent>
          </Tooltip>
        )
    }
  }

  return (
    <TooltipProvider delayDuration={150}>
      <header className="min-h-[48px] sm:h-13 border-b border-[var(--border)] bg-[var(--surface-primary)] px-2 sm:px-4 flex items-center justify-between gap-1.5 sm:gap-3 flex-shrink-0 z-10 w-full max-w-full overflow-hidden">
        {/* Left: Mobile Toggle, Breadcrumbs & Title */}
        <div className="flex items-center gap-1.5 sm:gap-2 min-w-0 flex-1 overflow-hidden">
          {/* Mobile sidebar drawer trigger */}
          <button
            onClick={() => setSidebarOpen(!state.isSidebarOpen)}
            className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md md:hidden text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] flex-shrink-0 cursor-pointer"
            aria-label="Toggle navigation sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="hidden sm:flex items-center gap-1 text-xs text-[var(--text-secondary)] flex-shrink-0">
            <span className="font-medium truncate max-w-[100px] md:max-w-[140px]">{activeProject?.name}</span>
            <ChevronRight className="w-3 h-3 text-[var(--text-subtle)] flex-shrink-0" />
            <span className="text-[var(--text-subtle)] truncate max-w-[80px] md:max-w-[110px]">{activeThread.module}</span>
            <ChevronRight className="w-3 h-3 text-[var(--text-subtle)] flex-shrink-0" />
          </div>

          {/* Editable Title */}
          {isEditingTitle ? (
            <div className="flex items-center gap-1 flex-1 min-w-0 max-w-xs sm:max-w-md">
              <input
                type="text"
                aria-label="Edit thread title"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveTitle()
                  if (e.key === 'Escape') setIsEditingTitle(false)
                }}
                className="h-8 px-2 text-xs font-semibold bg-[var(--surface-secondary)] text-[var(--text-primary)] rounded border border-[var(--accent)] outline-none w-full focus:ring-2 focus:ring-[var(--accent)]"
                autoFocus
              />
              <button
                onClick={handleSaveTitle}
                className="min-h-[44px] min-w-[36px] flex items-center justify-center p-1 text-[var(--success)] hover:bg-[var(--surface-hover)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)] cursor-pointer"
                aria-label="Save Title"
              >
                <Check className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1 min-w-0 flex-1 overflow-hidden">
              <h1 className="font-semibold text-xs text-[var(--text-primary)] truncate max-w-[120px] sm:max-w-xs md:max-w-md m-0">
                {activeThread.title}
              </h1>
              <button
                onClick={() => {
                  setEditedTitle(activeThread.title)
                  setIsEditingTitle(true)
                }}
                className="min-h-[44px] min-w-[32px] flex items-center justify-center p-1 text-[var(--text-subtle)] hover:text-[var(--text-primary)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)] flex-shrink-0 cursor-pointer"
                aria-label="Edit Thread Title"
              >
                <Edit2 className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Right: Badges, Controls & Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Branch tag */}
          {activeThread.branch && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="secondary" className="h-5 px-1.5 text-[10px] font-mono gap-1 text-[var(--text-secondary)] hidden md:inline-flex">
                  <GitBranch className="w-2.5 h-2.5" /> {activeThread.branch}
                </Badge>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <div>Git Worktree Branch</div>
                <div className="text-[10px] text-[var(--text-subtle)]">{activeThread.worktree || activeThread.branch}</div>
              </TooltipContent>
            </Tooltip>
          )}

          {/* Model & Reasoning selector badge */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="default" className="h-5 px-1.5 text-[10px] gap-1 hidden sm:inline-flex">
                <Cpu className="w-2.5 h-2.5" /> {activeThread.model} ({activeThread.reasoningEffort})
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <div>Active Engineering Model</div>
              <div className="text-[10px] text-[var(--text-subtle)]">Reasoning effort: {activeThread.reasoningEffort}</div>
            </TooltipContent>
          </Tooltip>

          {/* Permission Profile */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="secondary" className="h-5 px-1.5 text-[10px] gap-1 hidden lg:inline-flex">
                <Shield className="w-2.5 h-2.5 text-[var(--accent)]" /> {activeThread.permissionProfile.replace('_', ' ')}
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <div>Sandbox Permission Scope</div>
              <div className="text-[10px] text-[var(--text-subtle)]">Restricted to approved project roots.</div>
            </TooltipContent>
          </Tooltip>

          {/* Compaction Gauge */}
          {getCompactionBadge()}

          {/* Subagents Counter Pill */}
          {activeThread.subAgentCount > 0 && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setInspectorTab('subagents')}
                  className="inline-flex items-center gap-1 h-5 px-2 rounded-full text-[10px] font-medium bg-[var(--surface-hover)] text-[var(--text-primary)] hover:bg-[var(--accent-subtle)] hover:text-[var(--accent)] border border-[var(--border)] transition-colors cursor-pointer"
                  aria-label="Open Subagents Tab in Inspector"
                >
                  <Users className="w-3 h-3 text-[var(--accent)]" />
                  <span>{activeSubAgents.length || activeThread.subAgentCount} Sub-agents</span>
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <div>Parallel Sub-agents</div>
                <div className="text-[10px] text-[var(--text-subtle)]">Click to inspect and steer child agents</div>
              </TooltipContent>
            </Tooltip>
          )}

          {/* Open Diff Studio Button */}
          {state.diffFiles.length > 0 && (
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2 text-xs gap-1 font-medium text-[var(--accent)] border-[var(--accent)]/30 hover:bg-[var(--accent-subtle)]"
              onClick={() => setDiffStudioOpen(true)}
            >
              <FileCode2 className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Review Diffs ({state.diffFiles.length})</span>
            </Button>
          )}

          {/* Inspector Toggle */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={() => setInspectorOpen(!state.isInspectorOpen)}
                className={cn(
                  'min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md border transition-colors cursor-pointer',
                  state.isInspectorOpen
                    ? 'bg-[var(--surface-hover)] border-[var(--border-strong)] text-[var(--text-primary)]'
                    : 'bg-transparent border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                )}
                aria-label="Toggle Inspector Panel"
              >
                <SlidersHorizontal className="w-4 h-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom">Toggle Inspector Panel</TooltipContent>
          </Tooltip>

          {/* Overflow Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] cursor-pointer"
                aria-label="Thread options"
              >
                <MoreVertical className="w-4 h-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 text-xs">
              <DropdownMenuItem onClick={() => pinThread(activeThread.id)}>
                <Pin className="w-3.5 h-3.5 mr-2" /> {activeThread.isPinned ? 'Unpin Thread' : 'Pin Thread'}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => compactThread(activeThread.id)}>
                <Sparkles className="w-3.5 h-3.5 mr-2" /> Compact Conversation History
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => archiveThread(activeThread.id)}>
                <Archive className="w-3.5 h-3.5 mr-2" /> {activeThread.isArchived ? 'Unarchive Thread' : 'Archive Thread'}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => setInspectorTab('details')}>
                <Layers className="w-3.5 h-3.5 mr-2" /> View Thread Details & Audit
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
    </TooltipProvider>
  )
}
