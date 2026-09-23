import { useState, useEffect, useRef, useCallback } from "react";
import {
  MessageSquareText,
  Search,
  Send,
  Play,
  Ban,
  Sparkles,
  Pin,
  PinOff,
  CalendarDays,
  ShieldAlert,
  Edit3,
  Trash2,
  Bot,
  ChevronLeft,
  Clock3,
  ClipboardList,
  FileDown,
  Flag,
  NotebookPen,
  UserRound,
  CircleAlert,
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  compareConversationOrder,
  conversationStatePresentation,
  getOrCreateManualSendAttempt,
  isAutomationReleaseAllowed,
  matchesConversationFilter,
  shouldApplyConversationResponse,
  type ConversationFilter,
  type ManualSendAttempt,
} from "./operations-state";

interface SmsConversation {
  id: number;
  tenant_id: number;
  provider_id: number;
  sms_account_id: number;
  customer_address: string;
  client_id?: number;
  client_name?: string;
  state: string; // 'auto-reply', 'taken-over', 'paused', 'needs-review', 'escalated', 'resolved'
  unread_count: number;
  is_pinned: boolean;
  is_blocked: boolean;
  ai_enabled: boolean;
  last_activity_at: string;
  created_at: string;
  updated_at: string;
  // Optional enriched operations fields. They are rendered only when supplied
  // by the tenant-scoped backend contract.
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

interface SmsInboxTabProps {
  onNavigate?: (tabId: string) => void;
}

export default function SmsInboxTab({ onNavigate }: SmsInboxTabProps = {}) {
  const [conversations, setConversations] = useState<SmsConversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<TimelineItem[]>([]);
  const [activeConv, setActiveConv] = useState<SmsConversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [composeText, setComposeText] = useState("");
  const [sendingMessage, setSendingMessage] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterState, setFilterState] = useState<ConversationFilter>("all");

  // Draft Message Editing State
  const [editingDraftId, setEditingDraftId] = useState<number | null>(null);
  const [editingDraftBody, setEditingDraftBody] = useState("");
  const [pendingActionKey, setPendingActionKey] = useState<string | null>(null);

  type ActionDialogKind = "note" | "escalate" | "resolve" | "correction";
  const [actionDialog, setActionDialog] = useState<{ kind: ActionDialogKind; messageId?: number } | null>(null);
  const [actionReason, setActionReason] = useState("");
  const [correctedWording, setCorrectedWording] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const selectedConversationIdRef = useRef<number | null>(null);
  const loadSequenceRef = useRef(0);
  const manualSendAttemptRef = useRef<ManualSendAttempt | null>(null);
  const sendInFlightRef = useRef(false);
  const actionInFlightRef = useRef(false);

  const selectConversation = (conversationId: number | null) => {
    selectedConversationIdRef.current = conversationId;
    loadSequenceRef.current += 1;
    manualSendAttemptRef.current = null;
    setMessages([]);
    setActiveConv(null);
    setComposeText("");
    setSelectedConversationId(conversationId);
  };

  const loadConversations = useCallback(async () => {
    const selectedAtRequest = selectedConversationId;
    try {
      const res = await apiClient.get<SmsConversation[]>("/api/admin/sms/conversations");
      setConversations(res);

      if (selectedAtRequest && selectedConversationIdRef.current === selectedAtRequest) {
        const active = res.find(c => c.id === selectedAtRequest);
        if (active) setActiveConv(active);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load conversations.");
    } finally {
      setLoading(false);
    }
  }, [selectedConversationId]);

  useEffect(() => {
    loadConversations();
    const interval = setInterval(loadConversations, 10000);
    return () => clearInterval(interval);
  }, [loadConversations]);

  useEffect(() => {
    selectedConversationIdRef.current = selectedConversationId;
    loadSequenceRef.current += 1;
    manualSendAttemptRef.current = null;
    if (selectedConversationId) {
      loadMessages(selectedConversationId);
    } else {
      setMessages([]);
      setActiveConv(null);
    }
  }, [selectedConversationId]);

  const loadMessages = async (convId: number) => {
    const requestSequence = ++loadSequenceRef.current;
    try {
      const [timeline, detail] = await Promise.all([
        apiClient.get<TimelineItem[]>(`/api/admin/sms/conversations/${convId}/timeline`),
        apiClient.get<SmsConversation>(`/api/admin/sms/conversations/${convId}`),
      ]);
      if (!shouldApplyConversationResponse(
        convId,
        selectedConversationIdRef.current,
        requestSequence,
        loadSequenceRef.current,
      )) {
        return;
      }
      setMessages(timeline);
      setActiveConv(detail);

      // Clear local unread count
      setConversations(prev => prev.map(c => c.id === convId ? { ...c, unread_count: 0 } : c));

      setTimeout(scrollToBottom, 50);
    } catch (err: any) {
      if (shouldApplyConversationResponse(
        convId,
        selectedConversationIdRef.current,
        requestSequence,
        loadSequenceRef.current,
      )) {
        toast.error(err.message || "Failed to load messages.");
      }
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSend = async () => {
    if (
      sendInFlightRef.current
      || !composeText.trim()
      || !selectedConversationId
      || activeConv?.id !== selectedConversationId
    ) return;
    if (activeConv?.is_blocked) {
      toast.error("Cannot send SMS: Contact is currently blocked.");
      return;
    }

    const textToSend = composeText.trim();
    const conversationId = selectedConversationId;
    const attempt = getOrCreateManualSendAttempt(
      manualSendAttemptRef.current,
      conversationId,
      textToSend,
      () => crypto.randomUUID(),
    );
    manualSendAttemptRef.current = attempt;
    sendInFlightRef.current = true;
    setSendingMessage(true);
    setComposeText("");

    const payload = {
      body: textToSend,
      client_request_id: attempt.clientRequestId,
    };

    const optimisticMessage: TimelineItem = {
      kind: "message",
      id: -Date.now(),
      body: textToSend,
      direction: "outbound",
      author_type: "staff",
      status: "queued",
      occurred_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, optimisticMessage]);
    setTimeout(scrollToBottom, 50);

    try {
      await apiClient.post(`/api/admin/sms/conversations/${conversationId}/messages`, payload);
      manualSendAttemptRef.current = null;
      if (selectedConversationIdRef.current === conversationId) {
        loadMessages(conversationId);
      }
      loadConversations();
    } catch (err: any) {
      toast.error(err.message || "Failed to send message.");
      setMessages(prev => prev.filter(m => m.id !== optimisticMessage.id));
      if (selectedConversationIdRef.current === conversationId) {
        setComposeText(textToSend);
      }
    } finally {
      sendInFlightRef.current = false;
      setSendingMessage(false);
    }
  };

  // Toggle AI On / AI Off
  const handleToggleAi = async () => {
    if (!selectedConversationId || !activeConv || actionInFlightRef.current) return;
    const conversationId = selectedConversationId;
    const isActive = activeConv.state === "auto-reply" && activeConv.ai_enabled;
    if (!isActive && !isAutomationReleaseAllowed(activeConv)) {
      toast.error("This conversation must be unblocked and cleared from review, escalation, or resolution before automation can resume.");
      return;
    }

    actionInFlightRef.current = true;
    setPendingActionKey("automation");
    try {
      const endpoint = isActive ? "takeover" : "release";
      const updated = await apiClient.post<SmsConversation>(
        `/api/admin/sms/conversations/${conversationId}/${endpoint}`,
        {},
      );
      if (selectedConversationIdRef.current === conversationId) {
        setActiveConv(updated);
        loadMessages(conversationId);
      }
      setConversations(prev => prev.map(c => c.id === updated.id ? updated : c));
      toast.success(isActive ? "Human takeover enabled." : "Conversation released to automated handling.");
    } catch (err: any) {
      toast.error(err.message || "Failed to update automated handling.");
    } finally {
      actionInFlightRef.current = false;
      setPendingActionKey(null);
    }
  };

  const updateControls = async (
    patch: Partial<Pick<SmsConversation, "ai_enabled" | "is_pinned" | "is_blocked">>,
    successMessage: string,
  ) => {
    if (!selectedConversationId || actionInFlightRef.current) return;
    const conversationId = selectedConversationId;
    actionInFlightRef.current = true;
    setPendingActionKey("controls");
    try {
      const updated = await apiClient.patch<SmsConversation>(
        `/api/admin/sms/conversations/${conversationId}/controls`,
        patch,
      );
      if (selectedConversationIdRef.current === conversationId) {
        setActiveConv(updated);
        loadMessages(conversationId);
      }
      setConversations((current) => current.map((item) => item.id === updated.id ? updated : item));
      toast.success(successMessage);
    } catch (err: any) {
      toast.error(err.message || "Unable to update conversation controls.");
    } finally {
      actionInFlightRef.current = false;
      setPendingActionKey(null);
    }
  };

  const handleTogglePin = async () => {
    if (!activeConv) return;
    await updateControls(
      { is_pinned: !activeConv.is_pinned },
      activeConv.is_pinned ? "Conversation unpinned." : "Conversation pinned.",
    );
  };

  const handleToggleBlock = async () => {
    if (!activeConv) return;
    await updateControls(
      { is_blocked: !activeConv.is_blocked },
      activeConv.is_blocked ? "Contact unblocked." : "Contact blocked and automated replies paused.",
    );
  };

  // AI Draft Actions
  const handleDraftAction = async (msgId: number, action: "approve" | "discard") => {
    if (actionInFlightRef.current) return;
    actionInFlightRef.current = true;
    setPendingActionKey(`draft-${msgId}`);
    try {
      await apiClient.post(`/api/admin/sms/conversations/messages/${msgId}/${action}`);
      toast.success(action === "approve" ? "Draft approved and queued for delivery." : "Draft discarded.");
      if (selectedConversationId) loadMessages(selectedConversationId);
    } catch (err: any) {
      toast.error(err.message || `Draft ${action} failed.`);
    } finally {
      actionInFlightRef.current = false;
      setPendingActionKey(null);
    }
  };

  const handleApproveDraft = (msgId: number) => handleDraftAction(msgId, "approve");
  const handleDiscardDraft = (msgId: number) => handleDraftAction(msgId, "discard");

  const handleStartEditDraft = (msg: TimelineItem) => {
    setEditingDraftId(msg.id);
    setEditingDraftBody(msg.body || "");
  };

  const handleSaveAndSendEditedDraft = async (msgId: number) => {
    if (!editingDraftBody.trim() || !selectedConversationId || actionInFlightRef.current) return;
    actionInFlightRef.current = true;
    setPendingActionKey(`draft-${msgId}`);
    try {
      await apiClient.post(`/api/admin/sms/conversations/drafts/${msgId}/review`, {
        action: "approve",
        text: editingDraftBody.trim(),
      });
      toast.success("Edited draft approved and queued for delivery.");
      setEditingDraftId(null);
      loadMessages(selectedConversationId);
    } catch (err: any) {
      toast.error(err.message || "Failed to send edited draft.");
    } finally {
      actionInFlightRef.current = false;
      setPendingActionKey(null);
    }
  };

  const applyConversationUpdate = (updated: SmsConversation) => {
    if (selectedConversationIdRef.current === updated.id) {
      setActiveConv(updated);
    }
    setConversations((current) => current.map((item) => item.id === updated.id ? updated : item));
  };

  const runLifecycleAction = async (action: "escalate" | "resolve" | "release" | "review-state/clear", reason?: string) => {
    if (!selectedConversationId || actionInFlightRef.current) return;
    const conversationId = selectedConversationId;
    actionInFlightRef.current = true;
    setPendingActionKey(action);
    try {
      const updated = await apiClient.post<SmsConversation>(
        `/api/admin/sms/conversations/${conversationId}/${action}`,
        reason?.trim() ? { reason: reason.trim() } : {},
      );
      applyConversationUpdate(updated);
      await loadMessages(conversationId);
      toast.success(
        action === "escalate" ? "Conversation escalated."
          : action === "resolve" ? "Conversation resolved."
            : action === "review-state/clear" ? "Review-only state cleared; drafts were retained."
              : "Conversation released to automated handling.",
      );
    } catch (err: any) {
      toast.error(err.message || "Conversation action failed.");
    } finally {
      actionInFlightRef.current = false;
      setPendingActionKey(null);
    }
  };

  const openActionDialog = (kind: ActionDialogKind) => {
    if (kind === "correction") {
      const aiMessage = [...messages].reverse().find((item) => (
        item.kind === "message"
        && item.author_type === "ai"
        && item.status !== "draft"
      ));
      if (!aiMessage) {
        toast.error("No sent AI response is available to correct in this conversation.");
        return;
      }
      setActionDialog({ kind, messageId: aiMessage.id });
    } else {
      setActionDialog({ kind });
    }
    setActionReason("");
    setCorrectedWording("");
  };

  const submitActionDialog = async () => {
    if (!actionDialog || !selectedConversationId || !actionReason.trim() || actionInFlightRef.current) return;
    const conversationId = selectedConversationId;
    actionInFlightRef.current = true;
    setPendingActionKey(actionDialog.kind);
    try {
      if (actionDialog.kind === "note") {
        await apiClient.post(`/api/admin/sms/conversations/${conversationId}/notes`, {
          text: actionReason.trim(),
        });
        toast.success("Internal note added.");
      } else if (actionDialog.kind === "correction") {
        await apiClient.post(`/api/admin/sms/conversations/${conversationId}/corrections`, {
          message_id: actionDialog.messageId,
          reason: actionReason.trim(),
          corrected_wording: correctedWording.trim() || undefined,
          contains_dynamic_facts: false,
        });
        toast.success("Correction evidence recorded. Live AI knowledge was not changed.");
      } else {
        const updated = await apiClient.post<SmsConversation>(
          `/api/admin/sms/conversations/${conversationId}/${actionDialog.kind}`,
          { reason: actionReason.trim() },
        );
        applyConversationUpdate(updated);
        toast.success(actionDialog.kind === "escalate" ? "Conversation escalated." : "Conversation resolved.");
      }
      setActionDialog(null);
      await loadMessages(conversationId);
      loadConversations();
    } catch (err: any) {
      toast.error(err.message || "Unable to complete this action.");
    } finally {
      actionInFlightRef.current = false;
      setPendingActionKey(null);
    }
  };

  // Filter & Sort Conversations (pinned always first)
  const filteredConversations = conversations
    .filter((conversation) => matchesConversationFilter(conversation, filterState, searchQuery))
    .sort(compareConversationOrder);

  const getMessageStatus = (status: string) => {
    switch (status.toLowerCase()) {
      case "queued":
        return <span className="text-[9px] text-muted-foreground">Queued</span>;
      case "sending":
        return <span className="text-[9px] text-blue-500 animate-pulse">Sending</span>;
      case "sent":
        return <span className="text-[9px] text-blue-600">Sent</span>;
      case "delivered":
        return <span className="text-[9px] text-emerald-600 font-bold">✓ Delivered</span>;
      case "failed":
        return <span className="text-[9px] text-red-500 font-semibold">✕ Failed</span>;
      default:
        return null;
    }
  };

  const isCurrentContactBlocked = Boolean(activeConv?.is_blocked);
  const isCurrentConvPinned = Boolean(activeConv?.is_pinned);
  const isAiActive = Boolean(activeConv?.ai_enabled && activeConv.state === "auto-reply");
  const canReleaseAutomation = activeConv ? isAutomationReleaseAllowed(activeConv) : false;
  const automationControlDisabled = pendingActionKey !== null || (!isAiActive && !canReleaseAutomation);
  const automationRestriction = activeConv && !isAiActive && !canReleaseAutomation
    ? activeConv.is_blocked
      ? "Unblock this contact before returning it to automated handling."
      : activeConv.state === "needs-review"
        ? "Clear the review-only state before returning this thread to automation."
        : activeConv.state === "escalated"
          ? "Resolve the escalation before returning this thread to automation."
          : activeConv.state === "resolved"
            ? "Resolved conversations cannot resume automation directly."
            : "This conversation is not eligible for automated handling."
    : null;

  return (
    <div className="flex flex-1 h-full min-h-0 rounded-xl border bg-card overflow-hidden text-xs">
      {/* Side Conversation List - Hidden on mobile if a conversation is selected */}
      <div className={`w-full sm:w-80 border-r flex flex-col bg-muted/20 ${selectedConversationId !== null ? "hidden sm:flex" : "flex"}`}>
        <div className="p-2 sm:p-3 border-b space-y-1.5 sm:space-y-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input 
              aria-label="Search SMS conversations"
              placeholder="Search conversations..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs bg-background"
            />
          </div>
          <div className="flex items-center justify-between gap-1 flex-wrap">
            <div className="flex gap-1 sm:gap-1.5 flex-wrap" aria-label="Conversation filters">
              <Button size="xs" variant={filterState === "all" ? "default" : "outline"} onClick={() => setFilterState("all")}>All</Button>
              <Button size="xs" variant={filterState === "automatic" ? "default" : "outline"} onClick={() => setFilterState("automatic")}>Automatic</Button>
              <Button size="xs" variant={filterState === "review" ? "default" : "outline"} onClick={() => setFilterState("review")}>Needs review</Button>
              <Button size="xs" variant={filterState === "takeover" ? "default" : "outline"} onClick={() => setFilterState("takeover")}>Human</Button>
              <Button size="xs" variant={filterState === "escalated" ? "default" : "outline"} onClick={() => setFilterState("escalated")}>Escalated</Button>
              <Button size="xs" variant={filterState === "resolved" ? "default" : "outline"} onClick={() => setFilterState("resolved")}>Resolved</Button>
            </div>
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {loading ? (
              <div className="p-4 text-center text-muted-foreground">Loading threads...</div>
            ) : filteredConversations.length === 0 ? (
              <div className="p-6 text-center space-y-3">
                <MessageSquareText className="w-8 h-8 text-muted-foreground/30 mx-auto" />
                <div className="text-muted-foreground text-xs">No conversations found.</div>
                {onNavigate && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1.5 text-xs mx-auto block"
                    onClick={() => onNavigate("simulator")}
                  >
                    Open Simulator Panel
                  </Button>
                )}
              </div>
            ) : (
              filteredConversations.map(conv => {
                const isPinned = conv.is_pinned;
                const statePresentation = conversationStatePresentation(conv);
                const stateClass = statePresentation.tone === "automatic"
                  ? "border-indigo-500/20 text-indigo-600 bg-indigo-500/5"
                  : statePresentation.tone === "review"
                    ? "border-orange-500/30 text-orange-700 bg-orange-500/10"
                    : statePresentation.tone === "danger"
                      ? "border-red-500/30 text-red-700 bg-red-500/10"
                      : "border-muted-foreground/20 text-muted-foreground bg-muted/40";

                return (
                  <button
                    type="button"
                    key={conv.id}
                    onClick={() => selectConversation(conv.id)}
                    className={`w-full p-3 rounded-lg cursor-pointer text-left transition-colors border relative ${
                      selectedConversationId === conv.id
                        ? "bg-primary/5 border-primary/20 text-primary-foreground"
                        : "hover:bg-muted/40 border-transparent"
                    }`}
                  >
                    <div className="flex justify-between items-start gap-1">
                      <div className="flex items-center gap-1.5 truncate">
                        {isPinned && (
                          <Pin className="w-3 h-3 text-amber-500 fill-amber-500 flex-shrink-0" />
                        )}
                        <span className="font-semibold text-foreground truncate">
                          {conv.client_name || conv.customer_address}
                        </span>
                      </div>
                      <span className="text-[10px] text-muted-foreground flex-shrink-0">
                        {new Date(conv.last_activity_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>

                    {conv.client_name && (
                      <div className="text-[10px] text-muted-foreground font-mono mt-0.5">{conv.customer_address}</div>
                    )}

                    {conv.last_message_preview && (
                      <p className="mt-1 truncate text-[10px] text-muted-foreground">
                        {conv.last_message_preview}
                      </p>
                    )}

                    <div className="flex items-center justify-between mt-2">
                      <div className="flex gap-1 items-center flex-wrap">
                        <Badge variant="outline" className={`text-[9px] px-1 py-0 ${stateClass}`}>
                          {statePresentation.label}
                        </Badge>
                        {conv.priority && conv.priority !== "normal" && (
                          <Badge variant="outline" className="text-[9px] px-1 py-0 border-orange-500/30 text-orange-700 bg-orange-500/10 gap-0.5">
                            <Flag className="size-2.5" /> {conv.priority}
                          </Badge>
                        )}
                        {conv.sla_due_at && (
                          <Badge variant="outline" className="text-[9px] px-1 py-0 gap-0.5">
                            <Clock3 className="size-2.5" /> due {new Date(conv.sla_due_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </Badge>
                        )}
                        {conv.booking_id && (
                          <CalendarDays className="size-3 text-blue-600" aria-label="Linked booking" />
                        )}
                        {conv.arrival_id && (
                          <UserRound className="size-3 text-emerald-600" aria-label="Active arrival" />
                        )}
                      </div>
                      {conv.unread_count > 0 && (
                        <Badge className="bg-primary text-primary-foreground text-[10px] h-4 min-w-4 px-1 rounded-full flex items-center justify-center">
                          {conv.unread_count}
                        </Badge>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Conversation Thread Panel - Hidden on mobile if NO conversation is selected */}
      <div className={`flex-1 flex flex-col bg-background min-w-0 ${selectedConversationId === null ? "hidden sm:flex" : "flex"}`}>
        {activeConv ? (
          <>
            {/* Thread Header */}
            <div className="p-2 sm:p-2.5 border-b flex justify-between items-center bg-muted/10 gap-1.5">
              <div className="flex items-center gap-1.5 min-w-0 flex-1">
                {/* Mobile Back Button */}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => selectConversation(null)}
                  className="sm:hidden h-10 w-10 min-h-[44px] min-w-[44px] p-0 shrink-0 text-muted-foreground hover:text-foreground touch-manipulation flex items-center justify-center"
                >
                  <ChevronLeft className="h-5 w-5" />
                  <span className="sr-only">Back to conversations</span>
                </Button>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <h3 className="font-semibold text-xs sm:text-sm truncate">{activeConv.client_name || activeConv.customer_address}</h3>
                    {isCurrentConvPinned && (
                      <Badge variant="outline" className="text-[9px] text-amber-600 border-amber-500/30 bg-amber-500/10 gap-0.5 py-0 px-1 shrink-0">
                        <Pin className="w-2 h-2 fill-amber-600" /> <span className="hidden sm:inline">Pin</span>
                      </Badge>
                    )}
                    {isCurrentContactBlocked && (
                      <Badge variant="destructive" className="text-[9px] py-0 px-1 gap-0.5 shrink-0">
                        <Ban className="w-2 h-2" /> <span className="hidden sm:inline">Block</span>
                      </Badge>
                    )}
                  </div>
                  {activeConv.client_name && (
                    <p className="text-[9px] sm:text-[10px] text-muted-foreground font-mono truncate">{activeConv.customer_address}</p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                {/* AI Toggle Header Button */}
                {isAiActive ? (
                  <Button size="xs" variant="outline" className="text-amber-600 hover:text-amber-700 h-7 text-[10px] sm:text-xs px-2" onClick={handleToggleAi} disabled={automationControlDisabled} aria-label="Pause automated replies">
                    <Ban className="w-3 h-3 sm:mr-1" />
                    <span className="hidden sm:inline">Pause AI</span>
                  </Button>
                ) : (
                  <Button size="xs" variant="outline" className="text-indigo-600 hover:text-indigo-700 h-7 text-[10px] sm:text-xs px-2" onClick={handleToggleAi} disabled={automationControlDisabled} aria-label="Resume automated replies" aria-describedby={automationRestriction ? "automation-restriction" : undefined}>
                    <Play className="w-3 h-3 sm:mr-1" />
                    <span className="hidden sm:inline">Resume AI</span>
                  </Button>
                )}
              </div>
            </div>

            {automationRestriction && (
              <div id="automation-restriction" role="status" className="flex items-center gap-1.5 border-b bg-amber-500/10 px-3 py-1.5 text-[11px] text-amber-800 dark:text-amber-200">
                <CircleAlert className="size-3.5 shrink-0" />
                {automationRestriction}
              </div>
            )}

            {/* Blocked Alert Banner */}
            {isCurrentContactBlocked && (
              <div className="bg-red-500/15 border-b border-red-500/30 px-3 py-1.5 text-[11px] text-red-700 dark:text-red-300 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>This contact is blocked. Inbound auto-replies and outbound SMS are disabled.</span>
                </div>
                <Button size="xs" variant="outline" className="h-6 text-[10px] border-red-400" onClick={handleToggleBlock}>
                  Unblock Contact
                </Button>
              </div>
            )}

            <div className="flex items-center gap-1.5 overflow-x-auto border-b bg-muted/5 px-3 py-2" aria-label="Conversation actions and linked context">
              {activeConv.client_id ? (
                <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" asChild>
                  <a href={`/admin/clients?client_id=${activeConv.client_id}`}><UserRound className="size-3" /> Client</a>
                </Button>
              ) : (
                <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" disabled title="No client is linked to this conversation">
                  <UserRound className="size-3" /> Client
                </Button>
              )}
              <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" asChild>
                <a href={activeConv.booking_id ? `/admin/bookings?booking_id=${activeConv.booking_id}` : "/admin/bookings"}>
                  <CalendarDays className="size-3" /> Bookings
                </a>
              </Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" onClick={() => onNavigate?.("arrivals")}>
                <UserRound className="size-3" /> Arrivals
              </Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" onClick={() => onNavigate?.("triage")}>
                <ClipboardList className="size-3" /> Review queue
              </Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" onClick={() => openActionDialog("note")} disabled={pendingActionKey !== null}>
                <NotebookPen className="size-3" /> Add note
              </Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0" onClick={() => openActionDialog("escalate")} disabled={pendingActionKey !== null || activeConv.state === "resolved"}>Escalate</Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0" onClick={() => openActionDialog("resolve")} disabled={pendingActionKey !== null || activeConv.state === "resolved"}>Resolve</Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" onClick={() => openActionDialog("correction")} disabled={pendingActionKey !== null}>
                <Edit3 className="size-3" /> Correct AI
              </Button>
              {activeConv.state === "needs-review" && (
                <Button size="xs" variant="outline" className="h-7 shrink-0" onClick={() => runLifecycleAction("review-state/clear")} disabled={pendingActionKey !== null}>
                  Clear review flag
                </Button>
              )}
              <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" disabled aria-describedby="csv-export-unavailable">
                <FileDown className="size-3" /> Export
              </Button>
              <span id="csv-export-unavailable" className="shrink-0 text-[10px] text-muted-foreground">CSV export is awaiting an approved backend contract.</span>
            </div>

            {/* Messages Scroll Area */}
            <ScrollArea className="flex-1 p-4 bg-muted/5">
              <div className="space-y-3">
                {messages.map((msg) => {
                  const isInbound = msg.direction === "inbound";
                  const isDraft = msg.status === "draft";
                  const isOperationalEvent = msg.kind === "event";
                  const isInternalNote = msg.kind === "internal_note";
                  const isEditingThisDraft = editingDraftId === msg.id;

                  if (isOperationalEvent || isInternalNote) {
                    return (
                      <div key={`${msg.kind}-${msg.id}`} className="mx-auto max-w-2xl rounded-lg border border-dashed bg-muted/40 px-3 py-2 text-center text-[11px] text-muted-foreground">
                        <div className="font-semibold text-foreground">
                          {isInternalNote ? "Internal note" : (msg.event_type || "Operational event").replaceAll("_", " ")}
                        </div>
                        {msg.body && <p className="mt-0.5 whitespace-pre-wrap">{msg.body}</p>}
                        {isOperationalEvent && typeof msg.meta?.reason === "string" && (
                          <p className="mt-0.5 whitespace-pre-wrap">Reason: {msg.meta.reason}</p>
                        )}
                        <time className="mt-1 block text-[9px]">{new Date(msg.occurred_at).toLocaleString()}</time>
                      </div>
                    );
                  }

                  return (
                    <div 
                      key={`${msg.kind}-${msg.id}`}
                      className={`flex flex-col max-w-[85%] sm:max-w-[70%] ${isInbound ? "self-start mr-auto" : "self-end ml-auto"}`}
                    >
                      <div className={`p-3 rounded-lg text-xs leading-relaxed ${
                        isDraft 
                          ? "bg-indigo-50 border border-indigo-200 text-indigo-950 shadow-xs" 
                          : isInbound 
                            ? "bg-muted text-foreground" 
                            : "bg-primary text-primary-foreground"
                      }`}>
                        {isDraft && (
                          <div className="flex items-center gap-1.5 text-[9px] font-semibold text-indigo-700 mb-1.5">
                            <Sparkles className="w-3 h-3" /> Proposed AI Draft (Awaiting Approval)
                          </div>
                        )}

                        {isEditingThisDraft ? (
                          <div className="space-y-2">
                            <Textarea
                              aria-label="Edit proposed AI draft"
                              value={editingDraftBody}
                              onChange={(e) => setEditingDraftBody(e.target.value)}
                              rows={3}
                              maxLength={1600}
                              className="text-xs bg-white text-foreground border-indigo-300"
                            />
                            <div className="flex gap-1.5 justify-end">
                              <Button
                                size="xs"
                                variant="outline"
                                className="h-6 text-[11px] bg-white"
                                onClick={() => setEditingDraftId(null)}
                              >
                                Cancel
                              </Button>
                              <Button
                                size="xs"
                                className="h-6 text-[11px] bg-indigo-600 text-white"
                                onClick={() => handleSaveAndSendEditedDraft(msg.id)}
                                disabled={pendingActionKey !== null || !editingDraftBody.trim()}
                              >
                                <Send className="w-3 h-3 mr-1" /> Send Edited
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <p className="whitespace-pre-wrap">{msg.body}</p>

                            {/* AI Draft Action Buttons: Edit, Discard, Send */}
                            {isDraft && (
                              <div className="flex gap-1.5 mt-2.5 border-t border-indigo-200/50 pt-2 justify-end">
                                <Button
                                  size="xs"
                                  variant="outline"
                                  className="bg-white border-indigo-300 text-indigo-700 hover:bg-indigo-50 h-7 text-[11px] gap-1"
                                  onClick={() => handleStartEditDraft(msg)}
                                  disabled={pendingActionKey !== null}
                                >
                                  <Edit3 className="w-3 h-3" /> Edit
                                </Button>
                                <Button
                                  size="xs"
                                  variant="outline"
                                  className="bg-white border-red-200 text-red-600 hover:bg-red-50 h-7 text-[11px] gap-1"
                                  onClick={() => handleDiscardDraft(msg.id)}
                                  disabled={pendingActionKey !== null}
                                >
                                  <Trash2 className="w-3 h-3" /> Discard
                                </Button>
                                <Button
                                  size="xs"
                                  className="bg-indigo-600 hover:bg-indigo-700 text-white h-7 text-[11px] gap-1"
                                  onClick={() => handleApproveDraft(msg.id)}
                                  disabled={pendingActionKey !== null}
                                >
                                  <Send className="w-3 h-3" /> Send
                                </Button>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                      
                      <div className={`flex items-center gap-1.5 mt-1 text-[9px] text-muted-foreground ${
                        isInbound ? "justify-start" : "justify-end"
                      }`}>
                        <span>{new Date(msg.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        {!isInbound && msg.status && getMessageStatus(msg.status)}
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            {/* Input Composer */}
            <div className="p-3 border-t bg-muted/10 space-y-2">
              <div className="flex gap-2">
                <Input 
                  aria-label="Manual SMS reply"
                  disabled={isCurrentContactBlocked || sendingMessage}
                  placeholder={
                    isCurrentContactBlocked
                      ? "Contact is blocked. Unblock to send messages."
                      : activeConv.state === "taken-over"
                        ? "Type reply..."
                        : "Type reply (sending manually will automatically pause the AI)..."
                  } 
                  value={composeText}
                  onChange={e => {
                    setComposeText(e.target.value);
                    if (manualSendAttemptRef.current?.body !== e.target.value.trim()) {
                      manualSendAttemptRef.current = null;
                    }
                  }}
                  onKeyDown={e => e.key === "Enter" && handleSend()}
                  className="flex-1 h-9 text-xs bg-background"
                />
                <Button size="sm" onClick={handleSend} disabled={isCurrentContactBlocked || sendingMessage || !composeText.trim()} aria-label={sendingMessage ? "Sending message" : "Send manual SMS"}>
                  <Send className="w-4 h-4" />
                </Button>
              </div>

              {/* Conversation controls directly beneath the composer */}
              <div className="flex items-center gap-1.5 pt-1 pb-0.5 overflow-x-auto no-scrollbar scroll-smooth">
                <Button
                  type="button"
                  size="xs"
                  variant={isAiActive ? "default" : "outline"}
                  onClick={handleToggleAi}
                  disabled={automationControlDisabled}
                  aria-describedby={automationRestriction ? "automation-restriction" : undefined}
                  className={`h-7 text-xs px-2.5 gap-1.5 shrink-0 transition-all ${
                    isAiActive
                      ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                      : "border-muted-foreground/30 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full ${isAiActive ? "bg-white animate-pulse" : "bg-zinc-400"}`} />
                  <Bot className="w-3 h-3" />
                  <span>{isAiActive ? "AI On" : "AI Off"}</span>
                </Button>

                <Button type="button" size="xs" variant="outline" className="h-7 text-xs px-2.5 gap-1.5 shrink-0 border-blue-500/30 text-blue-600 hover:bg-blue-500/5" asChild>
                  <a href="/admin/bookings"><CalendarDays className="w-3 h-3" /><span>Bookings</span></a>
                </Button>

                {/* 4. Pin / Unpin */}
                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  onClick={handleTogglePin}
                  disabled={pendingActionKey !== null}
                  className={`h-7 text-xs px-2.5 gap-1.5 shrink-0 ${
                    isCurrentConvPinned
                      ? "text-amber-600 bg-amber-500/10 hover:bg-amber-500/20"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {isCurrentConvPinned ? (
                    <>
                      <PinOff className="w-3 h-3" />
                      <span>Unpin</span>
                    </>
                  ) : (
                    <>
                      <Pin className="w-3 h-3" />
                      <span>Pin</span>
                    </>
                  )}
                </Button>

                {/* 5. Block / Unblock */}
                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  onClick={handleToggleBlock}
                  disabled={pendingActionKey !== null}
                  className={`h-7 text-xs px-2.5 gap-1.5 shrink-0 ${
                    isCurrentContactBlocked
                      ? "text-red-600 bg-red-500/10 hover:bg-red-500/20"
                      : "text-muted-foreground hover:text-red-600"
                  }`}
                >
                  <Ban className="w-3 h-3" />
                  <span>{isCurrentContactBlocked ? "Unblock" : "Block"}</span>
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col justify-center items-center text-muted-foreground p-8">
            <MessageSquareText className="w-12 h-12 text-muted-foreground/20 mb-2" />
            <p>Select a conversation from the sidebar to view thread history and message clients.</p>
          </div>
        )}
      </div>

      <Dialog
        open={actionDialog !== null}
        onOpenChange={(open) => {
          if (!open && pendingActionKey === null) setActionDialog(null);
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {actionDialog?.kind === "note" ? "Add internal note"
                : actionDialog?.kind === "escalate" ? "Escalate conversation"
                  : actionDialog?.kind === "resolve" ? "Resolve conversation"
                    : "Record AI correction"}
            </DialogTitle>
            <DialogDescription>
              {actionDialog?.kind === "note"
                ? "Visible to authorised staff only. This note is never sent to the customer."
                : actionDialog?.kind === "correction"
                  ? "Explain what was wrong. This records audit and learning evidence but never changes live AI knowledge automatically."
                  : "A reason is required and will be retained in the operational audit timeline."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="sms-action-reason">
                {actionDialog?.kind === "note" ? "Internal note"
                  : actionDialog?.kind === "resolve" ? "Resolution note"
                    : actionDialog?.kind === "correction" ? "Why was the AI response wrong?"
                      : "Escalation reason"}
              </Label>
              <Textarea
                id="sms-action-reason"
                value={actionReason}
                onChange={(event) => setActionReason(event.target.value)}
                rows={4}
                maxLength={actionDialog?.kind === "note" ? 4000 : actionDialog?.kind === "correction" ? 2000 : 1000}
                autoFocus
              />
            </div>

            {actionDialog?.kind === "correction" && (
              <div className="space-y-1.5">
                <Label htmlFor="sms-corrected-wording">Corrected wording (optional)</Label>
                <Textarea
                  id="sms-corrected-wording"
                  value={correctedWording}
                  onChange={(event) => setCorrectedWording(event.target.value)}
                  rows={3}
                  maxLength={2000}
                />
                <p className="text-[11px] text-muted-foreground">
                  Prices, times, availability, links, customer data, and payment details remain live facts and are never promoted to reusable knowledge here.
                </p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setActionDialog(null)} disabled={pendingActionKey !== null}>Cancel</Button>
            <Button onClick={submitActionDialog} disabled={!actionReason.trim() || pendingActionKey !== null}>
              {pendingActionKey === actionDialog?.kind ? "Saving..." : "Save audited action"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
