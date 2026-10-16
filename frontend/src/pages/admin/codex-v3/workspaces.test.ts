// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync, existsSync } from 'node:fs'
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'

const workspacesDir = fileURLToPath(new URL('./workspaces/', import.meta.url))
const rootDir = fileURLToPath(new URL('./', import.meta.url))
const appSourcePath = fileURLToPath(new URL('../../../App.tsx', import.meta.url))

test('Package 4: All workspace files and main page index exist on disk', () => {
  const expectedFiles = [
    'TicketsWorkspace.tsx',
    'CodingWorkspace.tsx',
    'PlanningWorkspace.tsx',
    'SignalsWorkspace.tsx',
    'index.ts',
  ]

  for (const file of expectedFiles) {
    const fullPath = `${workspacesDir}${file}`
    assert.ok(existsSync(fullPath), `File ${file} must exist in workspaces/`)
  }

  assert.ok(existsSync(`${rootDir}index.tsx`), 'index.tsx must exist in codex-v3 root')
})

test('Package 4: TicketsWorkspace displays triage queue, filter pills, severity badges, and investigation launcher', () => {
  const content = readFileSync(`${workspacesDir}TicketsWorkspace.tsx`, 'utf8')
  assert.ok(content.includes('TicketsWorkspace'), 'Must export TicketsWorkspace')
  assert.ok(content.includes('filter-${pill.id}') || content.includes('filter-all'), 'Must have filter pills')
  assert.ok(content.includes('needs_auth'), 'Must support needs_auth filter')
  assert.ok(content.includes('in_progress'), 'Must support in_progress filter')
  assert.ok(content.includes('resolved'), 'Must support resolved filter')
  assert.ok(content.includes('High Severity'), 'Must render High Severity badge')
  assert.ok(content.includes('Med Severity'), 'Must render Med Severity badge')
  assert.ok(content.includes('Low Severity'), 'Must render Low Severity badge')
  assert.ok(content.includes('Error Context & Diagnostic Capture'), 'Must render Error Context preview')
  assert.ok(content.includes('Launch Codex Investigation'), 'Must render Launch Codex Investigation action button')
  assert.ok(content.includes('onLaunchInvestigation'), 'Must support onLaunchInvestigation callback')
})

test('Package 4: CodingWorkspace provides worktree selector, unified/side-by-side diff studio, test runner, and release promotion gate', () => {
  const content = readFileSync(`${workspacesDir}CodingWorkspace.tsx`, 'utf8')
  assert.ok(content.includes('CodingWorkspace'), 'Must export CodingWorkspace')
  assert.ok(content.includes('worktreePath'), 'Must display worktree path')
  assert.ok(content.includes('activeBranch'), 'Must manage active branch selector')
  assert.ok(content.includes('Unified'), 'Must support Unified diff mode')
  assert.ok(content.includes('Side-by-side'), 'Must support Side-by-side diff mode')
  assert.ok(content.includes('accept-diff-btn'), 'Must have Accept Diff button')
  assert.ok(content.includes('discard-diff-btn'), 'Must have Discard Diff button')
  assert.ok(content.includes('run-tests-btn'), 'Must have Run Tests action button')
  assert.ok(content.includes('passedCount'), 'Must display passed test count summary')
  assert.ok(content.includes('failedCount'), 'Must display failed test count summary')
  assert.ok(content.includes('promote-release-btn'), 'Must have Promote to Release Branch gate button')
})

test('Package 4: PlanningWorkspace provides DAG pipeline, acceptance criteria, checkpoints with rollback, and elevation launcher', () => {
  const content = readFileSync(`${workspacesDir}PlanningWorkspace.tsx`, 'utf8')
  assert.ok(content.includes('PlanningWorkspace'), 'Must export PlanningWorkspace')
  assert.ok(content.includes('dag-node-'), 'Must render work package DAG nodes')
  assert.ok(content.includes('Brief Acceptance Criteria Checklist'), 'Must render acceptance criteria list')
  assert.ok(content.includes('PASS'), 'Must render PASS badge for passed criteria')
  assert.ok(content.includes('PENDING'), 'Must render PENDING badge for pending criteria')
  assert.ok(content.includes('create-checkpoint-btn'), 'Must have Create Checkpoint button')
  assert.ok(content.includes('rollback-btn-'), 'Must have Rollback to Checkpoint button')
  assert.ok(content.includes('confirm-rollback-'), 'Must provide rollback safety confirmation')
  assert.ok(content.includes('grant-elevation-btn'), 'Must have Single-Run Elevation Grant launcher')
  assert.ok(content.includes('revoke-grant-btn'), 'Must support revoking elevation grant')
})

test('Package 4: SignalsWorkspace provides SigNoz APM link, live latency charts, sentinel health matrix, and sync cards', () => {
  const content = readFileSync(`${workspacesDir}SignalsWorkspace.tsx`, 'utf8')
  assert.ok(content.includes('SignalsWorkspace'), 'Must export SignalsWorkspace')
  assert.ok(content.includes('signoz-apm-link'), 'Must link to SigNoz APM dashboard')
  assert.ok(content.includes('P50 Median Latency'), 'Must display P50 latency metric')
  assert.ok(content.includes('P95 Tail Latency'), 'Must display P95 latency metric')
  assert.ok(content.includes('P99 Maximum Guard'), 'Must display P99 latency metric')
  assert.ok(content.includes('polyline'), 'Must render SVG latency trend chart')
  assert.ok(content.includes('sentinel-${sentinel.id}') || content.includes('sentinel-fastapi'), 'Must render sentinel cards')
  assert.ok(content.includes('fastapi'), 'Must monitor FastAPI core sentinel')
  assert.ok(content.includes('postgres'), 'Must monitor PostgreSQL database sentinel')
  assert.ok(content.includes('redis'), 'Must monitor Redis cache sentinel')
  assert.ok(content.includes('neo4j'), 'Must monitor Neo4j graph sentinel')
  assert.ok(content.includes('workers'), 'Must monitor background workers sentinel')
  assert.ok(content.includes('SMS Outbox Backlog'), 'Must render SMS outbox backlog card')
  assert.ok(content.includes('Chatwoot Webhook'), 'Must render Chatwoot sync status card')
})

test('Package 4: codex-v3/index.tsx orchestrates layout, workspaces, transparent stream, and voice context', () => {
  const content = readFileSync(`${rootDir}index.tsx`, 'utf8')
  assert.ok(content.includes('CodexV3Layout'), 'Must orchestrate CodexV3Layout')
  assert.ok(content.includes('activeView'), 'Must manage activeView state')
  assert.ok(content.includes('mobileTab'), 'Must manage mobileTab state')
  assert.ok(content.includes('TicketsWorkspace'), 'Must mount TicketsWorkspace')
  assert.ok(content.includes('CodingWorkspace'), 'Must mount CodingWorkspace')
  assert.ok(content.includes('PlanningWorkspace'), 'Must mount PlanningWorkspace')
  assert.ok(content.includes('SignalsWorkspace'), 'Must mount SignalsWorkspace')
  assert.ok(content.includes('TransparentStream'), 'Must mount TransparentStream')
  assert.ok(content.includes('useCodexVoice'), 'Must embed useCodexVoice hook')
  assert.ok(content.includes('CodexVoiceProvider'), 'Must be wrapped in CodexVoiceProvider')
})

test('Package 4: App.tsx registers /admin/codex-v3 route mapping to codex-v3 page', () => {
  const content = readFileSync(appSourcePath, 'utf8')
  assert.ok(content.includes("lazy(() => import('@/pages/admin/codex-v3'))") || content.includes('lazy(() => import("@/pages/admin/codex-v3"))'), 'Must lazy import codex-v3 page')
  assert.ok(content.includes('path="/admin/codex-v3"'), 'Must register route /admin/codex-v3')
})
