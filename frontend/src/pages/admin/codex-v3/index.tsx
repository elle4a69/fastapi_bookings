import React, { useState, useCallback, useMemo } from 'react'
import { CodexV3Layout } from './CodexV3Layout'
import type { CodexView, MobileTab, TimelineEvent } from './types'
import { CodexVoiceProvider, useCodexVoice } from './context/CodexVoiceContext'
import { TransparentStream } from './components/stream/TransparentStream'
import {
  TicketsWorkspace,
  CodingWorkspace,
  PlanningWorkspace,
  SignalsWorkspace,
  type SupportTicket
} from './workspaces'

const INITIAL_TIMELINE_EVENTS: TimelineEvent[] = [
  {
    type: 'user_message',
    id: 'msg-1',
    content: 'Codex, please triage high-severity lock contention ERR-503 in the booking engine and verify regression suite.',
    timestamp: '10:14 AM'
  },
  {
    type: 'thinking',
    id: 'th-1',
    thinking: {
      durationSeconds: 2.4,
      steps: [
        'Inspected PostgreSQL transaction locks on appointment_locks table',
        'Identified parallel slot acquisition race condition without nowait clause',
        'Formulated exponential backoff retry policy and composite index migration'
      ]
    }
  },
  {
    type: 'subagent',
    id: 'sa-1',
    subagent: {
      id: 'worker-db-concurrency',
      role: 'PostgreSQL Concurrency Specialist',
      task: 'Acquire row lock with exponential backoff & index optimization',
      status: 'done',
      elapsedSec: 6,
      currentAction: 'Verified isolation boundary in app/services/scheduling/booking_engine.py'
    }
  },
  {
    type: 'tool',
    id: 'tool-1',
    tool: {
      id: 'exec-1',
      toolName: 'replace_file_content',
      status: 'completed',
      targetFile: 'app/services/scheduling/booking_engine.py',
      durationMs: 220
    }
  },
  {
    type: 'diff',
    id: 'diff-1',
    patch: {
      id: 'patch-booking-engine',
      filePath: 'app/services/scheduling/booking_engine.py',
      additions: 14,
      deletions: 3,
      diffHunks: [
        '@@ -182,7 +182,18 @@ async def acquire_hold_lock(db: AsyncSession, provider_id: int, slot_id: str):',
        '-    stmt = select(AppointmentLock).where(AppointmentLock.slot_id == slot_id).with_for_update()',
        '+    for attempt in range(MAX_RETRIES):',
        '+        try:',
        '+            stmt = select(AppointmentLock).where(AppointmentLock.slot_id == slot_id).with_for_update(nowait=True)',
        '+            result = await db.execute(stmt)',
        '+            return result.scalar_one_or_none()',
        '+        except OperationalError as err:',
        '+            if attempt == MAX_RETRIES - 1: raise LockTimeoutError() from err',
        '+            await asyncio.sleep(0.05 * (2 ** attempt))'
      ],
      status: 'pending'
    }
  },
  {
    type: 'terminal',
    id: 'term-1',
    terminal: {
      id: 'run-pytest-bookings',
      command: 'pytest tests/test_bookings.py',
      output: '14 passed in 1.42s',
      exitCode: 0,
      passedCount: 14,
      failedCount: 0,
      durationMs: 1420,
      status: 'completed'
    }
  },
  {
    type: 'approval',
    id: 'gate-1',
    gate: {
      id: 'gate-promote-main',
      title: 'Promote to Release Tracking Branch',
      operation: 'git merge --ff-only fix/concurrency-booking into main',
      riskLevel: 'medium',
      status: 'pending'
    }
  },
  {
    type: 'agent_response',
    id: 'resp-1',
    content: 'I have hardened slot acquisition with optimistic nowait retry handling and confirmed all 14 concurrency tests pass. The approval gate above is ready for your sign-off.',
    timestamp: '10:16 AM'
  }
]

const CodexV3PageInner: React.FC = () => {
  const [activeView, setActiveView] = useState<CodexView>('tickets')
  const [mobileTab, setMobileTab] = useState<MobileTab>('workspace')
  const [events, setEvents] = useState<TimelineEvent[]>(INITIAL_TIMELINE_EVENTS)
  const [isStreaming, setIsStreaming] = useState(false)

  // Realtime Voice Context
  const voice = useCodexVoice()

  // Dynamic status counters
  const ticketCount = 4
  const subagentCount = 1
  const signalCount = 5

  // Interactivity: launch investigation from tickets workspace
  const handleLaunchInvestigation = useCallback((ticket: SupportTicket) => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const userMsg: TimelineEvent = {
      type: 'user_message',
      id: `msg-${Date.now()}`,
      content: `Launch Codex investigation for ticket ${ticket.id}: "${ticket.title}"`,
      timestamp
    }

    const thinking: TimelineEvent = {
      type: 'thinking',
      id: `th-${Date.now() + 1}`,
      thinking: {
        durationSeconds: 1.8,
        steps: [
          `Parsing captured error context from ${ticket.route || 'FastAPI core'}`,
          `Synthesizing diagnostic remediation hypothesis for ${ticket.category || 'System'}`,
          'Invoking specialized worker subagent to verify reproduction'
        ]
      }
    }

    const subagent: TimelineEvent = {
      type: 'subagent',
      id: `sa-${Date.now() + 2}`,
      subagent: {
        id: `worker-${ticket.id.toLowerCase()}`,
        role: `${ticket.category || 'Diagnostic'} Specialist`,
        task: `Isolate and remediate root cause for ${ticket.id}`,
        status: 'running',
        elapsedSec: 2,
        currentAction: `Analyzing stack trace in ${ticket.route || 'service worker'}`
      }
    }

    setEvents((prev) => [...prev, userMsg, thinking, subagent])

    // On mobile, switch to stream tab so the user sees the real-time execution
    if (window.innerWidth < 1024) {
      setMobileTab('stream')
    }
  }, [])

  // Interactivity: test run logging
  const handleRunTests = useCallback((command: string) => {
    const termEvent: TimelineEvent = {
      type: 'terminal',
      id: `term-${Date.now()}`,
      terminal: {
        id: `run-${Date.now()}`,
        command,
        output: 'All 14 tests completed with 0 errors.\n14 passed in 1.38s',
        exitCode: 0,
        passedCount: 14,
        failedCount: 0,
        status: 'completed'
      }
    }
    setEvents((prev) => [...prev, termEvent])
  }, [])

  // Interactivity: promote release logging
  const handlePromoteRelease = useCallback(() => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const agentResp: TimelineEvent = {
      type: 'agent_response',
      id: `resp-${Date.now()}`,
      content: 'Promotion to release branch initiated: staged cleanly with all zero-console gates verified.',
      timestamp
    }
    setEvents((prev) => [...prev, agentResp])
  }, [])

  // Interactivity: context rollback logging
  const handleRollback = useCallback((checkpointId: string) => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const rollbackEvent: TimelineEvent = {
      type: 'agent_response',
      id: `resp-${Date.now()}`,
      content: `Context rollback executed: working tree and memory restored to checkpoint [${checkpointId}].`,
      timestamp
    }
    setEvents((prev) => [...prev, rollbackEvent])
  }, [])

  // Interactivity: elevation grant logging
  const handleGrantAuthorization = useCallback((scopes: string[], durationMin: number) => {
    const gateEvent: TimelineEvent = {
      type: 'approval',
      id: `gate-${Date.now()}`,
      gate: {
        id: `elevate-${Date.now()}`,
        title: `Single-Run Elevation Granted (${durationMin} min)`,
        operation: `Authorized scopes: [${scopes.join(', ')}]`,
        riskLevel: 'high',
        status: 'approved'
      }
    }
    setEvents((prev) => [...prev, gateEvent])
  }, [])

  // Stream Composer message handler
  const handleSendMessage = useCallback((text: string) => {
    if (!text.trim()) return

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const userMsg: TimelineEvent = {
      type: 'user_message',
      id: `msg-${Date.now()}`,
      content: text,
      timestamp
    }

    setEvents((prev) => [...prev, userMsg])
    setIsStreaming(true)

    setTimeout(() => {
      const respTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      const agentMsg: TimelineEvent = {
        type: 'agent_response',
        id: `resp-${Date.now()}`,
        content: `I've received your instruction: "${text}". The Codex autonomous engine has cross-referenced the active workspace context and verified execution gates.`,
        timestamp: respTime
      }
      setEvents((prev) => [...prev, agentMsg])
      setIsStreaming(false)
    }, 1000)
  }, [])

  const handleAcceptDiff = useCallback((patchId: string) => {
    setEvents((prev) =>
      prev.map((e) =>
        e.type === 'diff' && e.patch.id === patchId
          ? { ...e, patch: { ...e.patch, status: 'accepted' } }
          : e
      )
    )
  }, [])

  const handleDiscardDiff = useCallback((patchId: string) => {
    setEvents((prev) =>
      prev.map((e) =>
        e.type === 'diff' && e.patch.id === patchId
          ? { ...e, patch: { ...e.patch, status: 'rejected' } }
          : e
      )
    )
  }, [])

  const handleApproveGate = useCallback((gateId: string) => {
    setEvents((prev) =>
      prev.map((e) =>
        e.type === 'approval' && e.gate.id === gateId
          ? { ...e, gate: { ...e.gate, status: 'approved' } }
          : e
      )
    )
  }, [])

  const handleRejectGate = useCallback((gateId: string) => {
    setEvents((prev) =>
      prev.map((e) =>
        e.type === 'approval' && e.gate.id === gateId
          ? { ...e, gate: { ...e.gate, status: 'rejected' } }
          : e
      )
    )
  }, [])

  // Render the active workspace surface in the center canvas
  const renderWorkspaceSurface = useMemo(() => {
    switch (activeView) {
      case 'tickets':
        return (
          <TicketsWorkspace
            onLaunchInvestigation={handleLaunchInvestigation}
          />
        )
      case 'coding':
        return (
          <CodingWorkspace
            activeBranch="feat/codex-v3-workspaces"
            onRunTests={handleRunTests}
            onPromoteRelease={handlePromoteRelease}
          />
        )
      case 'planning':
        return (
          <PlanningWorkspace
            onRollback={handleRollback}
            onGrantAuthorization={handleGrantAuthorization}
          />
        )
      case 'signals':
        return <SignalsWorkspace />
      default:
        return (
          <TicketsWorkspace
            onLaunchInvestigation={handleLaunchInvestigation}
          />
        )
    }
  }, [
    activeView,
    handleLaunchInvestigation,
    handleRunTests,
    handlePromoteRelease,
    handleRollback,
    handleGrantAuthorization
  ])

  // Transparent Stream Component
  const streamElement = (
    <TransparentStream
      events={events}
      isStreaming={isStreaming}
      voiceState={voice.voiceState}
      onSendMessage={handleSendMessage}
      onAcceptDiff={handleAcceptDiff}
      onDiscardDiff={handleDiscardDiff}
      onApproveGate={handleApproveGate}
      onRejectGate={handleRejectGate}
      onToggleVoice={() => void voice.toggleVoice()}
    />
  )

  return (
    <CodexV3Layout
      activeView={activeView}
      onViewChange={setActiveView}
      mobileTab={mobileTab}
      onMobileTabChange={setMobileTab}
      projectName="Codex Control Centre V3"
      activeBranch="feat/codex-v3-workspaces"
      ticketCount={ticketCount}
      subagentCount={subagentCount}
      signalCount={signalCount}
      streamContent={streamElement}
    >
      {renderWorkspaceSurface}
    </CodexV3Layout>
  )
}

export const CodexV3Page: React.FC = () => {
  return (
    <CodexVoiceProvider>
      <CodexV3PageInner />
    </CodexVoiceProvider>
  )
}

export default CodexV3Page
