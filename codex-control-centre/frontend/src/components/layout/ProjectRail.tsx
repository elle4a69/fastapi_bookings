import React, { useState } from 'react'
import { 
  Terminal, 
  Plus, 
  Sun, 
  Moon, 
  Settings, 
  Radio 
} from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { cn } from '../../lib/utils'

export const ProjectRail: React.FC = () => {
  const { 
    state, 
    activeProject, 
    selectProject, 
    createProject,
    toggleTheme, 
    retryConnection, 
    setCommandPaletteOpen,
    setAppMode
  } = useWorkbenchStore()

  const [isRegisterOpen, setIsRegisterOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectRepo, setNewProjectRepo] = useState('')
  const [registerError, setRegisterError] = useState('')

  const getHealthDotColor = (health: string) => {
    switch (health) {
      case 'healthy': return 'bg-[var(--success)]'
      case 'attention_required': return 'bg-[var(--warning)]'
      case 'degraded': return 'bg-[var(--warning)]'
      case 'disconnected': return 'bg-[var(--danger)]'
      default: return 'bg-[var(--text-subtle)]'
    }
  }

  return (
    <TooltipProvider delayDuration={150}>
      <aside 
        className="flex flex-col items-center justify-between w-14 md:w-16 h-full bg-[var(--surface-primary)] border-r border-[var(--border)] py-3 px-1 z-20 flex-shrink-0"
        aria-label="Project Navigation Rail"
      >
        {/* Top: Product Mark & Projects */}
        <div className="flex flex-col items-center gap-3 w-full">
          {/* Brand Mark */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button 
                onClick={() => setCommandPaletteOpen(true)}
                className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent)] to-[#4B79E4] flex items-center justify-center text-white shadow-xs hover:scale-105 transition-transform cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                aria-label="Codex Control Centre - Open Command Palette (Cmd+K)"
              >
                <Terminal className="w-5 h-5 text-white" aria-hidden="true" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <div className="font-semibold">Codex Control Centre</div>
              <div className="text-[10px] text-[var(--text-subtle)]">Press Cmd+K for actions</div>
            </TooltipContent>
          </Tooltip>

          <div className="w-6 h-px bg-[var(--border)] my-1" />

          {/* Registered Projects List */}
          <div className="flex flex-col items-center gap-2 w-full">
            {state.projects.map((project) => {
              const isActive = project.id === activeProject?.id
              const initials = project.name
                .split(' ')
                .map(n => n[0])
                .join('')
                .slice(0, 2)
                .toUpperCase()

              return (
                <Tooltip key={project.id}>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => selectProject(project.id)}
                      className={cn(
                        'relative w-10 h-10 rounded-lg flex items-center justify-center font-semibold text-xs transition-all cursor-pointer border',
                        isActive
                          ? 'bg-[var(--accent-subtle)] text-[var(--accent)] border-[var(--accent)] shadow-xs'
                          : 'bg-[var(--surface-secondary)] text-[var(--text-secondary)] border-transparent hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]'
                      )}
                      aria-label={`Switch to project: ${project.name}`}
                    >
                      {initials}
                      {/* Health state dot */}
                      <span
                        className={cn(
                          'absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ring-2 ring-[var(--surface-primary)]',
                          getHealthDotColor(project.healthState)
                        )}
                        aria-hidden="true"
                      />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <div className="font-medium text-xs">{project.name}</div>
                    <div className="text-[10px] text-[var(--text-subtle)]">{project.repository}</div>
                    <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">
                      {project.activeThreadCount} active threads · {project.healthState}
                    </div>
                  </TooltipContent>
                </Tooltip>
              )
            })}

            {/* Add/Register Project Button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setIsRegisterOpen(true)}
                  className="w-10 h-10 rounded-lg border border-dashed border-[var(--border-strong)] text-[var(--text-subtle)] hover:text-[var(--text-primary)] hover:border-[var(--accent)] flex items-center justify-center transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                  aria-label="Register New Project"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <div>Register Project</div>
                <div className="text-[10px] text-[var(--text-subtle)]">Connect local Git repository</div>
              </TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Bottom: Connection status, Theme & Settings */}
        <div className="flex flex-col items-center gap-2.5 w-full">
          {/* Connection Status Pill */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={retryConnection}
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)]',
                  state.connectionStatus === 'connected'
                    ? 'text-[var(--success)] hover:bg-[var(--success-subtle)]'
                    : state.connectionStatus === 'connecting'
                    ? 'text-[var(--warning)] animate-spin'
                    : 'text-[var(--danger)] hover:bg-[var(--danger-subtle)]'
                )}
                aria-label={`SSE Connection status: ${state.connectionStatus}. Click to reconnect.`}
              >
                <Radio className="w-4 h-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <div className="font-medium capitalize">{state.connectionStatus}</div>
              <div className="text-[10px] text-[var(--text-subtle)]">Last connected: {state.lastConnectedTime}</div>
              <div className="text-[10px] text-[var(--text-secondary)] mt-0.5">Click to refresh SSE stream</div>
            </TooltipContent>
          </Tooltip>

          {/* Theme Toggle */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={toggleTheme}
                className="w-8 h-8 rounded-md flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                aria-label={`Toggle theme (currently ${state.theme})`}
              >
                {state.theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <div>Theme: <span className="capitalize">{state.theme}</span></div>
              <div className="text-[10px] text-[var(--text-subtle)]">Click to switch</div>
            </TooltipContent>
          </Tooltip>

          {/* Settings */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={() => setIsSettingsOpen(true)}
                className="w-8 h-8 rounded-md flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                aria-label="Open Settings"
              >
                <Settings className="w-4 h-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Settings & Auth Mode</TooltipContent>
          </Tooltip>
        </div>
      </aside>

      {/* Register Project Modal */}
      <Dialog 
        open={isRegisterOpen} 
        onOpenChange={(open) => {
          setIsRegisterOpen(open)
          if (!open) setRegisterError('')
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Register Software Project</DialogTitle>
            <DialogDescription>
              Connect a local Git repository to allow Codex Engineering Agents to inspect and coordinate workflows.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {registerError && (
              <div className="p-2 rounded bg-[var(--danger-subtle)] text-[var(--danger)] text-xs font-medium">
                {registerError}
              </div>
            )}
            <div>
              <label htmlFor="reg-project-name-input" className="text-xs font-medium text-[var(--text-secondary)] block mb-1">Project Name *</label>
              <Input 
                id="reg-project-name-input"
                placeholder="e.g. Payments Microservice" 
                value={newProjectName} 
                onChange={e => {
                  setNewProjectName(e.target.value)
                  if (registerError) setRegisterError('')
                }} 
                className="mt-1"
                autoFocus
              />
            </div>
            <div>
              <label htmlFor="reg-project-repo-input" className="text-xs font-medium text-[var(--text-secondary)] block mb-1">Repository / Directory Path</label>
              <Input 
                id="reg-project-repo-input"
                placeholder="e.g. F:\Projects\payments-service" 
                value={newProjectRepo} 
                onChange={e => setNewProjectRepo(e.target.value)} 
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setIsRegisterOpen(false)}>Cancel</Button>
            <Button 
              onClick={async () => {
                const name = newProjectName.trim()
                const repo = newProjectRepo.trim()
                if (!name) {
                  setRegisterError('Please provide a project name.')
                  return
                }
                if (!repo) {
                  setRegisterError('Please provide a repository / directory path.')
                  return
                }
                try {
                  await createProject(name, repo)
                  setIsRegisterOpen(false)
                  setNewProjectName('')
                  setNewProjectRepo('')
                  setRegisterError('')
                } catch (err: any) {
                  setRegisterError(err?.message || 'Failed to register project. Ensure the directory path exists on disk.')
                }
              }}
            >
              Register Project
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Settings Modal */}
      <Dialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Control Centre Settings</DialogTitle>
            <DialogDescription>
              Privileged owner settings for Codex agents, authentication, and telemetry integration.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2 text-xs">
            <div className="p-3 rounded-md bg-[var(--surface-secondary)] border border-[var(--border)] flex flex-col gap-2">
              <div>
                <h3 className="font-semibold text-sm text-[var(--text-primary)] m-0">Application Mode</h3>
                <div className="text-[var(--text-secondary)] mt-1">
                  Currently running in <strong>{state.appMode.toUpperCase()}</strong> mode.
                </div>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => state.appMode === 'demo' ? setAppMode('live') : setAppMode('demo')}
              >
                Switch to {state.appMode === 'demo' ? 'Live' : 'Demo'} Mode
              </Button>
            </div>
            <div className="p-3 rounded-md bg-[var(--surface-secondary)] border border-[var(--border)]">
              <h3 className="font-semibold text-sm text-[var(--text-primary)] m-0">Authentication Mode</h3>
              <div className="text-[var(--text-secondary)] mt-1">
                Currently connected via <strong>ChatGPT Managed Mode</strong>. Platform API-key fallback enabled.
              </div>
            </div>
            <div className="p-3 rounded-md bg-[var(--surface-secondary)] border border-[var(--border)]">
              <h3 className="font-semibold text-sm text-[var(--text-primary)] m-0">SigNoz Telemetry Endpoint</h3>
              <div className="text-[var(--text-secondary)] mt-1">
                Collector active at <code>http://localhost:4318/v1/traces</code> with redaction privacy rules.
              </div>
            </div>
            <div className="p-3 rounded-md bg-[var(--surface-secondary)] border border-[var(--border)]">
              <h3 className="font-semibold text-sm text-[var(--text-primary)] m-0">Sandboxing & Permissions</h3>
              <div className="text-[var(--text-secondary)] mt-1">
                Workspace write permissions restricted to registered project directories.
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setIsSettingsOpen(false)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  )
}
