import { EmptyState, SupervisorLoading } from './SupervisorStates'
import { CheckpointForm } from './PlanningForms'
import type { Checkpoint, Mission } from './types'

export function ContextPanel({ mission, checkpoints, loading, onRecordCheckpoint }: { mission: Mission | null; checkpoints: Checkpoint[]; loading: boolean; onRecordCheckpoint: (fields: Record<string, string>) => Promise<void> }) {
  if (loading) return <SupervisorLoading />
  if (!mission) return <EmptyState title="Select a mission" detail="Context checkpoints are scoped to a selected mission." />
  return <section className="space-y-4"><header><h2 className="text-lg font-semibold">Context: {mission.title}</h2><p className="text-sm text-muted-foreground">Structural planning summaries only; this view does not include execution logs, evidence, or raw prompts.</p></header><CheckpointForm mission={mission} onSubmit={onRecordCheckpoint} />{checkpoints.length ? checkpoints.map((checkpoint) => <article className="rounded-xl border bg-card p-4" key={checkpoint.id}><p className="text-xs text-muted-foreground">Checkpoint {checkpoint.sequence} · {checkpoint.id}</p><h3 className="mt-2 font-semibold">{checkpoint.summary}</h3><dl className="mt-3 grid gap-3 text-sm"><div><dt className="font-medium">Decisions</dt><dd className="text-muted-foreground">{checkpoint.decisions}</dd></div><div><dt className="font-medium">Constraints</dt><dd className="text-muted-foreground">{checkpoint.constraints}</dd></div><div><dt className="font-medium">Open questions</dt><dd className="text-muted-foreground">{checkpoint.open_questions}</dd></div></dl></article>) : <EmptyState title="No context checkpoints recorded" detail="The live planning ledger has not returned an append-only checkpoint for this mission." />}</section>
}
