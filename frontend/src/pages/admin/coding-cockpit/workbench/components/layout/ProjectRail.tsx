import React, { useState, useEffect } from 'react'
import { 
  Terminal, 
  Plus, 
  Sun, 
  Moon, 
  Settings, 
  Radio,
  FolderKanban,
  FolderPlus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Activity,
  Check,
  ShieldCheck,
  RefreshCw,
  Folder
} from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Badge } from '../ui/badge'
import { cn } from '../../lib/utils'
import type { TelemetryTestResult } from '../../types/workbench'

export const ProjectRail: React.FC = () => {
  const { 
    state, 
    activeProject, 
    selectProject, 
    createProject,
    toggleTheme, 
    retryConnection, 
    setCommandPaletteOpen,
    setAppMode,
    fetchBoundaries,
    addBoundary,
    removeBoundary,
    fetchTelemetrySettings,
    updateTelemetrySettings,
    testTelemetry
  } = useWorkbenchStore()

  // Modal open states
  const [isRegisterOpen, setIsRegisterOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [settingsTab, setSettingsTab] = useState<'boundaries' | 'telemetry' | 'system'>('boundaries')

  // Project registration form state
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectRepo, setNewProjectRepo] = useState('')
  const [registerError, setRegisterError] = useState('')
  const [showInlineAddBoundary, setShowInlineAddBoundary] = useState(false)

  // Boundaries form state
  const [newBoundaryPath, setNewBoundaryPath] = useState('')
  const [newBoundaryName, setNewBoundaryName] = useState('')
  const [boundaryError, setBoundaryError] = useState('')
  const [boundarySuccess, setBoundarySuccess] = useState('')
  const [isAddingBoundary, setIsAddingBoundary] = useState(false)
  const [deletingBoundaryId, setDeletingBoundaryId] = useState<string | null>(null)

  // Telemetry form state
  const [telemetrySignozUrl, setTelemetrySignozUrl] = useState('http://localhost:3301')
  const [telemetryOtlpEndpoint, setTelemetryOtlpEndpoint] = useState('http://localhost:4318')
  const [telemetryEnabled, setTelemetryEnabled] = useState(true)
  const [isTestingTelemetry, setIsTestingTelemetry] = useState(false)
  const [testResult, setTestResult] = useState<TelemetryTestResult | null>(null)
  const [isSavingTelemetry, setIsSavingTelemetry] = useState(false)
  const [telemetryFeedback, setTelemetryFeedback] = useState('')

  // Sync telemetry state from store
  useEffect(() => {
    if (state.telemetrySettings) {
      setTelemetrySignozUrl(state.telemetrySettings.signoz_url || 'http://localhost:3301')
      setTelemetryOtlpEndpoint(state.telemetrySettings.otlp_endpoint || 'http://localhost:4318')
      setTelemetryEnabled(state.telemetrySettings.enabled ?? true)
    }
  }, [state.telemetrySettings])

  // Refresh boundaries and telemetry when settings open
  useEffect(() => {
    if (isSettingsOpen || isRegisterOpen) {
      fetchBoundaries?.()
      fetchTelemetrySettings?.()
    }
  }, [isSettingsOpen, isRegisterOpen])

  const getHealthDotColor = (health: string) => {
    switch (health) {
      case 'healthy': return 'bg-[var(--success)]'
      case 'attention_required': return 'bg-[var(--warning)]'
      case 'degraded': return 'bg-[var(--warning)]'
      case 'disconnected': return 'bg-[var(--danger)]'
      default: return 'bg-[var(--text-subtle)]'
    }
  }

  // Check if a path falls within active boundaries
  const isPathWithinBoundaries = (checkPath: string) => {
    if (!checkPath.trim()) return true
    if (state.boundaries.length === 0) return true
    const normalized = checkPath.trim().toLowerCase().replace(/\\/g, '/').replace(/\/+$/, '')
    return state.boundaries.some(b => {
      const bNorm = b.path.toLowerCase().replace(/\\/g, '/').replace(/\/+$/, '')
      return normalized === bNorm || normalized.startsWith(bNorm + '/')
    })
  }

  const isOutsideBoundaries = newProjectRepo.trim().length > 0 && !isPathWithinBoundaries(newProjectRepo)

  const handleAddBoundarySubmit = async (customPath?: string, customName?: string) => {
    const targetPath = (customPath || newBoundaryPath).trim()
    const targetName = (customName || newBoundaryName).trim()
    if (!targetPath) {
      setBoundaryError('Please enter a directory path.')
      return
    }
    setIsAddingBoundary(true)
    setBoundaryError('')
    setBoundarySuccess('')
    try {
      const created = await addBoundary(targetPath, targetName)
      setBoundarySuccess(`Added boundary: ${created.name}`)
      setNewBoundaryPath('')
      setNewBoundaryName('')
      setShowInlineAddBoundary(false)
      setTimeout(() => setBoundarySuccess(''), 4000)
    } catch (err: any) {
      setBoundaryError(err?.message || 'Failed to add workspace boundary. Ensure the folder exists on disk.')
    } finally {
      setIsAddingBoundary(false)
    }
  }

  const handleRemoveBoundary = async (boundaryId: string) => {
    if (state.boundaries.length <= 1) {
      setBoundaryError('Cannot remove the only remaining workspace boundary.')
      return
    }
    setDeletingBoundaryId(boundaryId)
    setBoundaryError('')
    setBoundarySuccess('')
    try {
      await removeBoundary(boundaryId)
      setBoundarySuccess('Workspace boundary removed.')
      setTimeout(() => setBoundarySuccess(''), 3000)
    } catch (err: any) {
      setBoundaryError(err?.message || 'Failed to remove boundary.')
    } finally {
      setDeletingBoundaryId(null)
    }
  }

  const handleTestTelemetry = async () => {
    setIsTestingTelemetry(true)
    setTestResult(null)
    setTelemetryFeedback('')
    try {
      const targetEndpoint = telemetryOtlpEndpoint.trim() || 'http://localhost:4318'
      const res = await testTelemetry(targetEndpoint)
      setTestResult(res)
    } catch (err: any) {
      setTestResult({
        connected: false,
        status: 'Unreachable',
        error: err?.message || 'Connection test failed',
        latency_ms: 0,
        url: telemetryOtlpEndpoint
      })
    } finally {
      setIsTestingTelemetry(false)
    }
  }

  const handleSaveTelemetry = async () => {
    setIsSavingTelemetry(true)
    setTelemetryFeedback('')
    try {
      await updateTelemetrySettings({
        signoz_url: telemetrySignozUrl.trim(),
        otlp_endpoint: telemetryOtlpEndpoint.trim(),
        enabled: telemetryEnabled
      })
      setTelemetryFeedback('Telemetry configuration saved successfully!')
      setTimeout(() => setTelemetryFeedback(''), 4000)
    } catch (err: any) {
      setTelemetryFeedback(`Failed to save: ${err?.message || 'Unknown error'}`)
    } finally {
      setIsSavingTelemetry(false)
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
                className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent)] to-[#4B79E4] flex items-center justify-center text-white shadow-xs hover:scale-105 transition-transform cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)] min-h-[44px] min-w-[44px]"
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
                        'relative w-10 h-10 rounded-lg flex items-center justify-center font-semibold text-xs transition-all cursor-pointer border min-h-[44px] min-w-[44px]',
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
                    <div className="text-[10px] text-[var(--text-subtle)] truncate max-w-xs">{project.repository}</div>
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
                  className="w-10 h-10 rounded-lg border border-dashed border-[var(--border-strong)] text-[var(--text-subtle)] hover:text-[var(--text-primary)] hover:border-[var(--accent)] flex items-center justify-center transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)] min-h-[44px] min-w-[44px]"
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

        {/* Bottom: Boundaries Shortcut, Connection status, Theme & Settings */}
        <div className="flex flex-col items-center gap-2.5 w-full">
          {/* Workspace Boundaries Quick Access */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={() => {
                  setSettingsTab('boundaries')
                  setIsSettingsOpen(true)
                }}
                className="w-9 h-9 rounded-md flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--accent)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)] min-h-[44px] min-w-[44px]"
                aria-label="Manage Workspace Boundaries"
              >
                <FolderKanban className="w-4 h-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <div className="font-medium">Workspace Boundaries</div>
              <div className="text-[10px] text-[var(--text-subtle)]">{state.boundaries.length} allowed folders</div>
            </TooltipContent>
          </Tooltip>

          {/* Connection Status Pill */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={retryConnection}
                className={cn(
                  'w-9 h-9 rounded-full flex items-center justify-center transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)] min-h-[44px] min-w-[44px]',
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
                className="w-9 h-9 rounded-md flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)] min-h-[44px] min-w-[44px]"
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
                onClick={() => {
                  setSettingsTab('boundaries')
                  setIsSettingsOpen(true)
                }}
                className="w-9 h-9 rounded-md flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent)] min-h-[44px] min-w-[44px]"
                aria-label="Open Settings"
              >
                <Settings className="w-4 h-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Settings & Workspace Boundaries</TooltipContent>
          </Tooltip>
        </div>
      </aside>

      {/* ========================================================= */}
      {/* Register Project Modal                                    */}
      {/* ========================================================= */}
      <Dialog 
        open={isRegisterOpen} 
        onOpenChange={(open) => {
          setIsRegisterOpen(open)
          if (!open) {
            setRegisterError('')
            setShowInlineAddBoundary(false)
          }
        }}
      >
        <DialogContent className="max-w-[95vw] sm:max-w-xl max-h-[88vh] overflow-y-auto p-4 sm:p-6">
          <DialogHeader>
            <DialogTitle className="text-base sm:text-lg">Register Software Project</DialogTitle>
            <DialogDescription className="text-xs">
              Connect a local Git repository to allow Codex Engineering Agents to inspect and coordinate workflows.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {registerError && (
              <div className="p-3 rounded-lg bg-[var(--danger-subtle)] text-[var(--danger)] text-xs font-medium flex items-start gap-2 border border-[var(--danger)]/20">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div className="break-words">{registerError}</div>
              </div>
            )}

            {/* Allowed Base Folders Indicator */}
            <div className="p-3 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)] space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <span className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-[var(--accent)]" /> Allowed Base Directories
                </span>
                <button
                  type="button"
                  onClick={() => setShowInlineAddBoundary(!showInlineAddBoundary)}
                  className="text-[11px] text-[var(--accent)] hover:underline flex items-center gap-1 font-medium cursor-pointer self-start sm:self-auto py-1"
                >
                  <FolderPlus className="w-3 h-3" />
                  {showInlineAddBoundary ? 'Hide Add Folder' : '+ Add New Allowed Folder'}
                </button>
              </div>

              {/* Boundary Badges */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {state.boundaries.length === 0 ? (
                  <span className="text-[11px] text-[var(--text-subtle)]">Loading active boundaries...</span>
                ) : (
                  state.boundaries.map(b => (
                    <Badge 
                      key={b.id} 
                      variant="outline" 
                      className="text-[11px] font-mono py-1 px-2 max-w-full truncate bg-[var(--surface-primary)] border-[var(--border-strong)]"
                      title={b.path}
                    >
                      <Folder className="w-3 h-3 mr-1 text-[var(--accent)] flex-shrink-0" />
                      <span className="truncate">{b.path}</span>
                    </Badge>
                  ))
                )}
              </div>

              {/* Inline Add Boundary Form */}
              {showInlineAddBoundary && (
                <div className="pt-2 border-t border-[var(--border)] mt-2 space-y-2">
                  <div className="text-[11px] text-[var(--text-secondary)]">Enter a directory to allow as a safe workspace base:</div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <Input
                      placeholder="e.g. F:\Projects\fastapi_bookings"
                      value={newBoundaryPath}
                      onChange={e => setNewBoundaryPath(e.target.value)}
                      className="text-xs h-9 min-h-[44px] flex-1 font-mono"
                    />
                    <Button
                      size="sm"
                      onClick={() => handleAddBoundarySubmit()}
                      disabled={isAddingBoundary || !newBoundaryPath.trim()}
                      className="min-h-[44px] px-3 text-xs flex-shrink-0"
                    >
                      {isAddingBoundary ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
                      Add Folder
                    </Button>
                  </div>
                  {boundaryError && <div className="text-[11px] text-[var(--danger)]">{boundaryError}</div>}
                  {boundarySuccess && <div className="text-[11px] text-[var(--success)]">{boundarySuccess}</div>}
                </div>
              )}
            </div>

            <div>
              <label htmlFor="reg-project-name-input" className="text-xs font-medium text-[var(--text-secondary)] block mb-1">
                Project Name *
              </label>
              <Input 
                id="reg-project-name-input"
                placeholder="e.g. Payments Microservice" 
                value={newProjectName} 
                onChange={e => {
                  setNewProjectName(e.target.value)
                  if (registerError) setRegisterError('')
                }} 
                className="text-xs min-h-[44px]"
                autoFocus
              />
            </div>

            <div>
              <label htmlFor="reg-project-repo-input" className="text-xs font-medium text-[var(--text-secondary)] block mb-1">
                Repository / Directory Path *
              </label>
              <Input 
                id="reg-project-repo-input"
                placeholder="e.g. F:\Projects\fastapi_bookings\backend" 
                value={newProjectRepo} 
                onChange={e => {
                  setNewProjectRepo(e.target.value)
                  if (registerError) setRegisterError('')
                }} 
                className="text-xs min-h-[44px] font-mono"
              />
            </div>

            {/* Outside boundaries warning and quick-add button */}
            {isOutsideBoundaries && (
              <div className="p-3 rounded-lg bg-[var(--warning-subtle)] border border-[var(--warning)]/30 text-[11px] space-y-2">
                <div className="flex items-start gap-1.5 text-[var(--warning)] font-medium">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>This repository path is outside the active workspace boundaries.</span>
                </div>
                <div className="text-[var(--text-secondary)]">
                  To protect system safety, the application only supervises projects within allowed base folders.
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full min-h-[44px] text-xs font-medium border-[var(--warning)]/50 text-[var(--text-primary)] hover:bg-[var(--warning-subtle)]"
                  disabled={isAddingBoundary}
                  onClick={async () => {
                    await handleAddBoundarySubmit(newProjectRepo.trim())
                  }}
                >
                  {isAddingBoundary ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  ) : (
                    <FolderPlus className="w-3.5 h-3.5 mr-1.5 text-[var(--accent)]" />
                  )}
                  Add &quot;{newProjectRepo.trim()}&quot; to Allowed Boundaries
                </Button>
              </div>
            )}
          </div>

          <DialogFooter className="flex-col sm:flex-row gap-2 pt-2">
            <Button 
              variant="secondary" 
              onClick={() => setIsRegisterOpen(false)}
              className="w-full sm:w-auto min-h-[44px] text-xs"
            >
              Cancel
            </Button>
            <Button 
              className="w-full sm:w-auto min-h-[44px] text-xs"
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
                  setRegisterError(err?.message || 'Failed to register project. Ensure the directory path exists on disk and is within an allowed boundary.')
                }
              }}
            >
              Register Project
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ========================================================= */}
      {/* Settings Modal (Boundaries, Telemetry, System)            */}
      {/* ========================================================= */}
      <Dialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
        <DialogContent className="max-w-[95vw] sm:max-w-2xl max-h-[88vh] overflow-y-auto p-4 sm:p-6">
          <DialogHeader>
            <DialogTitle className="text-base sm:text-lg">Control Centre Settings</DialogTitle>
            <DialogDescription className="text-xs">
              Configure workspace directory boundaries, telemetry collectors, and runtime modes.
            </DialogDescription>
          </DialogHeader>

          {/* Touch-Friendly Responsive Tabs Header */}
          <div className="flex border-b border-[var(--border)] gap-1 pt-1 overflow-x-auto no-scrollbar">
            <button
              onClick={() => setSettingsTab('boundaries')}
              className={cn(
                'py-2 px-3 text-xs font-medium border-b-2 transition-colors cursor-pointer min-h-[44px] flex items-center gap-1.5 whitespace-nowrap',
                settingsTab === 'boundaries'
                  ? 'border-[var(--accent)] text-[var(--accent)] font-semibold'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              )}
            >
              <FolderKanban className="w-4 h-4" />
              <span>Workspace Boundaries</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--surface-secondary)] font-mono">
                {state.boundaries.length}
              </span>
            </button>

            <button
              onClick={() => setSettingsTab('telemetry')}
              className={cn(
                'py-2 px-3 text-xs font-medium border-b-2 transition-colors cursor-pointer min-h-[44px] flex items-center gap-1.5 whitespace-nowrap',
                settingsTab === 'telemetry'
                  ? 'border-[var(--accent)] text-[var(--accent)] font-semibold'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              )}
            >
              <Activity className="w-4 h-4" />
              <span>Telemetry & SigNoz</span>
              <span className={cn(
                'w-2 h-2 rounded-full',
                state.telemetrySettings?.connected ? 'bg-[var(--success)]' : 'bg-[var(--warning)]'
              )} />
            </button>

            <button
              onClick={() => setSettingsTab('system')}
              className={cn(
                'py-2 px-3 text-xs font-medium border-b-2 transition-colors cursor-pointer min-h-[44px] flex items-center gap-1.5 whitespace-nowrap',
                settingsTab === 'system'
                  ? 'border-[var(--accent)] text-[var(--accent)] font-semibold'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              )}
            >
              <Settings className="w-4 h-4" />
              <span>System & Modes</span>
            </button>
          </div>

          {/* Tab 1: Workspace Boundaries */}
          {settingsTab === 'boundaries' && (
            <div className="space-y-4 py-3 text-xs">
              <div className="text-[var(--text-secondary)]">
                Dynamic boundaries specify allowed base directory paths where projects and git worktrees may reside. Projects outside these boundaries cannot be registered.
              </div>

              {boundaryError && (
                <div className="p-3 rounded-lg bg-[var(--danger-subtle)] text-[var(--danger)] text-xs font-medium flex items-start gap-2 border border-[var(--danger)]/20">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <div className="break-words">{boundaryError}</div>
                </div>
              )}
              {boundarySuccess && (
                <div className="p-3 rounded-lg bg-[var(--success-subtle)] text-[var(--success)] text-xs font-medium flex items-center gap-2 border border-[var(--success)]/20">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  <span>{boundarySuccess}</span>
                </div>
              )}

              {/* Current Allowed Boundaries List */}
              <div className="space-y-2">
                <div className="font-semibold text-xs text-[var(--text-primary)] flex items-center justify-between">
                  <span>Active Workspace Boundaries</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-[11px] text-[var(--text-secondary)] p-1 min-h-[36px]"
                    onClick={() => fetchBoundaries?.()}
                    title="Refresh boundaries"
                  >
                    <RefreshCw className="w-3 h-3 mr-1" /> Refresh
                  </Button>
                </div>

                <div className="space-y-2">
                  {state.boundaries.map((b) => (
                    <div 
                      key={b.id}
                      className="p-3 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                    >
                      <div className="space-y-0.5 min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-xs text-[var(--text-primary)]">{b.name}</span>
                          {b.is_default && (
                            <Badge variant="outline" className="text-[9px] py-0 px-1 bg-[var(--surface-primary)] text-[var(--accent)] border-[var(--accent)]/30">
                              Primary Default
                            </Badge>
                          )}
                        </div>
                        <div className="text-[11px] font-mono text-[var(--text-subtle)] break-all">
                          {b.path}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-center flex-shrink-0">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 text-[11px] text-[var(--danger)] hover:bg-[var(--danger-subtle)] hover:text-[var(--danger)] min-h-[44px] min-w-[44px] px-2"
                          disabled={state.boundaries.length <= 1 || deletingBoundaryId === b.id}
                          onClick={() => handleRemoveBoundary(b.id)}
                          title={state.boundaries.length <= 1 ? "Cannot remove last remaining boundary" : "Remove boundary"}
                        >
                          {deletingBoundaryId === b.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="w-3.5 h-3.5" />
                          )}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Add New Boundary Card */}
              <div className="p-3.5 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)] space-y-3">
                <div className="font-semibold text-xs text-[var(--text-primary)] flex items-center gap-1.5">
                  <FolderPlus className="w-4 h-4 text-[var(--accent)]" /> Add New Workspace Boundary
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <div className="sm:col-span-2">
                    <label className="text-[11px] font-medium text-[var(--text-secondary)] block mb-1">
                      Directory Path *
                    </label>
                    <Input
                      placeholder="e.g. F:\Projects\fastapi_bookings or E:\Projects\King of Kings"
                      value={newBoundaryPath}
                      onChange={e => setNewBoundaryPath(e.target.value)}
                      className="text-xs font-mono min-h-[44px]"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-medium text-[var(--text-secondary)] block mb-1">
                      Display Label (Optional)
                    </label>
                    <Input
                      placeholder="e.g. Bookings Project"
                      value={newBoundaryName}
                      onChange={e => setNewBoundaryName(e.target.value)}
                      className="text-xs min-h-[44px]"
                    />
                  </div>
                </div>
                <Button
                  onClick={() => handleAddBoundarySubmit()}
                  disabled={isAddingBoundary || !newBoundaryPath.trim()}
                  className="w-full sm:w-auto min-h-[44px] text-xs font-medium"
                >
                  {isAddingBoundary ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  ) : (
                    <Plus className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  Add Workspace Boundary
                </Button>
              </div>
            </div>
          )}

          {/* Tab 2: Telemetry Settings */}
          {settingsTab === 'telemetry' && (
            <div className="space-y-4 py-3 text-xs">
              <div className="text-[var(--text-secondary)]">
                Configure OpenTelemetry (OTel) ingestion and SigNoz observability collectors. Links in the Telemetry tab will dynamically route to the configured SigNoz URL.
              </div>

              {telemetryFeedback && (
                <div className={cn(
                  'p-3 rounded-lg text-xs font-medium flex items-center gap-2 border',
                  telemetryFeedback.includes('Failed')
                    ? 'bg-[var(--danger-subtle)] text-[var(--danger)] border-[var(--danger)]/20'
                    : 'bg-[var(--success-subtle)] text-[var(--success)] border-[var(--success)]/20'
                )}>
                  {telemetryFeedback.includes('Failed') ? <AlertCircle className="w-4 h-4 flex-shrink-0" /> : <CheckCircle2 className="w-4 h-4 flex-shrink-0" />}
                  <span>{telemetryFeedback}</span>
                </div>
              )}

              {/* Telemetry Enable/Disable Card */}
              <div className="p-3.5 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-xs text-[var(--text-primary)] m-0">OpenTelemetry SDK Pipeline</h4>
                  <div className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                    Export traces, metrics, and operational logs to collector
                  </div>
                </div>
                <Button
                  variant={telemetryEnabled ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setTelemetryEnabled(!telemetryEnabled)}
                  className="min-h-[44px] text-xs font-medium flex-shrink-0"
                >
                  {telemetryEnabled ? 'Enabled' : 'Disabled'}
                </Button>
              </div>

              {/* Endpoints Configuration */}
              <div className="p-3.5 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)] space-y-3">
                <div>
                  <label className="text-xs font-medium text-[var(--text-primary)] block mb-1">
                    SigNoz UI / Query URL
                  </label>
                  <Input
                    placeholder="e.g. http://localhost:3301"
                    value={telemetrySignozUrl}
                    onChange={e => setTelemetrySignozUrl(e.target.value)}
                    className="text-xs font-mono min-h-[44px]"
                  />
                  <span className="text-[10px] text-[var(--text-subtle)] mt-1 block">
                    URL for browser trace viewing links in the Telemetry inspector.
                  </span>
                </div>

                <div>
                  <label className="text-xs font-medium text-[var(--text-primary)] block mb-1">
                    OTLP Ingestion Endpoint
                  </label>
                  <Input
                    placeholder="e.g. http://localhost:4318"
                    value={telemetryOtlpEndpoint}
                    onChange={e => setTelemetryOtlpEndpoint(e.target.value)}
                    className="text-xs font-mono min-h-[44px]"
                  />
                  <span className="text-[10px] text-[var(--text-subtle)] mt-1 block">
                    HTTP OTLP receiver address for trace and metric dispatch.
                  </span>
                </div>

                {/* Connection Test Output */}
                {testResult && (
                  <div className={cn(
                    'p-3 rounded-lg text-xs font-mono border space-y-1',
                    testResult.connected
                      ? 'bg-[var(--success-subtle)] border-[var(--success)]/30 text-[var(--success)]'
                      : 'bg-[var(--danger-subtle)] border-[var(--danger)]/30 text-[var(--danger)]'
                  )}>
                    <div className="flex items-center gap-1.5 font-semibold">
                      {testResult.connected ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                      <span>{testResult.status}</span>
                      {testResult.latency_ms > 0 && <span className="text-[10px] font-normal">({testResult.latency_ms} ms)</span>}
                    </div>
                    {testResult.error && (
                      <div className="text-[10px] text-[var(--text-secondary)] font-sans">{testResult.error}</div>
                    )}
                  </div>
                )}

                {/* Actions */}
                <div className="flex flex-col sm:flex-row gap-2 pt-1">
                  <Button
                    variant="outline"
                    onClick={handleTestTelemetry}
                    disabled={isTestingTelemetry}
                    className="min-h-[44px] text-xs flex-1"
                  >
                    {isTestingTelemetry ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                    ) : (
                      <Activity className="w-3.5 h-3.5 mr-1.5 text-[var(--accent)]" />
                    )}
                    Test Connection
                  </Button>
                  <Button
                    onClick={handleSaveTelemetry}
                    disabled={isSavingTelemetry}
                    className="min-h-[44px] text-xs flex-1"
                  >
                    {isSavingTelemetry ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                    ) : (
                      <Check className="w-3.5 h-3.5 mr-1.5" />
                    )}
                    Save Telemetry Settings
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Tab 3: System & Modes */}
          {settingsTab === 'system' && (
            <div className="space-y-3 py-3 text-xs">
              <div className="p-3.5 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-xs text-[var(--text-primary)] m-0">Application Mode</h4>
                  <div className="text-[var(--text-secondary)] mt-0.5">
                    Currently running in <strong>{state.appMode.toUpperCase()}</strong> mode.
                  </div>
                </div>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="min-h-[44px] text-xs"
                  onClick={() => state.appMode === 'demo' ? setAppMode('live') : setAppMode('demo')}
                >
                  Switch to {state.appMode === 'demo' ? 'Live' : 'Demo'} Mode
                </Button>
              </div>

              <div className="p-3.5 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)]">
                <h4 className="font-semibold text-xs text-[var(--text-primary)] m-0">Authentication Mode</h4>
                <div className="text-[var(--text-secondary)] mt-1">
                  Currently connected via <strong>ChatGPT Managed Mode</strong>. Platform API-key fallback enabled.
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)]">
                <h4 className="font-semibold text-xs text-[var(--text-primary)] m-0">Sandboxing & Permissions</h4>
                <div className="text-[var(--text-secondary)] mt-1">
                  Workspace write permissions and git worktrees are strictly confined to active allowed boundaries.
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="pt-2">
            <Button 
              onClick={() => setIsSettingsOpen(false)}
              className="w-full sm:w-auto min-h-[44px] text-xs"
            >
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  )
}
