export type ConversationFilter = "all" | "automatic" | "review" | "takeover" | "escalated" | "resolved";

export interface ConversationOperationsState {
  id: number;
  state: string;
  ai_enabled: boolean;
  is_pinned: boolean;
  customer_address: string;
  client_name?: string;
  needs_review?: boolean;
  last_activity_at: string;
}

export interface ManualSendAttempt {
  conversationId: number;
  body: string;
  clientRequestId: string;
}

export interface ConversationStatePresentation {
  label: string;
  tone: "automatic" | "manual" | "review" | "danger" | "neutral";
}

export function matchesConversationFilter(
  conversation: ConversationOperationsState,
  filter: ConversationFilter,
  searchQuery: string,
): boolean {
  if (filter === "automatic" && (!conversation.ai_enabled || conversation.state !== "auto-reply")) {
    return false;
  }
  if (filter === "takeover" && conversation.state !== "taken-over") {
    return false;
  }
  if (filter === "review" && !conversation.needs_review && conversation.state !== "needs-review") {
    return false;
  }
  if (filter === "escalated" && conversation.state !== "escalated") return false;
  if (filter === "resolved" && conversation.state !== "resolved") return false;

  const query = searchQuery.trim().toLocaleLowerCase();
  if (!query) return true;

  return Boolean(
    conversation.client_name?.toLocaleLowerCase().includes(query)
      || conversation.customer_address.toLocaleLowerCase().includes(query),
  );
}

export function compareConversationOrder(
  left: ConversationOperationsState,
  right: ConversationOperationsState,
): number {
  if (left.is_pinned !== right.is_pinned) {
    return left.is_pinned ? -1 : 1;
  }
  return new Date(right.last_activity_at).getTime() - new Date(left.last_activity_at).getTime();
}

export function isAutomationReleaseAllowed(
  conversation: Pick<ConversationOperationsState, "state" | "ai_enabled" | "needs_review"> & { is_blocked?: boolean },
): boolean {
  if (conversation.is_blocked || conversation.needs_review) return false;
  return conversation.state === "taken-over" || conversation.state === "paused";
}

export function conversationStatePresentation(
  conversation: Pick<ConversationOperationsState, "state" | "ai_enabled" | "needs_review"> & { is_blocked?: boolean },
): ConversationStatePresentation {
  if (conversation.is_blocked) return { label: "Blocked", tone: "danger" };
  if (conversation.needs_review || conversation.state === "needs-review") return { label: "Needs review", tone: "review" };
  if (conversation.state === "escalated") return { label: "Escalated", tone: "danger" };
  if (conversation.state === "resolved") return { label: "Resolved", tone: "neutral" };
  if (conversation.state === "taken-over") return { label: "Human takeover", tone: "manual" };
  if (conversation.state === "paused" || !conversation.ai_enabled) return { label: "AI paused", tone: "manual" };
  if (conversation.state === "auto-reply" && conversation.ai_enabled) return { label: "Automatic", tone: "automatic" };
  return { label: conversation.state.replaceAll("-", " "), tone: "neutral" };
}

export function getOrCreateManualSendAttempt(
  current: ManualSendAttempt | null,
  conversationId: number,
  body: string,
  createId: () => string,
): ManualSendAttempt {
  if (current && current.conversationId === conversationId && current.body === body) {
    return current;
  }
  return { conversationId, body, clientRequestId: createId() };
}

export function shouldApplyConversationResponse(
  requestedConversationId: number,
  selectedConversationId: number | null,
  requestSequence: number,
  latestRequestSequence: number,
): boolean {
  return requestedConversationId === selectedConversationId && requestSequence === latestRequestSequence;
}
