// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync, existsSync } from 'node:fs'
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'
import type { TimelineEvent } from './types.ts'

const streamDir = fileURLToPath(new URL('./components/stream/', import.meta.url))

test('Package 3: All stream component files exist on disk', () => {
  const expectedFiles = [
    'ThinkingAccordion.tsx',
    'ToolExecutionCard.tsx',
    'SubagentCard.tsx',
    'InlineDiffCard.tsx',
    'ApprovalGateCard.tsx',
    'TerminalSnippet.tsx',
    'ComposerBar.tsx',
    'TransparentStream.tsx',
    'index.ts',
  ]

  for (const file of expectedFiles) {
    const fullPath = `${streamDir}${file}`
    assert.ok(existsSync(fullPath), `File ${file} must exist in components/stream/`)
  }
})

test('Package 3: ThinkingAccordion has collapsible reasoning and gradient animation', () => {
  const content = readFileSync(`${streamDir}ThinkingAccordion.tsx`, 'utf8')
  assert.ok(content.includes('ThinkingAccordion'), 'Must export ThinkingAccordion')
  assert.ok(content.includes('durationSeconds'), 'Must support durationSeconds')
  assert.ok(content.includes('steps'), 'Must support reasoning steps')
  assert.ok(content.includes('isThinking'), 'Must support isThinking state')
  assert.ok(content.includes('bg-clip-text text-transparent'), 'Must use shimmering gradient text animation')
})

test('Package 3: ToolExecutionCard has monospaced tool invocation card and status badges', () => {
  const content = readFileSync(`${streamDir}ToolExecutionCard.tsx`, 'utf8')
  assert.ok(content.includes('ToolExecutionCard'), 'Must export ToolExecutionCard')
  assert.ok(content.includes('running'), 'Must support running badge')
  assert.ok(content.includes('completed'), 'Must support completed badge')
  assert.ok(content.includes('failed'), 'Must support failed badge')
  assert.ok(content.includes('toolName'), 'Must display toolName')
  assert.ok(content.includes('targetFile'), 'Must display targetFile')
  assert.ok(content.includes('font-mono'), 'Must use monospaced styling')
})

test('Package 3: SubagentCard shows role, status, elapsed timer, and child thread view', () => {
  const content = readFileSync(`${streamDir}SubagentCard.tsx`, 'utf8')
  assert.ok(content.includes('SubagentCard'), 'Must export SubagentCard')
  assert.ok(content.includes('role'), 'Must display child subagent role')
  assert.ok(content.includes('status'), 'Must display status')
  assert.ok(content.includes('currentAction'), 'Must display current action')
  assert.ok(content.includes('onViewThread'), 'Must provide onViewThread action')
  assert.ok(content.includes('View Thread'), 'Must have touch-friendly View Thread button')
})

test('Package 3: InlineDiffCard syntax-highlights diff with line numbers and Accept/Discard actions', () => {
  const content = readFileSync(`${streamDir}InlineDiffCard.tsx`, 'utf8')
  assert.ok(content.includes('InlineDiffCard'), 'Must export InlineDiffCard')
  assert.ok(content.includes('additions'), 'Must display additions count')
  assert.ok(content.includes('deletions'), 'Must display deletions count')
  assert.ok(content.includes('onAccept'), 'Must support onAccept handler')
  assert.ok(content.includes('onDiscard'), 'Must support onDiscard handler')
  assert.ok(content.includes('newLineNumber'), 'Must compute line numbers')
  assert.ok(content.includes('Accept'), 'Must render Accept button')
  assert.ok(content.includes('Discard'), 'Must render Discard button')
})

test('Package 3: ApprovalGateCard pauses for high-risk operations with touch-friendly buttons', () => {
  const content = readFileSync(`${streamDir}ApprovalGateCard.tsx`, 'utf8')
  assert.ok(content.includes('ApprovalGateCard'), 'Must export ApprovalGateCard')
  assert.ok(content.includes('riskLevel'), 'Must support riskLevel indicator')
  assert.ok(content.includes('[ Approve & Apply ]'), 'Must have [ Approve & Apply ] button')
  assert.ok(content.includes('[ Steer / Reject ]'), 'Must have [ Steer / Reject ] button')
  assert.ok(content.includes('onApprove'), 'Must support onApprove callback')
  assert.ok(content.includes('onReject'), 'Must support onReject callback')
})

test('Package 3: TerminalSnippet renders dark zinc console block with test result summaries', () => {
  const content = readFileSync(`${streamDir}TerminalSnippet.tsx`, 'utf8')
  assert.ok(content.includes('TerminalSnippet'), 'Must export TerminalSnippet')
  assert.ok(content.includes('bg-zinc-950 text-zinc-100 font-mono'), 'Must use dark zinc console block')
  assert.ok(content.includes('passedCount'), 'Must display passed test badge')
  assert.ok(content.includes('failedCount'), 'Must display failed test badge')
  assert.ok(content.includes('exitCode'), 'Must display process exit code')
})

test('Package 3: ComposerBar features expanding textarea, voice state indicator, and send button', () => {
  const content = readFileSync(`${streamDir}ComposerBar.tsx`, 'utf8')
  assert.ok(content.includes('ComposerBar'), 'Must export ComposerBar')
  assert.ok(content.includes('voiceState'), 'Must support voice state')
  assert.ok(content.includes('onSendMessage'), 'Must support onSendMessage')
  assert.ok(content.includes('onAttach'), 'Must support context/attachment button')
  assert.ok(content.includes('textareaRef'), 'Must dynamically manage textarea expansion')
})

test('Package 3: TransparentStream coordinates the complete transparent timeline and auto-scroll', () => {
  const content = readFileSync(`${streamDir}TransparentStream.tsx`, 'utf8')
  assert.ok(content.includes('TransparentStream'), 'Must export TransparentStream')
  assert.ok(content.includes('ThinkingAccordion'), 'Must assemble ThinkingAccordion')
  assert.ok(content.includes('SubagentCard'), 'Must assemble SubagentCard')
  assert.ok(content.includes('ToolExecutionCard'), 'Must assemble ToolExecutionCard')
  assert.ok(content.includes('InlineDiffCard'), 'Must assemble InlineDiffCard')
  assert.ok(content.includes('TerminalSnippet'), 'Must assemble TerminalSnippet')
  assert.ok(content.includes('ApprovalGateCard'), 'Must assemble ApprovalGateCard')
  assert.ok(content.includes('ComposerBar'), 'Must assemble ComposerBar')
  assert.ok(content.includes('autoScroll'), 'Must support auto-scroll with manual toggle/lock')
  assert.ok(content.includes('user_message'), 'Must render user message')
  assert.ok(content.includes('agent_response'), 'Must render final agent response')
})

test('Package 3: TimelineEvent discriminated union supports complete transparent timeline sequence', () => {
  const events: TimelineEvent[] = [
    {
      type: 'user_message',
      id: 'm-1',
      content: 'Fix race condition in appointment booking',
      timestamp: '10:00 AM',
    },
    {
      type: 'thinking',
      id: 'm-2',
      thinking: {
        durationSeconds: 2.1,
        steps: ['Read concurrency locks', 'Verify optimistic locking version'],
      },
    },
    {
      type: 'subagent',
      id: 'm-3',
      subagent: {
        id: 'sa-1',
        role: 'Database Specialist',
        status: 'done',
        elapsedSec: 5,
        elapsedSeconds: 5,
        task: 'Verify isolation level',
        currentAction: 'Verified isolation level',
      },
    },
    {
      type: 'tool',
      id: 'm-4',
      tool: {
        id: 't-1',
        toolName: 'replace_file_content',
        status: 'completed',
        targetFile: 'app/models/booking.py',
        durationMs: 310,
      },
    },
    {
      type: 'diff',
      id: 'm-5',
      patch: {
        id: 'p-1',
        filePath: 'app/models/booking.py',
        additions: 5,
        deletions: 1,
        diffHunks: ['@@ -20,1 +20,5 @@\n-version = Column(Integer)\n+version = Column(Integer, nullable=False, default=1)'],
        diff: '@@ -20,1 +20,5 @@\n-version = Column(Integer)\n+version = Column(Integer, nullable=False, default=1)',
        status: 'pending',
      },
    },
    {
      type: 'terminal',
      id: 'm-6',
      terminal: {
        id: 'term-1',
        command: 'pytest tests/test_concurrency.py',
        output: '5 passed in 1.1s',
        exitCode: 0,
        passedCount: 5,
      },
    },
    {
      type: 'approval',
      id: 'm-7',
      gate: {
        id: 'g-1',
        title: 'Commit and Push Changes',
        operation: 'Push fix to origin branch',
        riskLevel: 'medium',
        status: 'pending',
      },
    },
    {
      type: 'agent_response',
      id: 'm-8',
      content: 'I have secured the booking transaction with optimistic locking and verified test passes.',
      timestamp: '10:01 AM',
    },
  ]

  assert.equal(events.length, 8)
  assert.equal(events[0].type, 'user_message')
  assert.equal(events[1].type, 'thinking')
  assert.equal(events[2].type, 'subagent')
  assert.equal(events[3].type, 'tool')
  assert.equal(events[4].type, 'diff')
  assert.equal(events[5].type, 'terminal')
  assert.equal(events[6].type, 'approval')
  assert.equal(events[7].type, 'agent_response')
})
