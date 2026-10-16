import { useState, useMemo } from 'react'
import {
  Globe,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  History,
  Undo2,
  Check,
  Send,
  Eye,
  ShieldCheck,
  Lock,
} from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  computeWebsiteDiff,
  isProposalStale,
  type ProposalDiffResult,
} from './proposal-diff'
import type { WebsiteConfigData } from '@/pages/public/website-page'

export interface ProposalDetail {
  id?: number
  version?: number
  expected_version?: number | null
  title: string
  content_payload?: Record<string, unknown>
  config?: WebsiteConfigData
  status?: string
  created_at?: string
  published_at?: string | null
  rollback_version?: number | null
}

export interface WebsiteRevisionItem {
  id: number
  version: number
  title: string
  status: string
  created_at?: string | null
  published_at?: string | null
  rollback_version?: number | null
}

export interface ProposalReviewDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  proposal: ProposalDetail | null
  currentConfig: WebsiteConfigData
  currentVersion?: number
  hasUnsavedChanges?: boolean
  isOwner: boolean
  onApplyDraft: (proposedConfig: WebsiteConfigData) => void
  onApproveAndPublish: (proposal: ProposalDetail) => Promise<void>
  onResyncProposal?: (proposal: ProposalDetail) => Promise<void>
  onRollback?: (targetVersion: number) => Promise<void>
  revisionsHistory?: WebsiteRevisionItem[]
}

export function ProposalReviewDrawer({
  open,
  onOpenChange,
  proposal,
  currentConfig,
  currentVersion,
  hasUnsavedChanges = false,
  isOwner,
  onApplyDraft,
  onApproveAndPublish,
  onResyncProposal,
  onRollback,
  revisionsHistory = [],
}: ProposalReviewDrawerProps) {
  const [activeTab, setActiveTab] = useState<'diff' | 'history'>('diff')
  const [selectedSectionFilter, setSelectedSectionFilter] = useState<string>('all')
  const [publishing, setPublishing] = useState<boolean>(false)
  const [resyncing, setResyncing] = useState<boolean>(false)
  const [rollingBackVersion, setRollingBackVersion] = useState<number | null>(null)

  // Compute proposed config: either directly provided or merged from payload
  const proposedPayload: Record<string, unknown> = useMemo(() => {
    if (!proposal) return {}
    if (proposal.config) return proposal.config as unknown as Record<string, unknown>
    if (proposal.content_payload) {
      if (proposal.content_payload.sections_data) {
        return proposal.content_payload
      }
      return proposal.content_payload
    }
    return {}
  }, [proposal])

  // Compute visual before / after diff
  const diffResult: ProposalDiffResult = useMemo(() => {
    if (!proposal) {
      return {
        hasAnyChanges: false,
        totalChangesCount: 0,
        sectionDiffs: [],
        changedSectionKeys: [],
      }
    }
    return computeWebsiteDiff(
      currentConfig as unknown as Record<string, unknown>,
      proposedPayload,
    )
  }, [currentConfig, proposedPayload, proposal])

  // Invalidate stale proposals
  const stale = useMemo(() => {
    if (!proposal) return false
    return isProposalStale(
      {
        version: proposal.version,
        expected_version: proposal.expected_version,
        created_at: proposal.created_at,
      },
      {
        version: currentVersion,
        hasUnsavedChanges,
      },
    )
  }, [proposal, currentVersion, hasUnsavedChanges])

  const handleApplyToDraft = () => {
    if (!proposal) return
    const targetConfig = (proposal.config || currentConfig) as WebsiteConfigData

    // Merge proposed changes into a complete WebsiteConfigData
    const mergedConfig: WebsiteConfigData = {
      ...currentConfig,
      ...(proposedPayload.template_id ? { template_id: proposedPayload.template_id as string } : {}),
      ...(proposedPayload.theme_id ? { theme_id: proposedPayload.theme_id as string } : {}),
      sections_data: {
        ...currentConfig.sections_data,
        ...((proposedPayload.sections_data as Record<string, any>) || {}),
        ...((proposedPayload.content_payload as Record<string, any>)?.sections_data || {}),
      },
    }

    onApplyDraft(mergedConfig || targetConfig)
    onOpenChange(false)
  }

  const handleApprovePublish = async () => {
    if (!proposal || !isOwner || stale || publishing) return
    try {
      setPublishing(true)
      await onApproveAndPublish(proposal)
      onOpenChange(false)
    } finally {
      setPublishing(false)
    }
  }

  const handleResync = async () => {
    if (!proposal || !onResyncProposal || resyncing) return
    try {
      setResyncing(true)
      await onResyncProposal(proposal)
    } finally {
      setResyncing(false)
    }
  }

  const handleRollbackClick = async (version: number) => {
    if (!onRollback || rollingBackVersion !== null) return
    try {
      setRollingBackVersion(version)
      await onRollback(version)
    } finally {
      setRollingBackVersion(null)
    }
  }

  if (!proposal) {
    return null
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-2xl md:max-w-3xl flex flex-col p-0 bg-white"
        showCloseButton={true}
      >
        {/* ── HEADER ────────────────────────────────────────────── */}
        <SheetHeader className="p-6 border-b bg-slate-50/80">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <SheetTitle className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-violet-600" />
                  {proposal.title || 'Website Edit Proposal'}
                </SheetTitle>
              </div>
              <SheetDescription className="text-xs text-slate-500">
                Detailed Before / After diff review before updating draft or publishing live.
              </SheetDescription>
            </div>

            <div className="flex items-center gap-2">
              {proposal.id && (
                <Badge variant="outline" className="text-xs font-mono">
                  #{proposal.id}
                </Badge>
              )}
              {proposal.version && (
                <Badge variant="outline" className="text-xs font-semibold">
                  v{proposal.version}
                </Badge>
              )}
              {stale ? (
                <Badge
                  variant="destructive"
                  className="bg-amber-600 hover:bg-amber-600 text-white flex items-center gap-1 text-xs"
                >
                  <AlertTriangle className="h-3 w-3" />
                  Stale Proposal
                </Badge>
              ) : proposal.status === 'published' ? (
                <Badge className="bg-emerald-600 text-white flex items-center gap-1 text-xs">
                  <Check className="h-3 w-3" /> Published
                </Badge>
              ) : (
                <Badge
                  variant="secondary"
                  className="bg-sky-50 text-sky-700 border-sky-200 text-xs"
                >
                  Pending Owner Review
                </Badge>
              )}
            </div>
          </div>

          {/* Stale Warning Banner */}
          {stale && (
            <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50/90 p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-start gap-2.5">
                <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                <div className="text-xs text-amber-900">
                  <p className="font-semibold">Website state has advanced since proposal creation</p>
                  <p className="text-amber-800">
                    The active draft (v{currentVersion ?? 'draft'}) has newer edits or unsaved changes.
                    Direct publication is blocked to prevent accidental overwrites.
                  </p>
                </div>
              </div>
              {onResyncProposal && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleResync}
                  disabled={resyncing}
                  className="border-amber-300 bg-white text-amber-900 hover:bg-amber-100 text-xs shrink-0 self-start sm:self-auto"
                >
                  <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${resyncing ? 'animate-spin' : ''}`} />
                  {resyncing ? 'Re-syncing...' : 'Re-sync with Current'}
                </Button>
              )}
            </div>
          )}
        </SheetHeader>

        {/* ── TABS (DIFF vs REVISION HISTORY) ────────────────────── */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'diff' | 'history')}>
            <div className="flex items-center justify-between border-b pb-3 mb-4">
              <TabsList className="bg-slate-100 p-1 rounded-lg">
                <TabsTrigger value="diff" className="text-xs px-3 py-1.5 flex items-center gap-1.5">
                  <Eye className="h-3.5 w-3.5" />
                  Proposed Diff ({diffResult.totalChangesCount})
                </TabsTrigger>
                <TabsTrigger value="history" className="text-xs px-3 py-1.5 flex items-center gap-1.5">
                  <History className="h-3.5 w-3.5" />
                  Revisions & Rollback ({revisionsHistory.length})
                </TabsTrigger>
              </TabsList>

              {activeTab === 'diff' && diffResult.changedSectionKeys.length > 1 && (
                <div className="flex items-center gap-1.5 overflow-x-auto text-xs">
                  <Button
                    variant={selectedSectionFilter === 'all' ? 'default' : 'ghost'}
                    size="sm"
                    className="h-7 px-2.5 text-xs"
                    onClick={() => setSelectedSectionFilter('all')}
                  >
                    All
                  </Button>
                  {diffResult.changedSectionKeys.map((sec) => (
                    <Button
                      key={sec}
                      variant={selectedSectionFilter === sec ? 'default' : 'ghost'}
                      size="sm"
                      className="h-7 px-2.5 text-xs capitalize"
                      onClick={() => setSelectedSectionFilter(sec)}
                    >
                      {sec}
                    </Button>
                  ))}
                </div>
              )}
            </div>

            {/* TAB 1: VISUAL BEFORE / AFTER DIFF */}
            <TabsContent value="diff" className="space-y-6 mt-0">
              {!diffResult.hasAnyChanges ? (
                <div className="py-12 text-center text-slate-500 space-y-2">
                  <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto" />
                  <p className="text-sm font-medium">No differences detected</p>
                  <p className="text-xs text-slate-400">
                    The proposed payload matches the current website configuration.
                  </p>
                </div>
              ) : (
                diffResult.sectionDiffs
                  .filter(
                    (sec) =>
                      selectedSectionFilter === 'all' ||
                      sec.sectionKey === selectedSectionFilter,
                  )
                  .map((secDiff) => (
                    <div
                      key={secDiff.sectionKey}
                      className="rounded-xl border border-slate-200 overflow-hidden bg-white shadow-xs"
                    >
                      {/* Section Card Header */}
                      <div className="bg-slate-50 px-4 py-2.5 border-b flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Globe className="h-4 w-4 text-primary" />
                          <h3 className="text-xs sm:text-sm font-semibold text-slate-800">
                            {secDiff.sectionTitle}
                          </h3>
                        </div>
                        <Badge variant="outline" className="text-[11px] font-mono text-slate-500">
                          {secDiff.changes.length} change{secDiff.changes.length > 1 ? 's' : ''}
                        </Badge>
                      </div>

                      {/* Section Field Diffs */}
                      <div className="divide-y divide-slate-100">
                        {secDiff.changes.map((fieldChange) => (
                          <div key={fieldChange.fieldKey} className="p-4 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-semibold text-slate-700">
                                {fieldChange.fieldLabel}
                              </span>
                              <Badge
                                variant="outline"
                                className={`text-[10px] font-medium uppercase tracking-wider ${
                                  fieldChange.changeType === 'added'
                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                    : fieldChange.changeType === 'removed'
                                      ? 'bg-rose-50 text-rose-700 border-rose-200'
                                      : 'bg-sky-50 text-sky-700 border-sky-200'
                                }`}
                              >
                                {fieldChange.changeType}
                              </Badge>
                            </div>

                            {/* Split Before / After Cards */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                              {/* Before Card */}
                              <div className="rounded-lg border border-rose-200/80 bg-rose-50/40 p-3 space-y-1">
                                <span className="text-[10px] font-bold text-rose-700 tracking-wider uppercase block">
                                  Current / Before
                                </span>
                                <DiffValueRenderer value={fieldChange.before} />
                              </div>

                              {/* After Card */}
                              <div className="rounded-lg border border-emerald-200/80 bg-emerald-50/40 p-3 space-y-1">
                                <span className="text-[10px] font-bold text-emerald-700 tracking-wider uppercase block">
                                  Proposed / After
                                </span>
                                <DiffValueRenderer value={fieldChange.after} />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
              )}
            </TabsContent>

            {/* TAB 2: REVISION HISTORY & ROLLBACK */}
            <TabsContent value="history" className="space-y-4 mt-0">
              <div className="rounded-lg border bg-slate-50 p-3 text-xs text-slate-600">
                <p className="font-semibold text-slate-800">Website Revision Snapshots</p>
                <p>
                  Revert your website draft or live content to an earlier snapshot. Only authenticated
                  owners may initiate rollbacks.
                </p>
              </div>

              {revisionsHistory.length === 0 ? (
                <div className="py-8 text-center text-slate-400 text-xs">
                  No previous revisions recorded.
                </div>
              ) : (
                <div className="space-y-3">
                  {revisionsHistory.map((rev) => (
                    <div
                      key={rev.id}
                      className="rounded-lg border p-3.5 bg-white flex flex-wrap items-center justify-between gap-3 shadow-xs"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-900">
                            Version {rev.version}
                          </span>
                          <span className="text-xs text-slate-600">— {rev.title}</span>
                          {rev.status === 'published' && (
                            <Badge className="bg-emerald-600 text-[10px] h-4 px-1.5">Live</Badge>
                          )}
                          {rev.rollback_version && (
                            <Badge variant="outline" className="text-[10px] text-amber-700 h-4 px-1.5">
                              Reverted to v{rev.rollback_version}
                            </Badge>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {rev.published_at
                            ? `Published: ${new Date(rev.published_at).toLocaleString()}`
                            : rev.created_at
                              ? `Created: ${new Date(rev.created_at).toLocaleString()}`
                              : 'Snapshot'}
                        </div>
                      </div>

                      {isOwner && onRollback && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRollbackClick(rev.version)}
                          disabled={rollingBackVersion !== null || rev.version === currentVersion}
                          className="h-8 text-xs flex items-center gap-1.5 border-slate-300 hover:bg-slate-50"
                        >
                          <Undo2 className="h-3.5 w-3.5" />
                          {rollingBackVersion === rev.version
                            ? 'Reverting...'
                            : rev.version === currentVersion
                              ? 'Active Version'
                              : `Rollback to v${rev.version}`}
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>

        {/* ── FOOTER & PUBLICATION GATE ─────────────────────────── */}
        <SheetFooter className="p-4 sm:p-6 border-t bg-slate-50 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-500 self-start sm:self-auto">
            {isOwner ? (
              <span className="flex items-center gap-1.5 text-emerald-700 font-medium">
                <ShieldCheck className="h-4 w-4" /> Owner Publication Gate Active
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-amber-700 font-medium">
                <Lock className="h-4 w-4" /> Owner Approval Required to Publish
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
              Discard
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleApplyToDraft}
              className="text-xs"
              title="Apply these changes only to the private draft without publishing live"
            >
              Apply to Draft
            </Button>

            {/* Strict Owner Publication Gate Button */}
            <Button
              size="sm"
              onClick={handleApprovePublish}
              disabled={!isOwner || stale || publishing}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-sm"
              title={
                !isOwner
                  ? 'Only business owners can publish changes to the live site.'
                  : stale
                    ? 'Cannot publish a stale proposal. Please re-sync first.'
                    : 'Manually approve and publish changes live'
              }
            >
              <Send className="h-3.5 w-3.5" />
              {publishing ? 'Publishing...' : 'Approve & Publish Live'}
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

function DiffValueRenderer({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === '') {
    return <span className="text-slate-400 italic">[Empty]</span>
  }

  if (typeof value === 'boolean') {
    return <span className="font-semibold">{value ? 'Yes (Enabled)' : 'No (Disabled)'}</span>
  }

  if (typeof value === 'string' && (value.startsWith('http://') || value.startsWith('https://'))) {
    return (
      <div className="space-y-1">
        <a
          href={value}
          target="_blank"
          rel="noreferrer"
          className="text-primary underline break-all text-[11px]"
        >
          {value}
        </a>
        {/\.(png|jpe?g|webp|gif|svg)$/i.test(value) && (
          <img
            src={value}
            alt="Preview"
            className="h-16 w-auto rounded border object-cover mt-1"
          />
        )}
      </div>
    )
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-slate-400 italic">[Empty list]</span>
    }
    return (
      <ul className="list-disc pl-4 space-y-0.5 text-slate-800">
        {value.map((item, idx) => (
          <li key={idx} className="break-words">
            {typeof item === 'object' && item !== null
              ? JSON.stringify(item)
              : String(item)}
          </li>
        ))}
      </ul>
    )
  }

  if (typeof value === 'object') {
    return (
      <pre className="text-[11px] font-mono bg-white/70 p-1.5 rounded overflow-x-auto text-slate-700">
        {JSON.stringify(value, null, 2)}
      </pre>
    )
  }

  return <span className="text-slate-800 break-words whitespace-pre-wrap">{String(value)}</span>
}
