// @ts-expect-error Node test types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node test types are intentionally not part of the app build.
import test from 'node:test'
import { createSettlementTracker, createSupervisorRequestGuards, getSupervisorTenantFromHost, loadSupervisorSnapshot, mapSupervisorError, mutatePlanning, planningEtag, shouldApplyMutationSelection, SupervisorApiError, supervisorCredentials } from './api.ts'
import { readSupervisorRoute, writeSupervisorRoute } from './routeState.ts'

function installBrowser(hostname: string, token: string | null) {
  const values = new Map<string, string>()
  if (token) values.set('token', token)
  const storage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) }
  ;(globalThis as unknown as { localStorage: unknown }).localStorage = storage
  ;(globalThis as unknown as { window: unknown }).window = {
    location: { hostname, pathname: '/admin/coding-cockpit-v2', origin: `https://${hostname}` },
    localStorage: storage,
  }
}

test('route state is URL-backed and selection-safe', () => {
  assert.deepEqual(readSupervisorRoute('?view=missions&mission=mis_1&workPackage=wpk_1'), { view: 'missions', missionId: 'mis_1', workPackageId: 'wpk_1' })
  assert.equal(writeSupervisorRoute('?view=context&mission=mis_old', { view: 'missions', missionId: 'mis_new', workPackageId: null }), '?view=missions&mission=mis_new')
  assert.equal(readSupervisorRoute('?view=run').view, 'overview')
})

test('V2 adapter sends only actual tenant/token credentials and no fallback', async () => {
  installBrowser('tenant.example.test', 'real-session-token')
  const calls: Array<{ url: string; headers: Headers }> = []
  globalThis.fetch = async (input, init) => {
    calls.push({ url: String(input), headers: new Headers(init?.headers) })
    const data = String(input).endsWith('/bootstrap') ? { capabilities: { can_view_supervisor: true, can_claim_project: false }, infrastructure: { state: 'ready', current_revision: '004', expected_revision: '004', reason_codes: [] }, project_resolution: null, cutover: { mode: 'v1_only', version: 1 }, cutover_absent_reason_code: null, project: null } : { projects: [] }
    return new Response(JSON.stringify({ data, meta: { request_id: 'req_test', schema_version: '0.1' } }), { headers: { ETag: '"test"' } })
  }
  await loadSupervisorSnapshot()
  assert.equal(calls.length, 2)
  assert.ok(calls.every((call) => call.url.startsWith('/api/admin/codex/v2/')))
  assert.ok(calls.every((call) => call.headers.get('X-Token') === 'real-session-token' && call.headers.get('X-Tenant') === 'tenant'))
  installBrowser('localhost', null)
  assert.equal(supervisorCredentials(), null)
  assert.equal(getSupervisorTenantFromHost('localhost'), null)
  assert.equal(getSupervisorTenantFromHost('127.0.0.1'), null)
  assert.equal(getSupervisorTenantFromHost('simplydemo.example.test'), null)
  assert.equal(getSupervisorTenantFromHost('tenant.trycloudflare.com'), null)
  assert.equal(getSupervisorTenantFromHost('tenant.run.app'), null)
})

test('error mapping never exposes arbitrary server messages', () => {
  const mapped = mapSupervisorError(new SupervisorApiError(500, 'internal_error', 'server detail that must never render', 'req_test'))
  assert.equal(mapped.detail.includes('server detail'), false)
  assert.equal(mapped.detail, 'The supervisor API could not provide safe planning data for this view.')
  assert.equal(mapSupervisorError(new Error('offline')).title, 'Supervisor connection failed')
})

test('planning mutations use the existing V2 contract, current revision, and no client identity fields', async () => {
  installBrowser('tenant.example.test', 'real-session-token')
  const calls: Array<{ url: string; init: RequestInit | undefined }> = []
  globalThis.fetch = async (input, init) => {
    calls.push({ url: String(input), init })
    return new Response(JSON.stringify({ data: { mission: { id: 'mis_1' } }, meta: { request_id: 'req_mutation', schema_version: '0.2' } }), { headers: { ETag: '"mission-v1-1"' } })
  }
  const result = await mutatePlanning<{ mission: { id: string } }>('/projects/prj_1/missions', 'create_mission', planningEtag('project', 4), { title: 'Bounded plan', summary: 'Structural summary' })
  assert.equal(result.mission.id, 'mis_1')
  assert.equal(calls.length, 1)
  const headers = new Headers(calls[0].init?.headers)
  const body = JSON.parse(String(calls[0].init?.body))
  assert.equal(calls[0].url, '/api/admin/codex/v2/projects/prj_1/missions')
  assert.equal(calls[0].init?.method, 'POST')
  assert.equal(headers.get('If-Match'), '"project-4"')
  assert.match(headers.get('Idempotency-Key') ?? '', /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  assert.deepEqual(body, { action: 'create_mission', registry_version: '0.2', confirmation: true, title: 'Bounded plan', summary: 'Structural summary' })
  assert.equal('tenant_id' in body || 'actor_id' in body || 'user_id' in body, false)
})

test('a lost planning response retries the exact pending request key, while terminal responses do not', async () => {
  installBrowser('tenant.example.test', 'real-session-token')
  const keys: string[] = []
  let attempt = 0
  globalThis.fetch = async (_input, init) => {
    keys.push(new Headers(init?.headers).get('Idempotency-Key') ?? '')
    attempt += 1
    if (attempt === 1) throw new TypeError('network interrupted')
    return new Response(JSON.stringify({ data: { mission: { id: 'mis_retry' } }, meta: { request_id: 'req_retry', schema_version: '0.2' } }))
  }
  const fields = { title: 'Retryable plan', summary: 'Structural summary' }
  await assert.rejects(() => mutatePlanning('/projects/prj_1/missions', 'create_mission', planningEtag('project', 4), fields), TypeError)
  await mutatePlanning('/projects/prj_1/missions', 'create_mission', planningEtag('project', 4), fields)
  await mutatePlanning('/projects/prj_1/missions', 'create_mission', planningEtag('project', 4), fields)
  assert.equal(keys[0], keys[1])
  assert.notEqual(keys[1], keys[2])
})

test('an in-progress planning response retains its key until a replay returns the entity', async () => {
  installBrowser('tenant.example.test', 'real-session-token')
  const keys: string[] = []
  let attempt = 0
  globalThis.fetch = async (_input, init) => {
    keys.push(new Headers(init?.headers).get('Idempotency-Key') ?? '')
    attempt += 1
    if (attempt === 1) return new Response(JSON.stringify({ data: { operation: { state: 'in_progress' } }, meta: { request_id: 'req_pending', schema_version: '0.2' } }), { status: 202 })
    return new Response(JSON.stringify({ data: { mission: { id: 'mis_replayed' } }, meta: { request_id: 'req_pending', schema_version: '0.2' } }), { headers: { 'Idempotency-Replayed': 'true' } })
  }
  const fields = { title: 'Pending plan', summary: 'Structural summary' }
  await assert.rejects(() => mutatePlanning('/projects/prj_2/missions', 'create_mission', planningEtag('project', 5), fields), (error: unknown) => error instanceof SupervisorApiError && error.status === 202)
  const replayed = await mutatePlanning<{ mission: { id: string } }>('/projects/prj_2/missions', 'create_mission', planningEtag('project', 5), fields)
  assert.equal(replayed.mission.id, 'mis_replayed')
  assert.equal(keys[0], keys[1])
})

test('mutation selection updates require the current independent epoch and original selection snapshot', () => {
  assert.equal(shouldApplyMutationSelection(3, 3, '/admin/coding-cockpit-v2?view=missions&mission=mis_a', '/admin/coding-cockpit-v2?view=missions&mission=mis_a'), true)
  assert.equal(shouldApplyMutationSelection(3, 4, '/admin/coding-cockpit-v2?view=missions&mission=mis_a', '/admin/coding-cockpit-v2?view=missions&mission=mis_a'), false)
  assert.equal(shouldApplyMutationSelection(3, 3, '/admin/coding-cockpit-v2?view=missions&mission=mis_a', '/admin/coding-cockpit-v2?view=missions&mission=mis_b'), false)
  assert.equal(shouldApplyMutationSelection(3, 3, '/admin/coding-cockpit-v2?view=missions', '/admin/calendar?view=missions'), false)
})

test('planning conflict mappings remain safe and actionable', () => {
  assert.equal(mapSupervisorError(new SupervisorApiError(409, 'idempotency_conflict', 'raw server detail', null)).title, 'Supervisor state changed')
  assert.equal(mapSupervisorError(new SupervisorApiError(412, 'revision_conflict', 'raw server detail', null)).title, 'Planning state changed')
})

test('independent request guards do not invalidate mission loading when mission-detail or work-package loading begins', () => {
  const guards = createSupervisorRequestGuards()
  const missionRequest = guards.missions.next()
  const missionDetailRequest = guards.missionDetail.next()
  const packagesRequest = guards.workPackages.next()
  const workPackageRequest = guards.workPackageDetail.next()
  assert.equal(guards.missions.current(missionRequest), true)
  assert.equal(guards.missionDetail.current(missionDetailRequest), true)
  assert.equal(guards.workPackages.current(packagesRequest), true)
  assert.equal(guards.workPackageDetail.current(workPackageRequest), true)
  const nextMissionRequest = guards.missions.next()
  assert.equal(guards.missions.current(missionRequest), false)
  assert.equal(guards.missions.current(nextMissionRequest), true)
  assert.equal(guards.missionDetail.current(missionDetailRequest), true)
  assert.equal(guards.workPackages.current(packagesRequest), true)
  assert.equal(guards.workPackageDetail.current(workPackageRequest), true)
})

test('composite selected-mission loading remains active until every independent read settles', () => {
  const tracker = createSettlementTracker(3)
  assert.equal(tracker.settle(), false)
  assert.equal(tracker.settle(), false)
  assert.equal(tracker.settle(), true)
})
