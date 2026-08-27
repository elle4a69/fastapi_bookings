import { useState, useEffect, useRef } from "react";
import { MessageSquareText, Search, Send, Play, Ban, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

interface SmsConversation {
  id: number;
  tenant_id: number;
  provider_id: number;
  sms_account_id: number;
  customer_address: string;
  client_id?: number;
  client_name?: string;
  state: string; // 'auto-reply', 'taken-over', 'paused'
  unread_count: number;
  last_activity_at: string;
}

interface SmsMessage {
  id: number;
  body: string;
  direction: string; // 'inbound', 'outbound', 'draft'
  author_type: string; // 'customer', 'staff', 'fixed_autoresponder', 'ai', 'system'
  status: string; // 'received', 'queued', 'sending', 'sent', 'delivered', 'failed', 'cancelled', 'draft', 'discarded'
  occurred_at: string;
  client_request_id?: string;
}

export default function SmsInboxTab() {
  const [conversations, setConversations] = useState<SmsConversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<SmsMessage[]>([]);
  const [activeConv, setActiveConv] = useState<SmsConversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [composeText, setComposeText] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterState, setFilterState] = useState("all");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadConversations();
    // Poll for updates every 10 seconds
    const interval = setInterval(loadConversations, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedConversationId) {
      loadMessages(selectedConversationId);
    } else {
      setMessages([]);
      setActiveConv(null);
    }
  }, [selectedConversationId]);

  const loadConversations = async () => {
    try {
      const res = await apiClient.get<SmsConversation[]>("/api/admin/sms/conversations");
      setConversations(res);
      
      // Update active conversation metadata if selected
      if (selectedConversationId) {
        const active = res.find(c => c.id === selectedConversationId);
        if (active) setActiveConv(active);
      }
    } catch (err: any) {
      console.error("Failed to load conversations:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (convId: number) => {
    try {
      const msgs = await apiClient.get<SmsMessage[]>(`/api/admin/sms/conversations/${convId}/messages`);
      setMessages(msgs);
      
      // Fetch details to mark unread count as read
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
    const textToSend = composeText;
    setComposeText("");

    const clientReqId = `click-${Date.now()}`;
    const payload = {
      body: textToSend,
      client_request_id: clientReqId
    };

    // Add message locally as "queued" immediately for fluid UX
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
      // Remove optimistic message on error
      setMessages(prev => prev.filter(m => m.id !== optimisticMessage.id));
    }
  };

  const handleTakeover = async () => {
    if (!selectedConversationId) return;
    try {
      const updated = await apiClient.post<SmsConversation>(`/api/admin/sms/conversations/${selectedConversationId}/takeover`);
      setActiveConv(updated);
      setConversations(prev => prev.map(c => c.id === updated.id ? updated : c));
      toast.success("AI paused. Conversation is now under human takeover.");
    } catch (err: any) {
      toast.error(err.message || "Takeover failed.");
    }
  };

  const handleRestoreAutoReply = async () => {
    if (!selectedConversationId) return;
    try {
      const updated = await apiClient.post<SmsConversation>(`/api/admin/sms/conversations/${selectedConversationId}/auto-reply`);
      setActiveConv(updated);
      setConversations(prev => prev.map(c => c.id === updated.id ? updated : c));
      toast.success("Auto-reply restored. AI is now active.");
    } catch (err: any) {
      toast.error(err.message || "Restoring auto-reply failed.");
    }
  };

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

  const filteredConversations = conversations.filter(c => {
    if (filterState !== "all" && c.state !== filterState) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = c.client_name?.toLowerCase().includes(q);
      const matchPhone = c.customer_address.toLowerCase().includes(q);
      return matchName || matchPhone;
    }
    return true;
  });

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

  return (
    <div className="flex h-[calc(100vh-14rem)] min-h-[500px] rounded-xl border bg-card overflow-hidden text-xs">
      {/* Side Conversation List */}
      <div className="w-80 border-r flex flex-col bg-muted/20">
        <div className="p-3 border-b space-y-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input 
              placeholder="Search conversations..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs bg-background"
            />
          </div>
          <div className="flex gap-1.5 flex-wrap">
            <Button size="xs" variant={filterState === "all" ? "default" : "outline"} onClick={() => setFilterState("all")}>All</Button>
            <Button size="xs" variant={filterState === "auto-reply" ? "default" : "outline"} onClick={() => setFilterState("auto-reply")}>AI Active</Button>
            <Button size="xs" variant={filterState === "taken-over" ? "default" : "outline"} onClick={() => setFilterState("taken-over")}>Paused</Button>
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {loading ? (
              <div className="p-4 text-center text-muted-foreground">Loading threads...</div>
            ) : filteredConversations.length === 0 ? (
              <div className="p-4 text-center text-muted-foreground">No conversations.</div>
            ) : (
              filteredConversations.map(conv => (
                <div
                  key={conv.id}
                  onClick={() => setSelectedConversationId(conv.id)}
                  className={`p-3 rounded-lg cursor-pointer transition-colors border ${
                    selectedConversationId === conv.id 
                      ? "bg-primary/5 border-primary/20 text-primary-foreground" 
                      : "hover:bg-muted/40 border-transparent"
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <span className="font-semibold text-foreground">
                      {conv.client_name || conv.customer_address}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {new Date(conv.last_activity_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  {conv.client_name && (
                    <div className="text-[10px] text-muted-foreground font-mono mt-0.5">{conv.customer_address}</div>
                  )}
                  <div className="flex items-center justify-between mt-2">
                    <div className="flex gap-1">
                      {conv.state === "taken-over" ? (
                        <Badge variant="outline" className="text-[9px] px-1 py-0 border-amber-500/20 text-amber-600 bg-amber-500/5">Manual</Badge>
                      ) : (
                        <Badge variant="outline" className="text-[9px] px-1 py-0 border-indigo-500/20 text-indigo-600 bg-indigo-500/5">AI Active</Badge>
                      )}
                    </div>
                    {conv.unread_count > 0 && (
                      <Badge className="bg-primary text-primary-foreground text-[10px] h-4 min-w-4 px-1 rounded-full flex items-center justify-center">
                        {conv.unread_count}
                      </Badge>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Conversation Thread Panel */}
      <div className="flex-1 flex flex-col bg-background">
        {activeConv ? (
          <>
            {/* Thread Header */}
            <div className="p-3 border-b flex justify-between items-center bg-muted/10">
              <div>
                <h3 className="font-semibold text-sm">{activeConv.client_name || activeConv.customer_address}</h3>
                {activeConv.client_name && (
                  <p className="text-[10px] text-muted-foreground font-mono">{activeConv.customer_address}</p>
                )}
              </div>
              <div className="flex gap-1.5">
                {activeConv.state === "taken-over" ? (
                  <Button size="xs" variant="outline" className="text-indigo-600 hover:text-indigo-700" onClick={handleRestoreAutoReply}>
                    <Play className="w-3.5 h-3.5 mr-1" /> Resume AI Bot
                  </Button>
                ) : (
                  <Button size="xs" variant="outline" className="text-amber-600 hover:text-amber-700" onClick={handleTakeover}>
                    <Ban className="w-3.5 h-3.5 mr-1" /> Pause AI / Takeover
                  </Button>
                )}
              </div>
            </div>

            {/* Messages Scroll Area */}
            <ScrollArea className="flex-1 p-4 bg-muted/5">
              <div className="space-y-3">
                {messages.map((msg) => {
                  const isInbound = msg.direction === "inbound";
                  const isDraft = msg.status === "draft";
                  
                  return (
                    <div 
                      key={msg.id}
                      className={`flex flex-col max-w-[70%] ${isInbound ? "self-start mr-auto" : "self-end ml-auto"}`}
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
                        <p className="whitespace-pre-wrap">{msg.body}</p>
                        
                        {isDraft && (
                          <div className="flex gap-1.5 mt-2.5 border-t border-indigo-200/50 pt-2 justify-end">
                            <Button size="xs" variant="outline" className="bg-white border-indigo-300 text-indigo-700 hover:bg-indigo-50" onClick={() => handleDiscardDraft(msg.id)}>
                              Discard
                            </Button>
                            <Button size="xs" className="bg-indigo-600 hover:bg-indigo-700 text-white" onClick={() => handleApproveDraft(msg.id)}>
                              Approve & Send
                            </Button>
                          </div>
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
            <div className="p-3 border-t bg-muted/10">
              <div className="flex gap-2">
                <Input 
                  placeholder={
                    activeConv.state === "taken-over" 
                      ? "Type reply..." 
                      : "Type reply (sending manually will automatically pause the AI)..."
                  } 
                  value={composeText}
                  onChange={e => setComposeText(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSend()}
                  className="flex-1 h-9 text-xs bg-background"
                />
                <Button size="sm" onClick={handleSend}>
                  <Send className="w-4 h-4" />
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
    </div>
  );
}
