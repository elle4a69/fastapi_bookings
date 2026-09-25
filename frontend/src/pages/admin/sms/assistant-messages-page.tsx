import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Search,
  RefreshCw,
  Pin,
  X,
  MessageSquare,
  BrainCircuit,
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { AssistantThreadPanel, type ThreadMessage } from "./assistant-thread-panel";

interface SmsConversation {
  id: number;
  tenant_id: number;
  provider_id: number;
  sms_account_id: number;
  customer_address: string;
  client_id?: number;
  client_name?: string;
  state: string;
  unread_count: number;
  is_pinned: boolean;
  is_blocked: boolean;
  ai_enabled: boolean;
  last_activity_at: string;
  created_at: string;
  updated_at: string;
  priority?: "low" | "normal" | "high" | "urgent";
  sla_due_at?: string | null;
  booking_id?: number | null;
  arrival_id?: number | null;
  last_message_preview?: string | null;
  needs_review?: boolean;
}

interface TimelineItem {
  kind: "message" | "internal_note" | "event";
  id: number;
  body?: string;
  direction?: string;
  author_type?: string;
  status?: string;
  occurred_at: string;
  event_type?: string;
  author_id?: number;
  meta?: Record<string, unknown>;
}

interface KnowledgeProposal {
  id: number;
  proposal_type: string;
  status: string;
  user_query?: string | null;
  proposed_response?: string | null;
  provider_id?: number | null;
}

interface AssistantMessagesPageProps {
  onNavigate?: (tabId: string) => void;
}

export default function AssistantMessagesPage({ onNavigate: _onNavigate }: AssistantMessagesPageProps = {}) {
  const [conversations, setConversations] = useState<SmsConversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<TimelineItem[]>([]);
  const [activeConv, setActiveConv] = useState<SmsConversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Global Header Toggles
  const [globalAiActive, setGlobalAiActive] = useState(true);
  const [globalTrainActive, setGlobalTrainActive] = useState(false);

  // Action in-flight state
  const [actionInFlight, setActionInFlight] = useState(false);

  // Information Request State
  const [hasInfoRequest, setHasInfoRequest] = useState(false);
  const [infoRequestPrompt, setInfoRequestPrompt] = useState("");

  // Track pending proposals for info request detection
  const [pendingProposals, setPendingProposals] = useState<KnowledgeProposal[]>([]);

  const selectedConvIdRef = useRef<number | null>(null);
  selectedConvIdRef.current = selectedConversationId;

  // Load conversations
  const loadConversations = useCallback(async (showToast = false) => {
    try {
      const res = await apiClient.get<SmsConversation[]>("/api/admin/sms/conversations");
      setConversations(res);

      if (selectedConvIdRef.current) {
        const found = res.find((c) => c.id === selectedConvIdRef.current);
        if (found) setActiveConv(found);
      }
      if (showToast) {
        toast.success("Inbox catch-up complete.");
      }
    } catch (err: any) {
      if (showToast) {
        toast.error(err.message || "Failed to refresh conversations.");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Load pending knowledge proposals for info requests
  const loadProposals = useCallback(async () => {
    try {
      const res = await apiClient.get<KnowledgeProposal[]>("/api/admin/sms/knowledge/proposals?status=pending");
      const list = Array.isArray(res) ? res : ((res as any)?.items || []);
      setPendingProposals(list);
    } catch {
      setPendingProposals([]);
    }
  }, []);

  useEffect(() => {
    loadConversations();
    loadProposals();
    const interval = setInterval(() => {
      loadConversations();
      loadProposals();
    }, 10000);
    return () => clearInterval(interval);
  }, [loadConversations, loadProposals]);

  // Load messages for selected conversation
  const loadMessages = useCallback(async (convId: number) => {
    try {
      const [timeline, detail] = await Promise.all([
        apiClient.get<TimelineItem[]>(`/api/admin/sms/conversations/${convId}/timeline`),
        apiClient.get<SmsConversation>(`/api/admin/sms/conversations/${convId}`),
      ]);

      if (selectedConvIdRef.current === convId) {
        setMessages(timeline);
        setActiveConv(detail);
        // Clear local unread count
        setConversations((prev) =>
          prev.map((c) => (c.id === convId ? { ...c, unread_count: 0 } : c))
        );

        // Determine if thread has a pending info request
        const matchingProposal = pendingProposals.find(
          (p) => p.provider_id === detail.provider_id && p.proposal_type === "gap"
        );
        const needsReview = detail.state === "needs-review" || Boolean(detail.needs_review);

        if (matchingProposal || needsReview) {
          setHasInfoRequest(true);
          setInfoRequestPrompt(
            matchingProposal?.user_query ||
              detail.last_message_preview ||
              "Customer asked a question that Assistant cannot verify from knowledge."
          );
        } else {
          setHasInfoRequest(false);
          setInfoRequestPrompt("");
        }
      }
    } catch (err: any) {
      if (selectedConvIdRef.current === convId) {
        toast.error(err.message || "Failed to load thread messages.");
      }
    }
  }, [pendingProposals]);

  const selectConversation = (convId: number | null) => {
    setSelectedConversationId(convId);
    selectedConvIdRef.current = convId;
    setMessages([]);
    setActiveConv(null);
    if (convId) {
      loadMessages(convId);
    }
  };

  // Send manual reply
  const handleSend = async (textToSend: string) => {
    if (!selectedConversationId || !activeConv || actionInFlight) return;
    if (activeConv.is_blocked) {
      toast.error("Cannot send SMS: Contact is currently blocked.");
      return;
    }

    const convId = selectedConversationId;
    const optimistic: TimelineItem = {
      kind: "message",
      id: -Date.now(),
      body: textToSend,
      direction: "outbound",
      author_type: "staff",
      status: "queued",
      occurred_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      await apiClient.post(`/api/admin/sms/conversations/${convId}/messages`, {
        body: textToSend,
        client_request_id: crypto.randomUUID(),
      });
      loadMessages(convId);
      loadConversations();
    } catch (err: any) {
      toast.error(err.message || "Failed to send message.");
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      throw err;
    }
  };

  // AI Toggle: Takeover / Release
  const handleToggleAi = async () => {
    if (!selectedConversationId || !activeConv || actionInFlight) return;
    const convId = selectedConversationId;
    const isAiActive = activeConv.state === "auto-reply" && activeConv.ai_enabled;

    setActionInFlight(true);
    try {
      const endpoint = isAiActive ? "takeover" : "release";
      const updated = await apiClient.post<SmsConversation>(
        `/api/admin/sms/conversations/${convId}/${endpoint}`,
        {}
      );
      setActiveConv(updated);
      setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      toast.success(isAiActive ? "Human takeover active (AI paused)." : "Conversation released to AI auto-reply.");
      loadMessages(convId);
    } catch (err: any) {
      toast.error(err.message || "Failed to change AI state.");
    } finally {
      setActionInFlight(false);
    }
  };

  // Pin / Unpin
  const handleTogglePin = async () => {
    if (!selectedConversationId || !activeConv || actionInFlight) return;
    const convId = selectedConversationId;
    const newPinned = !activeConv.is_pinned;
    setActionInFlight(true);
    try {
      const updated = await apiClient.patch<SmsConversation>(
        `/api/admin/sms/conversations/${convId}/controls`,
        { is_pinned: newPinned }
      );
      setActiveConv(updated);
      setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      toast.success(newPinned ? "Thread pinned to top." : "Thread unpinned.");
    } catch (err: any) {
      toast.error(err.message || "Failed to update pin state.");
    } finally {
      setActionInFlight(false);
    }
  };

  // Block / Unblock
  const handleToggleBlock = async () => {
    if (!selectedConversationId || !activeConv || actionInFlight) return;
    const convId = selectedConversationId;
    const newBlocked = !activeConv.is_blocked;
    setActionInFlight(true);
    try {
      const updated = await apiClient.patch<SmsConversation>(
        `/api/admin/sms/conversations/${convId}/controls`,
        { is_blocked: newBlocked }
      );
      setActiveConv(updated);
      setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      toast.success(newBlocked ? "Contact blocked and auto-reply paused." : "Contact unblocked.");
    } catch (err: any) {
      toast.error(err.message || "Failed to update block state.");
    } finally {
      setActionInFlight(false);
    }
  };

  // Draft Approve / Discard / Edit
  const handleApproveDraft = async (msgId: string | number) => {
    if (!selectedConversationId || actionInFlight) return;
    setActionInFlight(true);
    try {
      await apiClient.post(`/api/admin/sms/conversations/messages/${msgId}/approve`);
      toast.success("Draft approved and queued for delivery.");
      loadMessages(selectedConversationId);
    } catch (err: any) {
      toast.error(err.message || "Failed to approve draft.");
    } finally {
      setActionInFlight(false);
    }
  };

  const handleDiscardDraft = async (msgId: string | number) => {
    if (!selectedConversationId || actionInFlight) return;
    setActionInFlight(true);
    try {
      await apiClient.post(`/api/admin/sms/conversations/messages/${msgId}/discard`);
      toast.success("Draft discarded.");
      loadMessages(selectedConversationId);
    } catch (err: any) {
      toast.error(err.message || "Failed to discard draft.");
    } finally {
      setActionInFlight(false);
    }
  };

  const handleSendEditedDraft = async (msgId: string | number, text: string) => {
    if (!selectedConversationId || !text.trim() || actionInFlight) return;
    setActionInFlight(true);
    try {
      await apiClient.post(`/api/admin/sms/conversations/drafts/${msgId}/review`, {
        action: "approve",
        text: text.trim(),
      });
      toast.success("Edited draft sent to customer.");
      loadMessages(selectedConversationId);
    } catch (err: any) {
      toast.error(err.message || "Failed to send edited draft.");
    } finally {
      setActionInFlight(false);
    }
  };

  // Submit AI Correction
  const handleSubmitCorrection = async (
    target: { messageId: string | number; text: string },
    reason: string,
    correctedWording?: string
  ) => {
    if (!selectedConversationId || !target || !reason.trim()) return;
    try {
      await apiClient.post(`/api/admin/sms/conversations/${selectedConversationId}/corrections`, {
        message_id: target.messageId,
        reason: reason.trim(),
        corrected_wording: correctedWording?.trim() || undefined,
        contains_dynamic_facts: false,
      });
      toast.success("AI correction evidence recorded.");
    } catch (err: any) {
      toast.error(err.message || "Failed to record correction.");
      throw err;
    }
  };

  // Submit Info Request Answer
  const handleSubmitInfoAnswer = async (answer: string) => {
    if (!selectedConversationId || !answer.trim()) return;
    try {
      await apiClient.post(
        `/api/admin/sms/conversations/${selectedConversationId}/answer-info-request`,
        {
          question: infoRequestPrompt || "Customer question",
          answer: answer.trim(),
          reply: answer.trim(),
          category: "faq",
        }
      );
      toast.success("Reply queued and knowledge proposal submitted for review.");
      setHasInfoRequest(false);
      loadMessages(selectedConversationId);
      loadConversations();
    } catch (err: any) {
      toast.error(err.message || "Failed to submit answer to info request.");
      throw err;
    }
  };

  const handleRemoveInfoRequest = async () => {
    if (!selectedConversationId || !activeConv) return;
    if (activeConv.state === "needs-review") {
      try {
        await apiClient.post(`/api/admin/sms/conversations/${selectedConversationId}/review-state/clear`, {});
      } catch {
        // Clear locally regardless
      }
    }
    setHasInfoRequest(false);
    toast.success("Information request dismissed.");
  };

  // Filtered & Sorted conversations
  const filteredConversations = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return conversations
      .filter((c) => {
        if (!q) return true;
        const name = (c.client_name || "").toLowerCase();
        const address = c.customer_address.toLowerCase();
        const preview = (c.last_message_preview || "").toLowerCase();
        return name.includes(q) || address.includes(q) || preview.includes(q);
      })
      .sort((a, b) => {
        if (a.is_pinned && !b.is_pinned) return -1;
        if (!a.is_pinned && b.is_pinned) return 1;
        return new Date(b.last_activity_at).getTime() - new Date(a.last_activity_at).getTime();
      });
  }, [conversations, searchQuery]);

  const isAiActive = Boolean(activeConv?.ai_enabled && activeConv?.state === "auto-reply");

  // Get Initials for Avatar
  const getInitials = (c: SmsConversation) => {
    if (c.client_name && c.client_name.trim()) {
      const parts = c.client_name.trim().split(/\s+/);
      if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      return parts[0].slice(0, 2).toUpperCase();
    }
    const clean = c.customer_address.replace(/\D/g, "");
    return clean ? clean.slice(-2) : "SMS";
  };

  // Map TimelineItems to ThreadMessages for AssistantThreadPanel
  const threadMessages: ThreadMessage[] = useMemo(() => {
    return messages.map((m) => {
      const isOutbound = m.direction === "outbound";
      const authorType = m.author_type === "ai" ? "ai" : m.author_type === "staff" ? "staff" : "customer";
      return {
        id: m.id,
        kind: m.kind,
        direction: isOutbound ? "outbound" : "inbound",
        authorType,
        body: m.body || "",
        status: m.status as any,
        occurredAt: m.occurred_at,
        meta: m.meta,
      };
    });
  }, [messages]);

  const bookingUrl = activeConv
    ? activeConv.booking_id
      ? `/admin/bookings?booking_id=${activeConv.booking_id}`
      : activeConv.client_id
        ? `/admin/bookings?client_id=${activeConv.client_id}&phone=${encodeURIComponent(
            activeConv.customer_address
          )}`
        : `/admin/bookings?phone=${encodeURIComponent(activeConv.customer_address || "")}`
    : null;

  return (
    <div className="flex-1 w-full flex flex-col overflow-hidden bg-background text-foreground">
      {/* Centered Mobile Card Layout */}
      <div className="mx-auto flex h-full w-full max-w-3xl flex-col bg-card text-card-foreground border-x border-border shadow-md relative overflow-hidden">
        {selectedConversationId === null ? (
          <>
            {/* List Header */}
            <header className="flex flex-col gap-2 border-b border-border bg-card px-3 py-2 shrink-0">
              <div className="flex items-center justify-between gap-2">
                {/* Search Bar Input */}
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Search conversations..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full rounded-full border border-border bg-muted/60 dark:bg-muted/30 py-1 pl-8 pr-7 text-xs text-foreground placeholder:text-muted-foreground focus:border-indigo-500 focus:bg-card focus:outline-none"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </div>

                {/* Global Catch-up Refresh Button */}
                <button
                  type="button"
                  onClick={() => {
                    setRefreshing(true);
                    loadConversations(true);
                  }}
                  disabled={refreshing}
                  title="Catch-up and refresh conversations"
                  className="flex items-center gap-1 rounded-full border border-border bg-muted/40 hover:bg-muted px-2 py-1 text-xs font-semibold text-foreground active:scale-95 transition-all shrink-0 cursor-pointer"
                >
                  <RefreshCw className={`h-3.5 w-3.5 text-indigo-500 ${refreshing ? "animate-spin" : ""}`} />
                  <span className="hidden sm:inline">Catch-up</span>
                </button>

                {/* Global AI Toggle Pill */}
                <button
                  type="button"
                  onClick={() => {
                    const next = !globalAiActive;
                    setGlobalAiActive(next);
                    toast.success(next ? "Global AI responses active." : "Global AI responses paused.");
                  }}
                  className={`flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-bold transition-all shrink-0 cursor-pointer border ${
                    globalAiActive
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                      : "bg-muted text-muted-foreground border-border"
                  }`}
                >
                  <span
                    className={`h-2 w-2 rounded-full ${globalAiActive ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground/50"}`}
                  />
                  <span>{globalAiActive ? "AI On" : "AI Off"}</span>
                </button>

                {/* Global Train Toggle Pill */}
                <button
                  type="button"
                  onClick={() => {
                    const next = !globalTrainActive;
                    setGlobalTrainActive(next);
                    toast.success(next ? "Interactive training mode enabled." : "Training mode disabled.");
                  }}
                  className={`flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-bold transition-all shrink-0 cursor-pointer border ${
                    globalTrainActive
                      ? "bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/30"
                      : "bg-muted text-muted-foreground border-border"
                  }`}
                >
                  <BrainCircuit className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Train</span>
                </button>
              </div>
            </header>

            {/* THREAD LIST */}
            <div className="flex-1 overflow-y-auto divide-y divide-border bg-card">
              {loading ? (
                <div className="p-8 text-center text-xs text-muted-foreground">Loading conversations...</div>
              ) : filteredConversations.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground space-y-2">
                  <MessageSquare className="h-10 w-10 text-muted-foreground/40" />
                  <p className="text-xs">No conversations matching your search.</p>
                </div>
              ) : (
                filteredConversations.map((conv) => {
                  const initials = getInitials(conv);
                  const hasDraft = conv.needs_review || conv.state === "needs-review";
                  const hasArrived = Boolean(conv.arrival_id);

                  return (
                    <button
                      key={conv.id}
                      type="button"
                      onClick={() => selectConversation(conv.id)}
                      className="w-full flex items-start gap-3 p-3.5 text-left hover:bg-muted/50 transition-colors cursor-pointer group"
                    >
                      {/* Gradient Avatar */}
                      <div className="h-11 w-11 shrink-0 rounded-full bg-gradient-to-tr from-indigo-500 to-violet-600 text-white font-bold flex items-center justify-center text-sm shadow-sm">
                        {initials}
                      </div>

                      {/* Thread Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <div className="flex items-center gap-1.5 truncate">
                            {conv.is_pinned && <Pin className="h-3 w-3 text-amber-500 fill-amber-500 shrink-0" />}
                            <span className="font-semibold text-xs text-foreground truncate">
                              {conv.client_name || conv.customer_address}
                            </span>
                          </div>
                          <span className="text-[10px] text-muted-foreground shrink-0 font-medium">
                            {new Date(conv.last_activity_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>

                        {/* Preview Snippet */}
                        <p className="text-[11px] text-muted-foreground truncate mt-0.5 line-clamp-1">
                          {conv.last_message_preview || "No message history"}
                        </p>

                        {/* Badges Row */}
                        <div className="flex items-center justify-between gap-1 mt-1.5">
                          <div className="flex items-center gap-1 flex-wrap">
                            <span className="bg-muted text-muted-foreground border border-border text-[9.5px] font-semibold px-1.5 py-0.5 rounded">
                              SMS
                            </span>
                            {hasArrived && (
                              <span className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 text-[9.5px] font-bold px-1.5 py-0.5 rounded">
                                Arrived
                              </span>
                            )}
                            {hasDraft && (
                              <span className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30 text-[9.5px] font-bold px-1.5 py-0.5 rounded">
                                Draft
                              </span>
                            )}
                            {conv.is_blocked && (
                              <span className="bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/30 text-[9.5px] font-bold px-1.5 py-0.5 rounded">
                                Blocked
                              </span>
                            )}
                          </div>

                          {/* Unread Pill */}
                          {conv.unread_count > 0 && (
                            <span className="bg-emerald-500 text-white rounded-full text-[10px] font-bold px-2 py-0.2 min-w-[18px] text-center">
                              {conv.unread_count}
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </>
        ) : (
          /* Active Thread Workspace */
          <AssistantThreadPanel
            mode="live"
            conversationId={selectedConversationId}
            title={activeConv?.client_name || activeConv?.customer_address || "Conversation"}
            subtitle="SMS · Active Chat"
            isPinned={activeConv?.is_pinned}
            isBlocked={activeConv?.is_blocked}
            aiActive={isAiActive}
            messages={threadMessages}
            infoRequest={{
              hasRequest: hasInfoRequest,
              prompt: infoRequestPrompt,
            }}
            onSubmitInfoAnswer={handleSubmitInfoAnswer}
            onDismissInfoRequest={handleRemoveInfoRequest}
            onSendMessage={handleSend}
            onToggleAi={handleToggleAi}
            onTogglePin={handleTogglePin}
            onToggleBlock={handleToggleBlock}
            onBack={() => selectConversation(null)}
            onApproveDraft={handleApproveDraft}
            onDiscardDraft={handleDiscardDraft}
            onEditAndSendDraft={handleSendEditedDraft}
            onSubmitCorrection={handleSubmitCorrection}
            bookingUrl={bookingUrl}
            customerName={activeConv?.client_name}
            actionInFlight={actionInFlight}
          />
        )}
      </div>
    </div>
  );
}
