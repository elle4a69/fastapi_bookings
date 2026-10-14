import { useState, useRef, useEffect, useMemo } from 'react'
import {
  Terminal,
  Play,
  Pause,
  Trash2,
  Copy,
  Check,
  ChevronRight,
  ChevronDown,
  Search,
  Radio,
  ArrowDownCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  type AgentActivityLog,
  type AgentActivityType,
  loadPersistedAgentActivityLogs,
  savePersistedAgentActivityLogs,
  clearPersistedAgentActivityLogs,
  MAX_PERSISTED_AGENT_ACTIVITY_LOGS,
} from '../realtime-protocol'
import { useBusinessAssistantOptional } from '../business-assistant-context'

export interface LiveAgentActivityConsoleProps {
  logs?: AgentActivityLog[]
  onClear?: () => void
  className?: string
  title?: string
  maxHeight?: string
}

function getAgentBadgeConfig(agentLabel?: string, modelName?: string) {
  const norm = (modelName || agentLabel || '').toLowerCase()
  if (norm.includes('live-1') || norm.includes('voice front')) {
    return {
      tag: 'GPT-Live-1',
      className: 'bg-cyan-950/80 text-cyan-300 border-cyan-700/60 font-mono text-[10px] font-semibold',
    }
  }
  if (norm.includes('terra') || norm.includes('reasoning') || norm.includes('5.6')) {
    return {
      tag: 'GPT-5.6-Terra',
      className: 'bg-purple-950/80 text-purple-300 border-purple-700/60 font-mono text-[10px] font-semibold',
    }
  }
  if (norm.includes('fastapi') || norm.includes('tool runner') || norm.includes('python-tools') || norm.includes('tools')) {
    return {
      tag: 'FastAPI Backend',
      className: 'bg-amber-950/80 text-amber-300 border-amber-700/60 font-mono text-[10px] font-semibold',
    }
  }
  if (norm.includes('gpt-4o') || norm.includes('text assistant')) {
    return {
      tag: 'GPT-4o',
      className: 'bg-blue-950/80 text-blue-300 border-blue-700/60 font-mono text-[10px] font-semibold',
    }
  }
  if (norm.includes('grok') || norm.includes('xai')) {
    return {
      tag: 'xAI Grok Voice',
      className: 'bg-teal-950/80 text-teal-300 border-teal-700/60 font-mono text-[10px] font-semibold',
    }
  }
  if (norm.includes('gpt-live') || norm.includes('webrtc')) {
    return {
      tag: 'OpenAI GPT-Live',
      className: 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60 font-mono text-[10px] font-semibold',
    }
  }
  if (norm.includes('client') || norm.includes('user')) {
    return {
      tag: 'User',
      className: 'bg-zinc-800 text-zinc-300 border-zinc-700 font-mono text-[10px] font-semibold',
    }
  }
  return {
    tag: agentLabel || modelName || 'Agent',
    className: 'bg-zinc-800 text-zinc-300 border-zinc-700 font-mono text-[10px] font-semibold',
  }
}

function getEventBadgeConfig(type: AgentActivityType) {
  switch (type) {
    case 'VOICE_IN':
      return {
        label: '🎙️ VOICE_IN',
        className: 'bg-cyan-950/90 text-cyan-300 border-cyan-700/60 font-mono text-[10px]',
      }
    case 'USER_INPUT':
      return {
        label: '💬 USER_IN',
        className: 'bg-blue-950/90 text-blue-300 border-blue-700/60 font-mono text-[10px]',
      }
    case 'DELEGATION':
      return {
        label: '🔄 DELEGATION',
        className: 'bg-indigo-950/90 text-indigo-300 border-indigo-700/60 font-mono text-[10px]',
      }
    case 'TOOL_EXEC':
      return {
        label: '🛠️ TOOL_EXEC',
        className: 'bg-amber-950/90 text-amber-300 border-amber-700/60 font-mono text-[10px]',
      }
    case 'TOOL_RESULT':
      return {
        label: '📥 TOOL_RESULT',
        className: 'bg-emerald-950/90 text-emerald-300 border-emerald-700/60 font-mono text-[10px]',
      }
    case 'REASONING_OUT':
      return {
        label: '🧠 REASONING',
        className: 'bg-violet-950/90 text-violet-300 border-violet-700/60 font-mono text-[10px]',
      }
    case 'VOICE_OUT':
      return {
        label: '🔊 VOICE_OUT',
        className: 'bg-emerald-950/90 text-emerald-300 border-emerald-700/60 font-mono text-[10px]',
      }
    case 'ERROR':
      return {
        label: '❌ ERROR',
        className: 'bg-rose-950/90 text-rose-300 border-rose-700/60 font-mono text-[10px]',
      }
    default:
      return {
        label: type,
        className: 'bg-zinc-800 text-zinc-300 border-zinc-700 font-mono text-[10px]',
      }
  }
}

function formatTime(isoString: string): string {
  try {
    const d = new Date(isoString)
    const h = d.getHours().toString().padStart(2, '0')
    const m = d.getMinutes().toString().padStart(2, '0')
    const s = d.getSeconds().toString().padStart(2, '0')
    const ms = d.getMilliseconds().toString().padStart(3, '0')
    return `${h}:${m}:${s}.${ms}`
  } catch {
    return isoString.slice(11, 23) || isoString
  }
}

export function LiveAgentActivityConsole({
  logs: propsLogs,
  onClear: propsOnClear,
  className = '',
  title = 'Live Agent Activity Console',
  maxHeight = '600px',
}: LiveAgentActivityConsoleProps) {
  // Gracefully use context if available
  const ctx = useBusinessAssistantOptional()
  const contextLogs = ctx?.activityLogs
  const contextClear = ctx?.clearActivityLogs
  const voiceState = ctx?.voiceState

  const [fallbackLogs, setFallbackLogs] = useState<AgentActivityLog[]>(() => {
    return propsLogs || contextLogs ? [] : loadPersistedAgentActivityLogs()
  })

  useEffect(() => {
    if (propsLogs || contextLogs) return
    const handleEvent = (e: Event) => {
      const custom = e as CustomEvent<AgentActivityLog>
      if (custom.detail) {
        setFallbackLogs((prev) => {
          if (prev.some((item) => item.id === custom.detail.id)) return prev
          const seen = new Set<string>()
          const sanitizedPrev: AgentActivityLog[] = []
          for (const item of prev) {
            if (item?.id && !seen.has(item.id)) {
              seen.add(item.id)
              sanitizedPrev.push(item)
            }
          }
          const next = [...sanitizedPrev.slice(-(MAX_PERSISTED_AGENT_ACTIVITY_LOGS - 1)), custom.detail]
          savePersistedAgentActivityLogs(next)
          return next
        })
      }
    }
    window.addEventListener('live-agent-activity', handleEvent)
    return () => window.removeEventListener('live-agent-activity', handleEvent)
  }, [propsLogs, contextLogs])

  const logs = propsLogs ?? contextLogs ?? fallbackLogs
  const handleClear = () => {
    if (propsOnClear) {
      propsOnClear()
    } else if (contextClear) {
      contextClear()
    } else {
      setFallbackLogs([])
    }
    clearPersistedAgentActivityLogs()
  }

  const [autoScroll, setAutoScroll] = useState(true)
  const [copied, setCopied] = useState(false)
  const [filterType, setFilterType] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedLogIds, setExpandedLogIds] = useState<Set<string>>(new Set())

  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const toggleExpand = (id: string) => {
    setExpandedLogIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleCopyTrace = async () => {
    try {
      const tracePayload = JSON.stringify(logs, null, 2)
      await navigator.clipboard.writeText(tracePayload)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard write fallback
    }
  }

  const filteredLogs = useMemo(() => {
    const seenIds = new Set<string>()
    const deduplicatedLogs: AgentActivityLog[] = []
    for (const log of logs) {
      if (!seenIds.has(log.id)) {
        seenIds.add(log.id)
        deduplicatedLogs.push(log)
      }
    }

    return deduplicatedLogs.filter((log) => {
      if (filterType !== 'ALL') {
        if (filterType === 'VOICE' && !['VOICE_IN', 'VOICE_OUT', 'USER_INPUT'].includes(log.type)) return false
        if (filterType === 'TOOLS' && !['TOOL_EXEC', 'TOOL_RESULT'].includes(log.type)) return false
        if (filterType === 'REASONING' && !['REASONING_OUT', 'DELEGATION'].includes(log.type)) return false
        if (filterType === 'ERROR' && log.type !== 'ERROR') return false
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchesTitle = log.title.toLowerCase().includes(q)
        const matchesDetails = log.details?.toLowerCase().includes(q)
        const matchesType = log.type.toLowerCase().includes(q)
        const matchesAgent = (log.agentLabel?.toLowerCase() || '').includes(q) || (log.modelName?.toLowerCase() || '').includes(q)
        const matchesPayload = log.payload ? JSON.stringify(log.payload).toLowerCase().includes(q) : false
        return matchesTitle || matchesDetails || matchesType || matchesAgent || matchesPayload
      }
      return true
    })
  }, [logs, filterType, searchQuery])

  const isLive = voiceState === 'live' || voiceState === 'connecting'

  return (
    <section
      className={`flex flex-col h-full rounded-xl border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-xl overflow-hidden font-mono ${className}`}
      aria-label="Live Agent Activity Console"
      style={{ maxHeight }}
    >
      {/* Console Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/80 bg-zinc-900/90 px-3.5 py-2.5">
        <div className="flex items-center gap-2.5">
          <Terminal className="h-4 w-4 text-emerald-400" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-200">
            {title}
          </h2>
          <Badge
            variant="outline"
            className={`text-[10px] px-2 py-0.5 tracking-widest font-mono uppercase ${
              isLive
                ? 'border-emerald-500/80 bg-emerald-950/60 text-emerald-300 animate-pulse'
                : 'border-zinc-700 bg-zinc-800 text-zinc-400'
            }`}
          >
            <span className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full ${isLive ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
            {isLive ? '● LIVE' : 'IDLE'}
          </Badge>
          <span className="text-[11px] text-zinc-500 hidden sm:inline">
            {logs.length} event{logs.length === 1 ? '' : 's'}
          </span>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {/* Auto-scroll toggle */}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setAutoScroll((prev) => !prev)}
            className={`h-7 px-2 text-[11px] border border-zinc-800 hover:bg-zinc-800 hover:text-zinc-100 ${
              autoScroll ? 'text-emerald-400' : 'text-zinc-500'
            }`}
            title={autoScroll ? 'Pause auto-scrolling' : 'Resume auto-scrolling'}
          >
            {autoScroll ? <Pause className="h-3 w-3 mr-1" /> : <Play className="h-3 w-3 mr-1" />}
            {autoScroll ? 'Auto-scroll ON' : 'PAUSED'}
          </Button>

          {/* Copy Trace */}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleCopyTrace}
            disabled={logs.length === 0}
            className="h-7 px-2 text-[11px] border border-zinc-800 hover:bg-zinc-800 text-zinc-300"
            title="Copy trace log to clipboard"
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 mr-1 text-emerald-400" />
                <span className="text-emerald-400">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="h-3 w-3 mr-1" />
                <span>Copy Trace</span>
              </>
            )}
          </Button>

          {/* Clear Logs */}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleClear}
            disabled={logs.length === 0}
            className="h-7 px-2 text-[11px] border border-zinc-800 hover:bg-rose-950/50 hover:text-rose-300 text-zinc-400"
            title="Clear activity log history"
          >
            <Trash2 className="h-3 w-3 mr-1" />
            <span>Clear</span>
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/60 bg-zinc-900/40 px-3 py-1.5 text-xs">
        <div className="flex items-center gap-1 overflow-x-auto py-0.5">
          {(['ALL', 'VOICE', 'TOOLS', 'REASONING', 'ERROR'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setFilterType(tab)}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${
                filterType === tab
                  ? 'bg-zinc-800 text-zinc-100 border border-zinc-700'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5 min-w-[140px] max-w-[200px]">
          <Search className="h-3 w-3 text-zinc-500 shrink-0" />
          <input
            type="text"
            placeholder="Search trace…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-transparent text-[11px] text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
          />
        </div>
      </div>

      {/* Log Stream Container */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-3 space-y-2 select-text text-[11px] leading-relaxed scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-zinc-950"
        role="log"
        aria-live="polite"
      >
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[160px] text-center text-zinc-600 py-8">
            <Radio className="h-8 w-8 mb-2 opacity-40 animate-pulse" />
            <p className="font-medium text-xs">Waiting for live agent events…</p>
            <p className="text-[10px] text-zinc-600 max-w-sm mt-1">
              Real-time WebRTC audio frames, speech transcripts, intermediate reasoning, and tool executions will stream here live.
            </p>
          </div>
        ) : (
          filteredLogs.map((log, index) => {
            const badge = getEventBadgeConfig(log.type)
            const agentBadge = getAgentBadgeConfig(log.agentLabel, log.modelName)
            const isExpanded = expandedLogIds.has(log.id)
            const hasPayload = log.payload !== undefined && log.payload !== null

            return (
              <div
                key={`${log.id}-${index}`}
                className={`group rounded-md border p-2 transition-colors ${
                  log.type === 'ERROR'
                    ? 'border-rose-900/50 bg-rose-950/20 hover:bg-rose-950/30'
                    : log.type === 'TOOL_EXEC'
                      ? 'border-amber-900/40 bg-amber-950/10 hover:bg-amber-950/20'
                      : log.type === 'TOOL_RESULT'
                        ? 'border-emerald-900/40 bg-emerald-950/10 hover:bg-emerald-950/20'
                        : 'border-zinc-800/80 bg-zinc-900/50 hover:bg-zinc-900/80'
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[10px] text-zinc-500 font-mono">
                      {formatTime(log.timestamp)}
                    </span>
                    <Badge variant="outline" className={`py-0 px-1.5 ${agentBadge.className}`}>
                      [{agentBadge.tag}]
                    </Badge>
                    <Badge variant="outline" className={`py-0 px-1.5 ${badge.className}`}>
                      {badge.label}
                    </Badge>
                    <span className="font-semibold text-zinc-200 text-[11px]">
                      {log.title}
                    </span>
                  </div>

                  {hasPayload && (
                    <button
                      type="button"
                      onClick={() => toggleExpand(log.id)}
                      className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-zinc-200 border border-zinc-800 rounded px-1.5 py-0.5 bg-zinc-900/80 transition-colors"
                      aria-expanded={isExpanded}
                    >
                      {isExpanded ? (
                        <>
                          <ChevronDown className="h-3 w-3" />
                          <span>Hide Payload</span>
                        </>
                      ) : (
                        <>
                          <ChevronRight className="h-3 w-3" />
                          <span>Inspect Payload</span>
                        </>
                      )}
                    </button>
                  )}
                </div>

                {log.details && (
                  <div className="mt-1 text-zinc-300 font-mono text-[11px] break-words whitespace-pre-wrap pl-1 border-l-2 border-zinc-700/60 ml-0.5">
                    {log.details}
                  </div>
                )}

                {hasPayload && isExpanded && (
                  <div className="mt-2 rounded bg-zinc-950 border border-zinc-800 p-2 overflow-x-auto text-[10px] text-emerald-400 font-mono">
                    <div className="flex items-center justify-between text-zinc-500 pb-1 mb-1 border-b border-zinc-800 text-[9px] uppercase tracking-wider">
                      <span>Payload Inspector</span>
                      <span>JSON</span>
                    </div>
                    <pre className="whitespace-pre overflow-x-auto">
                      {JSON.stringify(log.payload, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Footer bar */}
      <div className="border-t border-zinc-800/70 bg-zinc-900/50 px-3 py-1.5 flex items-center justify-between text-[10px] text-zinc-500">
        <div className="flex items-center gap-2">
          <span>Channel: <strong className="text-zinc-400">oai-events (WebRTC)</strong></span>
          <span>•</span>
          <span>Buffer: <strong className="text-zinc-400">{logs.length}/500</strong></span>
        </div>
        {!autoScroll && (
          <button
            type="button"
            onClick={() => {
              setAutoScroll(true)
              if (scrollContainerRef.current) {
                scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight
              }
            }}
            className="flex items-center gap-1 text-emerald-400 hover:underline"
          >
            <ArrowDownCircle className="h-3 w-3" />
            <span>Jump to Latest</span>
          </button>
        )}
      </div>
    </section>
  )
}
