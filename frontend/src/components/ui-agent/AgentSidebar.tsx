import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot,
  Send,
  Square,
  RotateCcw,
  PanelRightClose,
  Sparkles,
  Settings,
  Mic,
  Activity,
  MessageSquare,
} from "lucide-react";
import { useAgent, type AgentMessage, type AgentLog } from "./AgentProvider.tsx";
import { VoiceBar } from "./VoiceBar.tsx";
import { SettingsPanel } from "./SettingsPanel.tsx";
import { MobileAgent } from "./MobileAgent.tsx";
import { AgentDiagnosticsPanel } from "./AgentDiagnosticsPanel.tsx";
import { useBusinessAssistantOptional } from "@/pages/admin/business-assistant/business-assistant-context.tsx";
import { cn } from "@/lib/utils.ts";

const STATUS_COLOR: Record<string, string> = {
  IDLE: "text-slate-400",
  THINKING: "text-amber-400",
  STOPPED: "text-rose-400",
};

const MessageItem: React.FC<{ m: AgentMessage; i: number }> = ({ m, i }) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    data-testid={`agent-message-${i}`}
    className={`agent-msg agent-msg-${m.role}`}
  >
    {m.source === "voice" && <Mic className="mr-1.5 inline h-3 w-3 opacity-70" />}
    {m.text}
  </motion.div>
);

const LogStream: React.FC<{ logs: AgentLog[] }> = ({ logs }) => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo(0, ref.current.scrollHeight);
  }, [logs]);

  return (
    <div
      ref={ref}
      data-testid="agent-action-log"
      className="h-28 overflow-y-auto border-t border-white/5 bg-black/30 px-4 py-2 font-mono text-[11px]"
    >
      {logs.length === 0 && <p className="text-slate-600">// action stream</p>}
      {logs.map((l, i) => (
        <p key={i} className={l.ok ? "text-cyan-300/80" : "text-rose-400"}>
          <span className="text-slate-600">[{l.t}s]</span> {l.text}
        </p>
      ))}
    </div>
  );
};

const DEFAULT_W = 380;
const clampW = (w: number) =>
  Math.round(
    Math.max(300, Math.min(w, Math.min(760, typeof window !== "undefined" ? window.innerWidth * 0.65 : 400))),
  );

const useResizable = () => {
  const [width, setWidth] = useState(() =>
    typeof window !== "undefined" ? Number(localStorage.getItem("agent_panel_w")) || DEFAULT_W : DEFAULT_W,
  );

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("agent_panel_w", String(width));
    }
  }, [width]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onResize = () => setWidth((w) => clampW(w));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    const move = (ev: MouseEvent) => setWidth(clampW(window.innerWidth - ev.clientX));
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      document.body.style.userSelect = "";
    };
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  return { width, setWidth, onPointerDown };
};

export interface AgentSidebarProps {
  suggestions?: string[];
}

export const AgentSidebar: React.FC<AgentSidebarProps> = (props) => (
  <>
    <DesktopSidebar {...props} />
    <MobileAgent />
  </>
);

const DesktopSidebar: React.FC<AgentSidebarProps> = ({
  suggestions = [
    "Navigate to services and check pricing",
    "Help me onboard a new client",
    "Open calendar and inspect schedule",
  ],
}) => {
  const { send, stop, reset, busy, status, messages, logs, lastSnapshot } = useAgent();
  const ba = useBusinessAssistantOptional();

  const [open, setOpen] = useState(() =>
    typeof window !== "undefined" ? localStorage.getItem("agent_panel_open") !== "false" : true,
  );
  const [activeTab, setActiveTab] = useState<"chat" | "diagnostics">("chat");
  const [flipped, setFlipped] = useState(false);
  const { width, setWidth, onPointerDown } = useResizable();

  // Keep layout CSS var synced with sidebar open state
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("agent_panel_open", String(open));
      document.documentElement.style.setProperty("--agent-w", open ? `${width}px` : "0px");
    }
  }, [open, width]);

  // Synchronize with external drawer open events (e.g. support button or header bot)
  useEffect(() => {
    if (ba?.drawerOpen) {
      setOpen(true);
    }
  }, [ba?.drawerOpen]);

  const [text, setText] = useState("");
  const chatRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    chatRef.current?.scrollTo(0, chatRef.current.scrollHeight);
  }, [messages]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (text.trim()) {
      send(text);
      setText("");
    }
  };

  const handleClose = () => {
    setOpen(false);
    if (ba?.drawerOpen) {
      ba.closeDrawer();
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        data-agent-ignore
        data-testid="agent-sidebar-open"
        onClick={() => setOpen(true)}
        className="agent-fab hidden md:grid"
        title="Open Pilot Agent"
      >
        <Bot className="h-5 w-5" />
      </button>
    );
  }

  return (
    <AnimatePresence>
      <motion.aside
        data-agent-ignore
        data-testid="agent-sidebar"
        initial={{ x: 400 }}
        animate={{ x: 0 }}
        style={{ width: `min(${width}px, 92vw)` }}
        className="agent-sidebar hidden md:block"
      >
        <div
          data-testid="agent-resize-handle"
          onPointerDown={onPointerDown}
          onDoubleClick={() => setWidth(DEFAULT_W)}
          title="Drag to resize · double-click to reset"
          className="agent-resize"
        />
        <motion.div
          className="agent-flip"
          animate={{ rotateY: flipped ? 180 : 0 }}
          transition={{ type: "spring", stiffness: 160, damping: 22 }}
        >
          <div className="agent-face" aria-hidden={flipped}>
            {/* Main Header */}
            <header className="flex items-center justify-between border-b border-white/5 px-4 py-3 shrink-0">
              <div className="flex items-center gap-2">
                <div className="grid h-8 w-8 place-items-center rounded-md bg-indigo-500/20 text-indigo-300">
                  <Bot className="h-4 w-4" />
                </div>
                <div>
                  <p className="font-display text-sm font-bold text-slate-100">Pilot Agent</p>
                  <p
                    data-testid="agent-status"
                    className={`font-mono text-[10px] tracking-widest ${
                      STATUS_COLOR[status] || "text-cyan-400"
                    }`}
                  >
                    ● {status}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  data-testid="agent-diagnostics-toggle"
                  title={activeTab === "diagnostics" ? "Switch to Chat View" : "Toggle Diagnostics Mode"}
                  onClick={() => setActiveTab((t) => (t === "diagnostics" ? "chat" : "diagnostics"))}
                  className={cn(
                    "agent-icon-btn",
                    activeTab === "diagnostics" && "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  )}
                >
                  <Activity className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  data-testid="agent-reset-btn"
                  title="New session"
                  onClick={reset}
                  className="agent-icon-btn"
                >
                  <RotateCcw className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  data-testid="agent-settings-btn"
                  title="Settings"
                  onClick={() => setFlipped(true)}
                  className="agent-icon-btn"
                >
                  <Settings className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  data-testid="agent-sidebar-close"
                  title="Collapse"
                  onClick={handleClose}
                  className="agent-icon-btn"
                >
                  <PanelRightClose className="h-4 w-4" />
                </button>
              </div>
            </header>

            {/* Mode Switcher Tabs (Chat vs Diagnostics) */}
            <div className="flex items-center gap-1 border-b border-white/5 bg-black/25 px-3 py-1.5 shrink-0">
              <button
                type="button"
                data-testid="agent-tab-chat"
                onClick={() => setActiveTab("chat")}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  activeTab === "chat"
                    ? "bg-indigo-500/20 text-indigo-200 border border-indigo-500/40"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                )}
              >
                <MessageSquare className="h-3.5 w-3.5" />
                <span>Chat</span>
              </button>
              <button
                type="button"
                data-testid="agent-tab-diagnostics"
                onClick={() => setActiveTab("diagnostics")}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  activeTab === "diagnostics"
                    ? "bg-cyan-500/20 text-cyan-200 border border-cyan-500/40"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                )}
              >
                <Activity className="h-3.5 w-3.5" />
                <span>Diagnostics</span>
                {(lastSnapshot?.elements.length ?? 0) > 0 && (
                  <span className="rounded-full bg-cyan-500/25 px-1.5 py-0.2 font-mono text-[9px] text-cyan-200">
                    {lastSnapshot?.elements.length}
                  </span>
                )}
              </button>
            </div>

            {/* Mode Content */}
            {activeTab === "diagnostics" ? (
              <AgentDiagnosticsPanel onSwitchToChat={() => setActiveTab("chat")} />
            ) : (
              <>
                <div
                  ref={chatRef}
                  data-testid="agent-chat-messages"
                  className="flex-1 space-y-3 overflow-y-auto px-4 py-4"
                >
                  {messages.length === 0 && (
                    <div className="space-y-3">
                      <p className="text-sm leading-relaxed text-slate-400">
                        I can drive this whole app for you — navigate, fill forms, click and read. Watch the cursor.
                      </p>
                      {suggestions.map((s, i) => (
                        <button
                          key={s}
                          type="button"
                          data-testid={`agent-suggestion-${i}`}
                          onClick={() => send(s)}
                          disabled={busy}
                          className="agent-chip"
                        >
                          <Sparkles className="h-3 w-3 shrink-0 text-cyan-400" /> {s}
                        </button>
                      ))}
                    </div>
                  )}
                  {messages.map((m, i) => (
                    <MessageItem key={i} m={m} i={i} />
                  ))}
                  {busy && status === "THINKING" && (
                    <div data-testid="agent-thinking" className="agent-dots">
                      <span />
                      <span />
                      <span />
                    </div>
                  )}
                </div>

                <LogStream logs={logs} />
                <VoiceBar />

                <form onSubmit={submit} className="flex items-center gap-2 border-t border-white/5 p-3 shrink-0">
                  <input
                    data-testid="agent-chat-input"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={busy ? "Agent is working…" : "Tell the agent what to do…"}
                    className="flex-1 rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-indigo-400/60"
                  />
                  {busy ? (
                    <button
                      type="button"
                      data-testid="agent-stop-btn"
                      onClick={stop}
                      className="agent-send bg-rose-500/80 hover:bg-rose-500"
                    >
                      <Square className="h-4 w-4" />
                    </button>
                  ) : (
                    <button
                      type="submit"
                      data-testid="agent-send-btn"
                      className="agent-send bg-indigo-500 hover:bg-indigo-400"
                    >
                      <Send className="h-4 w-4" />
                    </button>
                  )}
                </form>
              </>
            )}
          </div>

          {/* Flipped Card: Settings Panel */}
          <div className="agent-face agent-face-back" aria-hidden={!flipped}>
            {flipped && (
              <SettingsPanel
                onClose={() => setFlipped(false)}
                onResetWidth={() => setWidth(DEFAULT_W)}
              />
            )}
          </div>
        </motion.div>
      </motion.aside>
    </AnimatePresence>
  );
};
