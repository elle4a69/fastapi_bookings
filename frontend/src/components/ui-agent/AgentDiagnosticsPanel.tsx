import React, { useState, useMemo, useEffect, useRef } from "react";
import {
  Activity,
  Crosshair,
  Search,
  RefreshCw,
  Copy,
  Check,
  ChevronRight,
  ChevronDown,
  Terminal,
  Volume2,
  Mic,
  MicOff,
  Trash2,
  CheckCircle2,
  XCircle,
  Eye,
  MousePointer,
  Sparkles,
  MessageSquare,
} from "lucide-react";
import { useAgent } from "./AgentProvider.tsx";
import { useVoice } from "./VoiceProvider.tsx";
import { DiagnosticModeToggle } from "@/pages/admin/business-assistant/components/DiagnosticModeToggle.tsx";
import { cn } from "@/lib/utils.ts";

export interface AgentDiagnosticsPanelProps {
  className?: string;
  onSwitchToChat?: () => void;
}

type DiagSubTab = "dom" | "actions" | "voice" | "raw";

export const AgentDiagnosticsPanel: React.FC<AgentDiagnosticsPanelProps> = ({
  className = "",
  onSwitchToChat,
}) => {
  const {
    status,
    busy,
    lastSnapshot,
    refreshSnapshot,
    actionHistory,
    highlightRef,
    clearLogs,
    logs,
    highlight,
    messages,
    executeDirect,
  } = useAgent();

  const v = useVoice();

  const [subTab, setSubTab] = useState<DiagSubTab>("dom");
  const [domSearch, setDomSearch] = useState("");
  const [copied, setCopied] = useState(false);
  const [selectedRawView, setSelectedRawView] = useState<"snapshot" | "actions" | "messages">("snapshot");
  const [expandedActionIndex, setExpandedActionIndex] = useState<number | null>(null);
  const [logFilter, setLogFilter] = useState<"ALL" | "VOICE" | "TOOL" | "ERROR">("ALL");

  const logContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll log stream on new logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  // Refresh snapshot on mount if missing
  useEffect(() => {
    if (!lastSnapshot) {
      refreshSnapshot();
    }
  }, [lastSnapshot, refreshSnapshot]);

  // Filter scanned DOM elements
  const filteredElements = useMemo(() => {
    const list = lastSnapshot?.elements || [];
    if (!domSearch.trim()) return list;
    const q = domSearch.toLowerCase().trim();
    return list.filter(
      (el) =>
        el.ref.toLowerCase().includes(q) ||
        el.label.toLowerCase().includes(q) ||
        el.tag.toLowerCase().includes(q) ||
        (el.role && el.role.toLowerCase().includes(q)) ||
        (el.type && el.type.toLowerCase().includes(q))
    );
  }, [lastSnapshot?.elements, domSearch]);

  const handleCopyJson = (data: unknown) => {
    try {
      navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  const filteredLogs = useMemo(() => {
    if (logFilter === "ALL") return logs;
    if (logFilter === "ERROR") return logs.filter((l) => !l.ok);
    if (logFilter === "TOOL") return logs.filter((l) => l.text.includes("failed") || l.text.includes("Navigated") || l.text.includes("Clicked") || l.text.includes("Typed") || l.text.includes("Selected"));
    if (logFilter === "VOICE") return logs.filter((l) => l.text.toLowerCase().includes("voice") || l.text.toLowerCase().includes("gpt-live") || l.text.toLowerCase().includes("delegat"));
    return logs;
  }, [logs, logFilter]);

  return (
    <div
      data-testid="agent-diagnostics-panel"
      className={cn("flex flex-1 flex-col overflow-hidden bg-[#0A0F1D] text-slate-200 text-xs", className)}
    >
      {/* Diagnostics Header & Metric Strip */}
      <div className="border-b border-white/10 bg-black/40 p-3 space-y-2.5 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 font-semibold text-slate-100">
            <Activity className="h-4 w-4 text-cyan-400" />
            <span>Diagnostics Inspector</span>
          </div>
          <div className="flex items-center gap-1.5">
            {onSwitchToChat && (
              <button
                type="button"
                onClick={onSwitchToChat}
                className="flex items-center gap-1 rounded bg-white/5 px-2 py-0.5 text-[10px] text-slate-300 hover:bg-white/10 transition-colors"
                title="Return to Chat"
              >
                <MessageSquare className="h-3 w-3 text-indigo-400" />
                <span>Chat</span>
              </button>
            )}
            <span
              data-testid="diag-status-pill"
              className={cn(
                "rounded-full px-2 py-0.5 font-mono text-[10px] uppercase font-semibold",
                status === "THINKING"
                  ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                  : status === "RUNNING"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "bg-slate-800 text-slate-400 border border-slate-700"
              )}
            >
              ● {status}
            </span>
          </div>
        </div>

        {/* Global Diagnostic Mode Toggle */}
        <DiagnosticModeToggle compact />

        {/* 3 Metric Pills */}
        <div className="grid grid-cols-3 gap-1.5 text-center font-mono text-[10px]">
          <div className="rounded-md border border-white/5 bg-white/5 p-1.5">
            <span className="block text-slate-400">Scanned DOM</span>
            <span data-testid="diag-element-count" className="font-bold text-cyan-300 text-xs">
              {lastSnapshot?.elements.length ?? 0}
            </span>
          </div>
          <div className="rounded-md border border-white/5 bg-white/5 p-1.5 truncate">
            <span className="block text-slate-400">Target Ref</span>
            <span
              data-testid="diag-active-target"
              className="font-bold text-amber-300 text-xs truncate block"
              title={highlight?.label || "None"}
            >
              {highlight?.label ? highlight.label.slice(0, 14) : "None"}
            </span>
          </div>
          <div className="rounded-md border border-white/5 bg-white/5 p-1.5">
            <span className="block text-slate-400">Voice Link</span>
            <span
              className={cn(
                "font-bold text-xs",
                v.active ? "text-emerald-400" : "text-slate-400"
              )}
            >
              {v.state}
            </span>
          </div>
        </div>

        {/* Subtabs selector */}
        <div className="flex gap-1 border-t border-white/5 pt-2">
          {(
            [
              { id: "dom", label: "DOM Scanner", icon: Crosshair },
              { id: "actions", label: "Actions", icon: Terminal },
              { id: "voice", label: "Voice/Logs", icon: Volume2 },
              { id: "raw", label: "Raw JSON", icon: Sparkles },
            ] as const
          ).map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                type="button"
                data-testid={`diag-subtab-${t.id}`}
                onClick={() => setSubTab(t.id)}
                className={cn(
                  "flex flex-1 items-center justify-center gap-1 rounded py-1 text-[11px] font-medium transition-colors",
                  subTab === t.id
                    ? "bg-cyan-500/20 text-cyan-200 font-semibold"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                )}
              >
                <Icon className="h-3 w-3" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* SUBTAB 1: LIVE DOM SCANNER */}
      {subTab === "dom" && (
        <div className="flex flex-1 flex-col overflow-hidden p-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-500" />
              <input
                data-testid="diag-dom-search"
                type="text"
                placeholder="Filter refs, tags, labels…"
                value={domSearch}
                onChange={(e) => setDomSearch(e.target.value)}
                className="w-full rounded-md border border-white/10 bg-black/40 pl-8 pr-2.5 py-1 text-[11px] text-slate-100 placeholder:text-slate-600 outline-none focus:border-cyan-400/60"
              />
            </div>
            <button
              type="button"
              data-testid="diag-refresh-scan"
              onClick={() => refreshSnapshot()}
              title="Rescan current page DOM"
              className="flex items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
            >
              <RefreshCw className={cn("h-3 w-3", busy && "animate-spin")} />
              <span>Rescan</span>
            </button>
          </div>

          <div className="text-[10px] text-slate-500 flex justify-between font-mono">
            <span>Path: {lastSnapshot?.path || "/"}</span>
            <span>
              Showing {filteredElements.length} of {lastSnapshot?.elements.length ?? 0}
            </span>
          </div>

          {highlight && (
            <div className="rounded-md border border-cyan-500/40 bg-cyan-950/40 p-2 text-[11px] text-cyan-200">
              <div className="flex items-center justify-between font-medium">
                <span className="flex items-center gap-1">
                  <Eye className="h-3.5 w-3.5 text-cyan-400 animate-pulse" />
                  Active Highlight
                </span>
                <span className="font-mono text-[10px]">
                  x:{Math.round(highlight.x)} y:{Math.round(highlight.y)} w:{Math.round(highlight.w)} h:{Math.round(highlight.h)}
                </span>
              </div>
              <p className="mt-0.5 truncate text-[10px] text-cyan-300/80">
                {highlight.label || "Element targeted by GhostCursor"}
              </p>
            </div>
          )}

          <div
            data-testid="diag-elements-list"
            className="flex-1 overflow-y-auto space-y-1.5 pr-1 font-mono text-[11px]"
          >
            {filteredElements.length === 0 ? (
              <p className="text-center py-8 text-slate-600">No matching interactive elements</p>
            ) : (
              filteredElements.map((el, i) => {
                const isTarget = highlight?.label?.includes(el.ref) || highlight?.label?.includes(el.label);
                return (
                  <div
                    key={`${el.ref}-${i}`}
                    className={cn(
                      "rounded border p-2 transition-colors",
                      isTarget
                        ? "border-cyan-400 bg-cyan-950/60 shadow-[0_0_12px_rgba(6,182,212,0.25)]"
                        : "border-white/5 bg-white/5 hover:border-white/20"
                    )}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span
                        data-testid="diag-element-ref"
                        className="rounded bg-cyan-500/15 px-1.5 py-0.5 font-bold text-cyan-300 text-[10px]"
                      >
                        {el.ref}
                      </span>
                      <span className="text-[10px] text-slate-500 uppercase">
                        &lt;{el.tag}&gt;{el.type ? ` [${el.type}]` : ""}{el.role ? ` (${el.role})` : ""}
                      </span>
                    </div>

                    <div className="mt-1 font-sans text-xs text-slate-200 font-medium truncate">
                      {el.label || <span className="text-slate-600 italic">No accessible label</span>}
                    </div>

                    {el.value && (
                      <div className="mt-0.5 text-[10px] text-slate-400 truncate">
                        value: <span className="text-slate-300">"{el.value}"</span>
                      </div>
                    )}

                    <div className="mt-2 flex items-center justify-end gap-1.5 font-sans">
                      <button
                        type="button"
                        data-testid="diag-point-btn"
                        onClick={() => highlightRef(el.ref)}
                        className="flex items-center gap-1 rounded border border-cyan-500/40 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300 hover:bg-cyan-500/20 transition-colors"
                      >
                        <MousePointer className="h-3 w-3" />
                        Point
                      </button>
                      <button
                        type="button"
                        onClick={() => void executeDirect({ type: "click", ref: el.ref })}
                        className="flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-medium text-slate-300 hover:bg-white/10 transition-colors"
                      >
                        Click
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* SUBTAB 2: ACTIONS & REASONING HISTORY */}
      {subTab === "actions" && (
        <div className="flex flex-1 flex-col overflow-hidden p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-300">
              Tool Action Executions ({actionHistory.length})
            </span>
            <button
              type="button"
              onClick={clearLogs}
              className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
            >
              <Trash2 className="h-3 w-3" />
              Clear
            </button>
          </div>

          <div
            data-testid="diag-actions-history"
            className="flex-1 overflow-y-auto space-y-2 pr-1 font-mono text-[11px]"
          >
            {actionHistory.length === 0 ? (
              <div className="text-center py-12 text-slate-600 space-y-2">
                <Terminal className="h-6 w-6 mx-auto opacity-50" />
                <p>No tool actions executed yet.</p>
                <p className="text-[10px] text-slate-500">
                  Ask the assistant to navigate, click, or fill forms.
                </p>
              </div>
            ) : (
              actionHistory.map((act, i) => {
                const isExpanded = expandedActionIndex === i;
                return (
                  <div
                    key={i}
                    className="rounded border border-white/10 bg-black/30 overflow-hidden"
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedActionIndex(isExpanded ? null : i)}
                      className="w-full flex items-center justify-between p-2 text-left hover:bg-white/5 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        {act.ok ? (
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                        ) : (
                          <XCircle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
                        )}
                        <span className="rounded bg-indigo-500/20 px-1.5 py-0.2 font-bold text-indigo-300 text-[10px] uppercase">
                          {act.action.type}
                        </span>
                        <span className="truncate text-slate-200">
                          {act.action.ref || act.action.path || act.label || "Action"}
                        </span>
                      </div>
                      {isExpanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-slate-500" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-slate-500" />
                      )}
                    </button>

                    <div className="px-2.5 pb-2 text-[10px] text-slate-400 font-sans">
                      {act.ok ? (
                        <span className="text-emerald-300/90">{act.result}</span>
                      ) : (
                        <span className="text-rose-400">{act.error}</span>
                      )}
                    </div>

                    {isExpanded && (
                      <div className="border-t border-white/5 bg-black/60 p-2 font-mono text-[10px] text-cyan-300/80 overflow-x-auto">
                        <pre>{JSON.stringify(act, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* SUBTAB 3: VOICE & REALTIME EVENT LOGS */}
      {subTab === "voice" && (
        <div className="flex flex-1 flex-col overflow-hidden p-3 space-y-2.5">
          {/* Voice status card */}
          <div className="rounded-lg border border-white/10 bg-black/40 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="rounded bg-pink-500/20 px-2 py-0.5 font-mono text-[10px] uppercase font-bold text-pink-300">
                  {v.providerLabel}
                </span>
                <span className="text-slate-400 text-xs">
                  Voice: <strong className="text-slate-200 capitalize">{v.voices[v.provider]}</strong>
                </span>
              </div>
              <button
                type="button"
                onClick={v.toggle}
                className={cn(
                  "flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors",
                  v.active
                    ? "bg-pink-500 text-white shadow-[0_0_12px_rgba(236,72,153,0.5)] hover:bg-pink-400"
                    : "bg-white/10 text-slate-300 hover:bg-white/20"
                )}
              >
                {v.active ? <MicOff className="h-3 w-3" /> : <Mic className="h-3 w-3" />}
                <span>{v.active ? "Stop Voice" : "Start Voice"}</span>
              </button>
            </div>

            <div className="text-[11px] space-y-1">
              <div className="flex justify-between text-slate-400">
                <span>State: <strong className="text-slate-200 uppercase">{v.state}</strong></span>
                {v.idleLeft !== null && (
                  <span className="text-amber-400 font-mono">Auto-sleep in {v.idleLeft}s</span>
                )}
              </div>
              <div className="text-slate-400">
                Wake-word:{" "}
                <span className={v.wakeListening ? "text-cyan-400 font-mono" : "text-slate-500"}>
                  {v.wakeListening ? `Listening for "${v.wakePhrase}"` : v.wakeEnabled ? "Enabled (paused)" : "Off"}
                </span>
              </div>
              {v.caption && (
                <div className="rounded bg-black/60 p-2 text-xs italic text-slate-300 border border-white/5">
                  “{v.caption}”
                </div>
              )}
            </div>
          </div>

          {/* Logs Filter Bar */}
          <div className="flex items-center justify-between border-t border-white/5 pt-2">
            <div className="flex gap-1 font-mono text-[10px]">
              {(["ALL", "TOOL", "VOICE", "ERROR"] as const).map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setLogFilter(cat)}
                  className={cn(
                    "rounded px-2 py-0.5 transition-colors",
                    logFilter === cat
                      ? "bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/40"
                      : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={clearLogs}
              className="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
            >
              Clear
            </button>
          </div>

          {/* Log Stream Terminal */}
          <div
            ref={logContainerRef}
            data-testid="diag-event-log-stream"
            className="flex-1 overflow-y-auto rounded border border-white/5 bg-black/50 p-2.5 font-mono text-[11px] space-y-1"
          >
            {filteredLogs.length === 0 ? (
              <p className="text-slate-600">// No events matching filter</p>
            ) : (
              filteredLogs.map((l, i) => (
                <p key={i} className={l.ok ? "text-cyan-300/80" : "text-rose-400"}>
                  <span className="text-slate-600">[{l.t}s]</span> {l.text}
                </p>
              ))
            )}
          </div>
        </div>
      )}

      {/* SUBTAB 4: RAW PAYLOAD INSPECTOR */}
      {subTab === "raw" && (
        <div className="flex flex-1 flex-col overflow-hidden p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex gap-1 font-mono text-[10px]">
              {(
                [
                  { id: "snapshot", label: "DOM Snapshot" },
                  { id: "actions", label: "Tool Trace" },
                  { id: "messages", label: "Messages" },
                ] as const
              ).map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => setSelectedRawView(cat.id)}
                  className={cn(
                    "rounded px-2 py-0.5 transition-colors",
                    selectedRawView === cat.id
                      ? "bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/40"
                      : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
                  )}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              data-testid="diag-copy-json"
              onClick={() => {
                const targetData =
                  selectedRawView === "snapshot"
                    ? lastSnapshot
                    : selectedRawView === "actions"
                    ? actionHistory
                    : messages;
                handleCopyJson(targetData);
              }}
              className="flex items-center gap-1 rounded bg-white/5 px-2 py-0.5 text-[10px] text-slate-300 hover:bg-white/10 transition-colors"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
              <span>{copied ? "Copied!" : "Copy"}</span>
            </button>
          </div>

          <div className="flex-1 overflow-auto rounded border border-white/10 bg-black/60 p-3 font-mono text-[10px] text-slate-300 select-text">
            <pre>
              {JSON.stringify(
                selectedRawView === "snapshot"
                  ? lastSnapshot
                  : selectedRawView === "actions"
                  ? actionHistory
                  : messages,
                null,
                2
              )}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
