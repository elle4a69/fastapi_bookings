import { useState, useEffect, useCallback } from "react";
import { 
  Sparkles, 
  Check, 
  Trash2, 
  Edit3, 
  Send, 
  RefreshCw, 
  CheckCheck,
  MessageSquare,
  AlertCircle
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface TriageDraftItem {
  id: number;
  conversation_id: number;
  customer_name: string;
  customer_address: string;
  inbound_snippet?: string;
  customer_message?: string;
  draft_body: string;
  created_at: string;
}

export function SmsTriageTab() {
  const [drafts, setDrafts] = useState<TriageDraftItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [actionInProgress, setActionInProgress] = useState(false);

  // Bulk Discard Dialog State
  const [bulkDiscardOpen, setBulkDiscardOpen] = useState(false);
  const [bulkDiscardReason, setBulkDiscardReason] = useState("");

  const loadTriageDrafts = useCallback(async () => {
    setLoading(true);
    try {
      const rawQueue = await apiClient.get<any[]>("/api/admin/sms/conversations/drafts/queue");
      const mapped: TriageDraftItem[] = (Array.isArray(rawQueue) ? rawQueue : []).map((item: any) => ({
        id: item.id ?? item.message_id,
        conversation_id: item.conversation_id,
        customer_name: item.client_name || item.customer_name || item.customer_address || `Conversation #${item.conversation_id}`,
        customer_address: item.customer_address || "",
        inbound_snippet: item.inbound_snippet || "",
        customer_message: item.customer_message || "",
        draft_body: item.draft_body || item.body || "",
        created_at: item.created_at || item.occurred_at || item.received_at || new Date().toISOString(),
      }));

      setDrafts(mapped);
      setSelectedIds((prev) => prev.filter((id) => mapped.some((m) => m.id === id)));
      if (mapped.length === 0) {
        setSelectedIndex(0);
      } else {
        setSelectedIndex((prev) => Math.min(prev, mapped.length - 1));
      }
    } catch (err: any) {
      toast.error(err?.message || "Failed to load draft triage queue.");
      setDrafts([]);
      setSelectedIds([]);
      setSelectedIndex(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTriageDrafts();
  }, [loadTriageDrafts]);

  const currentDraft = drafts[selectedIndex] || null;
  const currentDraftId = currentDraft?.id;
  const currentDraftConvId = currentDraft?.conversation_id;
  const currentDraftHasSnippet = Boolean(currentDraft?.inbound_snippet || currentDraft?.customer_message);

  // Lazily fetch inbound customer context if missing from queue payload for current draft
  useEffect(() => {
    if (!currentDraftId || !currentDraftConvId || currentDraftHasSnippet) return;

    let cancelled = false;
    apiClient
      .get<any[]>(`/api/admin/sms/conversations/${currentDraftConvId}/messages`)
      .then((msgs) => {
        if (cancelled || !Array.isArray(msgs)) return;
        const lastInbound = msgs.filter((m: any) => m.direction === "inbound").slice(-1)[0];
        if (lastInbound?.body) {
          setDrafts((prev) =>
            prev.map((d) =>
              d.id === currentDraftId ? { ...d, inbound_snippet: lastInbound.body } : d
            )
          );
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [currentDraftId, currentDraftConvId, currentDraftHasSnippet]);

  // Checkbox selection helpers
  const handleToggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(drafts.map((d) => d.id));
    } else {
      setSelectedIds([]);
    }
  };

  const isAllSelected = drafts.length > 0 && selectedIds.length === drafts.length;

  // Approve Draft: POST /api/admin/sms/conversations/messages/${draft.id}/approve
  const handleApprove = async (draft: TriageDraftItem) => {
    if (actionInProgress) return;
    setActionInProgress(true);
    try {
      await apiClient.post(`/api/admin/sms/conversations/messages/${draft.id}/approve`);
      toast.success(`Approved & sent draft to ${draft.customer_name}`);
      setDrafts((prev) => prev.filter((d) => d.id !== draft.id));
      setSelectedIds((prev) => prev.filter((id) => id !== draft.id));
      setSelectedIndex((prev) => Math.max(0, Math.min(prev, drafts.length - 2)));
    } catch (err: any) {
      toast.error(err?.message || `Failed to approve draft for ${draft.customer_name}`);
    } finally {
      setActionInProgress(false);
    }
  };

  // Discard Draft: POST /api/admin/sms/conversations/messages/${draft.id}/discard
  const handleDiscard = async (draft: TriageDraftItem) => {
    if (actionInProgress) return;
    setActionInProgress(true);
    try {
      await apiClient.post(`/api/admin/sms/conversations/messages/${draft.id}/discard`);
      toast.info(`Discarded draft for ${draft.customer_name}`);
      setDrafts((prev) => prev.filter((d) => d.id !== draft.id));
      setSelectedIds((prev) => prev.filter((id) => id !== draft.id));
      setSelectedIndex((prev) => Math.max(0, Math.min(prev, drafts.length - 2)));
    } catch (err: any) {
      toast.error(err?.message || `Failed to discard draft for ${draft.customer_name}`);
    } finally {
      setActionInProgress(false);
    }
  };

  // Start Edit
  const handleStartEdit = (draft: TriageDraftItem) => {
    setEditingId(draft.id);
    setEditingText(draft.draft_body);
  };

  // Save & Send Edited Draft: POST /api/admin/sms/conversations/drafts/${draft.id}/review
  // with { action: "approve", text: editingText }
  const handleSaveAndSend = async (draft: TriageDraftItem) => {
    if (!editingText.trim() || actionInProgress) return;
    setActionInProgress(true);
    try {
      await apiClient.post(`/api/admin/sms/conversations/drafts/${draft.id}/review`, {
        action: "approve",
        text: editingText.trim(),
      });
      toast.success(`Approved and sent edited reply to ${draft.customer_name}`);
      setEditingId(null);
      setEditingText("");
      setDrafts((prev) => prev.filter((d) => d.id !== draft.id));
      setSelectedIds((prev) => prev.filter((id) => id !== draft.id));
      setSelectedIndex((prev) => Math.max(0, Math.min(prev, drafts.length - 2)));
    } catch (err: any) {
      toast.error(err?.message || "Failed to send edited draft.");
    } finally {
      setActionInProgress(false);
    }
  };

  // Bulk Discard: POST /api/admin/sms/conversations/drafts/bulk/discard
  const handleBulkDiscard = async () => {
    if (!bulkDiscardReason.trim() || selectedIds.length === 0 || actionInProgress) return;
    setActionInProgress(true);
    try {
      await apiClient.post("/api/admin/sms/conversations/drafts/bulk/discard", {
        message_ids: selectedIds,
        reason: bulkDiscardReason.trim(),
      });
      toast.success(`Discarded ${selectedIds.length} draft${selectedIds.length === 1 ? "" : "s"}.`);
      setDrafts((prev) => prev.filter((d) => !selectedIds.includes(d.id)));
      setSelectedIds([]);
      setBulkDiscardOpen(false);
      setBulkDiscardReason("");
      setSelectedIndex(0);
    } catch (err: any) {
      toast.error(err?.message || "Failed to bulk discard drafts.");
    } finally {
      setActionInProgress(false);
    }
  };

  // Approve All Pending Drafts
  const handleApproveAll = async () => {
    if (drafts.length === 0 || actionInProgress) return;
    setActionInProgress(true);
    const list = [...drafts];
    let approvedCount = 0;
    for (const d of list) {
      try {
        await apiClient.post(`/api/admin/sms/conversations/messages/${d.id}/approve`);
        approvedCount++;
      } catch {
        // continue trying remaining
      }
    }
    toast.success(`Approved ${approvedCount} of ${list.length} pending draft replies!`);
    loadTriageDrafts();
    setActionInProgress(false);
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl border bg-card shadow-xs">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-600 border border-amber-500/20">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold flex items-center gap-2">
              Draft Message Triage Console
              <Badge className="bg-amber-600 text-white font-bold text-[10px]">
                {drafts.length} Awaiting Approval
              </Badge>
            </h2>
            <p className="text-xs text-muted-foreground">
              Rapid-fire review desk for proposed AI replies. Approve, edit, or discard in one click.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {selectedIds.length > 0 && (
            <Button
              type="button"
              size="xs"
              variant="outline"
              onClick={() => setBulkDiscardOpen(true)}
              disabled={actionInProgress}
              className="h-8 text-xs gap-1.5 border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20 font-semibold"
            >
              <Trash2 className="w-3.5 h-3.5" /> Bulk Discard ({selectedIds.length})
            </Button>
          )}

          {drafts.length > 1 && (
            <Button
              type="button"
              size="xs"
              onClick={handleApproveAll}
              disabled={actionInProgress}
              className="h-8 text-xs gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
            >
              <CheckCheck className="w-3.5 h-3.5" /> Approve All ({drafts.length})
            </Button>
          )}

          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={loadTriageDrafts}
            disabled={loading || actionInProgress}
            className="h-8 text-xs text-muted-foreground"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </div>

      {drafts.length === 0 ? (
        <div className="p-12 rounded-xl border border-dashed bg-muted/20 text-center space-y-2">
          <CheckCheck className="w-10 h-10 text-emerald-600 mx-auto" />
          <h3 className="text-sm font-bold text-foreground">
            All caught up! No pending AI drafts to review.
          </h3>
          <p className="text-xs text-muted-foreground max-w-sm mx-auto">
            There are no pending AI autoresponder drafts waiting for staff sign-off.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left Column: Draft Queue List */}
          <div className="lg:col-span-5 space-y-2">
            <div className="flex items-center justify-between pb-1 px-1">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="select-all-drafts"
                  checked={isAllSelected}
                  onCheckedChange={handleSelectAll}
                  aria-label="Select all drafts"
                />
                <label
                  htmlFor="select-all-drafts"
                  className="font-semibold text-xs text-muted-foreground uppercase tracking-wider cursor-pointer select-none"
                >
                  Pending Queue ({drafts.length})
                </label>
              </div>
              {selectedIds.length > 0 && (
                <span className="text-[11px] font-medium text-amber-700 dark:text-amber-400">
                  {selectedIds.length} selected
                </span>
              )}
            </div>

            <div className="space-y-2">
              {drafts.map((d, index) => {
                const isSelected = selectedIndex === index;
                const isChecked = selectedIds.includes(d.id);
                const inboundText = d.inbound_snippet || d.customer_message || "Incoming customer inquiry";

                return (
                  <div
                    key={d.id}
                    onClick={() => {
                      setSelectedIndex(index);
                      setEditingId(null);
                    }}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      isSelected 
                        ? "bg-amber-500/10 border-amber-500 shadow-xs" 
                        : "bg-card hover:bg-muted/40 border-border"
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="pt-0.5">
                        <Checkbox
                          checked={isChecked}
                          onCheckedChange={() => handleToggleSelect(d.id)}
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`Select draft for ${d.customer_name}`}
                        />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <div className="font-bold text-xs text-foreground truncate">
                            {d.customer_name}
                          </div>
                          <span className="text-[10px] text-muted-foreground">
                            {new Date(d.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>

                        <div className="text-[11px] text-muted-foreground line-clamp-1 italic mb-1.5 flex items-center gap-1">
                          <MessageSquare className="w-3 h-3 shrink-0 text-muted-foreground/70" />
                          <span className="truncate">"{inboundText}"</span>
                        </div>

                        <div className="text-xs text-foreground font-medium line-clamp-2 bg-amber-500/5 p-2 rounded border border-amber-500/20">
                          {d.draft_body}
                        </div>

                        <div className="mt-2 flex justify-between items-center pt-1 border-t border-border/40">
                          <span className="text-[10px] font-mono text-muted-foreground truncate max-w-[130px]">
                            {d.customer_address}
                          </span>
                          <div className="flex gap-1">
                            <Button
                              size="xs"
                              variant="ghost"
                              className="h-6 text-[10px] text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20"
                              disabled={actionInProgress}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDiscard(d);
                              }}
                            >
                              Discard
                            </Button>
                            <Button
                              size="xs"
                              className="h-6 text-[10px] bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
                              disabled={actionInProgress}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleApprove(d);
                              }}
                            >
                              Approve
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Active Focused Draft Review & Edit Pane */}
          {currentDraft && (
            <div className="lg:col-span-7">
              <Card className="border-amber-500/30 shadow-md">
                <CardHeader className="pb-3 border-b">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <CardTitle className="text-sm font-bold">{currentDraft.customer_name}</CardTitle>
                        <Badge variant="outline" className="text-[10px] font-mono">
                          {currentDraft.customer_address}
                        </Badge>
                      </div>
                      <CardDescription className="text-xs">
                        Conversation Thread #{currentDraft.conversation_id}
                      </CardDescription>
                    </div>

                    <Badge className="bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-700">
                      Item {selectedIndex + 1} of {drafts.length}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="p-4 space-y-4">
                  {/* Customer's Incoming Message Context in Speech Bubble */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label className="text-[11px] font-semibold text-muted-foreground uppercase flex items-center gap-1.5">
                        <MessageSquare className="w-3.5 h-3.5 text-muted-foreground" /> Customer Inbound SMS:
                      </Label>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {currentDraft.customer_address}
                      </span>
                    </div>
                    <div className="relative p-3.5 rounded-2xl rounded-tl-sm bg-muted/60 border text-xs leading-relaxed text-foreground shadow-2xs">
                      {currentDraft.inbound_snippet || currentDraft.customer_message ? (
                        <p className="whitespace-pre-wrap">{currentDraft.inbound_snippet || currentDraft.customer_message}</p>
                      ) : (
                        <p className="text-muted-foreground italic flex items-center gap-1">
                          <AlertCircle className="w-3.5 h-3.5" /> No inbound customer message snippet available.
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Proposed Draft with Amber-Dashed Styling */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <Label className="text-[11px] font-semibold text-amber-700 dark:text-amber-300 uppercase flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" /> Proposed AI Response:
                      </Label>
                      {editingId !== currentDraft.id && (
                        <Button
                          type="button"
                          size="xs"
                          variant="ghost"
                          className="h-6 text-[10px] gap-1 text-amber-700 dark:text-amber-300 hover:bg-amber-500/10"
                          disabled={actionInProgress}
                          onClick={() => handleStartEdit(currentDraft)}
                        >
                          <Edit3 className="w-3 h-3" /> Edit in place
                        </Button>
                      )}
                    </div>

                    {editingId === currentDraft.id ? (
                      <div className="space-y-2 p-3.5 rounded-xl bg-amber-500/10 border border-dashed border-amber-500/40 text-foreground dark:text-amber-100 shadow-xs">
                        <div className="flex items-center justify-between gap-1.5 mb-1">
                          <Badge variant="outline" className="bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/40 text-[10px] font-semibold gap-1 py-0.5 px-2">
                            <Sparkles className="w-3 h-3 text-amber-600 dark:text-amber-400" /> AI Draft
                          </Badge>
                          <span className="text-[10px] font-medium text-amber-700/80 dark:text-amber-300/80">
                            Editing draft reply
                          </span>
                        </div>
                        <Textarea
                          aria-label="Edit proposed AI draft"
                          value={editingText}
                          onChange={(e) => setEditingText(e.target.value)}
                          rows={4}
                          maxLength={1600}
                          className="text-xs bg-background text-foreground border-amber-500/40 focus-visible:ring-amber-500"
                        />
                        <div className="flex items-center justify-between pt-1">
                          <span className="text-[10px] font-mono text-muted-foreground">
                            {editingText.length} / 1600 characters ({Math.ceil(editingText.length / 160) || 1} segment{Math.ceil(editingText.length / 160) > 1 ? "s" : ""})
                          </span>
                          <div className="flex gap-2">
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => setEditingId(null)}
                              disabled={actionInProgress}
                              className="h-7 text-xs"
                            >
                              Cancel
                            </Button>
                            <Button
                              size="xs"
                              onClick={() => handleSaveAndSend(currentDraft)}
                              disabled={!editingText.trim() || actionInProgress}
                              className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-semibold gap-1"
                            >
                              <Send className="w-3 h-3" /> Approve & Send
                            </Button>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="p-4 rounded-xl bg-amber-500/10 border border-dashed border-amber-500/40 text-foreground dark:text-amber-100 shadow-xs space-y-2">
                        <div className="flex items-center justify-between gap-1.5">
                          <Badge variant="outline" className="bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/40 text-[10px] font-semibold gap-1 py-0.5 px-2">
                            <Sparkles className="w-3 h-3 text-amber-600 dark:text-amber-400" /> AI Draft
                          </Badge>
                          <span className="text-[10px] font-medium text-amber-700/80 dark:text-amber-300/80">
                            Awaiting human approval
                          </span>
                        </div>
                        <p className="text-xs leading-relaxed whitespace-pre-wrap">
                          {currentDraft.draft_body}
                        </p>
                        <div className="flex justify-end pt-1 border-t border-amber-500/20">
                          <span className="text-[10px] font-mono text-amber-700/70 dark:text-amber-300/70">
                            {currentDraft.draft_body.length} / 1600 characters ({Math.ceil(currentDraft.draft_body.length / 160) || 1} segment{Math.ceil(currentDraft.draft_body.length / 160) > 1 ? "s" : ""})
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 1-Click Action Buttons */}
                  {editingId !== currentDraft.id && (
                    <div className="flex flex-col sm:flex-row gap-2 pt-2 border-t">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDiscard(currentDraft)}
                        disabled={actionInProgress}
                        className="flex-1 border-red-200 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20 text-xs gap-1.5 h-9"
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Discard Draft
                      </Button>

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleStartEdit(currentDraft)}
                        disabled={actionInProgress}
                        className="flex-1 text-xs gap-1.5 h-9"
                      >
                        <Edit3 className="w-3.5 h-3.5" /> Modify Reply
                      </Button>

                      <Button
                        size="sm"
                        onClick={() => handleApprove(currentDraft)}
                        disabled={actionInProgress}
                        className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs gap-1.5 h-9 shadow-xs"
                      >
                        <Check className="w-4 h-4" /> Approve & Send
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* Bulk Discard Confirmation Dialog */}
      <Dialog open={bulkDiscardOpen} onOpenChange={setBulkDiscardOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-base font-bold flex items-center gap-2 text-destructive">
              <Trash2 className="w-5 h-5" /> Bulk Discard Drafts
            </DialogTitle>
            <DialogDescription className="text-xs">
              You are about to discard {selectedIds.length} draft {selectedIds.length === 1 ? "reply" : "replies"}. This action cannot be undone. Please provide a reason for the audit log.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="bulk-discard-reason" className="text-xs font-medium">
                Discard Reason <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="bulk-discard-reason"
                placeholder="e.g. Customer query already answered in-person, obsolete proposal..."
                value={bulkDiscardReason}
                onChange={(e) => setBulkDiscardReason(e.target.value)}
                rows={3}
                maxLength={1000}
                className="text-xs resize-none"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>Required for compliance & audit history</span>
                <span>{bulkDiscardReason.length}/1000</span>
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setBulkDiscardOpen(false);
                setBulkDiscardReason("");
              }}
              disabled={actionInProgress}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={!bulkDiscardReason.trim() || actionInProgress}
              onClick={handleBulkDiscard}
              className="gap-1.5 font-semibold"
            >
              <Trash2 className="w-3.5 h-3.5" />
              {actionInProgress ? "Discarding..." : `Discard ${selectedIds.length} Draft${selectedIds.length === 1 ? "" : "s"}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default SmsTriageTab;
