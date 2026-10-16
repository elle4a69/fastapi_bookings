import { useState } from 'react'
import type { CriterionResult, StructuralGitFacts } from './types'

export interface EvidenceAuditCardProps {
  workPackageTitle?: string
  defaultBranch?: string
  gitFacts?: StructuralGitFacts | null
  criteria?: CriterionResult[]
  isPromoting?: boolean
  onPromoteToRelease?: () => Promise<void>
}

const DEFAULT_CRITERIA: CriterionResult[] = [
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

export function EvidenceAuditCard({
  workPackageTitle = 'Selected Work Package',
  defaultBranch = 'main',
  gitFacts,
  criteria = DEFAULT_CRITERIA,
  isPromoting = false,
  onPromoteToRelease,
}: EvidenceAuditCardProps) {
  const [promoteModalOpen, setPromoteModalOpen] = useState(false)
  const [confirmBranch, setConfirmBranch] = useState(false)

  const activeCriteria = criteria.length > 0 ? criteria : DEFAULT_CRITERIA

  // All criteria must have outcome === 'passed' for promotion to be enabled
  const allCriteriaPassed =
    activeCriteria.length > 0 && activeCriteria.every((criterion) => criterion.outcome === 'passed')

  const anyFailed = activeCriteria.some((criterion) => criterion.outcome === 'failed')

  const handlePromoteConfirm = async () => {
    if (!allCriteriaPassed || !confirmBranch || !onPromoteToRelease) return
    await onPromoteToRelease()
    setPromoteModalOpen(false)
  }

  return (
    <article className="space-y-4 rounded-xl border bg-card p-5 shadow-sm" aria-label="Evidence and Audit Matrix">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <div>
          <h3 className="text-base font-semibold">Structural Evidence & Audit Matrix</h3>
          <p className="text-xs text-muted-foreground">
            Fail-closed validation: Git tree integrity, sandbox attestation, and test evidence.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPromoteModalOpen(true)}
            disabled={!allCriteriaPassed || isPromoting}
            title={
              allCriteriaPassed
                ? `Promote verified changes to release branch (${defaultBranch})`
                : 'All criteria must pass before release promotion can be unlocked'
            }
            className={`rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors ${
              allCriteriaPassed
                ? 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm cursor-pointer'
                : 'border border-border bg-muted text-muted-foreground opacity-50 cursor-not-allowed'
            }`}
          >
            {isPromoting ? 'Promoting…' : 'Promote to Release Branch'}
          </button>
        </div>
      </div>

      {/* Structural Git Facts Grid */}
      <section aria-label="Structural Git facts" className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Structural Git Facts</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border bg-muted/30 p-3">
            <span className="block text-[11px] text-muted-foreground">Baseline Tree SHA</span>
            <span className="mt-1 block font-mono text-xs font-semibold text-foreground truncate">
              {gitFacts?.baseline_tree_sha ? gitFacts.baseline_tree_sha.slice(0, 12) : 'Awaiting baseline'}
            </span>
          </div>

          <div className="rounded-lg border bg-muted/30 p-3">
            <span className="block text-[11px] text-muted-foreground">Submitted Tree SHA</span>
            <span className="mt-1 block font-mono text-xs font-semibold text-foreground truncate">
              {gitFacts?.submitted_tree_sha ? gitFacts.submitted_tree_sha.slice(0, 12) : 'Pending submission'}
            </span>
          </div>

          <div className="rounded-lg border bg-muted/30 p-3">
            <span className="block text-[11px] text-muted-foreground">Changed Files</span>
            <span className="mt-1 block font-mono text-xs font-semibold text-foreground">
              {gitFacts?.changed_files_count !== undefined && gitFacts?.changed_files_count !== null
                ? `${gitFacts.changed_files_count} files`
                : '0 files'}
            </span>
          </div>

          <div className="rounded-lg border bg-muted/30 p-3">
            <span className="block text-[11px] text-muted-foreground">Line Changes</span>
            <span className="mt-1 block font-mono text-xs font-semibold">
              <span className="text-emerald-600 dark:text-emerald-400">
                +{gitFacts?.insertions ?? 0}
              </span>{' '}
              /{' '}
              <span className="text-rose-600 dark:text-rose-400">
                -{gitFacts?.deletions ?? 0}
              </span>
            </span>
          </div>
        </div>
      </section>

      {/* Test Evidence & Criteria Matrix Table */}
      <section aria-label="Criteria matrix" className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Test Evidence & Criteria Matrix
          </p>
          <span className="text-[11px] text-muted-foreground">
            {activeCriteria.filter((c) => c.outcome === 'passed').length} / {activeCriteria.length} criteria passed
          </span>
        </div>

        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/60 text-muted-foreground">
              <tr>
                <th className="px-3 py-2.5 font-medium">Criterion</th>
                <th className="px-3 py-2.5 font-medium hidden sm:table-cell">Description</th>
                <th className="px-3 py-2.5 font-medium">Status</th>
                <th className="px-3 py-2.5 font-medium hidden md:table-cell">Evidence Digest</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {activeCriteria.map((criterion) => (
                <tr key={criterion.criterion_code} className="hover:bg-muted/20">
                  <td className="px-3 py-2.5 font-medium text-foreground">
                    <div>{criterion.title}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">{criterion.criterion_code}</div>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground hidden sm:table-cell max-w-xs">
                    {criterion.description}
                  </td>
                  <td className="px-3 py-2.5">
                    {criterion.outcome === 'passed' && (
                      <span className="inline-flex items-center rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800 dark:text-emerald-300">
                        Passed
                      </span>
                    )}
                    {criterion.outcome === 'failed' && (
                      <span className="inline-flex items-center rounded-full border border-rose-500/40 bg-rose-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-rose-800 dark:text-rose-300">
                        Failed
                      </span>
                    )}
                    {criterion.outcome === 'not_evaluated' && (
                      <span className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800 dark:text-amber-300">
                        Not Evaluated
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[11px] text-muted-foreground hidden md:table-cell">
                    {criterion.evidence_digest ? (
                      <span title={criterion.evidence_digest}>{criterion.evidence_digest.slice(0, 16)}…</span>
                    ) : (
                      <span className="opacity-50">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Promotion Lock Status Banner */}
      {!allCriteriaPassed && (
        <div className="rounded-lg border border-border/80 bg-muted/40 p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Release promotion gate is locked</p>
          <p className="mt-0.5">
            {anyFailed
              ? 'One or more audit criteria failed. All failures must be resolved before changes can be promoted to release.'
              : 'All criteria (baseline integrity, attested execution sandbox, and verified tests) must pass before promoting changes.'}
          </p>
        </div>
      )}

      {/* Confirmation Modal for Promotion */}
      {promoteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-xl border bg-card p-5 shadow-xl space-y-4">
            <div className="space-y-1 border-b pb-3">
              <h4 className="text-base font-semibold">Promote to Release Branch</h4>
              <p className="text-xs text-muted-foreground">
                All structural evidence and audit criteria verified. Promote work package to release.
              </p>
            </div>

            <div className="space-y-3 text-xs">
              <div className="rounded-lg bg-muted p-3 space-y-1">
                <p className="font-medium">Target Branch: {defaultBranch}</p>
                <p className="text-muted-foreground">Work Package: {workPackageTitle}</p>
                <p className="text-emerald-600 dark:text-emerald-400 font-medium">✓ 4 of 4 criteria verified</p>
              </div>

              <label className="flex items-start gap-2.5 rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmBranch}
                  onChange={(e) => setConfirmBranch(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-border text-emerald-600 focus:ring-emerald-500"
                />
                <span className="font-medium text-foreground">
                  I confirm release branch promotion for this verified work package.
                </span>
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t">
              <button
                type="button"
                onClick={() => setPromoteModalOpen(false)}
                disabled={isPromoting}
                className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handlePromoteConfirm()}
                disabled={!confirmBranch || isPromoting}
                className="rounded-md bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {isPromoting ? 'Promoting…' : 'Confirm Promotion'}
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  )
}
