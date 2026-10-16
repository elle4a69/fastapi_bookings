import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createSettlementTracker, createSupervisorRequestGuards, loadAuditScope, loadBriefs, loadCheckpoints, loadMission, loadMissions, loadSupervisorSnapshot, loadWorkPackages, mapSupervisorError, supervisorCredentials } from './api'
import { ContextPanel } from './ContextPanel'
import { MissionDetail } from './MissionDetail'
import { MissionList } from './MissionList'
import { OverviewPanel } from './OverviewPanel'
import { readSupervisorRoute, writeSupervisorRoute } from './routeState'
import { SupervisorErrorState, SupervisorLoading, SupervisorSessionState } from './SupervisorStates'
import { SupervisorNav } from './SupervisorNav'
import { SupervisorShell } from './SupervisorShell'
import type { AuditScope, Brief, Checkpoint, Mission, SupervisorSnapshot, WorkPackage } from './types'

export function SupervisorPage() {
  const [search, setSearch] = useState(() => window.location.search)
  const route = useMemo(() => readSupervisorRoute(search), [search])
  const [snapshot, setSnapshot] = useState<SupervisorSnapshot | null>(null)
  const [missions, setMissions] = useState<Mission[]>([])
  const [mission, setMission] = useState<Mission | null>(null)
  const [packages, setPackages] = useState<WorkPackage[]>([])
  const [briefs, setBriefs] = useState<Brief[]>([])
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([])
  const [auditScope, setAuditScope] = useState<AuditScope | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const guards = useRef(createSupervisorRequestGuards())

  const updateRoute = useCallback((next: Parameters<typeof writeSupervisorRoute>[1]) => {
    const nextSearch = writeSupervisorRoute(window.location.search, next)
    window.history.pushState(null, '', `${window.location.pathname}${nextSearch}`)
    setSearch(nextSearch)
  }, [])

  useEffect(() => { const listener = () => setSearch(window.location.search); window.addEventListener('popstate', listener); return () => window.removeEventListener('popstate', listener) }, [])

  const refresh = useCallback(async () => {
    const request = guards.current.snapshot.next()
    const controller = new AbortController()
    setLoading(true); setError(null)
    try {
      const next = await loadSupervisorSnapshot(controller.signal)
      if (guards.current.snapshot.current(request)) setSnapshot(next)
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') return
      if (guards.current.snapshot.current(request)) { setSnapshot(null); setError(cause) }
    } finally { if (guards.current.snapshot.current(request)) setLoading(false) }
    return () => controller.abort()
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  const configuredProjectId = snapshot?.bootstrap.project?.project_id ?? snapshot?.projects[0]?.project_id ?? null
  useEffect(() => {
    if (!configuredProjectId) { setMissions([]); return }
    const controller = new AbortController(); const request = guards.current.missions.next()
    void loadMissions(configuredProjectId, controller.signal).then((data) => { if (guards.current.missions.current(request)) setMissions(data) }).catch((cause) => { if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.missions.current(request)) setError(cause) })
    return () => controller.abort()
  }, [configuredProjectId])

  useEffect(() => {
    if (!route.missionId) { setMission(null); setPackages([]); setCheckpoints([]); return }
    const missionController = new AbortController(); const packagesController = new AbortController(); const checkpointsController = new AbortController()
    const missionRequest = guards.current.missionDetail.next(); const packagesRequest = guards.current.workPackages.next(); const checkpointsRequest = guards.current.checkpoints.next(); const selectionRequest = guards.current.missionSelection.next(); const settlement = createSettlementTracker(3)
    setDetailLoading(true); setBriefs([]); setAuditScope(null)
    const finish = () => { if (settlement.settle() && guards.current.missionSelection.current(selectionRequest)) setDetailLoading(false) }
    void loadMission(route.missionId, missionController.signal).then((currentMission) => { if (guards.current.missionDetail.current(missionRequest)) setMission(currentMission) }).catch((cause) => { if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.missionDetail.current(missionRequest)) setError(cause) }).finally(finish)
    void loadWorkPackages(route.missionId, packagesController.signal).then((currentPackages) => { if (guards.current.workPackages.current(packagesRequest)) setPackages(currentPackages) }).catch((cause) => { if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.workPackages.current(packagesRequest)) setError(cause) }).finally(finish)
    void loadCheckpoints(route.missionId, checkpointsController.signal).then((currentCheckpoints) => { if (guards.current.checkpoints.current(checkpointsRequest)) setCheckpoints(currentCheckpoints) }).catch((cause) => { if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.checkpoints.current(checkpointsRequest)) setError(cause) }).finally(finish)
    return () => { missionController.abort(); packagesController.abort(); checkpointsController.abort() }
  }, [route.missionId])

  useEffect(() => {
    if (!route.workPackageId) { setBriefs([]); setAuditScope(null); return }
    const controller = new AbortController(); const request = guards.current.workPackageDetail.next(); setDetailLoading(true)
    void Promise.all([loadBriefs(route.workPackageId, controller.signal), loadAuditScope(route.workPackageId, controller.signal)]).then(([nextBriefs, nextAudit]) => { if (guards.current.workPackageDetail.current(request)) { setBriefs(nextBriefs); setAuditScope(nextAudit) } }).catch((cause) => { if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.workPackageDetail.current(request)) setError(cause) }).finally(() => { if (guards.current.workPackageDetail.current(request)) setDetailLoading(false) })
    return () => controller.abort()
  }, [route.workPackageId])

  if (!supervisorCredentials()) return <SupervisorSessionState />
  if (loading) return <SupervisorLoading />
  if (error || !snapshot) return <SupervisorErrorState error={mapSupervisorError(error)} refresh={() => void refresh()} />
  return <SupervisorShell snapshot={snapshot} onRefresh={() => void refresh()} refreshing={loading}><SupervisorNav view={route.view} onSelect={(view) => updateRoute({ view })} />{route.view === 'overview' && <OverviewPanel snapshot={snapshot} />}{route.view === 'missions' && <section className="grid gap-4 lg:grid-cols-[minmax(18rem,0.85fr)_minmax(0,2fr)]"><MissionList missions={missions} selectedId={route.missionId} onSelect={(missionId) => updateRoute({ view: 'missions', missionId, workPackageId: null })} /><MissionDetail mission={mission} packages={packages} selectedWorkPackageId={route.workPackageId} onSelectWorkPackage={(workPackageId) => updateRoute({ workPackageId })} briefs={briefs} auditScope={auditScope} loading={detailLoading} /></section>}{route.view === 'context' && <ContextPanel mission={mission} checkpoints={checkpoints} loading={detailLoading} />}</SupervisorShell>
}
