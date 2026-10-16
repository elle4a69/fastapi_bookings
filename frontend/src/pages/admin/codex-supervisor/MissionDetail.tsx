import { EmptyState, SupervisorLoading } from './SupervisorStates'
import { ApproveBriefForm, AuditScopeForm, CreateBriefForm, CreateWorkPackageForm } from './PlanningForms'
import { ActiveRunManager } from './ActiveRunManager'
import { EvidenceAuditCard } from './EvidenceAuditCard'
import type {
  ActiveRunLifecycleStatus,
  AuditRequest,
  AuditScope,
  Brief,
  CriterionResult,
  Mission,
  RunStartAuthorization,
  StructuralGitFacts,
  SupervisorRun,
  WorkPackage,
} from './types'

export interface MissionDetailProps {
  mission: Mission | null
  packages: WorkPackage[]
  selectedWorkPackageId: string | null
  onSelectWorkPackage: (id: string) => void
  briefs: Brief[]
  auditScope: AuditScope | null
  loading: boolean
  selectedWorkPackage: WorkPackage | null
  onCreateWorkPackage: (fields: Record<string, string>) => Promise<void>
  onCreateBrief: (fields: Record<string, string>) => Promise<void>
  onApproveBrief: (brief: Brief, fields: Record<string, string>) => Promise<void>
  onDefineAuditScope: (fields: Record<string, string>) => Promise<void>
  // Active-Run & Evidence props
  activeRun?: SupervisorRun | null
  lifecycleStatus?: ActiveRunLifecycleStatus
  authorization?: RunStartAuthorization | null
  auditRequest?: AuditRequest | null
  gitFacts?: StructuralGitFacts | null
  criteria?: CriterionResult[]
  runActionLoading?: boolean
  runActionError?: string | null
  defaultBranch?: string
  onRequestAuthorization?: (waiverRequested: boolean) => Promise<void>
  onDispatchRun?: () => Promise<void>
  onRefreshRun?: () => Promise<void>
  onRequestAudit?: () => Promise<void>
  onPromoteToRelease?: () => Promise<void>
}

export function MissionDetail({
  mission,
  packages,
  selectedWorkPackageId,
  onSelectWorkPackage,
  briefs,
  auditScope,
  loading,
  selectedWorkPackage,
  onCreateWorkPackage,
  onCreateBrief,
  onApproveBrief,
  onDefineAuditScope,
  activeRun = null,
  lifecycleStatus = 'idle',
  authorization = null,
  auditRequest = null,
  gitFacts = null,
  criteria = [],
  runActionLoading = false,
  runActionError = null,
  defaultBranch = 'main',
  onRequestAuthorization = async () => {},
  onDispatchRun = async () => {},
  onRefreshRun = async () => {},
  onRequestAudit = async () => {},
  onPromoteToRelease = async () => {},
}: MissionDetailProps) {
  if (loading) return <SupervisorLoading />
  if (!mission) return <EmptyState title="Select a mission" detail="Choose a mission to read its live work packages, briefs, and audit scope." />

  return (
    <section className="space-y-4">
      <article className="rounded-xl border bg-card p-4">
        <h2 className="text-lg font-semibold">{mission.title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{mission.summary}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          {mission.id} · {mission.state}
        </p>
      </article>

      <CreateWorkPackageForm mission={mission} onSubmit={onCreateWorkPackage} />

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-xl border bg-card">
          <h3 className="border-b p-4 font-semibold">Work packages</h3>
          {packages.length ? (
            <ul className="divide-y">
              {packages.map((item) => (
                <li key={item.id}>
                  <button
                    onClick={() => onSelectWorkPackage(item.id)}
                    className={
                      selectedWorkPackageId === item.id
                        ? 'w-full bg-muted p-4 text-left'
                        : 'w-full p-4 text-left hover:bg-muted/60'
                    }
                  >
                    <span className="block font-medium">{item.title}</span>
                    <span className="block text-sm text-muted-foreground">{item.scope}</span>
                    <span className="block text-xs text-muted-foreground">{item.state}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-4 text-sm text-muted-foreground">No work packages returned.</p>
          )}
        </article>

        <article className="space-y-4">
          <CreateBriefForm workPackage={selectedWorkPackage} onSubmit={onCreateBrief} />

          <section className="rounded-xl border bg-card">
            <h3 className="border-b p-4 font-semibold">Briefs</h3>
            {briefs.length ? (
              <ul className="divide-y">
                {briefs.map((brief) => (
                  <li className="space-y-3 p-4" key={brief.id}>
                    <p className="text-xs text-muted-foreground">
                      Revision {brief.revision} · {brief.state}
                    </p>
                    <p className="whitespace-pre-wrap text-sm">{brief.content}</p>
                    <p className="rounded bg-muted p-2 text-xs">
                      Future execution authorization:{' '}
                      {brief.future_execution_authorization_requirement === 'not_required_once_requested'
                        ? 'Brief policy permits a requestable one-run waiver.'
                        : 'Authorization will still be required for any future run.'}
                    </p>
                    <ApproveBriefForm brief={brief} onSubmit={(fields) => onApproveBrief(brief, fields)} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-4 text-sm text-muted-foreground">Select a work package to load briefs.</p>
            )}
          </section>

          <section className="space-y-3 rounded-xl border bg-card p-4">
            <h3 className="font-semibold">Audit scope</h3>
            {auditScope ? (
              <>
                <p className="text-sm">Criteria: {auditScope.criteria}</p>
                <p className="text-sm">Exclusions: {auditScope.exclusions}</p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                No audit scope returned. Define audit scope before requesting execution contracts.
              </p>
            )}
            <AuditScopeForm
              workPackage={selectedWorkPackage}
              hasApprovedBrief={briefs.some((brief) => brief.state === 'approved')}
              onSubmit={onDefineAuditScope}
            />
          </section>
        </article>
      </section>

      {/* Active-Run Management & Evidence Matrix (rendered when a work package is selected) */}
      {selectedWorkPackage && (
        <section className="grid gap-4 lg:grid-cols-2">
          <ActiveRunManager
            workPackage={selectedWorkPackage}
            briefs={briefs}
            activeRun={activeRun}
            lifecycleStatus={lifecycleStatus}
            authorization={authorization}
            auditRequest={auditRequest}
            loading={runActionLoading}
            error={runActionError}
            onRequestAuthorization={onRequestAuthorization}
            onDispatchRun={onDispatchRun}
            onRefreshRun={onRefreshRun}
            onRequestAudit={onRequestAudit}
          />
          <EvidenceAuditCard
            workPackageTitle={selectedWorkPackage.title}
            defaultBranch={defaultBranch}
            gitFacts={gitFacts}
            criteria={criteria}
            isPromoting={runActionLoading}
            onPromoteToRelease={onPromoteToRelease}
          />
        </section>
      )}
    </section>
  )
}
