import { useState, useEffect, useRef } from "react";
import {
  ChevronLeft,
  Send,
  Sparkles,
  Bot,
  Zap,
  Calendar,
  Pin,
  PinOff,
  Ban,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Flag,
} from "lucide-react";
import { toast } from "sonner";
import { QuickToolsSheet } from "./quick-tools-sheet";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";

export interface ThreadMessage {
  id: string | number;
  kind?: "message" | "internal_note" | "event";
  direction: "inbound" | "outbound";
  authorType: "customer" | "ai" | "staff";
  authorName?: string;
  body: string;
  status?: "draft" | "queued" | "sent" | "delivered" | "received" | "discarded";
  occurredAt: string;
  meta?: Record<string, unknown>;
}

export interface AssistantThreadPanelProps {
  mode: "live" | "bootcamp";
  showBottomToolbar?: boolean;
  conversationId: string | number;
  title: string;
  subtitle?: string;
  isPinned?: boolean;
  isBlocked?: boolean;
  aiActive?: boolean;
  statusBadge?: string;
  messages: ThreadMessage[];
  infoRequest?: {
    hasRequest: boolean;
    prompt: string;
  };
  onSubmitInfoAnswer?: (answer: string) => Promise<void>;
  onDismissInfoRequest?: () => Promise<void>;
  onSendMessage: (text: string) => Promise<void>;
  onToggleAi?: () => Promise<void>;
  onTogglePin?: () => Promise<void>;
  onToggleBlock?: () => Promise<void>;
  onBack?: () => void;
  onApproveDraft?: (msgId: string | number) => Promise<void>;
  onDiscardDraft?: (msgId: string | number) => Promise<void>;
  onEditAndSendDraft?: (msgId: string | number, text: string) => Promise<void>;
  onSubmitCorrection: (
    target: { messageId: string | number; text: string },
    reason: string,
    correctedWording?: string
  ) => Promise<void>;
  bookingUrl?: string | null;
  customerName?: string;
  actionInFlight?: boolean;
  isGenerating?: boolean;
}

function formatOccurredAt(raw: string): string {
  if (!raw) return "";
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function AssistantThreadPanel({
  mode = "live",
  showBottomToolbar = mode !== "bootcamp",
  conversationId,
  title,
  subtitle,
  isPinned = false,
  isBlocked = false,
  aiActive = true,
  statusBadge,
  messages,
  infoRequest,
  onSubmitInfoAnswer,
  onDismissInfoRequest,
  onSendMessage,
  onToggleAi,
  onTogglePin,
  onToggleBlock,
  onBack,
  onApproveDraft,
  onDiscardDraft,
  onEditAndSendDraft,
  onSubmitCorrection,
  bookingUrl,
  customerName,
  actionInFlight = false,
  isGenerating = false,
}: AssistantThreadPanelProps) {
  // Composer State
  const [composeText, setComposeText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Quick Tools Sheet State
  const [showQuickTools, setShowQuickTools] = useState(false);

  // AI Draft Inline Editing
  const [editingDraftId, setEditingDraftId] = useState<string | number | null>(null);
  const [editingDraftBody, setEditingDraftBody] = useState("");

  // AI Response Correction Dialog State
  const [correctionTarget, setCorrectionTarget] = useState<{
    messageId: string | number;
    text: string;
  } | null>(null);
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctedWording, setCorrectedWording] = useState("");
  const [submittingCorrection, setSubmittingCorrection] = useState(false);

  // Information Request Accordion State
  const [infoAccordionOpen, setInfoAccordionOpen] = useState(true);
  const [infoStaffAnswer, setInfoStaffAnswer] = useState("");
  const [submittingInfoAnswer, setSubmittingInfoAnswer] = useState(false);

  // Reset thread-local inputs on conversation switch
  useEffect(() => {
    setComposeText("");
    setEditingDraftId(null);
    setEditingDraftBody("");
    setInfoStaffAnswer("");
    setCorrectionTarget(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [conversationId]);

  // Auto-scroll on new messages or generation change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isGenerating]);

  // Adjust auto-expanding textarea
  const handleComposeChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setComposeText(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 128)}px`;
    }
  };

  // Dispatch manual message
  const handleSend = async () => {
    const textToSend = composeText.trim();
    if (!textToSend || isBlocked || isSending || actionInFlight) return;

    setIsSending(true);
    setComposeText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      await onSendMessage(textToSend);
    } catch {
      // Restore input text if send failed
      setComposeText(textToSend);
    } finally {
      setIsSending(false);
    }
  };

  // Information Request Actions
  const handleInfoSubmit = async () => {
    if (!infoStaffAnswer.trim() || submittingInfoAnswer || !onSubmitInfoAnswer) return;
    setSubmittingInfoAnswer(true);
    try {
      await onSubmitInfoAnswer(infoStaffAnswer.trim());
      setInfoStaffAnswer("");
    } catch (err: any) {
      toast.error(err.message || "Failed to submit information answer.");
    } finally {
      setSubmittingInfoAnswer(false);
    }
  };

  const handleInfoDismiss = async () => {
    if (!onDismissInfoRequest) return;
    try {
      await onDismissInfoRequest();
      setInfoStaffAnswer("");
    } catch (err: any) {
      toast.error(err.message || "Failed to dismiss request.");
    }
  };

  // Draft Moderation Actions
  const handleApproveDraft = async (msgId: string | number) => {
    if (actionInFlight || !onApproveDraft) return;
    try {
      await onApproveDraft(msgId);
    } catch (err: any) {
      toast.error(err.message || "Failed to approve draft.");
    }
  };

  const handleDiscardDraft = async (msgId: string | number) => {
    if (actionInFlight || !onDiscardDraft) return;
    try {
      await onDiscardDraft(msgId);
    } catch (err: any) {
      toast.error(err.message || "Failed to discard draft.");
    }
  };

  const handleSendEditedDraft = async (msgId: string | number) => {
    if (!editingDraftBody.trim() || actionInFlight) return;
    try {
      if (onEditAndSendDraft) {
        await onEditAndSendDraft(msgId, editingDraftBody.trim());
      } else if (onApproveDraft) {
        await onApproveDraft(msgId);
      }
      setEditingDraftId(null);
    } catch (err: any) {
      toast.error(err.message || "Failed to send edited draft.");
    }
  };

  // AI Correction Submission
  const handleCorrectionSubmit = async () => {
    if (!correctionTarget || !correctionReason.trim() || submittingCorrection) return;
    setSubmittingCorrection(true);
    try {
      await onSubmitCorrection(
        correctionTarget,
        correctionReason.trim(),
        correctedWording.trim() || undefined
      );
      setCorrectionTarget(null);
      setCorrectionReason("");
      setCorrectedWording("");
    } catch (err: any) {
      toast.error(err.message || "Failed to record correction.");
    } finally {
      setSubmittingCorrection(false);
    }
  };

  const hasInfo = Boolean(infoRequest?.hasRequest);

  return (
    <div className="flex flex-1 flex-col h-full min-h-0 bg-background text-foreground overflow-hidden">
      {/* 1. HEADER BAR */}
      <header className="flex items-center justify-between border-b border-border bg-card px-3 py-2 shrink-0 gap-2">
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          {/* Round Back Button */}
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-muted text-foreground hover:bg-muted/80 active:scale-95 transition-all cursor-pointer"
              aria-label="Back to conversations"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
          )}

          {/* Contact Header */}
          <div className="flex flex-col min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 flex-wrap">
              <span>{subtitle || "SMS · Active Chat"}</span>
              {isPinned && (
                <span className="inline-flex items-center text-amber-600 dark:text-amber-400 font-bold">
                  <Pin className="h-2.5 w-2.5 mr-0.5 fill-amber-500" /> Pinned
                </span>
              )}
              {isBlocked && (
                <span className="inline-flex items-center text-red-600 dark:text-red-400 font-bold">
                  <Ban className="h-2.5 w-2.5 mr-0.5" /> Blocked
                </span>
              )}
              {statusBadge && (
                <span className="inline-flex items-center text-indigo-600 dark:text-indigo-400 font-bold">
                  · {statusBadge}
                </span>
              )}
            </div>
            <div className="text-sm font-bold text-foreground truncate">{title || "Conversation"}</div>
          </div>
        </div>

        {/* Thread AI Status Pill */}
        {onToggleAi ? (
          <button
            type="button"
            onClick={onToggleAi}
            disabled={actionInFlight}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold transition-all cursor-pointer border shrink-0 ${
              aiActive
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                : "bg-muted text-muted-foreground border-border"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                aiActive ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground/50"
              }`}
            />
            <span>{aiActive ? "AI On" : "AI Off"}</span>
          </button>
        ) : (
          <div
            className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold border shrink-0 ${
              aiActive
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                : "bg-muted text-muted-foreground border-border"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                aiActive ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground/50"
              }`}
            />
            <span>{aiActive ? "AI On" : "AI Off"}</span>
          </div>
        )}
      </header>

      {/* 2. CHAT TIMELINE VIEWPORT WITH ACCORDION & BANNERS */}
      <div className="flex flex-1 flex-col min-h-0 bg-background overflow-hidden">
        {/* Information Request Accordion */}
        {hasInfo && (
          <div className="p-2.5 bg-red-500/10 border-b border-red-500/30 shrink-0">
            <div
              role="button"
              tabIndex={0}
              onClick={() => setInfoAccordionOpen((prev) => !prev)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setInfoAccordionOpen((prev) => !prev);
                }
              }}
              className="bg-red-700 hover:bg-red-800 text-white text-xs font-black uppercase tracking-wider py-2.5 px-4 rounded-lg cursor-pointer flex justify-between items-center transition-colors shadow-sm"
            >
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                <span>Action Required: Information Request</span>
              </div>
              {infoAccordionOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </div>

            {infoAccordionOpen && (
              <div className="mt-2 rounded-lg border border-red-500/30 bg-card p-3 space-y-2.5 shadow-sm text-xs">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-red-600 dark:text-red-400 block mb-1">
                    Customer Prompt / Knowledge Gap:
                  </span>
                  <div className="rounded-md bg-red-500/10 p-2 text-foreground border border-red-500/20 font-medium">
                    {infoRequest?.prompt}
                  </div>
                </div>

                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block mb-1">
                    Staff Ground-Truth Answer (Learned for Future AI Replies):
                  </label>
                  <textarea
                    value={infoStaffAnswer}
                    onChange={(e) => setInfoStaffAnswer(e.target.value)}
                    rows={3}
                    placeholder="Type answer here. This replies to the customer and queues learning for curator review..."
                    className="w-full rounded-md border border-border bg-card dark:bg-muted/30 p-2 text-xs text-foreground placeholder:text-muted-foreground focus:border-red-600 focus:outline-none resize-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-1">
                  {onDismissInfoRequest && (
                    <button
                      type="button"
                      onClick={handleInfoDismiss}
                      className="px-3 py-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground bg-card dark:bg-muted/20 border border-border rounded-md hover:bg-muted transition-colors cursor-pointer"
                    >
                      Remove request
                    </button>
                  )}
                  {onSubmitInfoAnswer && (
                    <button
                      type="button"
                      disabled={!infoStaffAnswer.trim() || submittingInfoAnswer}
                      onClick={handleInfoSubmit}
                      className="px-3 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-md shadow-xs transition-colors cursor-pointer"
                    >
                      {submittingInfoAnswer ? "Saving..." : "Send reply and save learning"}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Blocked Warning Banner */}
        {isBlocked && (
          <div className="bg-red-500/10 border-b border-red-500/30 px-3 py-1.5 text-[11px] text-red-600 dark:text-red-400 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-1.5">
              <Ban className="h-3.5 w-3.5 shrink-0" />
              <span>Contact is blocked. Automated replies and manual outbound SMS are paused.</span>
            </div>
            {onToggleBlock && (
              <button
                type="button"
                onClick={onToggleBlock}
                className="font-bold underline ml-2 shrink-0 cursor-pointer"
              >
                Unblock
              </button>
            )}
          </div>
        )}

        {/* Chat Timeline Viewport */}
        <div className="flex min-h-0 flex-1 flex-col bg-muted/30 dark:bg-background/80 overflow-y-auto px-3 py-3 space-y-2.5">
          {messages.length === 0 ? (
            <div className="m-auto text-center text-xs text-muted-foreground">
              No messages in this conversation yet.
            </div>
          ) : (
            messages.map((msg) => {
              const isStaff = msg.authorType === "staff" || (msg.direction === "outbound" && msg.authorType !== "ai");
              const isAiSent = msg.authorType === "ai" && msg.direction === "outbound" && msg.status !== "draft";
              const isDraft = msg.status === "draft";
              const isClientArrived =
                msg.kind === "event" &&
                ((msg.meta as any)?.event_type === "client_arrived" ||
                  (msg.body && msg.body.toLowerCase().includes("arrived")));

              // Client Arrived Notification Pill
              if (isClientArrived) {
                return (
                  <div key={msg.id} className="flex justify-center my-1">
                    <div className="border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-full px-3 py-1 text-xs font-bold shadow-xs">
                      Client Arrived: {msg.body || "Checked in to reception"}
                    </div>
                  </div>
                );
              }

              // Operational Event / Internal Note
              if (msg.kind === "event" || msg.kind === "internal_note") {
                return (
                  <div
                    key={msg.id}
                    className="mx-auto max-w-[85%] rounded-lg border border-dashed border-border bg-muted/50 px-3 py-1.5 text-center text-[11px] text-muted-foreground"
                  >
                    <span className="font-semibold text-foreground mr-1">
                      {msg.kind === "internal_note" ? "Staff Note:" : "Event:"}
                    </span>
                    <span>{msg.body}</span>
                    <div className="text-[9px] text-muted-foreground/70 mt-0.5">
                      {formatOccurredAt(msg.occurredAt)}
                    </div>
                  </div>
                );
              }

              // AI Draft (Unsent / Pending)
              if (isDraft) {
                const isEditing = editingDraftId === msg.id;

                return (
                  <div
                    key={msg.id}
                    className="self-end max-w-[85%] rounded-2xl rounded-br-md border border-blue-400/60 dark:border-blue-700/60 bg-blue-50/80 dark:bg-blue-950/40 text-foreground shadow-xs px-3 py-2 space-y-2"
                  >
                    <div className="flex items-center justify-between text-[11px] font-bold text-blue-600 dark:text-blue-400">
                      <div className="flex items-center gap-1">
                        <Sparkles className="h-3.5 w-3.5" />
                        <span>AI draft—not sent</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[10.5px] text-blue-500/80 dark:text-blue-400/80 font-normal shrink-0">
                        {msg.occurredAt && <span>{formatOccurredAt(msg.occurredAt)} ·</span>}
                        <span>Pending approval</span>
                      </div>
                    </div>

                    {isEditing ? (
                      <div className="space-y-2">
                        <textarea
                          value={editingDraftBody}
                          onChange={(e) => setEditingDraftBody(e.target.value)}
                          rows={3}
                          className="w-full rounded-md border border-blue-400/60 dark:border-blue-700/60 bg-card dark:bg-muted/40 p-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                        />
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => setEditingDraftId(null)}
                            className="px-2.5 py-1 text-xs font-semibold text-foreground bg-card dark:bg-muted/40 border border-border rounded hover:bg-muted transition-colors cursor-pointer"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            disabled={actionInFlight || !editingDraftBody.trim()}
                            onClick={() => handleSendEditedDraft(msg.id)}
                            className="px-2.5 py-1 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-500 rounded transition-colors shadow-xs cursor-pointer"
                          >
                            Send
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="text-[13px] leading-snug whitespace-pre-wrap text-foreground">
                          {msg.body}
                        </p>
                        <div className="flex items-center justify-end gap-1.5 pt-1 border-t border-blue-200/60 dark:border-blue-800/60">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingDraftId(msg.id);
                              setEditingDraftBody(msg.body || "");
                            }}
                            className="px-2.5 py-1 text-xs font-semibold text-foreground bg-card dark:bg-muted/40 border border-border rounded hover:bg-muted transition-colors cursor-pointer"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            disabled={actionInFlight}
                            onClick={() => handleDiscardDraft(msg.id)}
                            className="px-2.5 py-1 text-xs font-semibold text-red-600 dark:text-red-400 bg-card dark:bg-muted/40 border border-red-200 dark:border-red-900/60 rounded hover:bg-red-500/10 transition-colors cursor-pointer"
                          >
                            Discard
                          </button>
                          <button
                            type="button"
                            disabled={actionInFlight}
                            onClick={() => handleApproveDraft(msg.id)}
                            className="px-2.5 py-1 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-500 rounded transition-colors shadow-xs cursor-pointer"
                          >
                            Send
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                );
              }

              // AI Auto-Reply (Sent)
              if (isAiSent) {
                return (
                  <div
                    key={msg.id}
                    className="self-end max-w-[82%] rounded-2xl rounded-br-md bg-blue-600 dark:bg-blue-700 text-white shadow-xs px-3 py-2 text-[13px]"
                  >
                    <div className="flex items-center justify-between gap-2 text-[11px] font-bold text-blue-100 dark:text-blue-200 mb-1">
                      <div className="flex items-center gap-1">
                        <Bot className="h-3 w-3 shrink-0" />
                        <span>{msg.authorName || "AI"}</span>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0 text-[10.5px] font-normal">
                        <span>{formatOccurredAt(msg.occurredAt)}</span>
                        <span>· Sent</span>
                        <button
                          type="button"
                          onClick={() => {
                            setCorrectionTarget({ messageId: msg.id, text: msg.body || "" });
                            setCorrectionReason("");
                            setCorrectedWording(msg.body || "");
                          }}
                          title="Flag AI reply for correction"
                          className="text-blue-100 hover:text-white dark:text-blue-200 p-0.5 rounded cursor-pointer transition-colors"
                        >
                          <Flag className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                    <p className="leading-snug whitespace-pre-wrap">{msg.body}</p>
                  </div>
                );
              }

              // Staff Manual Reply
              if (isStaff) {
                return (
                  <div
                    key={msg.id}
                    className="self-end max-w-[82%] rounded-2xl rounded-br-md bg-slate-700 dark:bg-slate-800 text-white shadow-xs px-3 py-2 text-[13px]"
                  >
                    <div className="flex items-center justify-between gap-2 text-[10.5px] text-slate-300 dark:text-slate-400 mb-1">
                      <span className="font-semibold">{msg.authorName || "Staff"}</span>
                      <div className="flex items-center gap-1 shrink-0">
                        <span>{formatOccurredAt(msg.occurredAt)}</span>
                        <span>· {msg.status === "delivered" ? "Delivered" : "Sent"}</span>
                      </div>
                    </div>
                    <p className="leading-snug whitespace-pre-wrap">{msg.body}</p>
                  </div>
                );
              }

              // Customer Inbound SMS
              return (
                <div
                  key={msg.id}
                  className="self-start max-w-[82%] rounded-2xl rounded-bl-md bg-card dark:bg-muted/80 text-foreground border border-border/80 shadow-xs px-3 py-2 text-[13px]"
                >
                  <div className="flex items-center justify-between gap-2 text-[10.5px] text-muted-foreground mb-1">
                    <span className="font-semibold uppercase tracking-wider">
                      {msg.authorName || "Customer"}
                    </span>
                    <span className="font-medium shrink-0">
                      {formatOccurredAt(msg.occurredAt)}
                    </span>
                  </div>
                  <p className="leading-snug whitespace-pre-wrap">{msg.body}</p>
                </div>
              );
            })
          )}

          {/* Real-time simulation thinking indicator */}
          {isGenerating && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground pl-2 py-1">
              <span className="h-2 w-2 rounded-full bg-indigo-600 animate-ping" />
              <span className="italic">AI is analyzing persona cues and formulating reply...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 3. COMPOSER & BOTTOM 5-BUTTON TOOLBAR */}
        <div className="border-t border-border bg-card p-2 shrink-0 space-y-1">
          {/* Input Row */}
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={composeText}
              onChange={handleComposeChange}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={isBlocked || isSending}
              placeholder={
                isBlocked
                  ? "Contact is blocked."
                  : "Type a message... (Cmd+Enter to send)"
              }
              rows={1}
              className="flex-1 rounded-2xl border border-border bg-card dark:bg-muted/30 px-3.5 py-1.5 text-[13px] max-h-32 min-h-[38px] resize-none text-foreground placeholder:text-muted-foreground focus:border-indigo-500 focus:bg-card focus:outline-none leading-snug"
            />

            {/* Circular Green Send Button */}
            <button
              type="button"
              onClick={handleSend}
              disabled={!composeText.trim() || isSending || isBlocked}
              className="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-full bg-emerald-600 text-white shadow-sm active:scale-95 disabled:opacity-40 disabled:pointer-events-none hover:bg-emerald-700 transition-all cursor-pointer"
              aria-label="Send message"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Bottom 5-Button Toolbar */}
          {showBottomToolbar && (
            <div className="grid grid-cols-5 gap-1 pt-1 pb-1 border-t border-border/60">
              {/* 1. AI On / AI Off */}
              <button
                type="button"
                onClick={onToggleAi}
                disabled={!onToggleAi || actionInFlight}
                className="flex flex-col items-center justify-center py-1.5 px-1 rounded-lg bg-card dark:bg-muted/20 border border-border text-foreground hover:bg-muted transition-colors text-[11px] font-medium cursor-pointer disabled:opacity-50"
              >
                <div className="relative">
                  <Bot
                    className={`h-4 w-4 mb-0.5 ${aiActive ? "text-emerald-500" : "text-muted-foreground"}`}
                  />
                  <span
                    className={`absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full ${
                      aiActive ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground/50"
                    }`}
                  />
                </div>
                <span
                  className={
                    aiActive
                      ? "text-emerald-600 dark:text-emerald-400 font-bold"
                      : "text-muted-foreground"
                  }
                >
                  {aiActive ? "AI On" : "AI Off"}
                </span>
              </button>

              {/* 2. Tools (QuickToolsSheet) */}
              <button
                type="button"
                onClick={() => setShowQuickTools(true)}
                className="flex flex-col items-center justify-center py-1.5 px-1 rounded-lg bg-card dark:bg-muted/20 border border-border text-foreground hover:bg-muted transition-colors text-[11px] font-medium cursor-pointer"
              >
                <Zap className="h-4 w-4 mb-0.5 text-amber-500" />
                <span>Tools</span>
              </button>

              {/* 3. Booking */}
              {bookingUrl ? (
                <a
                  href={bookingUrl}
                  className="flex flex-col items-center justify-center py-1.5 px-1 rounded-lg bg-card dark:bg-muted/20 border border-border text-foreground hover:bg-muted transition-colors text-[11px] font-medium cursor-pointer"
                >
                  <Calendar className="h-4 w-4 mb-0.5 text-blue-500" />
                  <span>Booking</span>
                </a>
              ) : (
                <a
                  href="/admin/bookings"
                  className="flex flex-col items-center justify-center py-1.5 px-1 rounded-lg bg-card dark:bg-muted/20 border border-border text-foreground hover:bg-muted transition-colors text-[11px] font-medium cursor-pointer"
                >
                  <Calendar className="h-4 w-4 mb-0.5 text-blue-500" />
                  <span>Booking</span>
                </a>
              )}

              {/* 4. Pin / Unpin */}
              <button
                type="button"
                onClick={onTogglePin}
                disabled={!onTogglePin || actionInFlight}
                className="flex flex-col items-center justify-center py-1.5 px-1 rounded-lg bg-card dark:bg-muted/20 border border-border text-foreground hover:bg-muted transition-colors text-[11px] font-medium cursor-pointer disabled:opacity-50"
              >
                {isPinned ? (
                  <>
                    <PinOff className="h-4 w-4 mb-0.5 text-amber-500 fill-amber-500/20" />
                    <span className="text-amber-600 dark:text-amber-400 font-semibold">Unpin</span>
                  </>
                ) : (
                  <>
                    <Pin className="h-4 w-4 mb-0.5 text-muted-foreground" />
                    <span>Pin</span>
                  </>
                )}
              </button>

              {/* 5. Block / Unblock */}
              <button
                type="button"
                onClick={onToggleBlock}
                disabled={!onToggleBlock || actionInFlight}
                className="flex flex-col items-center justify-center py-1.5 px-1 rounded-lg bg-card dark:bg-muted/20 border border-border text-foreground hover:bg-muted transition-colors text-[11px] font-medium cursor-pointer disabled:opacity-50"
              >
                <Ban
                  className={`h-4 w-4 mb-0.5 ${
                    isBlocked ? "text-red-500" : "text-muted-foreground"
                  }`}
                />
                <span className={isBlocked ? "text-red-600 dark:text-red-400 font-semibold" : ""}>
                  {isBlocked ? "Unblock" : "Block"}
                </span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Quick Tools Sheet */}
      <QuickToolsSheet
        open={showQuickTools}
        onOpenChange={setShowQuickTools}
        onInsert={(text) => {
          setComposeText((prev) => (prev ? `${prev} ${text}` : text));
          if (textareaRef.current) {
            setTimeout(() => {
              if (textareaRef.current) {
                textareaRef.current.style.height = "auto";
                textareaRef.current.style.height = `${Math.min(
                  textareaRef.current.scrollHeight,
                  128
                )}px`;
              }
            }, 0);
          }
        }}
        customerName={customerName}
      />

      {/* AI Correction Flag Dialog */}
      <Dialog
        open={correctionTarget !== null}
        onOpenChange={(open) => {
          if (!open && !submittingCorrection) setCorrectionTarget(null);
        }}
      >
        <DialogContent className="max-w-md bg-card text-card-foreground border-border">
          <DialogHeader>
            <DialogTitle className="text-sm font-bold flex items-center gap-1.5 text-foreground">
              <Flag className="h-4 w-4 text-blue-500" /> Flag AI Response for Correction
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Record ground-truth correction evidence to train future assistant responses. Live facts are governed by
              curator review.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs">
            <div>
              <span className="font-semibold text-muted-foreground block mb-1">AI Output:</span>
              <p className="p-2 bg-muted/50 rounded border border-border text-foreground text-[11px]">
                {correctionTarget?.text}
              </p>
            </div>

            <div>
              <label className="font-semibold text-foreground block mb-1">
                Correction Reason <span className="text-red-500">*</span>:
              </label>
              <input
                type="text"
                value={correctionReason}
                onChange={(e) => setCorrectionReason(e.target.value)}
                placeholder="e.g. Quoted outdated prices; wrong weekend hours"
                className="w-full rounded border border-border bg-card dark:bg-muted/30 p-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="font-semibold text-foreground block mb-1">Corrected Ideal Wording (Optional):</label>
              <textarea
                value={correctedWording}
                onChange={(e) => setCorrectedWording(e.target.value)}
                rows={3}
                placeholder="The exact sentence the assistant should have replied..."
                className="w-full rounded border border-border bg-card dark:bg-muted/30 p-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500 resize-none"
              />
            </div>
          </div>

          <DialogFooter className="gap-1">
            <button
              type="button"
              onClick={() => setCorrectionTarget(null)}
              className="px-3 py-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground bg-card dark:bg-muted/20 border border-border rounded-md hover:bg-muted transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!correctionReason.trim() || submittingCorrection}
              onClick={handleCorrectionSubmit}
              className="px-3 py-1.5 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-md shadow-xs transition-colors cursor-pointer"
            >
              {submittingCorrection ? "Submitting..." : "Save Correction"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
