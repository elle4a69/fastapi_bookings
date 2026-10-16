export type CodexView = 'tickets' | 'coding' | 'planning' | 'signals'

export type MobileTab = 'workspace' | 'stream'

export type VoiceState = 'idle' | 'connecting' | 'listening' | 'speaking' | 'thinking' | 'error'

export type ToolStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface SubagentActivity {
  id: string
  role: string
  task: string
  status: 'running' | 'done' | 'failed'
  elapsedSec: number
  currentAction?: string
  elapsedSeconds?: number
  startedAt?: string
  completedAt?: string
  childThreadId?: string
  description?: string
  toolsCount?: number
}

export interface FilePatch {
  id?: string
  filePath: string
  additions: number
  deletions: number
  diffHunks: string[]
  status: 'pending' | 'accepted' | 'rejected'
  diff?: string
  oldContent?: string
  newContent?: string
  applied?: boolean
}

export interface ThinkingBlock {
  id?: string
  durationSeconds: number
  steps: string[]
  isThinking?: boolean
  startedAt?: string
  completedAt?: string
}

export interface ToolExecution {
  id: string
  toolName: string
  status: ToolStatus
  targetFile?: string
  durationMs?: number
  args?: Record<string, unknown> | string
  stdout?: string
  stderr?: string
  timestamp?: string
}

export interface ApprovalGate {
  id: string
  title: string
  operation: string
  description?: string
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  status: 'pending' | 'approved' | 'rejected'
  command?: string
  filePath?: string
  payload?: Record<string, unknown>
  timestamp?: string
}

export interface TerminalOutput {
  id: string
  command: string
  output: string
  exitCode?: number
  passedCount?: number
  failedCount?: number
  skippedCount?: number
  durationMs?: number
  status?: 'running' | 'completed' | 'failed'
  timestamp?: string
}

export type TimelineEvent =
  | {
      type: 'user_message'
      id: string
      content: string
      timestamp: string
      avatar?: string
    }
  | {
      type: 'thinking'
      id: string
      thinking: ThinkingBlock
    }
  | {
      type: 'subagent'
      id: string
      subagent: SubagentActivity
    }
  | {
      type: 'tool'
      id: string
      tool: ToolExecution
    }
  | {
      type: 'diff'
      id: string
      patch: FilePatch
    }
  | {
      type: 'terminal'
      id: string
      terminal: TerminalOutput
    }
  | {
      type: 'approval'
      id: string
      gate: ApprovalGate
    }
  | {
      type: 'agent_response'
      id: string
      content: string
      timestamp: string
      isStreaming?: boolean
    }

export interface CodexVoiceContextValue {
  voiceState: VoiceState
  toggleVoice: () => Promise<void>
  startVoice: () => Promise<void>
  stopVoice: () => void
  transcriptDelta: string
  audioLevel: number
  latencyMs: number
  error: string | null
  conversationId: number | null
}
