import { getAdminAccessToken } from '../../../lib/api.ts'
import type { AuditScope, Bootstrap, Brief, Checkpoint, Mission, Project, SupervisorEnvelope, SupervisorErrorPayload, SupervisorSnapshot, WorkPackage } from './types'

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
    if (error.status === 403) return { title: 'Platform-owner access required', detail: 'This planning surface is available only to an active platform owner.', canRetry: false }
    if (error.code === 'database_migration_required') return { title: 'Supervisor migration required', detail: 'The control-plane database is not ready. No planning data has been shown.', canRetry: true }
    if (error.code === 'supervisor_unconfigured') return { title: 'Project configuration required', detail: 'No configured project is available to this supervisor.', canRetry: false }
    if (error.status === 404) return { title: 'Planning resource unavailable', detail: 'The selected planning resource is not available in this scope.', canRetry: false }
    if (error.status === 409) return { title: 'Supervisor state changed', detail: 'The planning state is not currently available for this view. Refresh before continuing.', canRetry: true }
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

export function createRequestEpoch() {
  let epoch = 0
  return { next: () => ++epoch, current: (value: number) => value === epoch }
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
