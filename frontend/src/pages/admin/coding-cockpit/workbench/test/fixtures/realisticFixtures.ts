import type { Project, Thread, SubAgent, DiffFile, TelemetryIncident } from '../../types/workbench'

export const FIXTURE_PROJECTS: Project[] = [
  {
    id: 'proj_fastapi_bookings',
    name: 'FastAPI Bookings',
    repository: 'elle4a69/fastapi_bookings',
    defaultBranch: 'master',
    activeThreadCount: 4,
    healthState: 'healthy',
    lastActivity: '2 minutes ago',
    writeRoots: ['app/', 'frontend/', 'alembic/', 'tests/'],
    authMode: 'chatgpt_managed',
    modelPolicy: 'gpt-4o / o3-mini allowed',
    description: 'Core booking engine, SMS orchestration, provider routing, and staff inbox telemetry.'
  },
  {
    id: 'proj_king_of_kings',
    name: 'King of Kings',
    repository: 'frank/king-of-kings',
    defaultBranch: 'main',
    activeThreadCount: 2,
    healthState: 'healthy',
    lastActivity: '1 hour ago',
    writeRoots: ['src/', 'packages/'],
    authMode: 'platform_api_key',
    modelPolicy: 'o3-mini / o1 managed',
    description: 'Hierarchical multi-agent workflow engine with sandboxed SSE tool-pods.'
  },
  {
    id: 'proj_codex_control',
    name: 'Codex Control Centre',
    repository: 'frank/codex-control-centre',
    defaultBranch: 'main',
    activeThreadCount: 1,
    healthState: 'healthy',
    lastActivity: 'Just now',
    writeRoots: ['frontend/', 'backend/'],
    authMode: 'chatgpt_managed',
    modelPolicy: 'gpt-4o default',
    description: 'Engineering agent control centre and standalone workbench.'
  }
]

export const FIXTURE_DIFFS: DiffFile[] = [
  {
    path: 'app/services/availability.py',
    status: 'modified',
    additions: 18,
    deletions: 4,
    oldContent: `def calculate_slots(provider_id: str, date: datetime.date) -> List[Slot]:\n    # Fetch basic slots\n    return db.query(Slot).filter_by(provider_id=provider_id, date=date).all()`,
    newContent: `def calculate_slots(provider_id: str, date: datetime.date, timezone_offset: int = 0) -> List[Slot]:\n    # Fetch slots with timezone normalization and lock acquisition\n    slots = db.query(Slot).filter_by(provider_id=provider_id, date=date).all()\n    return [slot.normalize(timezone_offset) for slot in slots if not slot.is_reserved()]`,
    hunks: [
      {
        oldStart: 42,
        oldLines: 7,
        newStart: 42,
        newLines: 12,
        header: '@@ -42,7 +42,12 @@ def calculate_slots',
        lines: [
          { type: 'context', content: ' def validate_provider(provider_id: str):', oldLineNumber: 42, newLineNumber: 42 },
          { type: 'context', content: '     return provider_service.get_active(provider_id)', oldLineNumber: 43, newLineNumber: 43 },
          { type: 'del', content: '-def calculate_slots(provider_id: str, date: datetime.date) -> List[Slot]:', oldLineNumber: 44 },
          { type: 'del', content: '-    # Fetch basic slots', oldLineNumber: 45 },
          { type: 'del', content: '-    return db.query(Slot).filter_by(provider_id=provider_id, date=date).all()', oldLineNumber: 46 },
          { type: 'add', content: '+def calculate_slots(provider_id: str, date: datetime.date, timezone_offset: int = 0) -> List[Slot]:', newLineNumber: 44 },
          { type: 'add', content: '+    """Calculate available booking slots with concurrency locks and tz awareness."""', newLineNumber: 45 },
          { type: 'add', content: '+    with db.acquire_read_lock(provider_id):', newLineNumber: 46 },
          { type: 'add', content: '+        slots = db.query(Slot).filter_by(provider_id=provider_id, date=date).all()', newLineNumber: 47 },
          { type: 'add', content: '+        return [s.normalize(timezone_offset) for s in slots if not s.is_reserved()]', newLineNumber: 48 },
          { type: 'context', content: ' ', oldLineNumber: 47, newLineNumber: 49 },
          { type: 'context', content: ' def format_slot_response(slots: List[Slot]):', oldLineNumber: 48, newLineNumber: 50 }
        ]
      }
    ]
  },
  {
    path: 'tests/test_availability.py',
    status: 'modified',
    additions: 24,
    deletions: 0,
    hunks: [
      {
        oldStart: 88,
        oldLines: 3,
        newStart: 88,
        newLines: 15,
        header: '@@ -88,3 +88,15 @@ class TestAvailability',
        lines: [
          { type: 'context', content: '     def test_empty_slots(self):', oldLineNumber: 88, newLineNumber: 88 },
          { type: 'context', content: '         assert calculate_slots("unknown", today) == []', oldLineNumber: 89, newLineNumber: 89 },
          { type: 'add', content: '+    def test_timezone_offset_slot_calculation(self):', newLineNumber: 90 },
          { type: 'add', content: '+        slots = calculate_slots("prov_1", today, timezone_offset=600)', newLineNumber: 91 },
          { type: 'add', content: '+        assert len(slots) == 4', newLineNumber: 92 },
          { type: 'add', content: '+        assert slots[0].start_hour == 9', newLineNumber: 93 },
          { type: 'add', content: '+', newLineNumber: 94 },
          { type: 'add', content: '+    def test_concurrent_lock_prevents_double_booking(self):', newLineNumber: 95 },
          { type: 'add', content: '+        with pytest.raises(SlotLockedException):', newLineNumber: 96 },
          { type: 'add', content: '+            reserve_slot_concurrently("prov_1", "slot_9am")', newLineNumber: 97 },
          { type: 'context', content: ' ', oldLineNumber: 90, newLineNumber: 98 }
        ]
      }
    ]
  },
  {
    path: 'alembic/versions/2026_08_add_slot_concurrency_lock.py',
    status: 'added',
    additions: 38,
    deletions: 0,
    hunks: [
      {
        oldStart: 0,
        oldLines: 0,
        newStart: 1,
        newLines: 12,
        header: '@@ -0,0 +1,12 @@',
        lines: [
          { type: 'add', content: '+"""Add slot concurrency lock column"""', newLineNumber: 1 },
          { type: 'add', content: '+from alembic import op', newLineNumber: 2 },
          { type: 'add', content: '+import sqlalchemy as sa', newLineNumber: 3 },
          { type: 'add', content: '+', newLineNumber: 4 },
          { type: 'add', content: '+revision = "2026_08_add_slot_concurrency"', newLineNumber: 5 },
          { type: 'add', content: '+down_revision = "2026_07_baseline"', newLineNumber: 6 },
          { type: 'add', content: '+', newLineNumber: 7 },
          { type: 'add', content: '+def upgrade():', newLineNumber: 8 },
          { type: 'add', content: '+    op.add_column("slots", sa.Column("locked_until", sa.DateTime(), nullable=True))', newLineNumber: 9 },
          { type: 'add', content: '+    op.create_index("ix_slots_locked_until", "slots", ["locked_until"])', newLineNumber: 10 }
        ]
      }
    ]
  }
]

export const FIXTURE_SUBAGENTS: SubAgent[] = [
  {
    id: 'sub_agent_db_worker',
    parentThreadId: 'th_active_stream',
    role: 'Database Migration Architect',
    objective: 'Generate zero-downtime Alembic migration for slot concurrency locking table.',
    status: 'completed',
    model: 'gpt-4o',
    reasoningEffort: 'high',
    scope: 'workspace_write',
    branch: 'feat/slot-locking',
    startedAt: '12 minutes ago',
    elapsedSeconds: 45,
    progressSummary: 'Migration generated and verified against synthetic local SQLite test DB.',
    resultSummary: 'Created alembic/versions/2026_08_add_slot_concurrency_lock.py with downgrade support.',
    filesChangedCount: 1,
    testsRunCount: 4,
    childThreadId: 'th_child_db_worker'
  },
  {
    id: 'sub_agent_test_runner',
    parentThreadId: 'th_active_stream',
    role: 'Test Suite Specialist',
    objective: 'Execute isolated pytest suite for app/services/availability.py with synthetic fixtures.',
    status: 'running',
    model: 'o3-mini',
    reasoningEffort: 'medium',
    scope: 'read_only',
    branch: 'feat/slot-locking',
    startedAt: '1 minute ago',
    elapsedSeconds: 58,
    progressSummary: 'Running test_concurrent_lock_prevents_double_booking (3/6 passing)...',
    filesChangedCount: 0,
    testsRunCount: 6,
    childThreadId: 'th_child_test_runner'
  },
  {
    id: 'sub_agent_telemetry_auditor',
    parentThreadId: 'th_active_stream',
    role: 'Observability & Telemetry Auditor',
    objective: 'Verify OpenTelemetry span attributes in SigNoz collector for slot acquisition latency.',
    status: 'completed',
    model: 'gpt-4o',
    reasoningEffort: 'low',
    scope: 'read_only',
    startedAt: '8 minutes ago',
    elapsedSeconds: 22,
    progressSummary: 'Span attributes confirmed: slot.provider_id, slot.latency_ms (low cardinality).',
    resultSummary: 'Verified 0 secret leaks; traces confirmed in SigNoz preview.',
    filesChangedCount: 0,
    testsRunCount: 2
  },
  {
    id: 'sub_agent_security_scan',
    parentThreadId: 'th_active_stream',
    role: 'Static Code & Secret Scanner',
    objective: 'Run AST scan across changes to ensure no authorization boundaries are loosened.',
    status: 'completed',
    model: 'gpt-4o',
    reasoningEffort: 'high',
    scope: 'read_only',
    startedAt: '5 minutes ago',
    elapsedSeconds: 31,
    progressSummary: 'Clean scan. No hardcoded credentials or customer data in diffs.',
    resultSummary: 'Passed all 14 safety and privacy invariants.',
    filesChangedCount: 0,
    testsRunCount: 14
  },
  {
    id: 'sub_agent_api_validator',
    parentThreadId: 'th_active_stream',
    role: 'FastAPI Router Contract Validator',
    objective: 'Verify OpenAPI schema response model for /api/v1/availability/slots endpoint.',
    status: 'waiting',
    model: 'o3-mini',
    reasoningEffort: 'low',
    scope: 'read_only',
    startedAt: '30 seconds ago',
    elapsedSeconds: 30,
    progressSummary: 'Waiting for database migration apply approval before running contract tests.'
  },
  {
    id: 'sub_agent_frontend_sync',
    parentThreadId: 'th_active_stream',
    role: 'Frontend Client Sync Specialist',
    objective: 'Update TypeScript API client definitions to include timezone_offset parameter.',
    status: 'running',
    model: 'gpt-4o',
    reasoningEffort: 'medium',
    scope: 'workspace_write',
    startedAt: '40 seconds ago',
    elapsedSeconds: 40,
    progressSummary: 'Modifying frontend/src/lib/api.ts with typed parameters.'
  }
]

export const FIXTURE_INCIDENTS: TelemetryIncident[] = [
  {
    id: 'inc_sig_9901',
    traceId: 'tr_4f88e1a90c42',
    serviceName: 'fastapi-bookings-backend',
    environment: 'staging',
    timestamp: '14:22:05 UTC',
    severity: 'error',
    message: 'SlotAcquisitionTimeout: Lock on provider slot_9am expired after 5000ms',
    durationMs: 5042,
    httpStatus: 504,
    attributes: {
      'rpc.method': 'reserve_slot',
      'tenant.id': 'tenant_prod_melbourne_01',
      'provider.id': 'prov_dr_smith',
      'db.system': 'postgresql'
    }
  },
  {
    id: 'inc_sig_9902',
    traceId: 'tr_88b122f0d981',
    serviceName: 'fastapi-bookings-backend',
    environment: 'staging',
    timestamp: '14:20:11 UTC',
    severity: 'warning',
    message: 'High latency detected in calculate_slots query: 1,240ms',
    durationMs: 1240,
    httpStatus: 200,
    attributes: {
      'rpc.method': 'calculate_slots',
      'db.rows_scanned': '4200'
    }
  }
]

export const FIXTURE_THREADS: Thread[] = [
  {
    id: 'th_active_stream',
    projectId: 'proj_fastapi_bookings',
    title: 'Fix concurrent double-booking race condition with slot locking',
    module: 'Availability & Booking Core',
    status: 'active',
    branch: 'feat/slot-concurrency-locks',
    worktree: 'wt-slot-locks',
    model: 'gpt-4o',
    reasoningEffort: 'high',
    permissionProfile: 'workspace_write',
    contextCompactionState: 'healthy',
    subAgentCount: 6,
    approvalCount: 1,
    createdAt: '20 minutes ago',
    updatedAt: 'Just now',
    isPinned: true,
    goals: 'Eliminate duplicate appointment allocations under heavy load without degrading read performance.',
    tokenBudget: { limit: 128000, used: 34200 },
    turns: [
      {
        id: 'turn_1',
        threadId: 'th_active_stream',
        turnNumber: 1,
        status: 'completed',
        startedAt: '19 minutes ago',
        completedAt: '18 minutes ago',
        items: [
          {
            id: 'item_1_prompt',
            turnId: 'turn_1',
            type: 'user_instruction',
            timestamp: '19:35:10',
            content: 'We noticed in SigNoz incident #9901 that two customers booked the same 9:00 AM slot within 40ms of each other. Implement row-level concurrency locking in `app/services/availability.py`, add Alembic migration, and provide focused regression pytest tests.',
            authorName: 'Frank (Lead Engineer)',
            attachments: [{ name: 'signoz_trace_9901.json', size: '14.2 KB', type: 'application/json' }]
          },
          {
            id: 'item_1_reasoning',
            turnId: 'turn_1',
            type: 'reasoning_summary',
            timestamp: '19:35:14',
            summary: 'Analyzed trace #9901. Root cause: calculate_slots reads slots without row locking (SELECT ... FOR UPDATE). Concurrency window occurs between slot check and booking confirmation.',
            rawTrace: '1. Read app/services/availability.py\n2. Identify calculate_slots and reserve_slot functions\n3. Determine Alembic schema changes needed for locked_until timestamp\n4. Plan sub-agents: DB migration worker, test author, and security auditor.',
            elapsedMs: 2400
          },
          {
            id: 'item_1_plan',
            turnId: 'turn_1',
            type: 'plan',
            timestamp: '19:35:18',
            title: 'Execution Checklist for Slot Locking',
            tasks: [
              { id: 'task_1', title: 'Audit app/services/availability.py and database models', status: 'completed' },
              { id: 'task_2', title: 'Spawn DB sub-agent to draft Alembic migration', status: 'completed' },
              { id: 'task_3', title: 'Implement acquire_read_lock and lock expiration in availability service', status: 'completed' },
              { id: 'task_4', title: 'Author pytest unit & concurrency regression tests', status: 'active' },
              { id: 'task_5', title: 'Execute test suite and verify SigNoz trace attributes', status: 'pending' }
            ]
          },
          {
            id: 'item_1_msg',
            turnId: 'turn_1',
            type: 'agent_message',
            timestamp: '19:35:22',
            content: 'I have analyzed the race condition reported in SigNoz incident #9901. When two clients request the same availability window simultaneously, both pass the unreserved check before either writes a booking record.\n\nI will implement row locking with an automatic 60-second lease expiration to guarantee idempotency and isolation.'
          }
        ]
      },
      {
        id: 'turn_2',
        threadId: 'th_active_stream',
        turnNumber: 2,
        status: 'in_progress',
        startedAt: '12 minutes ago',
        items: [
          {
            id: 'item_2_tool_mcp',
            turnId: 'turn_2',
            type: 'tool_call',
            timestamp: '19:42:01',
            serverName: 'api-tester',
            toolName: 'generate_scenarios',
            args: { target_file: 'app/services/availability.py', mode: 'concurrency_race_condition' },
            resultSummary: 'Generated 4 concurrency stress test scenarios with synthetic customer fixtures.',
            status: 'success',
            durationMs: 420
          },
          {
            id: 'item_2_cmd',
            turnId: 'turn_2',
            type: 'command_execution',
            timestamp: '19:43:10',
            command: 'pytest tests/test_availability.py -k "test_timezone or test_concurrent" -v',
            summary: 'Running focused availability pytest suite',
            workingDirectory: 'F:\\Projects\\fastapi_bookings',
            status: 'completed',
            durationMs: 1840,
            exitCode: 0,
            stdout: '============================= test session starts =============================\nplatform win32 -- Python 3.11.9, pytest-8.3.2, pluggy-1.5.0\nrootdir: F:\\Projects\\fastapi_bookings\ncollected 8 items / 6 deselected / 2 selected\n\ntests/test_availability.py::TestAvailability::test_timezone_offset_slot_calculation PASSED [ 50%]\ntests/test_availability.py::TestAvailability::test_concurrent_lock_prevents_double_booking PASSED [100%]\n\n======================= 2 passed, 6 deselected in 1.84s =======================',
            lineCount: 10,
            processId: 'pid_9182'
          },
          {
            id: 'item_2_file_change',
            turnId: 'turn_2',
            type: 'file_change',
            timestamp: '19:44:15',
            summary: 'Updated availability logic and added concurrency test fixtures',
            totalAdditions: 80,
            totalDeletions: 4,
            files: [
              { path: 'app/services/availability.py', status: 'proposed', additions: 18, deletions: 4, requiresApproval: false },
              { path: 'tests/test_availability.py', status: 'proposed', additions: 24, deletions: 0, requiresApproval: false },
              { path: 'alembic/versions/2026_08_add_slot_concurrency_lock.py', status: 'proposed', additions: 38, deletions: 0, requiresApproval: true }
            ]
          },
          {
            id: 'item_2_approval',
            turnId: 'turn_2',
            type: 'approval_request',
            timestamp: '19:45:00',
            approvalId: 'appr_migration_apply',
            category: 'command',
            title: 'Apply Database Schema Migration',
            consequence: 'Will alter the local SQLite/PostgreSQL `slots` table schema by adding `locked_until` datetime column and B-Tree index.',
            command: 'alembic upgrade head',
            workingDirectory: 'F:\\Projects\\fastapi_bookings',
            reason: 'Required so that the availability service can write lock expiration timestamps during slot allocation.',
            risk: 'medium',
            status: 'pending',
            scope: 'once'
          },
          {
            id: 'item_2_tests',
            turnId: 'turn_2',
            type: 'test_run',
            timestamp: '19:45:20',
            framework: 'pytest 8.3.2',
            status: 'passed',
            totalDurationMs: 1840,
            suites: [
              {
                name: 'tests/test_availability.py',
                passed: 2,
                failed: 0,
                skipped: 0,
                durationMs: 1840
              }
            ]
          },
          {
            id: 'item_2_agent_streaming',
            turnId: 'turn_2',
            type: 'agent_message',
            timestamp: '19:45:30',
            isStreaming: true,
            content: 'The concurrency logic and unit tests have passed cleanly. I am now awaiting your approval to apply the schema migration via `alembic upgrade head` before concluding the verification gate.'
          }
        ]
      }
    ]
  },
  {
    id: 'th_needs_approval_high_risk',
    projectId: 'proj_fastapi_bookings',
    title: 'Purge stale temporary SMS customer test sessions',
    module: 'SMS Orchestration',
    status: 'needs_approval',
    branch: 'chore/cleanup-test-sms',
    worktree: 'wt-sms-cleanup',
    model: 'gpt-4o',
    reasoningEffort: 'medium',
    permissionProfile: 'workspace_write',
    contextCompactionState: 'healthy',
    subAgentCount: 1,
    approvalCount: 1,
    createdAt: '1 hour ago',
    updatedAt: '10 minutes ago',
    goals: 'Safely purge ephemeral test tokens and expired synthetic SMS sessions.',
    turns: [
      {
        id: 'turn_sms_1',
        threadId: 'th_needs_approval_high_risk',
        turnNumber: 1,
        status: 'in_progress',
        startedAt: '1 hour ago',
        items: [
          {
            id: 'item_sms_appr',
            turnId: 'turn_sms_1',
            type: 'approval_request',
            timestamp: '18:50:00',
            approvalId: 'appr_purge_db',
            category: 'command',
            title: 'Truncate Synthetic SMS Test Session Records',
            consequence: 'Will permanently delete 142 records matching prefix `test_synthetic_*` from the local development database.',
            command: 'python -m app.cli purge-synthetic-sessions --confirm --force',
            workingDirectory: 'F:\\Projects\\fastapi_bookings',
            reason: 'Clean up local test state before running end-to-end Chatwoot webhook simulation.',
            risk: 'high',
            status: 'pending',
            scope: 'once'
          }
        ]
      }
    ]
  },
  {
    id: 'th_compacted_history',
    projectId: 'proj_fastapi_bookings',
    title: 'Refactor Chatwoot staff inbox webhook payload deserializer',
    module: 'Chatwoot Integration',
    status: 'completed',
    branch: 'refactor/chatwoot-serde',
    worktree: 'wt-chatwoot',
    model: 'o3-mini',
    reasoningEffort: 'high',
    permissionProfile: 'workspace_write',
    contextCompactionState: 'compacted',
    subAgentCount: 2,
    approvalCount: 0,
    createdAt: '3 hours ago',
    updatedAt: '1 hour ago',
    goals: 'Improve robustness of webhook receiver against schema variations.',
    turns: [
      {
        id: 'turn_c1',
        threadId: 'th_compacted_history',
        turnNumber: 1,
        status: 'completed',
        startedAt: '3 hours ago',
        completedAt: '2 hours ago',
        items: [
          {
            id: 'item_comp_1',
            turnId: 'turn_c1',
            type: 'compaction_notice',
            timestamp: '17:15:00',
            explanation: 'Codex condensed 14 earlier conversation turns to preserve room for continued deep refactoring. Persisted project files, diffs, and thread records remain available.',
            tokensSaved: 48500,
            originalTurnCount: 14
          },
          {
            id: 'item_comp_summary',
            turnId: 'turn_c1',
            type: 'completion_summary',
            timestamp: '17:30:00',
            outcome: 'Chatwoot payload parser successfully refactored with Pydantic V2 discriminator models.',
            changedFilesCount: 4,
            testsPassedCount: 18,
            durationSeconds: 145,
            summary: 'All 18 regression tests passed. Verified zero payload loss under malformed input.'
          }
        ]
      }
    ]
  },
  {
    id: 'th_interrupted_turn',
    projectId: 'proj_fastapi_bookings',
    title: 'Benchmark OpenTelemetry trace export throughput',
    module: 'Telemetry & Observability',
    status: 'interrupted',
    branch: 'perf/otel-bench',
    worktree: 'wt-otel',
    model: 'gpt-4o',
    reasoningEffort: 'low',
    permissionProfile: 'read_only',
    contextCompactionState: 'healthy',
    subAgentCount: 0,
    approvalCount: 0,
    createdAt: '5 hours ago',
    updatedAt: '4 hours ago',
    goals: 'Profile memory footprint of OTLP exporter under 500 req/sec load.',
    turns: [
      {
        id: 'turn_i1',
        threadId: 'th_interrupted_turn',
        turnNumber: 1,
        status: 'interrupted',
        startedAt: '5 hours ago',
        items: [
          {
            id: 'item_int_1',
            turnId: 'turn_i1',
            type: 'interruption',
            timestamp: '15:20:00',
            reason: 'Turn stopped by operator via stop button during 10-minute load simulation.',
            interruptedBy: 'Frank'
          }
        ]
      }
    ]
  }
]
