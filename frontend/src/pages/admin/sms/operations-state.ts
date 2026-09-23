export type ConversationFilter = "all" | "automatic" | "review" | "takeover";

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
  if (filter === "review" && !conversation.needs_review && conversation.state !== "info-needed") {
    return false;
  }

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
