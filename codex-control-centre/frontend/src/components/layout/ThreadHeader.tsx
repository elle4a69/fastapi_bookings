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
      <header className="h-12 border-b border-[var(--border)] bg-[var(--surface-primary)] px-4 flex items-center justify-between text-xs text-[var(--text-subtle)]">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSidebarOpen(!state.isSidebarOpen)}
            className="p-1 rounded md:hidden text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            aria-label="Toggle navigation sidebar"
          >
            <Menu className="w-4 h-4" />
          </button>
          <h1 className="text-xs font-medium text-[var(--text-subtle)] m-0">
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
              <Badge variant="success" className="h-5 px-1.5 text-[10px] gap-1 cursor-pointer">
                <Sparkles className="w-2.5 h-2.5" /> Compacted
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
              <Badge variant="warning" className="h-5 px-1.5 text-[10px] gap-1 cursor-pointer">
                <Sparkles className="w-2.5 h-2.5" /> 82% Context
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
              <Badge variant="secondary" className="h-5 px-1.5 text-[10px] gap-1 text-[var(--text-subtle)] cursor-pointer">
                <Sparkles className="w-2.5 h-2.5" /> 27% Token Budget
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
      <header className="h-13 border-b border-[var(--border)] bg-[var(--surface-primary)] px-4 flex items-center justify-between gap-3 flex-shrink-0 z-10">
        {/* Left: Mobile Toggle, Breadcrumbs & Title */}
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {/* Mobile sidebar drawer trigger */}
          <button
            onClick={() => setSidebarOpen(!state.isSidebarOpen)}
            className="p-1 rounded md:hidden text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] flex-shrink-0"
            aria-label="Toggle navigation sidebar"
          >
            <Menu className="w-4 h-4" />
          </button>

          <div className="hidden sm:flex items-center gap-1.5 text-xs text-[var(--text-secondary)] flex-shrink-0">
            <span className="font-medium">{activeProject?.name}</span>
            <ChevronRight className="w-3 h-3 text-[var(--text-subtle)]" />
            <span className="text-[var(--text-subtle)]">{activeThread.module}</span>
            <ChevronRight className="w-3 h-3 text-[var(--text-subtle)]" />
          </div>

          {/* Editable Title */}
          {isEditingTitle ? (
            <div className="flex items-center gap-1 flex-1 max-w-md">
              <input
                type="text"
                aria-label="Edit thread title"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveTitle()
                  if (e.key === 'Escape') setIsEditingTitle(false)
                }}
                className="h-6 px-1.5 text-xs font-semibold bg-[var(--surface-secondary)] text-[var(--text-primary)] rounded border border-[var(--accent)] outline-none w-full focus:ring-2 focus:ring-[var(--accent)]"
                autoFocus
              />
              <button
                onClick={handleSaveTitle}
                className="p-1 text-[var(--success)] hover:bg-[var(--surface-hover)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                aria-label="Save Title"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 min-w-0">
              <h1 className="font-semibold text-xs text-[var(--text-primary)] truncate max-w-sm sm:max-w-md m-0">
                {activeThread.title}
              </h1>
              <button
                onClick={() => {
                  setEditedTitle(activeThread.title)
                  setIsEditingTitle(true)
                }}
                className="p-0.5 text-[var(--text-subtle)] hover:text-[var(--text-primary)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                aria-label="Edit Thread Title"
              >
                <Edit2 className="w-3 h-3" />
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
                  'p-1.5 rounded-md border transition-colors cursor-pointer',
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
                className="p-1.5 rounded-md text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]"
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
