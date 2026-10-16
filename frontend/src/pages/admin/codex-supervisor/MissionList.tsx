import { EmptyState } from './SupervisorStates'
import type { Mission } from './types'

export function MissionList({ missions, selectedId, onSelect }: { missions: Mission[]; selectedId: string | null; onSelect: (id: string) => void }) {
  if (!missions.length) return <EmptyState title="No missions recorded" detail="The live planning ledger has not returned any missions for this project." />
  return <section className="rounded-xl border bg-card"><h2 className="border-b p-4 font-semibold">Missions</h2><ul className="divide-y">{missions.map((mission) => <li key={mission.id}><button onClick={() => onSelect(mission.id)} className={selectedId === mission.id ? 'w-full bg-muted p-4 text-left' : 'w-full p-4 text-left hover:bg-muted/60'}><span className="block font-medium">{mission.title}</span><span className="mt-1 block text-sm text-muted-foreground">{mission.summary}</span><span className="mt-2 block text-xs text-muted-foreground">{mission.state} · {mission.id}</span></button></li>)}</ul></section>
}
