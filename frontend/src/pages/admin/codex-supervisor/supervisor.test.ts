// @ts-expect-error Node test types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node test types are intentionally not part of the app build.
import test from 'node:test'
import { createSettlementTracker, createSupervisorRequestGuards, getSupervisorTenantFromHost, loadSupervisorSnapshot, mapSupervisorError, SupervisorApiError, supervisorCredentials } from './api.ts'
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
