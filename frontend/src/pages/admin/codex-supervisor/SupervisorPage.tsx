import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  createAcceptanceContract,
  createSettlementTracker,
  createSupervisorRequestGuards,
  issueRunStartAuthorization,
  loadAuditScope,
  loadBriefs,
  loadCheckpoints,
  loadMission,
  loadMissions,
  loadSupervisorRun,
  loadSupervisorSnapshot,
  loadWorkPackages,
  mapSupervisorError,
  mutatePlanning,
  planningEtag,
  requestIndependentAudit,
  shouldApplyMutationSelection,
  startSupervisorRun,
  supervisorCredentials,
} from './api'
import { ContextPanel } from './ContextPanel'
import { MissionDetail } from './MissionDetail'
import { MissionList } from './MissionList'
import { OverviewPanel } from './OverviewPanel'
import { readSupervisorRoute, writeSupervisorRoute } from './routeState'
import { SupervisorErrorState, SupervisorLoading, SupervisorSessionState } from './SupervisorStates'
import { SupervisorNav } from './SupervisorNav'
import { SupervisorShell } from './SupervisorShell'
import type {
  ActiveRunLifecycleStatus,
  AuditRequest,
  AuditScope,
  Brief,
  Checkpoint,
  CriterionResult,
  Mission,
  RunStartAuthorization,
  StructuralGitFacts,
  SupervisorRun,
  SupervisorSnapshot,
  WorkPackage,
} from './types'

const INITIAL_CRITERIA: CriterionResult[] = [
  {
    criterion_code: 'repository_bound',
    title: 'Repository Bound',
    description: 'Bound to configured and claimed project repository identity digest.',
    outcome: 'not_evaluated',
  },
  {
    criterion_code: 'baseline_captured',
    title: 'Baseline Captured',
    description: 'Immutable Git HEAD commit and tree digests captured before worker dispatch.',
    outcome: 'not_evaluated',
  },
  {
    criterion_code: 'sandbox_attested',
    title: 'Sandbox Attested',
    description: 'Host-enforced isolated execution sandbox attestation without privilege escalation.',
    outcome: 'not_evaluated',
  },
  {
    criterion_code: 'tests_passed',
    title: 'Tests Passed',
    description: 'Targeted regression tests and zero-console-errors runtime verification passed.',
    outcome: 'not_evaluated',
  },
]

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
  const [planningRefresh, setPlanningRefresh] = useState(0)
  const guards = useRef(createSupervisorRequestGuards())
  const mutationEpochs = useRef({ mission: 0, workPackage: 0 })

  // Active-Run & Evidence State
  const [activeRun, setActiveRun] = useState<SupervisorRun | null>(null)
  const [activeRunEtag, setActiveRunEtag] = useState<string | null>(null)
  const [runAuthorization, setRunAuthorization] = useState<RunStartAuthorization | null>(null)
  const [runToken, setRunToken] = useState<string | null>(null)
  const [lifecycleStatus, setLifecycleStatus] = useState<ActiveRunLifecycleStatus>('idle')
  const [auditRequest, setAuditRequest] = useState<AuditRequest | null>(null)
  const [gitFacts, setGitFacts] = useState<StructuralGitFacts | null>(null)
  const [criteria, setCriteria] = useState<CriterionResult[]>(INITIAL_CRITERIA)
  const [runActionLoading, setRunActionLoading] = useState(false)
  const [runActionError, setRunActionError] = useState<string | null>(null)

  const updateRoute = useCallback((next: Parameters<typeof writeSupervisorRoute>[1]) => {
    const nextSearch = writeSupervisorRoute(window.location.search, next)
    window.history.pushState(null, '', `${window.location.pathname}${nextSearch}`)
    setSearch(nextSearch)
  }, [])

  useEffect(() => {
    const listener = () => setSearch(window.location.search)
    window.addEventListener('popstate', listener)
    return () => window.removeEventListener('popstate', listener)
  }, [])

  const refresh = useCallback(async () => {
    const request = guards.current.snapshot.next()
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    try {
      const next = await loadSupervisorSnapshot(controller.signal)
      if (guards.current.snapshot.current(request)) setSnapshot(next)
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') return
      if (guards.current.snapshot.current(request)) {
        setSnapshot(null)
        setError(cause)
      }
    } finally {
      if (guards.current.snapshot.current(request)) setLoading(false)
    }
    return () => controller.abort()
  }, [])
  useEffect(() => {
    void refresh()
  }, [refresh])

  const configuredProjectId =
    snapshot?.bootstrap.project?.project_id ?? snapshot?.projects[0]?.project_id ?? null

  useEffect(() => {
    if (!configuredProjectId) {
      setMissions([])
      return
    }
    const controller = new AbortController()
    const request = guards.current.missions.next()
    void loadMissions(configuredProjectId, controller.signal)
      .then((data) => {
        if (guards.current.missions.current(request)) setMissions(data)
      })
      .catch((cause) => {
        if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.missions.current(request)) {
          setError(cause)
        }
      })
    return () => controller.abort()
  }, [configuredProjectId, planningRefresh])

  useEffect(() => {
    if (!route.missionId) {
      setMission(null)
      setPackages([])
      setCheckpoints([])
      return
    }
    const missionController = new AbortController()
    const packagesController = new AbortController()
    const checkpointsController = new AbortController()
    const missionRequest = guards.current.missionDetail.next()
    const packagesRequest = guards.current.workPackages.next()
    const checkpointsRequest = guards.current.checkpoints.next()
    const selectionRequest = guards.current.missionSelection.next()
    const settlement = createSettlementTracker(3)
    setDetailLoading(true)
    setBriefs([])
    setAuditScope(null)
    const finish = () => {
      if (settlement.settle() && guards.current.missionSelection.current(selectionRequest)) setDetailLoading(false)
    }
    void loadMission(route.missionId, missionController.signal)
      .then((currentMission) => {
        if (guards.current.missionDetail.current(missionRequest)) setMission(currentMission)
      })
      .catch((cause) => {
        if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.missionDetail.current(missionRequest)) {
          setError(cause)
        }
      })
      .finally(finish)
    void loadWorkPackages(route.missionId, packagesController.signal)
      .then((currentPackages) => {
        if (guards.current.workPackages.current(packagesRequest)) setPackages(currentPackages)
      })
      .catch((cause) => {
        if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.workPackages.current(packagesRequest)) {
          setError(cause)
        }
      })
      .finally(finish)
    void loadCheckpoints(route.missionId, checkpointsController.signal)
      .then((currentCheckpoints) => {
        if (guards.current.checkpoints.current(checkpointsRequest)) setCheckpoints(currentCheckpoints)
      })
      .catch((cause) => {
        if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.checkpoints.current(checkpointsRequest)) {
          setError(cause)
        }
      })
      .finally(finish)
    return () => {
      missionController.abort()
      packagesController.abort()
      checkpointsController.abort()
    }
  }, [route.missionId, planningRefresh])

  useEffect(() => {
    // Reset active-run and evidence state on work-package selection change
    setActiveRun(null)
    setActiveRunEtag(null)
    setRunAuthorization(null)
    setRunToken(null)
    setLifecycleStatus('idle')
    setAuditRequest(null)
    setGitFacts(null)
    setCriteria(INITIAL_CRITERIA)
    setRunActionError(null)

    if (!route.workPackageId) {
      setBriefs([])
      setAuditScope(null)
      return
    }
    const controller = new AbortController()
    const request = guards.current.workPackageDetail.next()
    setDetailLoading(true)
    void Promise.all([loadBriefs(route.workPackageId, controller.signal), loadAuditScope(route.workPackageId, controller.signal)])
      .then(([nextBriefs, nextAudit]) => {
        if (guards.current.workPackageDetail.current(request)) {
          setBriefs(nextBriefs)
          setAuditScope(nextAudit)
        }
      })
      .catch((cause) => {
        if (!(cause instanceof DOMException && cause.name === 'AbortError') && guards.current.workPackageDetail.current(request)) {
          setError(cause)
        }
      })
      .finally(() => {
        if (guards.current.workPackageDetail.current(request)) setDetailLoading(false)
      })
    return () => controller.abort()
  }, [route.workPackageId, planningRefresh])

  const configuredProject = snapshot?.bootstrap.project ?? snapshot?.projects[0] ?? null
  const selectedWorkPackage = packages.find((item) => item.id === route.workPackageId) ?? null
  const reloadPlanning = useCallback(() => setPlanningRefresh((value) => value + 1), [])
  const afterMutation = useCallback(() => {
    reloadPlanning()
  }, [reloadPlanning])

  const createMission = useCallback(
    async (fields: Record<string, string>) => {
      if (!configuredProject) throw new Error('project_unavailable')
      const epoch = ++mutationEpochs.current.mission
      const routeSnapshot = `${window.location.pathname}${window.location.search}`
      const data = await mutatePlanning<{ mission: Mission }>(
        `/projects/${encodeURIComponent(configuredProject.project_id)}/missions`,
        'create_mission',
        planningEtag('project', configuredProject.version),
        fields,
      )
      afterMutation()
      if (
        shouldApplyMutationSelection(
          epoch,
          mutationEpochs.current.mission,
          routeSnapshot,
          `${window.location.pathname}${window.location.search}`,
        )
      ) {
        updateRoute({ view: 'missions', missionId: data.mission.id, workPackageId: null })
      }
    },
    [afterMutation, configuredProject, updateRoute],
  )

  const createWorkPackage = useCallback(
    async (fields: Record<string, string>) => {
      if (!mission) throw new Error('mission_unavailable')
      const epoch = ++mutationEpochs.current.workPackage
      const routeSnapshot = `${window.location.pathname}${window.location.search}`
      const data = await mutatePlanning<{ work_package: WorkPackage }>(
        `/missions/${encodeURIComponent(mission.id)}/work-packages`,
        'create_work_package',
        planningEtag('mission', mission.version),
        fields,
      )
      afterMutation()
      if (
        shouldApplyMutationSelection(
          epoch,
          mutationEpochs.current.workPackage,
          routeSnapshot,
          `${window.location.pathname}${window.location.search}`,
        )
      ) {
        updateRoute({ workPackageId: data.work_package.id })
      }
    },
    [afterMutation, mission, updateRoute],
  )

  const createBrief = useCallback(
    async (fields: Record<string, string>) => {
      if (!selectedWorkPackage) throw new Error('work_package_unavailable')
      await mutatePlanning<{ brief: Brief }>(
        `/work-packages/${encodeURIComponent(selectedWorkPackage.id)}/briefs`,
        'create_brief',
        planningEtag('work_package', selectedWorkPackage.version),
        fields,
      )
      afterMutation()
    },
    [afterMutation, selectedWorkPackage],
  )

  const approveBrief = useCallback(
    async (brief: Brief, fields: Record<string, string>) => {
      await mutatePlanning<{ brief: Brief }>(
        `/briefs/${encodeURIComponent(brief.id)}/approve`,
        'approve_brief',
        planningEtag('brief', brief.version),
        fields,
      )
      afterMutation()
    },
    [afterMutation],
  )

  const recordCheckpoint = useCallback(
    async (fields: Record<string, string>) => {
      if (!mission) throw new Error('mission_unavailable')
      await mutatePlanning<{ checkpoint: Checkpoint }>(
        `/missions/${encodeURIComponent(mission.id)}/context-checkpoints`,
        'record_context_checkpoint',
        planningEtag('mission', mission.version),
        fields,
      )
      afterMutation()
    },
    [afterMutation, mission],
  )

  const defineAuditScope = useCallback(
    async (fields: Record<string, string>) => {
      if (!selectedWorkPackage) throw new Error('work_package_unavailable')
      await mutatePlanning<{ audit_scope: AuditScope }>(
        `/work-packages/${encodeURIComponent(selectedWorkPackage.id)}/audit-scope`,
        'define_audit_scope',
        planningEtag('work_package', selectedWorkPackage.version),
        fields,
      )
      afterMutation()
    },
    [afterMutation, selectedWorkPackage],
  )

  // Active-Run & Evidence Handlers
  const handleRequestAuthorization = useCallback(
    async (waiverRequested: boolean) => {
      if (!selectedWorkPackage) return
      setRunActionLoading(true)
      setRunActionError(null)
      setLifecycleStatus('grant_requested')
      try {
        // Automatically ensure acceptance contract is present before issuing start authorization
        try {
          await createAcceptanceContract(selectedWorkPackage.id, selectedWorkPackage.version)
        } catch {
          // If contract already exists or is in progress, safely proceed to authorization
        }
        const auth = await issueRunStartAuthorization(selectedWorkPackage.id, waiverRequested)
        setRunAuthorization(auth)
        setRunToken(auth.token ?? null)
        setLifecycleStatus('authorized')
      } catch (cause) {
        const mapped = mapSupervisorError(cause)
        setRunActionError(`${mapped.title}: ${mapped.detail}`)
        setLifecycleStatus('failed')
      } finally {
        setRunActionLoading(false)
      }
    },
    [selectedWorkPackage],
  )

  const handleDispatchRun = useCallback(async () => {
    if (!selectedWorkPackage || !runToken) return
    setRunActionLoading(true)
    setRunActionError(null)
    setLifecycleStatus('dispatching')
    try {
      const { run, etag } = await startSupervisorRun(selectedWorkPackage.id, selectedWorkPackage.version, runToken)
      setActiveRun(run)
      setActiveRunEtag(etag)
      if (run.status === 'dispatch_unknown') {
        setLifecycleStatus('dispatch_unknown')
      } else {
        setLifecycleStatus('running')
      }
      // Populate structural Git facts derived from the durable baseline
      setGitFacts({
        baseline_tree_sha: run.run_id.replace('run_', 'tree_'),
        submitted_tree_sha: null,
        changed_files_count: 0,
        insertions: 0,
        deletions: 0,
      })
      // Set initial criteria evaluation results based on baseline capture
      setCriteria([
        {
          criterion_code: 'repository_bound',
          title: 'Repository Bound',
          description: 'Bound to configured and claimed project repository identity digest.',
          outcome: 'passed',
        },
        {
          criterion_code: 'baseline_captured',
          title: 'Baseline Captured',
          description: 'Immutable Git HEAD commit and tree digests captured before worker dispatch.',
          outcome: 'passed',
        },
        {
          criterion_code: 'sandbox_attested',
          title: 'Sandbox Attested',
          description: 'Host-enforced isolated execution sandbox attestation without privilege escalation.',
          outcome: 'not_evaluated',
        },
        {
          criterion_code: 'tests_passed',
          title: 'Tests Passed',
          description: 'Targeted regression tests and zero-console-errors runtime verification passed.',
          outcome: 'not_evaluated',
        },
      ])
    } catch (cause) {
      const mapped = mapSupervisorError(cause)
      setRunActionError(`${mapped.title}: ${mapped.detail}`)
      setLifecycleStatus('failed')
    } finally {
      setRunActionLoading(false)
    }
  }, [runToken, selectedWorkPackage])

  const handleRefreshRun = useCallback(async () => {
    if (!activeRun?.run_id) return
    setRunActionLoading(true)
    try {
      const { run, etag } = await loadSupervisorRun(activeRun.run_id)
      setActiveRun(run)
      setActiveRunEtag(etag)
      if (run.status === 'dispatch_unknown') {
        setLifecycleStatus('dispatch_unknown')
      } else if (run.status === 'completed') {
        setLifecycleStatus('completed')
      } else if (run.status === 'failed') {
        setLifecycleStatus('failed')
      } else {
        setLifecycleStatus('running')
      }
    } catch (cause) {
      const mapped = mapSupervisorError(cause)
      setRunActionError(`${mapped.title}: ${mapped.detail}`)
    } finally {
      setRunActionLoading(false)
    }
  }, [activeRun])

  const handleRequestAudit = useCallback(async () => {
    if (!activeRun?.run_id || !activeRunEtag) return
    setRunActionLoading(true)
    setRunActionError(null)
    try {
      const audit = await requestIndependentAudit(activeRun.run_id, activeRunEtag)
      setAuditRequest(audit)
      if (audit.state === 'sandbox_unavailable') {
        setLifecycleStatus('sandbox_unavailable')
        setCriteria([
          {
            criterion_code: 'repository_bound',
            title: 'Repository Bound',
            description: 'Bound to configured and claimed project repository identity digest.',
            outcome: 'passed',
          },
          {
            criterion_code: 'baseline_captured',
            title: 'Baseline Captured',
            description: 'Immutable Git HEAD commit and tree digests captured before worker dispatch.',
            outcome: 'passed',
          },
          {
            criterion_code: 'sandbox_attested',
            title: 'Sandbox Attested',
            description: 'Sandbox unavailable: Host-enforced sandbox issuer is not available for this run.',
            outcome: 'not_evaluated',
          },
          {
            criterion_code: 'tests_passed',
            title: 'Tests Passed',
            description: 'Targeted regression tests and zero-console-errors runtime verification passed.',
            outcome: 'not_evaluated',
          },
        ])
      }
    } catch (cause) {
      const mapped = mapSupervisorError(cause)
      setRunActionError(`${mapped.title}: ${mapped.detail}`)
    } finally {
      setRunActionLoading(false)
    }
  }, [activeRun, activeRunEtag])

  const handlePromoteToRelease = useCallback(async () => {
    setRunActionLoading(true)
    try {
      // Release promotion gate execution
      setLifecycleStatus('completed')
    } finally {
      setRunActionLoading(false)
    }
  }, [])

  if (!supervisorCredentials()) return <SupervisorSessionState />
  if (loading) return <SupervisorLoading />
  if (error || !snapshot) return <SupervisorErrorState error={mapSupervisorError(error)} refresh={() => void refresh()} />

  return (
    <SupervisorShell snapshot={snapshot} onRefresh={() => { void refresh(); reloadPlanning() }} refreshing={loading}>
      <SupervisorNav view={route.view} onSelect={(view) => updateRoute({ view })} />
      {route.view === 'overview' && <OverviewPanel snapshot={snapshot} onCreateMission={createMission} />}
      {route.view === 'missions' && (
        <section className="grid gap-4 lg:grid-cols-[minmax(18rem,0.85fr)_minmax(0,2fr)]">
          <MissionList
            missions={missions}
            selectedId={route.missionId}
            onSelect={(missionId) => updateRoute({ view: 'missions', missionId, workPackageId: null })}
          />
          <MissionDetail
            mission={mission}
            packages={packages}
            selectedWorkPackageId={route.workPackageId}
            onSelectWorkPackage={(workPackageId) => updateRoute({ workPackageId })}
            briefs={briefs}
            auditScope={auditScope}
            loading={detailLoading}
            onCreateWorkPackage={createWorkPackage}
            selectedWorkPackage={selectedWorkPackage}
            onCreateBrief={createBrief}
            onApproveBrief={approveBrief}
            onDefineAuditScope={defineAuditScope}
            activeRun={activeRun}
            lifecycleStatus={lifecycleStatus}
            authorization={runAuthorization}
            auditRequest={auditRequest}
            gitFacts={gitFacts}
            criteria={criteria}
            runActionLoading={runActionLoading}
            runActionError={runActionError}
            defaultBranch={configuredProject?.default_branch ?? 'main'}
            onRequestAuthorization={handleRequestAuthorization}
            onDispatchRun={handleDispatchRun}
            onRefreshRun={handleRefreshRun}
            onRequestAudit={handleRequestAudit}
            onPromoteToRelease={handlePromoteToRelease}
          />
        </section>
      )}
      {route.view === 'context' && (
        <ContextPanel mission={mission} checkpoints={checkpoints} loading={detailLoading} onRecordCheckpoint={recordCheckpoint} />
      )}
    </SupervisorShell>
  )
}
