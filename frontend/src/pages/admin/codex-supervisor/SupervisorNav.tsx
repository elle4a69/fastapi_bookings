import type { SupervisorView } from './routeState'

const items: Array<{ id: SupervisorView; label: string; detail: string }> = [
  { id: 'overview', label: 'Overview', detail: 'Readiness and project boundary' },
  { id: 'missions', label: 'Missions', detail: 'Planning ledger' },
  { id: 'context', label: 'Context', detail: 'Saved checkpoints' },
]

export function SupervisorNav({ view, onSelect }: { view: SupervisorView; onSelect: (view: SupervisorView) => void }) {
  return <nav aria-label="Development Supervisor sections" className="flex flex-wrap gap-2 border-b pb-4">
    {items.map((item) => <button key={item.id} onClick={() => onSelect(item.id)} className={view === item.id ? 'rounded-md bg-primary px-3 py-2 text-left text-sm text-primary-foreground' : 'rounded-md border px-3 py-2 text-left text-sm hover:bg-muted'}><span className="block font-medium">{item.label}</span><span className="block text-xs opacity-80">{item.detail}</span></button>)}
  </nav>
}
