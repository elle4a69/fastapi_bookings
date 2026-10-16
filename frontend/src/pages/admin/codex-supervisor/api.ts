import { getAdminAccessToken } from '../../../lib/api.ts'
import type { AcceptanceContract, AuditRequest, AuditScope, Bootstrap, Brief, Checkpoint, Mission, Project, RunStartAuthorization, SupervisorEnvelope, SupervisorErrorPayload, SupervisorRun, SupervisorSnapshot, WorkPackage } from './types'


const PREFIX = '/api/admin/codex/v2'
const LOCAL_BYPASS_TOKEN = 'local-development-bypass'

export class SupervisorApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null
  constructor(status: number, code: string, message: string, requestId: string | null) {
    super(message)
    this.name = 'SupervisorApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

export type SupervisorUiError = { title: string; detail: string; canRetry: boolean }

export function mapSupervisorError(error: unknown): SupervisorUiError {
  if (error instanceof SupervisorApiError) {
    if (error.status === 401) return { title: 'Sign-in required', detail: 'Your signed-in administrator session is required to view the Development Supervisor.', canRetry: false }
    if (error.status === 202 || error.code === 'operation_in_progress') return { title: 'Planning action is still in progress', detail: 'The server is still resolving this exact action. Retry without editing to safely recover its result.', canRetry: true }
    if (error.status === 403) return { title: 'Platform-owner access required', detail: 'This planning surface is available only to an active platform owner.', canRetry: false }
    if (error.code === 'database_migration_required') return { title: 'Supervisor migration required', detail: 'The control-plane database is not ready. No planning data has been shown.', canRetry: true }
    if (error.code === 'supervisor_unconfigured') return { title: 'Project configuration required', detail: 'No configured project is available to this supervisor.', canRetry: false }
    if (error.status === 404) return { title: 'Planning resource unavailable', detail: 'The selected planning resource is not available in this scope.', canRetry: false }
    if (error.code === 'start_authorization_already_issued') return { title: 'Start authorization active', detail: 'A valid start authorization has already been issued for this work package.', canRetry: false }
    if (error.code === 'start_authorization_unavailable') return { title: 'Authorization unavailable', detail: 'The start authorization has expired or already been consumed.', canRetry: false }
    if (error.code === 'active_run_exists') return { title: 'Active run in progress', detail: 'An active run already exists for this work package.', canRetry: false }
    if (error.code === 'approved_acceptance_contract_required') return { title: 'Acceptance contract required', detail: 'An approved acceptance contract is required before initiating a run.', canRetry: true }
    if (error.code === 'dispatch_prerequisite_unavailable') return { title: 'Dispatch prerequisite unavailable', detail: 'The repository runtime or worker manager is not available for dispatch.', canRetry: false }
    if (error.code === 'run_baseline_required') return { title: 'Baseline capture required', detail: 'A Git baseline could not be captured before dispatch.', canRetry: false }
    if (error.code === 'sandbox_unavailable') return { title: 'Sandbox unavailable', detail: 'A host-enforced independent sandbox is not available to evaluate audit criteria.', canRetry: false }
    if (error.status === 409) return { title: 'Supervisor state changed', detail: 'The planning state is not currently available for this view. Refresh before continuing.', canRetry: true }
    if (error.status === 412 || error.code === 'revision_conflict') return { title: 'Planning state changed', detail: 'This planning record changed before the action could be applied. Refresh and review the current state.', canRetry: true }
    if (error.status === 422 || error.code === 'validation_failed') return { title: 'Planning details need review', detail: 'Use the required bounded planning fields and try again.', canRetry: false }
    if (error.status === 428) return { title: 'Planning state needs refresh', detail: 'The required current revision is unavailable. Refresh before continuing.', canRetry: true }
    return { title: 'Supervisor data is unavailable', detail: 'The supervisor API could not provide safe planning data for this view.', canRetry: error.status >= 500 }
  }
  return { title: 'Supervisor connection failed', detail: 'The Development Supervisor could not reach its API. No local or demo data is used.', canRetry: true }
}

export function getSupervisorTenantFromHost(hostname = typeof window === 'undefined' ? '' : window.location.hostname): string | null {
  const normalized = hostname.toLowerCase().replace(/\.$/, '')
  const parts = normalized.split('.')
  const tenant = parts[0]
  if (
    parts.length < 3 ||
    !tenant ||
    ['www', 'api', 'localhost', 'simplydemo'].includes(tenant) ||
    normalized.endsWith('.localhost') ||
    normalized.endsWith('.run.app') ||
    normalized.endsWith('.trycloudflare.com') ||
    /^(?:\d{1,3}\.){3}\d{1,3}$/.test(normalized) ||
    !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(tenant)
  ) return null
  return tenant
}

export function supervisorCredentials(): Headers | null {
  const token = getAdminAccessToken()
  const tenant = getSupervisorTenantFromHost()
  // The general admin API intentionally has development fallbacks. V2 does not.
  if (!token || token === LOCAL_BYPASS_TOKEN || !tenant) return null
  return new Headers({ Accept: 'application/json', 'X-Token': token, 'X-Tenant': tenant })
}

async function get<T>(path: string, signal?: AbortSignal): Promise<{ envelope: SupervisorEnvelope<T>; etag: string | null }> {
  const headers = supervisorCredentials()
  if (!headers) throw new SupervisorApiError(401, 'supervisor_session_unavailable', 'A signed-in tenant administrator session is not available.', null)
  const response = await fetch(`${PREFIX}${path}`, { method: 'GET', headers, signal })
  const text = await response.text()
  let payload: SupervisorEnvelope<T> | SupervisorErrorPayload | null = null
  try { payload = text ? JSON.parse(text) as SupervisorEnvelope<T> : null } catch { /* handled below */ }
  if (!response.ok) {
    const error = payload as SupervisorErrorPayload | null
    throw new SupervisorApiError(response.status, error?.error?.code ?? `HTTP_${response.status}`, error?.error?.message ?? response.statusText ?? 'Supervisor request failed.', error?.meta?.request_id ?? response.headers.get('X-Request-ID'))
  }
  if (!payload || !('data' in payload) || !('meta' in payload)) throw new SupervisorApiError(502, 'invalid_supervisor_response', 'The supervisor API returned an invalid response envelope.', response.headers.get('X-Request-ID'))
  return { envelope: payload as SupervisorEnvelope<T>, etag: response.headers.get('ETag') }
}

type PlanningAction = 'create_mission' | 'create_work_package' | 'create_brief' | 'approve_brief' | 'record_context_checkpoint' | 'define_audit_scope'
const pendingMutationKeys = new Map<string, string>()

export function planningEtag(prefix: 'project' | 'mission' | 'work_package' | 'brief', version: number): string {
  return `"${prefix}-${version}"`
}

function newIdempotencyKey(): string {
  const key = globalThis.crypto?.randomUUID?.()
  if (!key) throw new SupervisorApiError(503, 'idempotency_unavailable', 'The browser cannot create the required request identifier.', null)
  return key
}

function mutationFingerprint(path: string, action: PlanningAction, ifMatch: string, fields: Record<string, string>): string {
  return JSON.stringify({ action, path, ifMatch, fields: Object.fromEntries(Object.entries(fields).sort(([left], [right]) => left.localeCompare(right))) })
}

export async function mutatePlanning<T>(path: string, action: PlanningAction, ifMatch: string, fields: Record<string, string>): Promise<T> {
  const credentials = supervisorCredentials()
  if (!credentials) throw new SupervisorApiError(401, 'supervisor_session_unavailable', 'A signed-in tenant administrator session is not available.', null)
  const fingerprint = mutationFingerprint(path, action, ifMatch, fields)
  const idempotencyKey = pendingMutationKeys.get(fingerprint) ?? newIdempotencyKey()
  pendingMutationKeys.set(fingerprint, idempotencyKey)
  const headers = new Headers(credentials)
  headers.set('Content-Type', 'application/json')
  headers.set('Idempotency-Key', idempotencyKey)
  headers.set('If-Match', ifMatch)
  let response: Response
  try {
    response = await fetch(`${PREFIX}${path}`, { method: 'POST', headers, body: JSON.stringify({ action, registry_version: '0.2', confirmation: true, ...fields }) })
  } catch (cause) {
    // A response may have been committed but lost in transit. Preserve this key
    // only for an identical retry so the server can safely replay it.
    throw cause
  }
  const text = await response.text()
  let payload: SupervisorEnvelope<T> | SupervisorErrorPayload | null = null
  try { payload = text ? JSON.parse(text) as SupervisorEnvelope<T> : null } catch { /* safely mapped below */ }
  if (response.status === 202) {
    // Reservation is still live. Preserve the exact fingerprint/key for a
    // retry; callers must not treat the operation envelope as an entity.
    throw new SupervisorApiError(202, 'operation_in_progress', 'The supervisor action is still in progress.', response.headers.get('X-Request-ID'))
  }
  // A non-202 HTTP response is definitive for this browser attempt. A later
  // edit or new action gets a fresh key; a server replay has already returned.
  pendingMutationKeys.delete(fingerprint)
  if (!response.ok) {
    const error = payload as SupervisorErrorPayload | null
    throw new SupervisorApiError(response.status, error?.error?.code ?? `HTTP_${response.status}`, error?.error?.message ?? response.statusText ?? 'Supervisor request failed.', error?.meta?.request_id ?? response.headers.get('X-Request-ID'))
  }
  if (!payload || !('data' in payload)) throw new SupervisorApiError(502, 'invalid_supervisor_response', 'The supervisor API returned an invalid response envelope.', response.headers.get('X-Request-ID'))
  return (payload as SupervisorEnvelope<T>).data
}

export async function loadSupervisorSnapshot(signal?: AbortSignal): Promise<SupervisorSnapshot> {
  const [bootstrap, projects] = await Promise.all([get<Bootstrap>('/bootstrap', signal), get<{ projects: Project[] }>('/projects', signal)])
  return { bootstrap: bootstrap.envelope.data, projects: projects.envelope.data.projects, etags: { bootstrap: bootstrap.etag, projects: projects.etag } }
}
export async function loadMissions(projectId: string, signal?: AbortSignal) { return (await get<{ missions: Mission[] }>(`/projects/${encodeURIComponent(projectId)}/missions`, signal)).envelope.data.missions }
export async function loadMission(id: string, signal?: AbortSignal) { return (await get<{ mission: Mission }>(`/missions/${encodeURIComponent(id)}`, signal)).envelope.data.mission }
export async function loadWorkPackages(id: string, signal?: AbortSignal) { return (await get<{ work_packages: WorkPackage[] }>(`/missions/${encodeURIComponent(id)}/work-packages`, signal)).envelope.data.work_packages }
export async function loadWorkPackage(id: string, signal?: AbortSignal) { return (await get<{ work_package: WorkPackage }>(`/work-packages/${encodeURIComponent(id)}`, signal)).envelope.data.work_package }
export async function loadBriefs(id: string, signal?: AbortSignal) { return (await get<{ briefs: Brief[] }>(`/work-packages/${encodeURIComponent(id)}/briefs`, signal)).envelope.data.briefs }
export async function loadCheckpoints(id: string, signal?: AbortSignal) { return (await get<{ context_checkpoints: Checkpoint[] }>(`/missions/${encodeURIComponent(id)}/context-checkpoints`, signal)).envelope.data.context_checkpoints }
export async function loadAuditScope(id: string, signal?: AbortSignal) { return (await get<{ audit_scope: AuditScope | null }>(`/work-packages/${encodeURIComponent(id)}/audit-scope`, signal)).envelope.data.audit_scope }

export async function createAcceptanceContract(workPackageId: string, workPackageVersion: number): Promise<AcceptanceContract> {
  const credentials = supervisorCredentials()
  if (!credentials) throw new SupervisorApiError(401, 'supervisor_session_unavailable', 'A signed-in tenant administrator session is not available.', null)
  const headers = new Headers(credentials)
  headers.set('Content-Type', 'application/json')
  headers.set('Idempotency-Key', newIdempotencyKey())
  headers.set('If-Match', `"work_package-${workPackageVersion}"`)
  const response = await fetch(`${PREFIX}/work-packages/${encodeURIComponent(workPackageId)}/acceptance-contracts`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ action: 'create_acceptance_contract', registry_version: '1', confirmation: true }),
  })
  const text = await response.text()
  let payload: SupervisorEnvelope<{ acceptance_contract: AcceptanceContract }> | SupervisorErrorPayload | null = null
  try { payload = text ? (JSON.parse(text) as SupervisorEnvelope<{ acceptance_contract: AcceptanceContract }>) : null } catch { /* handled below */ }
  if (!response.ok) {
    const error = payload as SupervisorErrorPayload | null
    throw new SupervisorApiError(response.status, error?.error?.code ?? `HTTP_${response.status}`, error?.error?.message ?? response.statusText ?? 'Request failed.', error?.meta?.request_id ?? response.headers.get('X-Request-ID'))
  }
  if (!payload || !('data' in payload)) throw new SupervisorApiError(502, 'invalid_supervisor_response', 'The supervisor API returned an invalid response envelope.', response.headers.get('X-Request-ID'))
  return (payload as SupervisorEnvelope<{ acceptance_contract: AcceptanceContract }>).data.acceptance_contract
}

export async function issueRunStartAuthorization(workPackageId: string, waiverRequested = false): Promise<RunStartAuthorization> {
  const credentials = supervisorCredentials()
  if (!credentials) throw new SupervisorApiError(401, 'supervisor_session_unavailable', 'A signed-in tenant administrator session is not available.', null)
  const headers = new Headers(credentials)
  headers.set('Content-Type', 'application/json')
  headers.set('Idempotency-Key', newIdempotencyKey())
  const response = await fetch(`${PREFIX}/work-packages/${encodeURIComponent(workPackageId)}/run-start-authorizations`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ action: 'issue_run_start_authorization', registry_version: '0.3', confirmation: true, waiver_requested: Boolean(waiverRequested) }),
  })
  const text = await response.text()
  let payload: SupervisorEnvelope<{ authorization: RunStartAuthorization }> | SupervisorErrorPayload | null = null
  try { payload = text ? (JSON.parse(text) as SupervisorEnvelope<{ authorization: RunStartAuthorization }>) : null } catch { /* handled below */ }
  if (!response.ok) {
    const error = payload as SupervisorErrorPayload | null
    throw new SupervisorApiError(response.status, error?.error?.code ?? `HTTP_${response.status}`, error?.error?.message ?? response.statusText ?? 'Request failed.', error?.meta?.request_id ?? response.headers.get('X-Request-ID'))
  }
  if (!payload || !('data' in payload)) throw new SupervisorApiError(502, 'invalid_supervisor_response', 'The supervisor API returned an invalid response envelope.', response.headers.get('X-Request-ID'))
  return (payload as SupervisorEnvelope<{ authorization: RunStartAuthorization }>).data.authorization
}

export async function startSupervisorRun(workPackageId: string, workPackageVersion: number, grantToken: string): Promise<{ run: SupervisorRun; etag: string | null }> {
  const credentials = supervisorCredentials()
  if (!credentials) throw new SupervisorApiError(401, 'supervisor_session_unavailable', 'A signed-in tenant administrator session is not available.', null)
  const headers = new Headers(credentials)
  headers.set('Content-Type', 'application/json')
  headers.set('Idempotency-Key', newIdempotencyKey())
  headers.set('If-Match', `"work_package-${workPackageVersion}"`)
  const response = await fetch(`${PREFIX}/work-packages/${encodeURIComponent(workPackageId)}/runs`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ action: 'start_supervisor_run', registry_version: '0.3', confirmation: true, grant_token: grantToken }),
  })
  const text = await response.text()
  let payload: SupervisorEnvelope<{ run: SupervisorRun }> | SupervisorErrorPayload | null = null
  try { payload = text ? (JSON.parse(text) as SupervisorEnvelope<{ run: SupervisorRun }>) : null } catch { /* handled below */ }
  if (!response.ok) {
    const error = payload as SupervisorErrorPayload | null
    throw new SupervisorApiError(response.status, error?.error?.code ?? `HTTP_${response.status}`, error?.error?.message ?? response.statusText ?? 'Request failed.', error?.meta?.request_id ?? response.headers.get('X-Request-ID'))
  }
  if (!payload || !('data' in payload)) throw new SupervisorApiError(502, 'invalid_supervisor_response', 'The supervisor API returned an invalid response envelope.', response.headers.get('X-Request-ID'))
  return { run: (payload as SupervisorEnvelope<{ run: SupervisorRun }>).data.run, etag: response.headers.get('ETag') }
}

export async function loadSupervisorRun(runId: string, signal?: AbortSignal): Promise<{ run: SupervisorRun; etag: string | null }> {
  const res = await get<{ run: SupervisorRun }>(`/runs/${encodeURIComponent(runId)}`, signal)
  return { run: res.envelope.data.run, etag: res.etag }
}

export async function requestIndependentAudit(runId: string, runEtag: string): Promise<AuditRequest> {
  const credentials = supervisorCredentials()
  if (!credentials) throw new SupervisorApiError(401, 'supervisor_session_unavailable', 'A signed-in tenant administrator session is not available.', null)
  const headers = new Headers(credentials)
  headers.set('Content-Type', 'application/json')
  headers.set('Idempotency-Key', newIdempotencyKey())
  headers.set('If-Match', runEtag)
  const response = await fetch(`${PREFIX}/runs/${encodeURIComponent(runId)}/audit-requests`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ action: 'request_independent_audit', registry_version: '1', confirmation: true }),
  })
  const text = await response.text()
  let payload: SupervisorEnvelope<{ audit_request: AuditRequest }> | SupervisorErrorPayload | null = null
  try { payload = text ? (JSON.parse(text) as SupervisorEnvelope<{ audit_request: AuditRequest }>) : null } catch { /* handled below */ }
  if (!response.ok) {
    const error = payload as SupervisorErrorPayload | null
    throw new SupervisorApiError(response.status, error?.error?.code ?? `HTTP_${response.status}`, error?.error?.message ?? response.statusText ?? 'Request failed.', error?.meta?.request_id ?? response.headers.get('X-Request-ID'))
  }
  if (!payload || !('data' in payload)) throw new SupervisorApiError(502, 'invalid_supervisor_response', 'The supervisor API returned an invalid response envelope.', response.headers.get('X-Request-ID'))
  return (payload as SupervisorEnvelope<{ audit_request: AuditRequest }>).data.audit_request
}


export function createRequestEpoch() {
  let epoch = 0
  return { next: () => ++epoch, current: (value: number) => value === epoch }
}

export function shouldApplyMutationSelection(expectedEpoch: number, currentEpoch: number, routeSnapshot: string, currentRoute: string): boolean {
  return expectedEpoch === currentEpoch && routeSnapshot === currentRoute
}

export function createSupervisorRequestGuards() {
  return {
    snapshot: createRequestEpoch(),
    missions: createRequestEpoch(),
    missionDetail: createRequestEpoch(),
    workPackages: createRequestEpoch(),
    checkpoints: createRequestEpoch(),
    missionSelection: createRequestEpoch(),
    workPackageDetail: createRequestEpoch(),
  }
}

export function createSettlementTracker(expected: number) {
  let settled = 0
  return { settle: () => ++settled === expected }
}
