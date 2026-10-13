import React, { useState, useEffect } from 'react'
import {
  Shield,
  Activity,
  Plus,
  Trash2,
  Loader2
} from 'lucide-react'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { Button } from '../../ui/button'
import { Input } from '../../ui/input'
import { Badge } from '../../ui/badge'

export const SettingsInspectorTab: React.FC = () => {
  const {
    state,
    fetchBoundaries,
    addBoundary,
    removeBoundary,
    fetchTelemetrySettings,
    updateTelemetrySettings,
    testTelemetry
  } = useWorkbenchStore()

  const [newPath, setNewPath] = useState('')
  const [newName, setNewName] = useState('')
  const [boundaryErr, setBoundaryErr] = useState('')
  const [signozUrl, setSignozUrl] = useState('')
  const [otlpEndpoint, setOtlpEndpoint] = useState('')
  const [isTesting, setIsTesting] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  useEffect(() => {
    fetchBoundaries()
    fetchTelemetrySettings()
    if (state.telemetrySettings) {
      setSignozUrl(state.telemetrySettings.signoz_url)
      setOtlpEndpoint(state.telemetrySettings.otlp_endpoint)
    }
  }, [])

  const handleAddBoundary = async () => {
    if (!newPath.trim()) {
      setBoundaryErr('Path is required')
      return
    }
    setBoundaryErr('')
    await addBoundary(newPath.trim(), newName.trim() || undefined)
    setNewPath('')
    setNewName('')
  }

  const handleTest = async () => {
    setIsTesting(true)
    setFeedback(null)
    try {
      const res = await testTelemetry()
      if (res.connected) {
        setFeedback(`Connected (${res.latency_ms}ms latency)`)
      } else {
        setFeedback(`Failed: ${(res as any).error || (res as any).status || 'Unreachable'}`)
      }
    } catch (err: any) {
      setFeedback(`Error: ${err.message}`)
    } finally {
      setIsTesting(false)
    }
  }

  const handleSaveTelemetry = async () => {
    await updateTelemetrySettings({
      signoz_url: signozUrl || 'http://localhost:3301',
      otlp_endpoint: otlpEndpoint || 'http://localhost:4318',
      enabled: true
    })
    setFeedback('Telemetry settings saved.')
  }

  return (
    <div className="p-3 space-y-4 text-xs text-slate-200">
      {/* 1. Workspace Boundaries */}
      <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-xs text-slate-100 flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-indigo-400" />
            Workspace Boundaries
          </span>
          <Badge variant="outline" className="text-[10px] border-slate-700 text-slate-300">
            {state.boundaries.length} Active
          </Badge>
        </div>

        <p className="text-[11px] text-slate-400 leading-relaxed">
          Filesystem isolation roots protecting repository assets from out-of-boundary tool access.
        </p>

        <div className="space-y-1.5">
          {state.boundaries.map((b) => (
            <div
              key={b.id}
              className="p-2 rounded border border-slate-800 bg-slate-900 flex items-center justify-between text-[11px]"
            >
              <div className="min-w-0 flex-1 pr-1.5">
                <div className="font-medium text-slate-200 truncate">{b.name}</div>
                <div className="font-mono text-[10px] text-slate-400 truncate">{b.path}</div>
              </div>
              {b.is_default ? (
                <Badge variant="outline" className="text-[9px] border-emerald-500/40 text-emerald-400 shrink-0">
                  Default
                </Badge>
              ) : (
                <button
                  type="button"
                  onClick={() => removeBoundary(b.id)}
                  className="p-1 text-slate-400 hover:text-rose-400 shrink-0"
                  aria-label="Remove boundary"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="pt-2 border-t border-slate-800 space-y-1.5">
          <Input
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
            placeholder="Filesystem path..."
            className="h-7 text-[11px] bg-slate-900 border-slate-700 text-slate-100 font-mono"
          />
          <div className="flex gap-1.5">
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Display label..."
              className="h-7 text-[11px] bg-slate-900 border-slate-700 text-slate-100 flex-1"
            />
            <Button
              size="sm"
              onClick={handleAddBoundary}
              className="h-7 px-2.5 text-xs bg-indigo-600 hover:bg-indigo-500 text-white"
            >
              <Plus className="w-3 h-3 mr-0.5" />
              Add
            </Button>
          </div>
          {boundaryErr && <p className="text-[11px] text-rose-400">{boundaryErr}</p>}
        </div>
      </div>

      {/* 2. OTel Telemetry Settings */}
      <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-xs text-slate-100 flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            SigNoz OTel Telemetry
          </span>
          <span className="flex items-center gap-1 text-[10px] text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Active
          </span>
        </div>

        <div>
          <label className="text-[11px] font-medium text-slate-400 block mb-0.5">
            SigNoz URL
          </label>
          <Input
            value={signozUrl}
            onChange={(e) => setSignozUrl(e.target.value)}
            placeholder="http://localhost:3301"
            className="h-7 text-[11px] bg-slate-900 border-slate-700 text-slate-100 font-mono"
          />
        </div>

        <div>
          <label className="text-[11px] font-medium text-slate-400 block mb-0.5">
            OTLP Collector Endpoint
          </label>
          <Input
            value={otlpEndpoint}
            onChange={(e) => setOtlpEndpoint(e.target.value)}
            placeholder="http://localhost:4318"
            className="h-7 text-[11px] bg-slate-900 border-slate-700 text-slate-100 font-mono"
          />
        </div>

        {feedback && (
          <p className="text-[11px] p-1.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
            {feedback}
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleTest}
            disabled={isTesting}
            className="h-7 px-2 text-[11px] border-slate-700 text-slate-300 hover:bg-slate-800 flex-1"
          >
            {isTesting ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
            Test Link
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleSaveTelemetry}
            className="h-7 px-2 text-[11px] bg-indigo-600 hover:bg-indigo-500 text-white flex-1"
          >
            Save
          </Button>
        </div>
      </div>
    </div>
  )
}
