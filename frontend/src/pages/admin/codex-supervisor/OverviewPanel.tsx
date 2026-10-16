import { EmptyState } from './SupervisorStates'
import { CreateMissionForm } from './PlanningForms'
import type { SupervisorSnapshot } from './types'

export function OverviewPanel({ snapshot, onCreateMission }: { snapshot: SupervisorSnapshot; onCreateMission: (fields: Record<string, string>) => Promise<void> }) {
  const { bootstrap } = snapshot
  if (!bootstrap.project && bootstrap.project_resolution?.state === 'unconfigured') return <EmptyState title="Project configuration required" detail="The V2 API has no configured project for this supervisor scope." />
  return <section className="space-y-4"><div className="grid gap-4 md:grid-cols-3"><article className="rounded-xl border bg-card p-4"><h2 className="font-semibold">Infrastructure</h2><p className="mt-2 text-sm">{bootstrap.infrastructure.state}</p><p className="mt-1 text-xs text-muted-foreground">Revision {bootstrap.infrastructure.current_revision ?? 'unknown'} / expected {bootstrap.infrastructure.expected_revision}</p></article><article className="rounded-xl border bg-card p-4"><h2 className="font-semibold">Project resolution</h2><p className="mt-2 text-sm">{bootstrap.project_resolution?.state ?? 'unavailable'}</p><p className="mt-1 text-xs text-muted-foreground">{bootstrap.project_resolution?.reason_codes.join(', ') || 'No reason code supplied.'}</p></article><article className="rounded-xl border bg-card p-4"><h2 className="font-semibold">Control boundary</h2><p className="mt-2 text-sm">{bootstrap.cutover?.mode ?? 'not available'}</p><p className="mt-1 text-xs text-muted-foreground">This UI cannot dispatch, execute, approve tools, or produce audit verdicts.</p></article></div><CreateMissionForm ready={Boolean(bootstrap.project ?? snapshot.projects[0])} onSubmit={onCreateMission} /></section>
}
