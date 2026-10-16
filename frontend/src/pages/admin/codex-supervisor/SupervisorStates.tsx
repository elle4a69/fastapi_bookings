import type { ReactNode } from 'react'
import type { SupervisorUiError } from './api'

export function SupervisorNotice({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <section className="rounded-xl border bg-card p-5 shadow-sm" role="status"><h2 className="text-base font-semibold">{title}</h2><p className="mt-2 text-sm text-muted-foreground">{children}</p>{action && <div className="mt-4">{action}</div>}</section>
}

export function SupervisorLoading() { return <SupervisorNotice title="Loading Development Supervisor">Requesting the configured supervisor state. No local or demo planning data is displayed.</SupervisorNotice> }
export function SupervisorErrorState({ error, refresh }: { error: SupervisorUiError; refresh?: () => void }) {
  return <SupervisorNotice title={error.title} action={error.canRetry && refresh ? <button className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground" onClick={refresh}>Try again</button> : undefined}>{error.detail}</SupervisorNotice>
}
export function SupervisorSessionState() { return <SupervisorNotice title="Sign-in and tenant context required">This V2 surface only uses an actual signed-in administrator token and tenant host context. It does not use local, tunnel, or demo fallbacks.</SupervisorNotice> }
export function EmptyState({ title, detail }: { title: string; detail: string }) { return <SupervisorNotice title={title}>{detail}</SupervisorNotice> }
