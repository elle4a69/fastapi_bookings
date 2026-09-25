import React, { useState } from 'react'
import { 
  Pin, 
  Archive, 
  GitBranch, 
  Users, 
  AlertTriangle, 
  MoreVertical, 
  Copy, 
  Edit3, 
  Sparkles, 
  CheckCircle2, 
  XCircle, 
  PauseCircle, 
  PlayCircle,
  Trash2
} from 'lucide-react'
import type { Thread } from '../../types/workbench'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from '../ui/dropdown-menu'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Badge } from '../ui/badge'
import { cn } from '../../lib/utils'

interface ThreadRowProps {
  thread: Thread
  isActive: boolean
}

export const ThreadRow: React.FC<ThreadRowProps> = ({ thread, isActive }) => {
  const { 
    selectThread, 
    pinThread, 
    archiveThread, 
    compactThread, 
    renameThread, 
    deleteThread,
    setInspectorTab 
  } = useWorkbenchStore()

  const [isRenameOpen, setIsRenameOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [renamedTitle, setRenamedTitle] = useState(thread.title)

  const getStatusIcon = () => {
    if (thread.approvalCount > 0) {
      return <AlertTriangle className="w-3.5 h-3.5 text-[var(--warning)] animate-pulse flex-shrink-0" />
    }
    switch (thread.status) {
      case 'active':
        return <PlayCircle className="w-3.5 h-3.5 text-[var(--accent)] flex-shrink-0" />
      case 'completed':
        return <CheckCircle2 className="w-3.5 h-3.5 text-[var(--success)] flex-shrink-0" />
      case 'failed':
        return <XCircle className="w-3.5 h-3.5 text-[var(--danger)] flex-shrink-0" />
      case 'interrupted':
        return <PauseCircle className="w-3.5 h-3.5 text-[var(--warning)] flex-shrink-0" />
      case 'archived':
        return <Archive className="w-3.5 h-3.5 text-[var(--text-subtle)] flex-shrink-0" />
      default:
        return <PlayCircle className="w-3.5 h-3.5 text-[var(--text-secondary)] flex-shrink-0" />
    }
  }

  const handleCopyId = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(thread.id)
  }

  return (
    <>
      <div
        className={cn(
          'group relative flex items-stretch rounded-lg text-left transition-all border mb-1.5 focus-within:ring-2 focus-within:ring-[var(--accent)]',
          isActive
            ? 'bg-[var(--surface-primary)] border-[var(--border-strong)] shadow-xs'
            : 'bg-[var(--surface-secondary)]/50 border-transparent hover:bg-[var(--surface-hover)] hover:border-[var(--border)]'
        )}
      >
        {/* Main interactive thread select button */}
        <button
          type="button"
          onClick={() => selectThread(thread.id)}
          aria-label={`Select thread: ${thread.title}`}
          aria-current={isActive ? 'true' : undefined}
          className="flex-1 min-w-0 p-2.5 flex flex-col text-left focus:outline-none rounded-l-lg"
        >
          {/* Top line: Status icon & Title */}
          <div className="flex items-start gap-1.5 w-full">
            <span className="mt-0.5">{getStatusIcon()}</span>
            <span className="font-medium text-xs text-[var(--text-primary)] truncate leading-snug">
              {thread.title}
            </span>
          </div>

          {/* Sub-line: module, branch & metadata chips */}
          <div className="flex items-center justify-between w-full mt-2 pt-1 border-t border-[var(--border)]/40 text-[11px] text-[var(--text-secondary)]">
            <div className="flex items-center gap-1.5 truncate">
              {thread.branch && (
                <span className="inline-flex items-center gap-0.5 text-[10px] font-mono text-[var(--text-subtle)] truncate max-w-[90px]">
                  <GitBranch className="w-2.5 h-2.5 flex-shrink-0" />
                  {thread.branch}
                </span>
              )}
              <span className="text-[10px] text-[var(--text-subtle)]">·</span>
              <span className="text-[10px] text-[var(--text-subtle)]">{thread.updatedAt}</span>
            </div>

            <div className="flex items-center gap-1 flex-shrink-0">
              {thread.approvalCount > 0 && (
                <Badge variant="warning" className="px-1 py-0 text-[9px] font-semibold uppercase">
                  Approval ({thread.approvalCount})
                </Badge>
              )}
              {thread.subAgentCount > 0 && (
                <span className="inline-flex items-center gap-0.5 text-[10px] text-[var(--text-secondary)] bg-[var(--surface-hover)] px-1 rounded">
                  <Users className="w-2.5 h-2.5" />
                  {thread.subAgentCount}
                </span>
              )}
            </div>
          </div>
        </button>

        {/* Action controls outside the main row button (no nested interactive controls) */}
        <div className="flex items-center pr-2 flex-shrink-0">
          {thread.isPinned && (
            <Pin className="w-3 h-3 text-[var(--accent)] fill-current rotate-45 mr-1" aria-hidden="true" />
          )}

          {/* Context menu dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 rounded text-[var(--text-subtle)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] transition-opacity"
                aria-label={`Actions for thread: ${thread.title}`}
              >
                <MoreVertical className="w-3.5 h-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={() => setIsRenameOpen(true)}>
                <Edit3 className="w-3.5 h-3.5 mr-2" /> Rename
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => pinThread(thread.id)}>
                <Pin className="w-3.5 h-3.5 mr-2" /> {thread.isPinned ? 'Unpin' : 'Pin to top'}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => compactThread(thread.id)}>
                <Sparkles className="w-3.5 h-3.5 mr-2" /> Compact context
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => archiveThread(thread.id)}>
                <Archive className="w-3.5 h-3.5 mr-2" /> {thread.isArchived ? 'Unarchive' : 'Archive thread'}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleCopyId}>
                <Copy className="w-3.5 h-3.5 mr-2" /> Copy Thread ID
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setInspectorTab('details')}>
                Open Thread Details
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem 
                onClick={() => setIsDeleteOpen(true)}
                className="text-[var(--danger)] focus:text-[var(--danger)] focus:bg-[var(--danger-subtle)]"
              >
                <Trash2 className="w-3.5 h-3.5 mr-2" /> Delete Thread
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Rename Dialog */}
      <Dialog open={isRenameOpen} onOpenChange={setIsRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename Thread</DialogTitle>
            <DialogDescription>Change the title of this engineering thread.</DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <label
              htmlFor={`rename-thread-input-${thread.id}`}
              className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
            >
              Thread Title
            </label>
            <Input 
              id={`rename-thread-input-${thread.id}`}
              value={renamedTitle} 
              onChange={(e) => setRenamedTitle(e.target.value)} 
              placeholder="Thread title" 
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setIsRenameOpen(false)}>Cancel</Button>
            <Button 
              onClick={() => {
                if (renamedTitle.trim()) {
                  renameThread(thread.id, renamedTitle.trim())
                  setIsRenameOpen(false)
                }
              }}
            >
              Save Title
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Engineering Thread</DialogTitle>
            <DialogDescription>
              Are you sure you want to permanently delete "{thread.title}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setIsDeleteOpen(false)}>Cancel</Button>
            <Button 
              variant="danger"
              onClick={() => {
                deleteThread(thread.id)
                setIsDeleteOpen(false)
              }}
            >
              Delete Thread
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
