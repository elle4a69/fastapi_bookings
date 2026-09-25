export type HealthState = 'healthy' | 'degraded' | 'disconnected' | 'attention_required'

export type ThreadStatus = 
  | 'active'
  | 'needs_approval'
  | 'failed'
  | 'interrupted'
  | 'pinned'
  | 'completed'
  | 'archived'

export type ReasoningEffort = 'low' | 'medium' | 'high'

export type PermissionProfile = 'read_only' | 'workspace_write' | 'managed' | 'elevated'

export type AuthMode = 'chatgpt_managed' | 'platform_api_key'

export type ContextCompactionState = 'healthy' | 'approaching' | 'compacting' | 'compacted' | 'failed'

export interface Project {
  id: string
  name: string
  repository: string
  defaultBranch: string
  activeThreadCount: number
  healthState: HealthState
  lastActivity: string
  writeRoots: string[]
  authMode: AuthMode
  modelPolicy: string
  description?: string
  repo_path?: string
}

export type TimelineItemType = 
  | 'user_instruction'
  | 'agent_message'
  | 'reasoning_summary'
  | 'plan'
  | 'command_execution'
  | 'file_read'
  | 'file_change'
  | 'tool_call'
  | 'web_research'
  | 'test_run'
  | 'approval_request'
  | 'user_input_request'
  | 'sub_agent_activity'
  | 'compaction_notice'
  | 'warning'
  | 'failure'
  | 'interruption'
  | 'completion_summary'

export interface BaseTimelineItem {
  id: string
  turnId: string
  type: TimelineItemType
  timestamp: string
  isStreaming?: boolean
}

export interface UserInstructionItem extends BaseTimelineItem {
  type: 'user_instruction'
  content: string
  authorName?: string
  attachments?: { name: string; size: string; type: string }[]
}

export interface AgentMessageItem extends BaseTimelineItem {
  type: 'agent_message'
  content: string
}

export interface ReasoningSummaryItem extends BaseTimelineItem {
  type: 'reasoning_summary'
  summary: string
  rawTrace?: string
  elapsedMs: number
}

export interface PlanTask {
  id: string
  title: string
  status: 'pending' | 'active' | 'completed' | 'blocked'
}

export interface PlanItem extends BaseTimelineItem {
  type: 'plan'
  title: string
  tasks: PlanTask[]
}

export interface CommandExecutionItem extends BaseTimelineItem {
  type: 'command_execution'
  command: string
  summary: string
  workingDirectory: string
  status: 'running' | 'completed' | 'failed'
  durationMs: number
  exitCode?: number
  stdout: string
  stderr?: string
  lineCount: number
  processId?: string
}

export interface FileReadItem extends BaseTimelineItem {
  type: 'file_read'
  path: string
  lineRange?: string
  summary: string
  matchCount?: number
}

export interface FileChangeEntry {
  path: string
  status: 'proposed' | 'applied' | 'declined' | 'failed'
  additions: number
  deletions: number
  requiresApproval?: boolean
}

export interface FileChangeItem extends BaseTimelineItem {
  type: 'file_change'
  summary: string
  files: FileChangeEntry[]
  totalAdditions: number
  totalDeletions: number
}

export interface ToolCallItem extends BaseTimelineItem {
  type: 'tool_call'
  serverName: string
  toolName: string
  args: Record<string, any>
  resultSummary: string
  status: 'success' | 'failed' | 'running'
  durationMs?: number
}

export interface WebResearchCitation {
  title: string
  url: string
  snippet: string
}

export interface WebResearchItem extends BaseTimelineItem {
  type: 'web_research'
  query: string
  citations: WebResearchCitation[]
  summary: string
}

export interface TestSuiteResult {
  name: string
  passed: number
  failed: number
  skipped: number
  durationMs: number
  failures?: { testName: string; message: string; trace?: string }[]
}

export interface TestRunItem extends BaseTimelineItem {
  type: 'test_run'
  framework: string
  status: 'running' | 'passed' | 'failed'
  totalDurationMs: number
  suites: TestSuiteResult[]
}

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface ApprovalRequestItem extends BaseTimelineItem {
  type: 'approval_request'
  approvalId: string
  category: 'command' | 'file_write' | 'network' | 'permission'
  title: string
  consequence: string
  command?: string
  targetPath?: string
  workingDirectory?: string
  reason: string
  risk: RiskLevel
  status: 'pending' | 'approved' | 'declined'
  scope: 'once' | 'session'
}

export interface FormFieldSchema {
  id: string
  label: string
  type: 'text' | 'select' | 'checkbox' | 'radio'
  options?: string[]
  defaultValue?: any
  description?: string
  required?: boolean
}

export interface UserInputRequestItem extends BaseTimelineItem {
  type: 'user_input_request'
  requestId: string
  question: string
  schema: FormFieldSchema[]
  status: 'pending' | 'submitted' | 'declined'
  response?: Record<string, any>
}

export interface SubAgentActivityItem extends BaseTimelineItem {
  type: 'sub_agent_activity'
  agentId: string
  role: string
  objective: string
  status: 'running' | 'completed' | 'failed' | 'waiting' | 'stopped'
  progressSummary: string
  resultSummary?: string
  filesChangedCount?: number
  testsRunCount?: number
}

export interface CompactionNoticeItem extends BaseTimelineItem {
  type: 'compaction_notice'
  explanation: string
  tokensSaved: number
  originalTurnCount: number
}

export interface WarningItem extends BaseTimelineItem {
  type: 'warning'
  title: string
  message: string
  actionLabel?: string
}

export interface FailureItem extends BaseTimelineItem {
  type: 'failure'
  errorCategory: 'context_window' | 'usage_limit' | 'authentication' | 'connection' | 'sandbox' | 'internal'
  summary: string
  details?: string
  canRetry: boolean
  suggestedAction?: 'retry' | 'reconnect' | 'resume' | 'change_settings' | 'inspect_logs'
}

export interface InterruptionItem extends BaseTimelineItem {
  type: 'interruption'
  reason: string
  interruptedBy: string
}

export interface CompletionSummaryItem extends BaseTimelineItem {
  type: 'completion_summary'
  outcome: string
  changedFilesCount: number
  testsPassedCount: number
  durationSeconds: number
  summary: string
}

export type TimelineItem = 
  | UserInstructionItem
  | AgentMessageItem
  | ReasoningSummaryItem
  | PlanItem
  | CommandExecutionItem
  | FileReadItem
  | FileChangeItem
  | ToolCallItem
  | WebResearchItem
  | TestRunItem
  | ApprovalRequestItem
  | UserInputRequestItem
  | SubAgentActivityItem
  | CompactionNoticeItem
  | WarningItem
  | FailureItem
  | InterruptionItem
  | CompletionSummaryItem

export interface Turn {
  id: string
  threadId: string
  turnNumber: number
  status: 'in_progress' | 'completed' | 'failed' | 'interrupted'
  items: TimelineItem[]
  startedAt: string
  completedAt?: string
}

export interface SubAgent {
  id: string
  parentThreadId: string
  role: string
  objective: string
  status: 'running' | 'completed' | 'failed' | 'waiting' | 'stopped'
  model: string
  reasoningEffort: ReasoningEffort
  scope: 'read_only' | 'workspace_write'
  branch?: string
  startedAt: string
  elapsedSeconds: number
  progressSummary: string
  resultSummary?: string
  filesChangedCount?: number
  testsRunCount?: number
  childThreadId?: string
}

export interface Thread {
  id: string
  projectId: string
  title: string
  module: string
  status: ThreadStatus
  branch: string
  worktree: string
  model: string
  reasoningEffort: ReasoningEffort
  permissionProfile: PermissionProfile
  contextCompactionState: ContextCompactionState
  subAgentCount: number
  approvalCount: number
  createdAt: string
  updatedAt: string
  isPinned?: boolean
  isArchived?: boolean
  turns: Turn[]
  goals?: string
  tokenBudget?: {
    limit: number
    used: number
  }
}

export interface DiffLine {
  type: 'context' | 'add' | 'del'
  content: string
  oldLineNumber?: number
  newLineNumber?: number
}

export interface DiffHunk {
  oldStart: number
  oldLines: number
  newStart: number
  newLines: number
  header: string
  lines: DiffLine[]
}

export interface DiffFile {
  path: string
  oldPath?: string
  status: 'added' | 'modified' | 'deleted'
  additions: number
  deletions: number
  hunks: DiffHunk[]
  oldContent?: string
  newContent?: string
}

export interface TelemetryIncident {
  id: string
  traceId: string
  serviceName: string
  environment: string
  timestamp: string
  severity: 'info' | 'warning' | 'error'
  message: string
  durationMs?: number
  httpStatus?: number
  attributes?: Record<string, string>
}

// -------------------------------------------------------------
// SSE & REST API DTOs
// -------------------------------------------------------------

export interface SSEEventEnvelope<T = any> {
  id: string
  schema_version?: string
  project_id: string
  thread_id: string
  sequence: number
  type: string
  occurred_at: string
  payload: T
}

export interface ThreadResponse {
  id: string
  project_id: string
  title: string
  status: string
  is_pinned: boolean
  is_archived: boolean
}

export interface CreateThreadPayload {
  project_id: string
  title: string
}

export interface UpdateThreadPayload {
  title?: string
  is_pinned?: boolean
  is_archived?: boolean
  status?: string
}

export interface TurnStartPayload {
  thread_id: string
  prompt: string
}

export interface TurnSteerPayload {
  thread_id: string
  turn_id: number
  instruction: string
}

export interface TurnInterruptPayload {
  thread_id: string
  turn_id: number
}

export interface ToolApprovalResponse {
  id: string
  thread_id: string
  tool_call_id: string
  command: string
  risk_level: string
  consequence: string
  status: string
  created_at?: string | null
  resolved_at?: string | null
}

export interface ResolveApprovalPayload {
  approved: boolean
  feedback?: string
}

export interface CreateWorktreePayload {
  repo_path: string
  branch: string
  worktree_name: string
}

export interface WorktreeResponse {
  worktree_name?: string
  branch?: string
  path?: string
  [key: string]: any
}

export interface SubAgentResponse {
  id: string
  thread_id: string
  parent_thread_id?: string | null
  name: string
  role: string
  status: string
  progress: number
  current_action?: string | null
  created_at?: string | null
}

export interface DeepDiagnosticsResponse {
  status: string
  [key: string]: any
}

