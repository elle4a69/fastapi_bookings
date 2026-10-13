import React, { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/lib/api'
import { toast } from 'sonner'
import { CodexWorkbenchTab } from './CodexWorkbenchTab'
import { useWorkbenchStore } from './workbench/store/useWorkbenchStore'
import type { AgentStatusData } from './types'

interface CodingCockpitPageProps {
  initialTab?: string
}

export const CodingCockpitPage: React.FC<CodingCockpitPageProps> = ({ initialTab }) => {
  const [searchParams] = useSearchParams()
  const { setActiveToolModal } = useWorkbenchStore()

  const [statusData, setStatusData] = useState<AgentStatusData | null>(null)
  const [loadingStatus, setLoadingStatus] = useState<boolean>(false)
  const targetThreadId = searchParams.get('thread') || undefined

  // Fetch System Status Baseline
  const fetchStatus = useCallback(async () => {
    try {
      setLoadingStatus(true)
      const res = await apiClient.get<AgentStatusData>('/api/admin/resident-agent/status')
      const data = (res as any)?.data ?? res
      setStatusData(data)
    } catch (err: any) {
      toast.error('Failed to load system baseline status: ' + (err.message || 'Unknown error'))
    } finally {
      setLoadingStatus(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  // Map incoming URL tab parameter (e.g. ?tab=issues or ?tab=health) to full-screen tool modals
  useEffect(() => {
    const tabParam = searchParams.get('tab') || initialTab
    if (tabParam && ['health', 'fuzzer', 'issues', 'skills', 'stream'].includes(tabParam)) {
      setActiveToolModal(tabParam as any)
    }
  }, [searchParams, initialTab, setActiveToolModal])

  return (
    <div className="h-full w-full flex flex-col min-h-0 flex-1 overflow-hidden bg-slate-900 text-slate-100">
      <CodexWorkbenchTab
        initialThreadId={targetThreadId}
        statusData={statusData}
        loadingStatus={loadingStatus}
        onRefreshStatus={fetchStatus}
      />
    </div>
  )
}

export default CodingCockpitPage
