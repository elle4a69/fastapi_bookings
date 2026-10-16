export type SupervisorView = 'overview' | 'missions' | 'context'

export type SupervisorRouteState = { view: SupervisorView; missionId: string | null; workPackageId: string | null }

const VIEWS = new Set<SupervisorView>(['overview', 'missions', 'context'])

export function readSupervisorRoute(search: string): SupervisorRouteState {
  const params = new URLSearchParams(search)
  const value = params.get('view')
  return {
    view: value && VIEWS.has(value as SupervisorView) ? value as SupervisorView : 'overview',
    missionId: params.get('mission'),
    workPackageId: params.get('workPackage'),
  }
}

export function writeSupervisorRoute(currentSearch: string, next: Partial<SupervisorRouteState>): string {
  const current = readSupervisorRoute(currentSearch)
  const state = { ...current, ...next }
  const params = new URLSearchParams()
  if (state.view !== 'overview') params.set('view', state.view)
  if (state.missionId) params.set('mission', state.missionId)
  if (state.workPackageId) params.set('workPackage', state.workPackageId)
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}
