export interface AgentIssue {
  id: string
  category: string
  title: string
  severity: 'INFO' | 'WARNING' | 'CRITICAL'
  description: string
  status: 'OPEN' | 'RESOLVED' | 'IN_PROGRESS'
  discovered_at?: string
  resolved_at?: string
}

export interface RemediationModification {
  file_path: string
  description: string
  diff: string
}

export interface RemediationPlan {
  plan_id: string
  issue_id: string
  title: string
  severity: string
  root_cause_analysis: string
  proposed_modifications: RemediationModification[]
  verification_steps: string[]
  rollback_steps: string[]
  requires_approval: boolean
  approved: boolean
  status: string
  created_at: string
}

export interface AgentStatusData {
  health_score: number
  status: 'HEALTHY' | 'DEGRADED' | 'CRITICAL'
  telemetry_baseline: {
    telemetry_enabled: boolean
    trace_exporter_active: boolean
    metric_exporter_active: boolean
    log_exporter_active: boolean
    service_name: string
    environment: string
  }
  outbox_status: {
    failed_sms_jobs: number
    retry_backlog: number
    dead_letter_deliveries: number
  }
  chatwoot_status: {
    active_bindings: number
    webhook_latency_ms: number
    inbound_cipher_valid: boolean
  }
  latest_code_audit?: {
    timestamp: string
    git: {
      branch: string
      clean: boolean
      untracked_count: number
      modified_count: number
    }
    secret_leak_clean: boolean
  }
  active_issues: AgentIssue[]
}

export interface StreamEvent {
  timestamp: string
  type: 'thought' | 'step' | 'audit' | 'fix_status' | 'heartbeat'
  data: any
  title?: string
}

export interface SkillItem {
  skill_id: string
  name: string
  description: string
  tags?: string[]
}

export interface RaceConditionFuzzResult {
  test_id: string
  concurrency_tested: number
  successful_bookings: number
  conflicts_prevented: number
  conflict_rate_pct: number
  double_bookings_prevented_pct: number
  avg_lock_contention_ms: number
}
