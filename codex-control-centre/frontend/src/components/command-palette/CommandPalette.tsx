import React, { useState, useEffect, useMemo } from 'react'
import { 
  Search, 
  GitBranch, 
  FolderGit2, 
  FileCode2, 
  Users, 
  Sparkles, 
  Moon, 
  Sun, 
  Radio, 
  Plus
} from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { Dialog, DialogContent, DialogTitle } from '../ui/dialog'
import { Input } from '../ui/input'
import { cn } from '../../lib/utils'

export const CommandPalette: React.FC = () => {
  const { 
    state, 
    setCommandPaletteOpen, 
    selectProject, 
    selectThread, 
    createThread, 
    setDiffStudioOpen, 
    setInspectorTab, 
    toggleTheme, 
    compactThread, 
    retryConnection 
  } = useWorkbenchStore()

  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)

  // Listen for global Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCommandPaletteOpen(!state.isCommandPaletteOpen)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [state.isCommandPaletteOpen, setCommandPaletteOpen])

  // Build command items
  const commands = useMemo(() => {
    const list: Array<{
      id: string
      group: string
      title: string
      subtitle?: string
      icon: React.ReactNode
      action: () => void
    }> = []

    // Quick Actions
    list.push({
      id: 'cmd_new_thread',
      group: 'Quick Actions',
      title: 'Create New Thread',
      subtitle: 'Start a new engineering turn with Codex',
      icon: <Plus className="w-4 h-4 text-[var(--accent)]" />,
      action: () => {
        createThread('New Engineering Thread')
        setCommandPaletteOpen(false)
      }
    })

    list.push({
      id: 'cmd_diffs',
      group: 'Quick Actions',
      title: 'Review File Changes & Diffs',
      subtitle: `${state.diffFiles.length} modified files ready for review`,
      icon: <FileCode2 className="w-4 h-4 text-[var(--accent)]" />,
      action: () => {
        setDiffStudioOpen(true)
        setCommandPaletteOpen(false)
      }
    })

    list.push({
      id: 'cmd_subagents',
      group: 'Quick Actions',
      title: 'Inspect Parallel Sub-agents',
      subtitle: 'View and steer concurrent child agents',
      icon: <Users className="w-4 h-4 text-[var(--accent)]" />,
      action: () => {
        setInspectorTab('subagents')
        setCommandPaletteOpen(false)
      }
    })

    if (state.activeThreadId) {
      list.push({
        id: 'cmd_compact',
        group: 'Quick Actions',
        title: 'Compact Conversation Context',
        subtitle: 'Condense earlier turns to free token window',
        icon: <Sparkles className="w-4 h-4 text-[var(--warning)]" />,
        action: () => {
          compactThread(state.activeThreadId!)
          setCommandPaletteOpen(false)
        }
      })
    }

    list.push({
      id: 'cmd_theme',
      group: 'Preferences',
      title: `Switch to ${state.theme === 'dark' ? 'Light' : 'Dark'} Theme`,
      subtitle: `Current theme: ${state.theme}`,
      icon: state.theme === 'dark' ? <Sun className="w-4 h-4 text-[var(--warning)]" /> : <Moon className="w-4 h-4 text-[var(--accent)]" />,
      action: () => {
        toggleTheme()
        setCommandPaletteOpen(false)
      }
    })

    list.push({
      id: 'cmd_reconnect',
      group: 'Preferences',
      title: 'Reconnect Codex SSE Stream',
      subtitle: `Status: ${state.connectionStatus}`,
      icon: <Radio className="w-4 h-4 text-[var(--success)]" />,
      action: () => {
        retryConnection()
        setCommandPaletteOpen(false)
      }
    })

    // Projects
    state.projects.forEach(project => {
      list.push({
        id: `proj_${project.id}`,
        group: 'Switch Project',
        title: project.name,
        subtitle: project.repository,
        icon: <FolderGit2 className="w-4 h-4 text-[var(--text-secondary)]" />,
        action: () => {
          selectProject(project.id)
          setCommandPaletteOpen(false)
        }
      })
    })

    // Active Project Threads
    state.threads.forEach(thread => {
      list.push({
        id: `th_${thread.id}`,
        group: 'Switch Thread',
        title: thread.title,
        subtitle: `${thread.module} · ${thread.branch}`,
        icon: <GitBranch className="w-4 h-4 text-[var(--text-subtle)]" />,
        action: () => {
          selectThread(thread.id)
          setCommandPaletteOpen(false)
        }
      })
    })

    return list
  }, [state, createThread, setDiffStudioOpen, setInspectorTab, compactThread, toggleTheme, retryConnection, selectProject, selectThread, setCommandPaletteOpen])

  // Filter commands by query
  const filteredCommands = useMemo(() => {
    if (!query.trim()) return commands
    const q = query.toLowerCase()
    return commands.filter(c => 
      c.title.toLowerCase().includes(q) || 
      c.subtitle?.toLowerCase().includes(q) ||
      c.group.toLowerCase().includes(q)
    )
  }, [commands, query])

  // Handle arrow navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(prev => (prev + 1) % (filteredCommands.length || 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(prev => (prev - 1 + filteredCommands.length) % (filteredCommands.length || 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filteredCommands[selectedIndex]) {
        filteredCommands[selectedIndex].action()
      }
    }
  }

  return (
    <Dialog open={state.isCommandPaletteOpen} onOpenChange={setCommandPaletteOpen}>
      <DialogContent className="max-w-xl p-0 overflow-hidden border-[var(--border-strong)] bg-[var(--surface-primary)] shadow-2xl">
        <DialogTitle className="sr-only">Command Palette</DialogTitle>
        <div className="flex items-center px-3.5 py-2.5 border-b border-[var(--border)] gap-2">
          <label htmlFor="command-palette-search-input" className="sr-only">
            Type a command, search threads, or switch project
          </label>
          <Search className="w-4 h-4 text-[var(--text-subtle)]" aria-hidden="true" />
          <Input
            id="command-palette-search-input"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            onKeyDown={handleKeyDown}
            placeholder="Type a command, search threads, switch project..."
            aria-label="Type a command, search threads, switch project"
            className="border-0 shadow-none focus-visible:ring-0 text-sm h-8 bg-transparent px-1 placeholder:text-[var(--text-subtle)]"
            autoFocus
          />
          <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono font-medium text-[var(--text-subtle)] bg-[var(--surface-secondary)] border border-[var(--border)] rounded">
            ESC
          </kbd>
        </div>

        <div className="max-h-[360px] overflow-y-auto p-1.5" role="listbox" aria-label="Available commands">
          {filteredCommands.length === 0 ? (
            <div className="p-8 text-center text-xs text-[var(--text-subtle)]">
              No matching commands or threads.
            </div>
          ) : (
            <div className="space-y-1">
              {filteredCommands.map((cmd, index) => (
                <button
                  key={cmd.id}
                  type="button"
                  onClick={cmd.action}
                  onMouseEnter={() => setSelectedIndex(index)}
                  aria-label={`${cmd.group}: ${cmd.title}`}
                  className={cn(
                    'w-full flex items-center justify-between p-2 rounded-md cursor-pointer transition-colors text-xs text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]',
                    index === selectedIndex
                      ? 'bg-[var(--surface-hover)] text-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)] hover:bg-[var(--surface-secondary)]'
                  )}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="p-1 rounded bg-[var(--surface-secondary)] flex-shrink-0" aria-hidden="true">
                      {cmd.icon}
                    </div>
                    <div className="min-w-0 truncate">
                      <div className="font-medium text-[var(--text-primary)] truncate">{cmd.title}</div>
                      {cmd.subtitle && (
                        <div className="text-[10px] text-[var(--text-subtle)] truncate">{cmd.subtitle}</div>
                      )}
                    </div>
                  </div>
                  <span className="text-[10px] font-medium text-[var(--text-subtle)] ml-2 flex-shrink-0">
                    {cmd.group}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
