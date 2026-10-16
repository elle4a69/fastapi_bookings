import React, { useState, useEffect, useRef } from 'react'
import { ListFilter, Trash2, Terminal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { authenticatedAdminFetch } from '@/lib/api'
import type { StreamEvent } from './types'
import {
  connectResidentEventStream,
  type ResidentStreamState,
} from './residentEventStream'

export const EventStream: React.FC = () => {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [eventFilter, setEventFilter] = useState<string>('all')
  const [autoScroll, setAutoScroll] = useState<boolean>(true)
  const [streamState, setStreamState] = useState<ResidentStreamState>({
    status: 'connecting',
  })
  const terminalBottomRef = useRef<HTMLDivElement>(null)

  // SSE Live Event Stream Connection
  useEffect(() => {
    return connectResidentEventStream({
      fetchStream: authenticatedAdminFetch,
      onEvent: (event) => {
        setEvents((prev) => [...prev.slice(-250), event])
      },
      onState: setStreamState,
    })
  }, [])

  // Auto-scroll terminal log
  useEffect(() => {
    if (autoScroll && terminalBottomRef.current) {
      terminalBottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events, autoScroll])

  const filteredEvents = events.filter((ev) => {
    if (eventFilter === 'all') return true
    if (eventFilter === 'thoughts') return ev.type === 'thought'
    if (eventFilter === 'steps') return ev.type === 'step'
    if (eventFilter === 'audit') return ev.type === 'audit'
    if (eventFilter === 'fixes') return ev.type === 'fix_status'
    return true
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border rounded-xl p-3 bg-muted/20">
        {/* Filters */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-muted-foreground mr-1 flex items-center gap-1">
            <ListFilter className="w-3.5 h-3.5" /> Filter:
          </span>
          {['all', 'thoughts', 'steps', 'audit', 'fixes'].map((flt) => (
            <Button
              key={flt}
              size="sm"
              variant={eventFilter === flt ? 'default' : 'outline'}
              onClick={() => setEventFilter(flt)}
              className="h-7 text-[11px] capitalize"
            >
              {flt}
            </Button>
          ))}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4">
          <span
            className="text-xs text-muted-foreground"
            role={streamState.status === 'error' ? 'alert' : 'status'}
          >
            {streamState.status === 'live' && 'Live'}
            {streamState.status === 'connecting' && 'Connecting…'}
            {streamState.status === 'retrying' &&
              `Reconnecting (attempt ${streamState.attempt})…`}
            {streamState.status === 'error' && streamState.message}
          </span>
          <div className="flex items-center space-x-2">
            <Switch
              id="autoscroll-switch"
              checked={autoScroll}
              onCheckedChange={setAutoScroll}
            />
            <Label htmlFor="autoscroll-switch" className="text-xs font-medium cursor-pointer">
              Auto-scroll
            </Label>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setEvents([])}
            className="h-7 text-xs text-muted-foreground hover:text-destructive gap-1"
          >
            <Trash2 className="w-3.5 h-3.5" /> Clear Log
          </Button>
        </div>
      </div>

      {/* Terminal Output */}
      <div className="font-mono text-xs bg-zinc-950 text-zinc-100 rounded-xl border border-zinc-800 p-4 h-[550px] overflow-y-auto space-y-2 shadow-inner">
        {filteredEvents.length === 0 ? (
          <div className="text-zinc-500 italic text-center py-28 flex flex-col items-center justify-center">
            <Terminal className="w-8 h-8 text-zinc-600 mb-2 opacity-50" />
            No events streamed yet. Run an audit or execute a plan to stream live thoughts and steps.
          </div>
        ) : (
          filteredEvents.map((ev, i) => {
            const time = new Date(ev.timestamp).toLocaleTimeString()
            return (
              <div key={i} className="flex items-start gap-2.5 py-1 border-b border-zinc-900/60 leading-relaxed">
                <span className="text-zinc-500 select-none shrink-0 text-[10px] mt-0.5">[{time}]</span>

                {/* Badge */}
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase shrink-0 ${
                    ev.type === 'thought'
                      ? 'bg-purple-950 text-purple-300 border border-purple-800'
                      : ev.type === 'step'
                      ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                      : ev.type === 'audit'
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      : ev.type === 'fix_status'
                      ? 'bg-amber-950 text-amber-300 border border-amber-800'
                      : 'bg-zinc-800 text-zinc-300'
                  }`}
                >
                  {ev.type}
                </span>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  {ev.title && <span className="font-semibold text-zinc-200 mr-1.5">{ev.title}:</span>}
                  <span className="text-zinc-300 break-words">
                    {typeof ev.data === 'string' ? ev.data : JSON.stringify(ev.data)}
                  </span>
                </div>
              </div>
            )
          })
        )}
        <div ref={terminalBottomRef} />
      </div>
    </div>
  )
}
