import type { ReactNode } from 'react'
import type { Project, SupervisorSnapshot } from './types'

export function SupervisorShell({ snapshot, children, onRefresh, refreshing }: { snapshot: SupervisorSnapshot; children: ReactNode; onRefresh: () => void; refreshing: boolean }) {
  const project: Project | null = snapshot.bootstrap.project ?? snapshot.projects[0] ?? null
  return <section className="mx-auto flex w-full max-w-7xl flex-col gap-5" aria-label="Development Supervisor">
    <header className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm font-medium text-primary">Native Codex Control Centre</p><h1 className="text-2xl font-semibold tracking-tight">Development Supervisor</h1><p className="mt-1 text-sm text-muted-foreground">{project ? `${project.display_name} · ${project.default_branch}` : 'No configured project reported by the API.'}</p></div><div className="flex items-center gap-2"><span className="rounded-full border border-amber-500/50 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-800 dark:text-amber-300">Planning only — no execution</span><button onClick={onRefresh} disabled={refreshing} className="rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-50">{refreshing ? 'Refreshing…' : 'Refresh'}</button></div></div>
      <p className="mt-4 text-xs text-muted-foreground">Freshness: request {snapshot.etags.bootstrap ? 'validated with a server ETag' : 'reported without an ETag'} · cutover remains {snapshot.bootstrap.cutover?.mode ?? 'unavailable'}.</p>
    </header>{children}
  </section>
}
