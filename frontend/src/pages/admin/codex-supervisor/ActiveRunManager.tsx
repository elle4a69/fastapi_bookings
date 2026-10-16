import { useState } from 'react'
import type { ActiveRunLifecycleStatus, AuditRequest, Brief, RunStartAuthorization, SupervisorRun, WorkPackage } from './types'

export interface ActiveRunManagerProps {
  workPackage: WorkPackage | null
  briefs: Brief[]
  activeRun: SupervisorRun | null
  lifecycleStatus: ActiveRunLifecycleStatus
  authorization: RunStartAuthorization | null
  auditRequest: AuditRequest | null
  loading: boolean
  error: string | null
  onRequestAuthorization: (waiverRequested: boolean) => Promise<void>
  onDispatchRun: () => Promise<void>
  onRefreshRun: () => Promise<void>
  onRequestAudit: () => Promise<void>
}

const LIFECYCLE_STEPS: Array<{ key: ActiveRunLifecycleStatus; label: string; description: string }> = [
  { key: 'grant_requested', label: '1. Grant Requested', description: 'Requesting one-run start authorization' },
  { key: 'authorized', label: '2. Authorized', description: 'Single-use grant issued and bound' },
  { key: 'dispatching', label: '3. Dispatching', description: 'Transmitting intent to runtime' },
  { key: 'running', label: '4. Running', description: 'Worker active and dispatch acknowledged' },
  { key: 'completed', label: '5. Completed', description: 'Run finished and evidence captured' },
]

export function ActiveRunManager({
  workPackage,
  briefs,
  activeRun,
  lifecycleStatus,
  authorization,
  auditRequest,
  loading,
  error,
  onRequestAuthorization,
  onDispatchRun,
  onRefreshRun,
  onRequestAudit,
}: ActiveRunManagerProps) {
  const [modalOpen, setModalOpen] = useState(false)
  const [confirmChecked, setConfirmChecked] = useState(false)
  const [waiverRequested, setWaiverRequested] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const approvedBrief = briefs.find((brief) => brief.state === 'approved') ?? null
  const hasApprovedBrief = Boolean(approvedBrief)
  const allowsWaiver = approvedBrief?.future_execution_authorization_requirement === 'not_required_once_requested'

  const handleOpenModal = () => {
    setConfirmChecked(false)
    setWaiverRequested(Boolean(allowsWaiver))
    setModalOpen(true)
  }

  const handleConfirmAuthorize = async () => {
    if (!confirmChecked) return
    setSubmitting(true)
    try {
      await onRequestAuthorization(waiverRequested)
      setModalOpen(false)
    } finally {
      setSubmitting(false)
    }
  }

  const getStepState = (stepKey: ActiveRunLifecycleStatus) => {
    const order: ActiveRunLifecycleStatus[] = ['grant_requested', 'authorized', 'dispatching', 'running', 'completed']
    const currentIndex = order.indexOf(lifecycleStatus)
    const stepIndex = order.indexOf(stepKey)
    if (lifecycleStatus === 'failed') return stepIndex <= 1 ? 'passed' : 'failed'
    if (lifecycleStatus === 'dispatch_unknown') return stepIndex <= 2 ? 'passed' : 'warning'
    if (lifecycleStatus === 'sandbox_unavailable') return stepIndex <= 3 ? 'passed' : 'warning'
    if (stepIndex < currentIndex) return 'passed'
    if (stepIndex === currentIndex) return 'current'
    return 'pending'
  }

  return (
    <article className="space-y-4 rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <div>
          <h3 className="text-base font-semibold">Active-Run Management</h3>
          <p className="text-xs text-muted-foreground">
            Supervised execution ledger and expiring single-use authorization boundary.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasApprovedBrief && lifecycleStatus === 'idle' && (
            <button
              onClick={handleOpenModal}
              disabled={loading || submitting}
              className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              Request One-Run Authorization
            </button>
          )}
          {lifecycleStatus === 'authorized' && (
            <button
              onClick={() => void onDispatchRun()}
              disabled={loading || submitting}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              Dispatch Run
            </button>
          )}
          {(lifecycleStatus === 'running' || lifecycleStatus === 'dispatch_unknown') && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => void onRefreshRun()}
                disabled={loading}
                className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
              >
                Refresh Run
              </button>
              {auditRequest === null && (
                <button
                  onClick={() => void onRequestAudit()}
                  disabled={loading}
                  className="rounded-md border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 disabled:opacity-50"
                >
                  Request Independent Audit
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
          <p className="font-semibold">Action could not be completed</p>
          <p className="mt-0.5">{error}</p>
        </div>
      )}

      {!hasApprovedBrief && (
        <div className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
          A brief must be approved for this work package before a one-run execution grant can be requested.
        </div>
      )}

      {/* Lifecycle Status Stepper */}
      <section aria-label="Run lifecycle progression" className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Lifecycle State</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {LIFECYCLE_STEPS.map((step) => {
            const state = getStepState(step.key)
            return (
              <div
                key={step.key}
                className={`rounded-lg border p-2.5 text-left transition-colors ${
                  state === 'current'
                    ? 'border-primary bg-primary/10'
                    : state === 'passed'
                      ? 'border-emerald-500/40 bg-emerald-500/5'
                      : state === 'failed'
                        ? 'border-destructive/40 bg-destructive/5'
                        : state === 'warning'
                          ? 'border-amber-500/40 bg-amber-500/5'
                          : 'border-border/60 bg-muted/20 opacity-60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-medium">{step.label}</span>
                  {state === 'passed' && <span className="text-xs text-emerald-600 dark:text-emerald-400">✓</span>}
                  {state === 'current' && <span className="h-1.5 w-1.5 rounded-full bg-primary" />}
                </div>
                <p className="mt-1 text-[10px] text-muted-foreground leading-tight">{step.description}</p>
              </div>
            )
          })}
        </div>
      </section>

      {/* Detailed Status Panels */}
      {lifecycleStatus === 'dispatch_unknown' && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3.5 text-xs text-amber-900 dark:text-amber-200">
          <p className="font-semibold">Dispatch status unknown</p>
          <p className="mt-1">
            External worker launch could not be confirmed over the process boundary. To protect the ledger from double-dispatch,
            do not launch a new run. Retry the request or inspect the run ledger.
          </p>
        </div>
      )}

      {lifecycleStatus === 'sandbox_unavailable' && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3.5 text-xs text-amber-900 dark:text-amber-200">
          <p className="font-semibold">Sandbox unavailable</p>
          <p className="mt-1">
            Host-enforced independent sandbox is not configured or reachable. All audit criteria remain not evaluated;
            no execution verdict or promotion can occur without an attested sandbox.
          </p>
        </div>
      )}

      {authorization && (
        <div className="rounded-lg border bg-muted/40 p-3 text-xs space-y-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-foreground">Authorization Grant:</span>
            <span className="font-mono text-muted-foreground">{authorization.grant_id}</span>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-muted-foreground">Expires at:</span>
            <span className="text-muted-foreground">{new Date(authorization.expires_at).toLocaleTimeString()}</span>
          </div>
          <p className="text-[11px] text-muted-foreground pt-1 border-t">
            Single-use credential held in active session memory; never persisted to disk or logs.
          </p>
        </div>
      )}

      {activeRun && (
        <div className="rounded-lg border bg-muted/40 p-3 text-xs space-y-1.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-foreground">Run ID:</span>
            <span className="font-mono text-muted-foreground">{activeRun.run_id}</span>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-muted-foreground">Worker Profile:</span>
            <span className="text-muted-foreground">{activeRun.capability_profile}</span>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-muted-foreground">Ledger Status:</span>
            <span className="rounded bg-muted px-2 py-0.5 font-mono text-[11px] font-semibold">{activeRun.status}</span>
          </div>
        </div>
      )}

      {/* Authorization Confirmation Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-xl border bg-card p-5 shadow-xl space-y-4">
            <div className="space-y-1 border-b pb-3">
              <h4 className="text-base font-semibold">Request One-Run Authorization</h4>
              <p className="text-xs text-muted-foreground">
                Issue a single-use, hash-bound start credential for approved brief {approvedBrief?.revision}.
              </p>
            </div>

            <div className="space-y-3 text-xs">
              <div className="rounded-lg bg-muted p-3 space-y-1">
                <p className="font-medium">Target Work Package</p>
                <p className="text-muted-foreground">{workPackage?.title ?? 'None selected'}</p>
                <p className="text-[11px] text-muted-foreground">{workPackage?.id}</p>
              </div>

              {allowsWaiver && (
                <label className="flex items-start gap-2.5 rounded-lg border p-3 cursor-pointer hover:bg-muted/30">
                  <input
                    type="checkbox"
                    checked={waiverRequested}
                    onChange={(e) => setWaiverRequested(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                  />
                  <div>
                    <span className="font-medium block">Request Policy Waiver</span>
                    <span className="text-muted-foreground block text-[11px]">
                      The approved brief permits execution authorization to be waived once requested.
                    </span>
                  </div>
                </label>
              )}

              <p className="text-[11px] text-muted-foreground">
                Authorizations expire automatically in 120 seconds. They grant no arbitrary tool execution or prompt injection rights.
              </p>

              <label className="flex items-start gap-2.5 rounded-lg border border-primary/30 bg-primary/5 p-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmChecked}
                  onChange={(e) => setConfirmChecked(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                />
                <span className="font-medium text-foreground">
                  I confirm the issuance of this one-run execution grant.
                </span>
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                disabled={submitting}
                className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmAuthorize()}
                disabled={!confirmChecked || submitting}
                className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {submitting ? 'Issuing…' : 'Issue Authorization'}
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  )
}
