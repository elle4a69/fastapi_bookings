import { useState, useEffect, useRef } from "react";
import { 
  Terminal, 
  Play, 
  Pause, 
  Trash2, 
  Send, 
  Activity, 
  Cpu, 
  Download
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

interface LogEntry {
  id: string;
  timestamp: string;
  level: "INFO" | "TOOL" | "AI" | "WARN" | "SUCCESS";
  tag: string;
  message: string;
}

const INITIAL_LOGS: LogEntry[] = [
  {
    id: "1",
    timestamp: new Date(Date.now() - 30000).toLocaleTimeString(),
    level: "INFO",
    tag: "AGENT_INIT",
    message: "FastAPI SMS Assistant daemon initialized. Listening on Webhook channels."
  },
  {
    id: "2",
    timestamp: new Date(Date.now() - 25000).toLocaleTimeString(),
    level: "INFO",
    tag: "RAG_LOAD",
    message: "Loaded 24 vector knowledge embeddings into in-memory search space."
  },
  {
    id: "3",
    timestamp: new Date(Date.now() - 18000).toLocaleTimeString(),
    level: "TOOL",
    tag: "TOOL_CALL",
    message: "tool=check_calendar_availability service_id=1 duration=60 range=7_days"
  },
  {
    id: "4",
    timestamp: new Date(Date.now() - 15000).toLocaleTimeString(),
    level: "AI",
    tag: "LLM_INFERENCE",
    message: "Tokens: 242 prompt, 58 completion. Model: gpt-4o-mini latency: 310ms"
  },
  {
    id: "5",
    timestamp: new Date(Date.now() - 10000).toLocaleTimeString(),
    level: "SUCCESS",
    tag: "DISPATCH",
    message: "Outbound draft queued for conversation_id=4: 'We have Friday at 2:00 PM available!'"
  }
];

export function SmsAgentConsoleTab() {
  const [logs, setLogs] = useState<LogEntry[]>(INITIAL_LOGS);
  const [isRunning, setIsRunning] = useState(true);
  const [inputCommand, setInputCommand] = useState("");
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Simulate periodic heartbeat/activity when running
  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => {
      const mockEvents = [
        { level: "INFO" as const, tag: "HEARTBEAT", message: "Polling SMS outbox jobs queue: 0 pending, 0 retrying." },
        { level: "TOOL" as const, tag: "CALENDAR_SYNC", message: "Cached slot index refreshed for next 7 days." },
        { level: "INFO" as const, tag: "SESSION_GC", message: "Cleaned up 0 expired visitor arrival tokens." }
      ];
      const randomEvent = mockEvents[Math.floor(Math.random() * mockEvents.length)];
      setLogs(prev => [
        ...prev.slice(-80), // keep last 80 logs
        {
          id: String(Date.now()),
          timestamp: new Date().toLocaleTimeString(),
          level: randomEvent.level,
          tag: randomEvent.tag,
          message: randomEvent.message
        }
      ]);
    }, 12000);
    return () => clearInterval(interval);
  }, [isRunning]);

  const handleInjectCommand = () => {
    if (!inputCommand.trim()) return;
    const cmd = inputCommand.trim();
    setInputCommand("");

    const newLogs: LogEntry[] = [
      {
        id: String(Date.now()),
        timestamp: new Date().toLocaleTimeString(),
        level: "INFO",
        tag: "USER_INPUT",
        message: `Command issued: "${cmd}"`
      },
      {
        id: String(Date.now() + 1),
        timestamp: new Date().toLocaleTimeString(),
        level: "TOOL",
        tag: "AGENT_EXEC",
        message: `Parsing query "${cmd}" -> extracted intent=INQUIRY, routing to PromptEngine.`
      },
      {
        id: String(Date.now() + 2),
        timestamp: new Date().toLocaleTimeString(),
        level: "SUCCESS",
        tag: "EXEC_OK",
        message: `Simulated agent turn completed successfully.`
      }
    ];

    setLogs(prev => [...prev, ...newLogs]);
    toast.success("Command injected into agent runner");
  };

  const handleClearLogs = () => {
    setLogs([]);
    toast.info("Console log cleared");
  };

  const handleDownloadLogs = () => {
    const text = logs.map(l => `[${l.timestamp}] [${l.level}] [${l.tag}] ${l.message}`).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agent-console-logs-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Console trace downloaded");
  };

  const getLevelStyle = (level: LogEntry["level"]) => {
    switch (level) {
      case "INFO":
        return "text-blue-400";
      case "TOOL":
        return "text-amber-400";
      case "AI":
        return "text-purple-400";
      case "SUCCESS":
        return "text-emerald-400";
      case "WARN":
        return "text-rose-400";
      default:
        return "text-zinc-400";
    }
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 sm:p-4 rounded-xl border bg-card shadow-xs">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-zinc-900 text-emerald-400 border border-zinc-800 shrink-0">
            <Terminal className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-bold text-foreground">Onboard Agent Console & Live Runner</h2>
              <Badge variant={isRunning ? "default" : "secondary"} className="gap-1.5 text-[10px]">
                <span className={`w-2 h-2 rounded-full ${isRunning ? "bg-emerald-400 animate-pulse" : "bg-zinc-400"}`} />
                {isRunning ? "Daemon Active" : "Paused"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Direct terminal window inspecting live reasoning loops, tool invocations, and vector RAG retrieval.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={() => setIsRunning(prev => !prev)}
            className="h-8 text-xs gap-1.5"
          >
            {isRunning ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span>{isRunning ? "Pause Loop" : "Resume Loop"}</span>
          </Button>

          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={handleDownloadLogs}
            className="h-8 text-xs gap-1"
          >
            <Download className="w-3 h-3" /> <span className="hidden sm:inline">Export Trace</span>
          </Button>

          <Button
            type="button"
            size="xs"
            variant="ghost"
            onClick={handleClearLogs}
            className="h-8 text-xs text-muted-foreground"
          >
            <Trash2 className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Terminal Display */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-3 sm:p-4 shadow-xl font-mono text-[11px] text-zinc-300 min-h-[380px] max-h-[550px] flex flex-col justify-between overflow-hidden">
        {/* Terminal Header */}
        <div className="flex items-center justify-between pb-3 mb-2 border-b border-zinc-800 text-zinc-500 text-[10px]">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block shrink-0" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block shrink-0" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block shrink-0" />
            <span className="ml-1.5 font-bold text-zinc-400 truncate max-w-[140px] sm:max-w-none">
              agent-orchestrator://fastapi-bookings/worker-1
            </span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            <span className="hidden sm:flex items-center gap-1"><Cpu className="w-3 h-3" /> Worker ID: #001</span>
            <span className="flex items-center gap-1"><Activity className="w-3 h-3 text-emerald-400" /> 100% OK</span>
          </div>
        </div>

        {/* Scrollable logs */}
        <div className="flex-1 overflow-y-auto space-y-1.5 pr-2">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start gap-2 leading-relaxed">
              <span className="text-zinc-600 select-none">[{log.timestamp}]</span>
              <span className={`font-bold px-1 rounded text-[9px] ${getLevelStyle(log.level)} select-none`}>
                [{log.tag}]
              </span>
              <span className="flex-1 text-zinc-200">{log.message}</span>
            </div>
          ))}
          <div ref={terminalEndRef} />
        </div>

        {/* Terminal Input Bar */}
        <div className="pt-3 mt-2 border-t border-zinc-800 flex gap-2 items-center">
          <span className="text-emerald-400 font-bold select-none">&gt;</span>
          <Input
            value={inputCommand}
            onChange={(e) => setInputCommand(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleInjectCommand()}
            placeholder="Inject test SMS text or agent instruction (e.g. 'Can I book for tomorrow?')..."
            className="flex-1 h-8 text-xs font-mono bg-zinc-900 border-zinc-800 text-zinc-100 placeholder:text-zinc-600 focus-visible:ring-emerald-500"
          />
          <Button
            size="xs"
            onClick={handleInjectCommand}
            className="h-8 bg-emerald-600 hover:bg-emerald-700 text-white font-mono gap-1 text-xs"
          >
            <Send className="w-3 h-3" /> Inject
          </Button>
        </div>
      </div>
    </div>
  );
}
export default SmsAgentConsoleTab;
