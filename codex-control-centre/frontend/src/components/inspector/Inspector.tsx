import React from 'react'
import { 
  FileDiff, 
  Files, 
  Users, 
  FlaskConical, 
  Terminal, 
  Activity, 
  Info, 
  X, 
  SlidersHorizontal 
} from 'lucide-react'
import { useWorkbenchStore, type InspectorTab } from '../../store/useWorkbenchStore'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs'
import { ChangesTab } from './tabs/ChangesTab'
import { FilesTab } from './tabs/FilesTab'
import { SubAgentsTab } from './tabs/SubAgentsTab'
import { TestsTab } from './tabs/TestsTab'
import { TerminalTab } from './tabs/TerminalTab'
import { TelemetryTab } from './tabs/TelemetryTab'
import { ThreadDetailsTab } from './tabs/ThreadDetailsTab'

export const Inspector: React.FC = () => {
  const { 
    state, 
    setInspectorOpen, 
    setInspectorTab, 
    activeSubAgents 
  } = useWorkbenchStore()

  if (!state.isInspectorOpen) return null

  return (
    <>
      {/* Mobile backdrop for small viewport inspector drawer */}
      <div 
        className="fixed inset-0 bg-black/50 z-30 md:hidden transition-opacity" 
        onClick={() => setInspectorOpen(false)} 
        aria-hidden="true" 
      />

      <aside
        style={{ width: `${state.inspectorWidth}px` }}
        className="fixed md:relative inset-y-0 right-0 z-40 flex flex-col h-full bg-[var(--surface-primary)] border-l border-[var(--border)] max-w-[90vw] sm:max-w-md shadow-2xl md:shadow-none flex-shrink-0 overflow-hidden"
        aria-label="Inspector Panel"
      >
        {/* Header with Tab Navigation */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)] bg-[var(--surface-primary)] flex-shrink-0">
          <h2 className="flex items-center gap-1.5 font-semibold text-xs text-[var(--text-primary)] m-0">
            <SlidersHorizontal className="w-3.5 h-3.5 text-[var(--accent)]" />
            <span>Inspector</span>
          </h2>

          <button
            onClick={() => setInspectorOpen(false)}
            className="p-1 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-colors"
            aria-label="Close Inspector"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

      <Tabs
        value={state.activeInspectorTab}
        onValueChange={(val) => setInspectorTab(val as InspectorTab)}
        className="flex-1 flex flex-col overflow-hidden"
      >
        {/* Tab Bar */}
        <div className="px-2 pt-1 border-b border-[var(--border)] bg-[var(--surface-secondary)]/30 flex-shrink-0">
          <TabsList className="h-8 gap-0.5 overflow-x-auto">
            <TabsTrigger value="changes" className="text-[11px] px-2 h-7 gap-1">
              <FileDiff className="w-3 h-3" />
              <span>Changes</span>
              {state.diffFiles.length > 0 && (
                <span className="text-[9px] font-mono px-1 rounded bg-[var(--accent-subtle)] text-[var(--accent)]">
                  {state.diffFiles.length}
                </span>
              )}
            </TabsTrigger>

            <TabsTrigger value="subagents" className="text-[11px] px-2 h-7 gap-1">
              <Users className="w-3 h-3" />
              <span>Agents</span>
              {activeSubAgents.length > 0 && (
                <span className="text-[9px] font-mono px-1 rounded bg-[var(--accent-subtle)] text-[var(--accent)]">
                  {activeSubAgents.length}
                </span>
              )}
            </TabsTrigger>

            <TabsTrigger value="files" className="text-[11px] px-2 h-7 gap-1">
              <Files className="w-3 h-3" />
              <span>Files</span>
            </TabsTrigger>

            <TabsTrigger value="tests" className="text-[11px] px-2 h-7 gap-1">
              <FlaskConical className="w-3 h-3" />
              <span>Tests</span>
            </TabsTrigger>

            <TabsTrigger value="telemetry" className="text-[11px] px-2 h-7 gap-1">
              <Activity className="w-3 h-3" />
              <span>Telemetry</span>
            </TabsTrigger>

            <TabsTrigger value="terminal" className="text-[11px] px-2 h-7 gap-1">
              <Terminal className="w-3 h-3" />
              <span>Terminal</span>
            </TabsTrigger>

            <TabsTrigger value="details" className="text-[11px] px-2 h-7 gap-1">
              <Info className="w-3 h-3" />
              <span>Details</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Tab Contents */}
        <div className="flex-1 overflow-y-auto">
          <TabsContent value="changes" className="m-0 h-full">
            <ChangesTab />
          </TabsContent>
          <TabsContent value="subagents" className="m-0 h-full">
            <SubAgentsTab />
          </TabsContent>
          <TabsContent value="files" className="m-0 h-full">
            <FilesTab />
          </TabsContent>
          <TabsContent value="tests" className="m-0 h-full">
            <TestsTab />
          </TabsContent>
          <TabsContent value="telemetry" className="m-0 h-full">
            <TelemetryTab />
          </TabsContent>
          <TabsContent value="terminal" className="m-0 h-full">
            <TerminalTab />
          </TabsContent>
          <TabsContent value="details" className="m-0 h-full">
            <ThreadDetailsTab />
          </TabsContent>
        </div>
      </Tabs>
    </aside>
    </>
  )
}
