import React, { useState } from 'react'
import {
  ShieldAlert,
  AlertTriangle,
  Check,
  X,
  CornerDownRight,
  Terminal,
  FileCode,
  Send
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ApprovalGate } from '../../types'

export interface ApprovalGateCardProps {
  gate?: ApprovalGate
  title?: string
  operation?: string
  description?: string
  riskLevel?: 'low' | 'medium' | 'high' | 'critical'
  command?: string
  filePath?: string
  status?: 'pending' | 'approved' | 'rejected'
  onApprove?: (gateId: string) => void
  onReject?: (gateId: string, steerFeedback?: string) => void
  className?: string
}

export const ApprovalGateCard: React.FC<ApprovalGateCardProps> = ({
  gate,
  title: propTitle,
  operation: propOperation,
  description: propDescription,
  riskLevel: propRiskLevel = 'high',
  command: propCommand,
  filePath: propFilePath,
  status: propStatus = 'pending',
  onApprove,
  onReject,
  className,
}) => {
  const gateId = gate?.id ?? 'gate-unknown'
  const title = gate?.title ?? propTitle ?? 'Approval Required'
  const operation = gate?.operation ?? propOperation ?? 'Executing high-impact operation'
  const description = gate?.description ?? propDescription
  const riskLevel = gate?.riskLevel ?? propRiskLevel
  const command = gate?.command ?? propCommand
  const filePath = gate?.filePath ?? propFilePath

  const [currentStatus, setCurrentStatus] = useState<'pending' | 'approved' | 'rejected'>(
    gate?.status ?? propStatus
  )
  const [showSteerInput, setShowSteerInput] = useState(false)
  const [steerFeedback, setSteerFeedback] = useState('')

  const handleApprove = () => {
    setCurrentStatus('approved')
    onApprove?.(gateId)
  }

  const handleRejectConfirm = () => {
    setCurrentStatus('rejected')
    onReject?.(gateId, steerFeedback.trim() || undefined)
  }

  const getRiskBadge = () => {
    switch (riskLevel) {
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <AlertTriangle className="w-3 h-3" />
            Critical Risk
          </span>
        )
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-3 h-3" />
            High Risk
          </span>
        )
      case 'medium':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
            Medium
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted text-muted-foreground">
            Standard
          </span>
        )
    }
  }

  return (
    <div
      className={cn(
        'rounded-xl border-2 p-4 shadow-md transition-all backdrop-blur-xs',
        currentStatus === 'pending' &&
          (riskLevel === 'critical'
            ? 'border-rose-500/60 bg-linear-to-b from-rose-950/20 via-background to-rose-950/10'
            : 'border-amber-500/60 bg-linear-to-b from-amber-950/20 via-background to-amber-950/10'),
        currentStatus === 'approved' &&
          'border-emerald-500/50 bg-emerald-950/10 opacity-90',
        currentStatus === 'rejected' &&
          'border-rose-500/40 bg-muted/20 opacity-80',
        className
      )}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="flex items-center gap-2.5">
          <div
            className={cn(
              'p-2 rounded-lg shrink-0',
              currentStatus === 'approved'
                ? 'bg-emerald-500/20 text-emerald-400'
                : currentStatus === 'rejected'
                ? 'bg-rose-500/20 text-rose-400'
                : riskLevel === 'critical'
                ? 'bg-rose-500/20 text-rose-400 animate-pulse'
                : 'bg-amber-500/20 text-amber-400 animate-pulse'
            )}
          >
            <ShieldAlert className="w-5 h-5" />
          </div>

          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="text-sm font-semibold tracking-tight text-foreground">
                {title}
              </h4>
              {getRiskBadge()}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">{operation}</p>
          </div>
        </div>

        {currentStatus !== 'pending' && (
          <div className="sm:self-center">
            <span
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border',
                currentStatus === 'approved'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
              )}
            >
              {currentStatus === 'approved' ? (
                <>
                  <Check className="w-3.5 h-3.5" /> Approved & Applied
                </>
              ) : (
                <>
                  <X className="w-3.5 h-3.5" /> Rejected
                </>
              )}
            </span>
          </div>
        )}
      </div>

      {description && (
        <p className="mt-3 text-xs text-foreground/80 leading-relaxed pl-1">
          {description}
        </p>
      )}

      {/* Target File or Command Preview */}
      {(command || filePath) && (
        <div className="mt-3 rounded-lg border border-border/80 bg-zinc-950 p-2.5 font-mono text-xs text-zinc-200">
          {filePath && (
            <div className="flex items-center gap-1.5 text-zinc-400 mb-1.5 text-[11px]">
              <FileCode className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="text-zinc-500">Target File:</span>
              <span className="text-zinc-200 truncate">{filePath}</span>
            </div>
          )}

          {command && (
            <div className="flex items-start gap-2 text-[11px] text-zinc-300">
              <Terminal className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
              <code className="text-zinc-100 break-all select-all">{command}</code>
            </div>
          )}
        </div>
      )}

      {/* Steer/Reject Input Drawer */}
      {currentStatus === 'pending' && showSteerInput && (
        <div className="mt-3 pt-3 border-t border-border/60 space-y-2">
          <label className="block text-xs font-medium text-foreground">
            Provide feedback or redirection instructions:
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={steerFeedback}
              onChange={(e) => setSteerFeedback(e.target.value)}
              placeholder="e.g. Do not touch that table, use the synthetic test harness instead..."
              className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-border bg-background focus:outline-hidden focus:ring-1 focus:ring-ring text-foreground"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRejectConfirm()
              }}
            />
            <button
              type="button"
              onClick={handleRejectConfirm}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-600 hover:bg-rose-500 text-white cursor-pointer active:scale-95 transition-all"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Submit Rejection</span>
            </button>
            <button
              type="button"
              onClick={() => setShowSteerInput(false)}
              className="px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground rounded-lg"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Decision Buttons (Touch Friendly) */}
      {currentStatus === 'pending' && !showSteerInput && (
        <div className="mt-4 pt-3 border-t border-border/40 flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={() => setShowSteerInput(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold text-rose-300 bg-rose-950/40 border border-rose-800/60 hover:bg-rose-900/60 active:scale-98 transition-all cursor-pointer"
          >
            <CornerDownRight className="w-4 h-4" />
            <span>[ Steer / Reject ]</span>
          </button>

          <button
            type="button"
            onClick={handleApprove}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-xs font-semibold text-white bg-linear-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 active:scale-98 transition-all shadow-sm cursor-pointer"
          >
            <Check className="w-4 h-4" />
            <span>[ Approve & Apply ]</span>
          </button>
        </div>
      )}
    </div>
  )
}
export default ApprovalGateCard
