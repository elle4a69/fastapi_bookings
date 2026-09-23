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
  Wrench,
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
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { QuickToolsSheet } from "./quick-tools-sheet";
import {
  compareConversationOrder,
  matchesConversationFilter,
  type ConversationFilter,
} from "./operations-state";

interface SmsConversation {
  id: number;
  tenant_id: number;
  provider_id: number;
  sms_account_id: number;
  customer_address: string;
  client_id?: number;
  client_name?: string;
  state: string; // 'auto-reply', 'taken-over', 'paused', 'info-needed'
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

interface SmsMessage {
  id: number;
  body: string;
  direction: string; // 'inbound', 'outbound', 'draft'
  author_type: string; // 'customer', 'staff', 'fixed_autoresponder', 'ai', 'system'
  status: string; // 'received', 'queued', 'sending', 'sent', 'delivered', 'failed', 'cancelled', 'draft', 'discarded'
  occurred_at: string;
  client_request_id?: string;
  event_type?: string;
}

interface SmsInboxTabProps {
  onNavigate?: (tabId: string) => void;
}

export default function SmsInboxTab({ onNavigate }: SmsInboxTabProps = {}) {
  const [conversations, setConversations] = useState<SmsConversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<SmsMessage[]>([]);
  const [activeConv, setActiveConv] = useState<SmsConversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [seedingScenarios, setSeedingScenarios] = useState(false);
  const [composeText, setComposeText] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterState, setFilterState] = useState<ConversationFilter>("all");

  // Quick Tools Sheet
  const [toolsSheetOpen, setToolsSheetOpen] = useState(false);

  // Draft Message Editing State
  const [editingDraftId, setEditingDraftId] = useState<number | null>(null);
  const [editingDraftBody, setEditingDraftBody] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async () => {
    try {
      const res = await apiClient.get<SmsConversation[]>("/api/admin/sms/conversations");
      setConversations(res);
      
      if (selectedConversationId) {
        const active = res.find(c => c.id === selectedConversationId);
        if (active) setActiveConv(active);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load conversations.");
    } finally {
      setLoading(false);
    }
  }, [selectedConversationId]);

  const handlePreloadScenarios = async () => {
    setSeedingScenarios(true);
    try {
      const res = await apiClient.post<any>("/api/admin/sms/conversations/seed-scenarios", {
        clear_existing: true
      });
      toast.success("16 Test Scenarios Injected!", {
        description: res.message || "Populated Client 1..5 test conversations."
      });
      const updated = await apiClient.get<SmsConversation[]>("/api/admin/sms/conversations");
      setConversations(updated);
      if (updated.length > 0) {
        setSelectedConversationId(updated[0].id);
        setActiveConv(updated[0]);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to seed test scenarios.");
    } finally {
      setSeedingScenarios(false);
    }
  };

  useEffect(() => {
    loadConversations();
    const interval = setInterval(loadConversations, 10000);
    return () => clearInterval(interval);
  }, [loadConversations]);

  useEffect(() => {
    if (selectedConversationId) {
      loadMessages(selectedConversationId);
    } else {
      setMessages([]);
      setActiveConv(null);
    }
  }, [selectedConversationId]);

  const loadMessages = async (convId: number) => {
    try {
      const msgs = await apiClient.get<SmsMessage[]>(`/api/admin/sms/conversations/${convId}/messages`);
      setMessages(msgs);
      
      const detail = await apiClient.get<SmsConversation>(`/api/admin/sms/conversations/${convId}`);
      setActiveConv(detail);
      
      // Clear local unread count
      setConversations(prev => prev.map(c => c.id === convId ? { ...c, unread_count: 0 } : c));
      
      setTimeout(scrollToBottom, 50);
    } catch (err: any) {
      toast.error(err.message || "Failed to load messages.");
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSend = async () => {
    if (!composeText.trim() || !selectedConversationId) return;
    if (activeConv?.is_blocked) {
      toast.error("Cannot send SMS: Contact is currently blocked.");
      return;
    }

    const textToSend = composeText;
    setComposeText("");

    const clientReqId = `click-${Date.now()}`;
    const payload = {
      body: textToSend,
      client_request_id: clientReqId
    };

    const optimisticMessage: SmsMessage = {
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
      await apiClient.post(`/api/admin/sms/conversations/${selectedConversationId}/messages`, payload);
      loadMessages(selectedConversationId);
      loadConversations();
    } catch (err: any) {
      toast.error(err.message || "Failed to send message.");
      setMessages(prev => prev.filter(m => m.id !== optimisticMessage.id));
    }
  };

  // Toggle AI On / AI Off
  const handleToggleAi = async () => {
    if (!selectedConversationId || !activeConv) return;
    if (activeConv.state === "auto-reply") {
      try {
        const updated = await apiClient.post<SmsConversation>(`/api/admin/sms/conversations/${selectedConversationId}/takeover`);
        setActiveConv(updated);
        setConversations(prev => prev.map(c => c.id === updated.id ? updated : c));
        toast.info("AI turned OFF. Human takeover mode active.");
      } catch (err: any) {
        toast.error(err.message || "Failed to toggle AI mode.");
      }
    } else {
      try {
        const updated = await apiClient.post<SmsConversation>(`/api/admin/sms/conversations/${selectedConversationId}/auto-reply`);
        setActiveConv(updated);
        setConversations(prev => prev.map(c => c.id === updated.id ? updated : c));
        toast.success("AI turned ON. Autoresponder is actively assisting.");
      } catch (err: any) {
        toast.error(err.message || "Failed to resume AI.");
      }
    }
  };

  const updateControls = async (
    patch: Partial<Pick<SmsConversation, "ai_enabled" | "is_pinned" | "is_blocked">>,
    successMessage: string,
  ) => {
    if (!selectedConversationId) return;
    try {
      const updated = await apiClient.patch<SmsConversation>(
        `/api/admin/sms/conversations/${selectedConversationId}/controls`,
        patch,
      );
      setActiveConv(updated);
      setConversations((current) => current.map((item) => item.id === updated.id ? updated : item));
      toast.success(successMessage);
    } catch (err: any) {
      toast.error(err.message || "Unable to update conversation controls.");
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
  const handleApproveDraft = async (msgId: number) => {
    try {
      await apiClient.post(`/api/admin/sms/conversations/messages/${msgId}/approve`);
      toast.success("Draft reply approved and enqueued for send!");
      if (selectedConversationId) loadMessages(selectedConversationId);
    } catch (err: any) {
      toast.error(err.message || "Approval failed.");
    }
  };

  const handleDiscardDraft = async (msgId: number) => {
    try {
      await apiClient.post(`/api/admin/sms/conversations/messages/${msgId}/discard`);
      toast.success("Draft reply discarded.");
      if (selectedConversationId) loadMessages(selectedConversationId);
    } catch (err: any) {
      toast.error(err.message || "Discard failed.");
    }
  };

  const handleStartEditDraft = (msg: SmsMessage) => {
    setEditingDraftId(msg.id);
    setEditingDraftBody(msg.body);
  };

  const handleSaveAndSendEditedDraft = async (msgId: number) => {
    if (!editingDraftBody.trim() || !selectedConversationId) return;
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

  return (
    <div className="flex flex-1 h-full min-h-0 rounded-xl border bg-card overflow-hidden text-xs">
      {/* Side Conversation List - Hidden on mobile if a conversation is selected */}
      <div className={`w-full sm:w-80 border-r flex flex-col bg-muted/20 ${selectedConversationId !== null ? "hidden sm:flex" : "flex"}`}>
        <div className="p-2 sm:p-3 border-b space-y-1.5 sm:space-y-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input 
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
              <Button size="xs" variant="outline" disabled title="Requires the backend escalation workflow">Escalated</Button>
              <Button size="xs" variant="outline" disabled title="Requires the backend resolution workflow">Resolved</Button>
            </div>
            <Button
              size="xs"
              variant="outline"
              className="h-6 px-2 text-[10px] border-primary/30 text-primary hover:bg-primary/10 gap-1 ml-auto"
              onClick={handlePreloadScenarios}
              disabled={seedingScenarios}
              title="Preload 16 test scenarios for Client 1..5"
            >
              <Sparkles className={`w-3 h-3 ${seedingScenarios ? "animate-spin" : "text-primary"}`} />
              {seedingScenarios ? "Injecting..." : "Preload Scenarios"}
            </Button>
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
                <Button
                  size="sm"
                  variant="default"
                  className="gap-1.5 text-xs mx-auto"
                  onClick={handlePreloadScenarios}
                  disabled={seedingScenarios}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {seedingScenarios ? "Generating Scenarios..." : "Preload 16 Test Scenarios"}
                </Button>
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
                const isBlocked = conv.is_blocked;

                return (
                  <div
                    key={conv.id}
                    onClick={() => setSelectedConversationId(conv.id)}
                    className={`p-3 rounded-lg cursor-pointer transition-colors border relative ${
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
                        {isBlocked ? (
                          <Badge variant="outline" className="text-[9px] px-1 py-0 border-red-500/30 text-red-600 bg-red-500/10">
                            Blocked
                          </Badge>
                        ) : conv.state === "taken-over" ? (
                          <Badge variant="outline" className="text-[9px] px-1 py-0 border-amber-500/20 text-amber-600 bg-amber-500/5">
                            Manual
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-[9px] px-1 py-0 border-indigo-500/20 text-indigo-600 bg-indigo-500/5">
                            AI Active
                          </Badge>
                        )}
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
                  </div>
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
                  onClick={() => setSelectedConversationId(null)}
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
                  <Button size="xs" variant="outline" className="text-amber-600 hover:text-amber-700 h-7 text-[10px] sm:text-xs px-2" onClick={handleToggleAi}>
                    <Ban className="w-3 h-3 sm:mr-1" />
                    <span className="hidden sm:inline">Pause AI</span>
                  </Button>
                ) : (
                  <Button size="xs" variant="outline" className="text-indigo-600 hover:text-indigo-700 h-7 text-[10px] sm:text-xs px-2" onClick={handleToggleAi}>
                    <Play className="w-3 h-3 sm:mr-1" />
                    <span className="hidden sm:inline">Resume AI</span>
                  </Button>
                )}
              </div>
            </div>

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
              <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" disabled title="Internal notes require the audited notes endpoint">
                <NotebookPen className="size-3" /> Add note
              </Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0" disabled title="Escalation requires the backend escalation workflow">Escalate</Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0" disabled title="Resolution requires the backend resolution workflow">Resolve</Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" disabled title="Correction evidence requires the backend correction workflow">
                <Edit3 className="size-3" /> Correct AI
              </Button>
              <Button size="xs" variant="outline" className="h-7 shrink-0 gap-1" disabled title="Tenant-scoped CSV export is not exposed by the backend yet">
                <FileDown className="size-3" /> Export
              </Button>
            </div>

            {/* Messages Scroll Area */}
            <ScrollArea className="flex-1 p-4 bg-muted/5">
              <div className="space-y-3">
                {messages.map((msg) => {
                  const isInbound = msg.direction === "inbound";
                  const isDraft = msg.status === "draft";
                  const isOperationalEvent = msg.author_type === "system" || msg.direction === "event";
                  const isInternalNote = msg.author_type === "note" || msg.direction === "internal";
                  const isEditingThisDraft = editingDraftId === msg.id;

                  if (isOperationalEvent || isInternalNote) {
                    return (
                      <div key={msg.id} className="mx-auto max-w-2xl rounded-lg border border-dashed bg-muted/40 px-3 py-2 text-center text-[11px] text-muted-foreground">
                        <div className="font-semibold text-foreground">
                          {isInternalNote ? "Internal note" : (msg.event_type || "Operational event").replaceAll("_", " ")}
                        </div>
                        <p className="mt-0.5 whitespace-pre-wrap">{msg.body}</p>
                        <time className="mt-1 block text-[9px]">{new Date(msg.occurred_at).toLocaleString()}</time>
                      </div>
                    );
                  }

                  return (
                    <div 
                      key={msg.id}
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
                              value={editingDraftBody}
                              onChange={(e) => setEditingDraftBody(e.target.value)}
                              rows={3}
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
                                >
                                  <Edit3 className="w-3 h-3" /> Edit
                                </Button>
                                <Button
                                  size="xs"
                                  variant="outline"
                                  className="bg-white border-red-200 text-red-600 hover:bg-red-50 h-7 text-[11px] gap-1"
                                  onClick={() => handleDiscardDraft(msg.id)}
                                >
                                  <Trash2 className="w-3 h-3" /> Discard
                                </Button>
                                <Button
                                  size="xs"
                                  className="bg-indigo-600 hover:bg-indigo-700 text-white h-7 text-[11px] gap-1"
                                  onClick={() => handleApproveDraft(msg.id)}
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
                        {!isInbound && getMessageStatus(msg.status)}
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
                  disabled={isCurrentContactBlocked}
                  placeholder={
                    isCurrentContactBlocked
                      ? "Contact is blocked. Unblock to send messages."
                      : activeConv.state === "taken-over"
                        ? "Type reply..."
                        : "Type reply (sending manually will automatically pause the AI)..."
                  } 
                  value={composeText}
                  onChange={e => setComposeText(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSend()}
                  className="flex-1 h-9 text-xs bg-background"
                />
                <Button size="sm" onClick={handleSend} disabled={isCurrentContactBlocked || !composeText.trim()}>
                  <Send className="w-4 h-4" />
                </Button>
              </div>

              {/* 5 Bottom Action Buttons Directly Beneath Composer Input */}
              <div className="flex items-center gap-1.5 pt-1 pb-0.5 overflow-x-auto no-scrollbar scroll-smooth">
                {/* 1. AI On / AI Off Toggle with Visual Indicator */}
                <Button
                  type="button"
                  size="xs"
                  variant={isAiActive ? "default" : "outline"}
                  onClick={handleToggleAi}
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

                {/* 2. Tools: Opens QuickToolsSheet */}
                <Button
                  type="button"
                  size="xs"
                  variant="outline"
                  onClick={() => setToolsSheetOpen(true)}
                  className="h-7 text-xs px-2.5 gap-1.5 shrink-0 border-primary/30 text-primary hover:bg-primary/5"
                >
                  <Wrench className="w-3 h-3" />
                  <span>Tools</span>
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

      {/* Quick Tools Slide-up Bottom Sheet */}
      <QuickToolsSheet
        open={toolsSheetOpen}
        onOpenChange={setToolsSheetOpen}
        onInsert={(insertedText) => {
          setComposeText(prev => prev ? `${prev} ${insertedText}` : insertedText);
          setToolsSheetOpen(false);
        }}
        customerName={activeConv?.client_name || activeConv?.customer_address}
      />

    </div>
  );
}
