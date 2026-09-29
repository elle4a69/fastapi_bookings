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
  warmth: number; // 1-5
  wit: number; // 1-5
  sarcasm: number; // 0-5
  directness: number; // 1-5
  chattiness: number; // 1-5
  patience: number; // 1-5
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
  content_hash: string;
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
  status: 'pending' | 'quarantined' | 'approved' | 'rejected';
  reason_code?: string;
  resolution_code?: string;
  confidence_score: number;
  is_dynamic_risk?: boolean;
  created_at: string;
}

export interface VariableItem {
  name: string;
  scope: 'system' | 'tenant' | 'provider' | 'runtime';
  source: string;
  resolved_value: string;
  description: string;
}

export interface LiveToolItem {
  name: string;
  description: string;
  server_bound_params: string[];
  client_allowed_params: string[];
  execution_mode: 'read_only' | 'idempotent_query';
  example_input: Record<string, any>;
  example_output: Record<string, any>;
}

export interface EvalScenario {
  id: string;
  name: string;
  category: 'safety' | 'availability' | 'travel' | 'pii' | 'distress';
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

export interface InspectionData {
  assembledTiers: PromptHierarchyTier[];
  executedTools: Array<{
    name: string;
    arguments: Record<string, any>;
    output: Record<string, any>;
    server_bound_keys: string[];
  }>;
  resolvedVariables: Record<string, string>;
  activePriors: StyleLabPriors;
  situationalSuppressionActive: boolean;
  suppressionReason?: string;
}
