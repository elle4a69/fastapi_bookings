export type SupervisorMeta = { request_id: string; schema_version: string; resource_version?: number }

export type SupervisorEnvelope<T> = { data: T; meta: SupervisorMeta }

export type SupervisorErrorPayload = {
  error?: { code?: string; message?: string; details?: Record<string, unknown> }
  meta?: { request_id?: string }
}

export type Project = {
  project_id: string
  display_name: string
  default_branch: string
  state: 'claim_required' | 'ready'
  version: number
  control_plane: 'legacy'
}

export type Bootstrap = {
  capabilities: { can_view_supervisor: true; can_claim_project: boolean }
  infrastructure: { state: 'ready' | 'migration_required'; current_revision: string | null; expected_revision: '004'; reason_codes: string[] }
  project_resolution: { state: string; reason_codes: string[] } | null
  cutover: { mode: 'v1_only'; version: number } | null
  cutover_absent_reason_code: string | null
  project: Project | null
}

export type Mission = { id: string; project_id: string; title: string; summary: string; state: string; version: number; created_at: string }
export type WorkPackage = { id: string; mission_id: string; project_id: string; title: string; scope: string; state: string; version: number; created_at: string }
export type Brief = { id: string; work_package_id: string; project_id: string; revision: number; content: string; state: string; version: number; future_execution_authorization_requirement: 'requires_authorization' | 'not_required_once_requested'; created_at: string; approved_at?: string | null }
export type Checkpoint = { id: string; mission_id: string; sequence: number; summary: string; decisions: string; constraints: string; open_questions: string; created_at: string }
export type AuditScope = { id: string; work_package_id: string; criteria: string; exclusions: string; created_at: string }

export type SupervisorSnapshot = {
  bootstrap: Bootstrap
  projects: Project[]
  etags: Record<string, string | null>
}

export type PlanningMutation =
  | { mission: Mission }
  | { work_package: WorkPackage }
  | { brief: Brief }
  | { checkpoint: Checkpoint }
  | { audit_scope: AuditScope }

export type RunStatus = 'dispatching' | 'dispatch_acknowledged' | 'running' | 'completed' | 'failed' | 'dispatch_unknown'

export type SupervisorRun = {
  run_id: string
  work_package_id: string
  brief_id: string
  audit_scope_id: string
  capability_profile: string
  status: RunStatus
  created_at: string
}

export type RunStartAuthorization = {
  grant_id: string
  expires_at: string
  token?: string
  state?: string
}

export type AcceptanceContract = {
  contract_id: string
  work_package_id: string
  registry_version: string
  criterion_codes: string[]
  state: string
  created_at: string
}

export type AuditRequestState = 'sandbox_unavailable' | 'pending' | 'evaluating' | 'passed' | 'failed'

export type AuditRequest = {
  audit_request_id: string
  run_id: string
  state: AuditRequestState
  requested_at: string
}

export type CriterionOutcome = 'passed' | 'failed' | 'not_evaluated'

export type CriterionResult = {
  criterion_code: string
  title: string
  description: string
  outcome: CriterionOutcome
  evidence_digest?: string | null
  recorded_at?: string
}

export type StructuralGitFacts = {
  baseline_tree_sha: string
  submitted_tree_sha?: string | null
  changed_files_count?: number | null
  insertions?: number | null
  deletions?: number | null
}

export type ActiveRunLifecycleStatus =
  | 'idle'
  | 'grant_requested'
  | 'authorized'
  | 'dispatching'
  | 'running'
  | 'completed'
  | 'failed'
  | 'dispatch_unknown'
  | 'sandbox_unavailable'

