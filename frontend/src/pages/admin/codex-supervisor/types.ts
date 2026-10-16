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
