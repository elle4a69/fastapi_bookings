import React from 'react'
import {
  FileDiff,
  Files,
  Users,
  FlaskConical,
  Settings,
  X,
  SlidersHorizontal
} from 'lucide-react'
import { useWorkbenchStore, type InspectorTab } from '../../store/useWorkbenchStore'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs'
import { ChangesTab } from './tabs/ChangesTab'
import { FilesTab } from './tabs/FilesTab'
import { SubAgentsTab } from './tabs/SubAgentsTab'
import { TestsTab } from './tabs/TestsTab'
import { SettingsInspectorTab } from './tabs/SettingsInspectorTab'
import { Button } from '../ui/button'

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
      {/* Mobile Backdrop for slide-out off-canvas sheet */}
      <div
        className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-xs transition-opacity"
        onClick={() => setInspectorOpen(false)}
        aria-hidden="true"
      />

      {/* Inspector Panel: Off-canvas on mobile/tablet, inline collapsible on desktop */}
      <aside
        style={{ width: `${state.inspectorWidth || 380}px` }}
        className="fixed lg:relative inset-y-0 right-0 z-50 lg:z-auto flex flex-col h-full bg-slate-900 border-l border-slate-800 text-slate-100 w-full max-w-[92vw] sm:max-w-md lg:max-w-none shadow-2xl lg:shadow-none shrink-0 overflow-hidden select-none transition-transform duration-200"
        aria-label="Inspector Panel"
      >
        {/* Header with Title and Close Button (Standardized h-11 slim header) */}
        <div className="h-11 px-3 border-b border-slate-800 bg-slate-950/70 shrink-0 flex items-center justify-between box-border">
          <h2 className="flex items-center gap-2 font-semibold text-xs text-slate-100 m-0 leading-tight">
            <SlidersHorizontal className="w-3.5 h-3.5 text-indigo-400" />
            <span>Inspector & Diff Review</span>
          </h2>

          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => setInspectorOpen(false)}
            className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
            aria-label="Close Inspector"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Tab Navigation using Radix Tabs */}
        <Tabs
          value={state.activeInspectorTab}
          onValueChange={(val) => setInspectorTab(val as InspectorTab)}
          className="flex-1 flex flex-col min-h-0 overflow-hidden"
        >
          <div className="px-2 pt-1.5 border-b border-slate-800 bg-slate-950/40 shrink-0 overflow-x-auto scrollbar-none">
            <TabsList className="h-8 bg-slate-900 p-0.5 rounded-lg border border-slate-800 gap-1 flex items-center w-max min-w-full sm:w-auto">
              {/* Tab 1: Diff Review */}
              <TabsTrigger
                value="changes"
                className="text-xs px-2.5 h-7 gap-1.5 text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium shrink-0 min-h-[36px] sm:min-h-0"
              >
                <FileDiff className="w-3.5 h-3.5 text-indigo-400" />
                <span>Diff Review</span>
                {state.diffFiles.length > 0 && (
                  <span className="text-[10px] font-mono px-1 rounded bg-indigo-500/20 text-indigo-400">
                    {state.diffFiles.length}
                  </span>
                )}
              </TabsTrigger>

              {/* Tab 2: Active Files */}
              <TabsTrigger
                value="files"
                className="text-xs px-2 h-7 gap-1 text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium shrink-0 min-h-[36px] sm:min-h-0"
              >
                <Files className="w-3 h-3 text-slate-400" />
                <span>Files</span>
              </TabsTrigger>

              {/* Tab 3: Settings */}
              <TabsTrigger
                value="settings"
                className="text-xs px-2 h-7 gap-1 text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium shrink-0 min-h-[36px] sm:min-h-0"
              >
                <Settings className="w-3 h-3 text-slate-400" />
                <span>Settings</span>
              </TabsTrigger>

              {/* Tab 4: SubAgents */}
              <TabsTrigger
                value="subagents"
                className="text-xs px-2 h-7 gap-1 text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium shrink-0 min-h-[36px] sm:min-h-0"
              >
                <Users className="w-3 h-3 text-slate-400" />
                <span>Agents</span>
                {activeSubAgents.length > 0 && (
                  <span className="text-[10px] font-mono px-1 rounded bg-indigo-500/20 text-indigo-400">
                    {activeSubAgents.length}
                  </span>
                )}
              </TabsTrigger>

              {/* Tab 5: Tests */}
              <TabsTrigger
                value="tests"
                className="text-xs px-2 h-7 gap-1 text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium shrink-0 min-h-[36px] sm:min-h-0"
              >
                <FlaskConical className="w-3 h-3 text-slate-400" />
                <span>Tests</span>
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Tab Content Panels */}
          <div className="flex-1 min-h-0 overflow-y-auto">
            <TabsContent value="changes" className="mt-0 h-full">
              <ChangesTab />
            </TabsContent>

            <TabsContent value="files" className="mt-0 h-full">
              <FilesTab />
            </TabsContent>

            <TabsContent value="settings" className="mt-0 h-full">
              <SettingsInspectorTab />
            </TabsContent>

            <TabsContent value="subagents" className="mt-0 h-full">
              <SubAgentsTab />
            </TabsContent>

            <TabsContent value="tests" className="mt-0 h-full">
              <TestsTab />
            </TabsContent>
          </div>
        </Tabs>
      </aside>
    </>
  )
}
export default Inspector
