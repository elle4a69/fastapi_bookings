export type StudioTabKey =
  | 'overview'
  | 'prompt-composer'
  | 'simulator'
  | 'example-library'
  | 'knowledge-curator'
  | 'import-centre'
  | 'variables-tools'
  | 'evaluation-safety';

export type ChannelType = 'sms' | 'whatsapp' | 'webchat' | 'simulated';

export interface ProviderItem {
  id: number | null;
  name: string;
  email?: string;
  is_active?: boolean;
}

export interface StyleLabPriors {
  warmth: number; // 0-5
  wit: number; // 0-5
  sarcasm: number; // 0-5
  directness: number; // 0-5
  chattiness: number; // 0-5
  patience: number; // 0-5
}

export interface PromptHierarchyTier {
  tier: number;
  name: string;
  badge: string;
  authority: string;
  isEnforcedByPlatform: boolean;
  content: string;
  tokenCount: number;
  description: string;
}

export interface OverviewStats {
  channel_accounts_count: number;
  active_conversations_count: number;
  curated_facts_count: number;
  approved_examples_count: number;
  message_volume: number;
  pending_proposals_count: number;
  channels_breakdown: Record<string, number>;
  readiness_score: number;
}

export interface PolicyReadResponse {
  immutable_safety: string;
  shared_base_policy: string;
  tenant_policy: string;
  provider_overlay: string;
  custom_training_notes: string;
  system_prompt_template: string;
  style_profile: StyleLabPriors;
  agent_name: string;
  model: string;
  tiers: PromptHierarchyTier[];
}

export interface MessageStyleExampleItem {
  id: number;
  tenant_id: number | null;
  provider_id: number | null;
  intent: string;
  client_message: string;
  assistant_reply: string;
  category: string;
  tags: string[];
  is_approved: boolean;
  is_active: boolean;
  source: string;
  content_hash?: string;
  created_at: string;
}

export interface KnowledgeProposalItem {
  id: number;
  tenant_id: number;
  provider_id: number | null;
  proposal_type: string;
  category: string;
  user_query: string;
  ideal_response: string;
  proposed_fact?: string;
  knowledge_kind?: string;
  status: 'pending' | 'quarantined' | 'approved' | 'rejected' | 'accepted' | 'evidence_only' | 'superseded' | string;
  reason_code?: string;
  resolution_code?: string;
  confidence_score: number;
  is_dynamic_risk?: boolean;
  extracted_variables?: Record<string, string> | string[];
  variables?: Record<string, string> | string[];
  created_at: string;
}

export interface VariableItem {
  name: string;
  scope: string;
  source: string;
  resolved_value: string | null;
  description: string;
}

export interface LiveToolItem {
  name: string;
  description: string;
  parameters: Record<string, any>;
  server_enforced_scoping: string[];
}

export interface EvalScenario {
  id: string;
  name: string;
  category: 'safety' | 'availability' | 'travel' | 'pii' | 'distress' | string;
  description: string;
  prompt_input: string;
  expected_guardrail: string;
  status: 'idle' | 'running' | 'passed' | 'failed';
  score: number;
  details?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: string;
  toolCall?: {
    name: string;
    params: Record<string, any>;
    result?: Record<string, any>;
  };
}

export interface SimulateTurnResponse {
  reply: string;
  executed_tools: Array<{
    name: string;
    tool_name?: string;
    status: 'success' | 'error';
    success: boolean;
    timestamp: string;
    argument_keys: string[];
    result_keys: string[];
    server_bound_keys: string[];
  }>;
  assembled_prompt: {
    system_prompt: string;
    messages: any[];
    sections: Record<string, string>;
    unresolved_variables: string[];
  };
  resolved_variables: Record<string, any>;
  active_priors: StyleLabPriors;
  distress_detected: boolean;
  situational_modulation_active: boolean;
}

export interface ImportReportData {
  status: 'idle' | 'success' | 'failed';
  timestamp?: string;
  scanned: number;
  imported: number;
  skippedDuplicates: number;
  rejected: number;
  sha256_verified: boolean;
  computed_sha256?: string;
  scopeUsed: string;
  dryRunUsed: boolean;
  errors?: string[];
}

export interface CuratedMemoryItem {
  id: number;
  tenant_id: number;
  provider_id: number | null;
  category: string;
  user_query: string;
  ideal_response: string;
  knowledge_kind: string;
  authority: string;
  status: 'active' | 'quarantined' | 'superseded' | string;
  conflict_state: 'clear' | 'needs_review' | string;
  confidence_score: number;
  content_hash?: string;
  source_reference?: string;
  effective_from: string;
  effective_until?: string | null;
  supersedes_id?: number | null;
  is_tenant_shared: boolean;
  graph_projection_status: 'none' | 'pending' | 'processing' | 'projected' | 'retry' | 'dead_letter' | string;
  projection_id?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'provider' | 'tenant' | 'topic' | 'fact' | 'preference' | 'behaviour' | 'policy' | 'boundary' | string;
  title: string;
  content?: string | null;
  scope: 'tenant_shared' | 'provider_private' | string;
  status: 'active' | 'superseded' | 'quarantined' | string;
  category?: string | null;
  authority?: string | null;
  confidence_score?: number | null;
  curated_memory_id?: number | null;
  projection_status?: string | null;
  group_id: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: 'PREFERS' | 'AVOIDS' | 'SUPERSEDES' | 'APPLIES_WHEN' | 'HAS_BOUNDARY' | 'SUPPORTED_BY' | 'OWNS' | string;
  label: string;
}

export interface EpistemicGraphData {
  ok: boolean;
  provider_id?: number | null;
  provider_name: string;
  tenant_id: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    node_count: number;
    edge_count: number;
    provider_nodes: number;
    shared_nodes: number;
    neo4j_online: boolean;
  };
}

export interface PipelineStageMetric {
  stage_id: number;
  name: string;
  status: 'active' | 'idle' | 'warning' | 'error';
  pending_count: number;
  total_processed: number;
  details: Record<string, any>;
}

export interface PipelineStatusData {
  ok: boolean;
  tenant_id: number;
  provider_id?: number | null;
  stages: PipelineStageMetric[];
  queue_counters: {
    pending_curation: number;
    active_memories: number;
    pending_projections: number;
    neo4j_node_count: number;
    redis_cache_hit_ratio: number;
    dead_letters: number;
  };
  redis_epoch: number;
  neo4j_online: boolean;
  updated_at: string;
}

export interface DrawerDetailContext {
  itemType: 'memory' | 'node' | 'proposal' | 'stage';
  memory?: CuratedMemoryItem | null;
  node?: GraphNode | null;
  stage?: PipelineStageMetric | null;
}
