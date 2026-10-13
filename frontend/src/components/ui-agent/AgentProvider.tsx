import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import { scanPage, type PageSnapshot } from "./scanner.ts";
import {
  createExecutor,
  type AgentAction,
  type ActionResult,
  type UIController,
} from "./executor.ts";
import { GhostCursor, type CursorState, type HighlightState } from "./GhostCursor.tsx";
import { streamChat } from "./stream.ts";
import { authenticatedAdminFetch } from "../../lib/api.ts";

export const SPEEDS = { slow: 1.8, realistic: 1, fast: 0.4 } as const;
export type AgentSpeed = keyof typeof SPEEDS;

const MAX_STEPS = 12;

export interface AgentMessage {
  id?: string;
  role: "user" | "agent" | "error";
  text: string;
  source?: string;
}

export interface AgentLog {
  t: string;
  text: string;
  ok: boolean;
}

export interface AgentContextValue {
  send: (text: string, options?: { source?: string }) => Promise<string | null>;
  executeDirect: (action: AgentAction) => Promise<ActionResult>;
  replay: (actions: AgentAction[]) => Promise<void>;
  stop: () => void;
  reset: () => void;
  busy: boolean;
  status: string;
  messages: AgentMessage[];
  logs: AgentLog[];
  speed: AgentSpeed;
  setSpeed: (speed: AgentSpeed) => void;
  cursor: CursorState;
  highlight: HighlightState | null;
}

const AgentCtx = createContext<AgentContextValue | null>(null);

export const useAgent = (): AgentContextValue => {
  const ctx = useContext(AgentCtx);
  if (!ctx) {
    throw new Error("useAgent must be used within an AgentProvider");
  }
  return ctx;
};

const newSession = () => {
  const id = `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  if (typeof window !== "undefined") {
    localStorage.setItem("agent_session", id);
  }
  return id;
};

export interface AgentProviderProps {
  children: React.ReactNode;
  routes?: Array<{ path: string; title?: string } | string>;
  contentSelector?: string;
  apiEndpoint?: string;
}

export const AgentProvider: React.FC<AgentProviderProps> = ({
  children,
  routes = [],
  contentSelector = "main",
  apiEndpoint = "/api/admin/ui-agent",
}) => {
  const navigate = useNavigate();
  const [cursor, setCursor] = useState<CursorState>({
    x: typeof window !== "undefined" ? window.innerWidth / 2 : 0,
    y: 120,
    visible: false,
    pulse: false,
  });
  const [highlight, setHighlight] = useState<HighlightState | null>(null);
  const [status, setStatus] = useState("IDLE");
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [busy, setBusy] = useState(false);
  const [speed, setSpeed] = useState<AgentSpeed>("realistic");

  const sessionRef = useRef<string>(
    typeof window !== "undefined"
      ? localStorage.getItem("agent_session") || newSession()
      : "ssr-session",
  );
  const abortRef = useRef(false);
  const busyRef = useRef(false);
  const speedRef = useRef<number>(SPEEDS[speed]);
  speedRef.current = SPEEDS[speed];
  const t0 = useRef(Date.now());

  const log = useCallback((text: string, ok = true) => {
    setLogs((l) => [
      ...l.slice(-80),
      { t: ((Date.now() - t0.current) / 1000).toFixed(1), text, ok },
    ]);
  }, []);

  const ui: UIController = useMemo(
    () => ({
      point: (el: HTMLElement, label?: string) => {
        const r = el.getBoundingClientRect();
        setCursor((c) => ({
          ...c,
          visible: true,
          x: r.left + Math.min(r.width / 2, 60),
          y: r.top + r.height / 2,
        }));
        setHighlight({
          x: r.left,
          y: r.top,
          w: r.width,
          h: r.height,
          label,
        });
      },
      clickPulse: () => {
        setCursor((c) => ({ ...c, pulse: true }));
        setTimeout(() => setCursor((c) => ({ ...c, pulse: false })), 450);
      },
      hide: () => setHighlight(null),
      status: setStatus,
      speed: () => speedRef.current,
      aborted: () => abortRef.current,
    }),
    [],
  );

  const execute = useMemo(() => createExecutor({ ui, navigate }), [ui, navigate]);
  const snapshot = useCallback(
    (): PageSnapshot => scanPage({ routes, contentSelector }),
    [routes, contentSelector],
  );

  const executeDirect = useCallback(
    async (action: AgentAction): Promise<ActionResult> => {
      return execute(action);
    },
    [execute],
  );

  const send = useCallback(
    async (text: string, { source = "text" }: { source?: string } = {}): Promise<string | null> => {
      if (busyRef.current || !text.trim()) return null;
      busyRef.current = true;
      abortRef.current = false;
      t0.current = Date.now();
      setBusy(true);
      setMessages((m) => [...m, { role: "user", text, source }]);

      let body: Record<string, unknown> = {
        session_id: sessionRef.current,
        message: text,
        page_state: snapshot(),
      };
      const said: string[] = [];

      try {
        for (let step = 0; step < MAX_STEPS && !abortRef.current; step++) {
          setStatus("THINKING");
          const id = `${Date.now()}-${step}`;
          const upsert = (fn: (cur: string) => string) =>
            setMessages((m) =>
              m.some((x) => x.id === id)
                ? m.map((x) => (x.id === id ? { ...x, text: fn(x.text) } : x))
                : [...m, { id, role: "agent", text: fn("") }],
            );

          const data = await streamChat(
            `${apiEndpoint}/chat/stream`,
            body,
            (delta) => upsert((cur) => cur + delta),
          );

          if (data.say) {
            upsert(() => data.say);
            said.push(data.say);
          }

          const results: ActionResult[] = [];
          for (const a of data.actions || []) {
            if (abortRef.current) break;
            const r = await execute(a);
            log(r.ok ? r.result || "Action succeeded" : `${a.type} failed: ${r.error}`, r.ok);
            results.push(r);
          }

          if (!data.continue && results.every((r) => r.ok)) {
            if (results.length) {
              authenticatedAdminFetch(
                `${apiEndpoint}/sessions/${sessionRef.current}/final`,
                {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    results,
                    path: typeof window !== "undefined" ? window.location.pathname : "",
                  }),
                },
              ).catch(() => {});
            }
            break;
          }

          await new Promise((r) => setTimeout(r, 300));
          body = {
            session_id: sessionRef.current,
            observation: results,
            page_state: snapshot(),
          };
        }
      } catch (e) {
        const msg = (e as any)?.response?.data?.detail || (e as Error).message;
        setMessages((m) => [...m, { role: "error", text: msg }]);
        said.push(`Sorry, something went wrong: ${msg}`);
      } finally {
        busyRef.current = false;
        setBusy(false);
        setStatus(abortRef.current ? "STOPPED" : "IDLE");
        setHighlight(null);
        setCursor((c) => ({ ...c, visible: false }));
      }

      return said.slice(-2).join(" ");
    },
    [apiEndpoint, execute, log, snapshot],
  );

  const stop = useCallback(() => {
    abortRef.current = true;
    log("Execution stopped by user", false);
  }, [log]);

  const replay = useCallback(
    async (actions: AgentAction[]) => {
      if (busy) return;
      abortRef.current = false;
      t0.current = Date.now();
      setBusy(true);
      log(`Replaying ${actions.length} actions`);
      try {
        for (const a of actions) {
          if (abortRef.current) break;
          const r = await execute(a);
          log(
            r.ok ? `[replay] ${r.result}` : `[replay] ${a.type} failed: ${r.error}`,
            r.ok,
          );
        }
      } finally {
        setBusy(false);
        setStatus(abortRef.current ? "STOPPED" : "IDLE");
        setHighlight(null);
        setCursor((c) => ({ ...c, visible: false }));
      }
    },
    [busy, execute, log],
  );

  const reset = useCallback(() => {
    sessionRef.current = newSession();
    setMessages([]);
    setLogs([]);
  }, []);

  // Listen for window events to trigger UI automation (e.g. from Business Assistant or Grok tool runner)
  useEffect(() => {
    if (typeof window === "undefined") return;

    const handleOperateApp = (event: Event) => {
      const custom = event as CustomEvent<{
        instruction?: string;
        text?: string;
        action?: AgentAction;
        actions?: AgentAction[];
        source?: string;
      }>;
      const instruction = custom.detail?.instruction || custom.detail?.text;
      if (instruction) {
        send(instruction, { source: custom.detail?.source || "rpc" });
      } else if (custom.detail?.action) {
        executeDirect(custom.detail.action);
      } else if (custom.detail?.actions && Array.isArray(custom.detail.actions)) {
        replay(custom.detail.actions);
      }
    };

    window.addEventListener("ui-agent:operate", handleOperateApp);
    window.addEventListener("operate_app", handleOperateApp);
    return () => {
      window.removeEventListener("ui-agent:operate", handleOperateApp);
      window.removeEventListener("operate_app", handleOperateApp);
    };
  }, [executeDirect, replay, send]);

  const value: AgentContextValue = useMemo(
    () => ({
      send,
      executeDirect,
      replay,
      stop,
      reset,
      busy,
      status,
      messages,
      logs,
      speed,
      setSpeed,
      cursor,
      highlight,
    }),
    [
      busy,
      cursor,
      executeDirect,
      highlight,
      logs,
      messages,
      replay,
      reset,
      send,
      speed,
      status,
      stop,
    ],
  );

  return (
    <AgentCtx.Provider value={value}>
      {children}
      <GhostCursor cursor={cursor} highlight={highlight} />
    </AgentCtx.Provider>
  );
};
