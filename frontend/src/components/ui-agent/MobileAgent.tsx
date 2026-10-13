import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Settings, Loader2 } from "lucide-react";
import { useAgent } from "./AgentProvider.tsx";
import { useVoice, type VoiceContextValue } from "./VoiceProvider.tsx";
import { SettingsPanel } from "./SettingsPanel.tsx";

const ringFor = (v: VoiceContextValue, busy: boolean): string =>
  v.state === "speaking"
    ? "bg-pink-500 shadow-[0_0_28px_rgba(236,72,153,.7)]"
    : v.active
    ? "bg-cyan-500 shadow-[0_0_28px_rgba(6,182,212,.7)]"
    : busy
    ? "bg-amber-500"
    : "bg-indigo-500 shadow-[0_0_20px_rgba(99,102,241,.5)]";

export const MobileAgent: React.FC = () => {
  const { messages, busy, status } = useAgent();
  const v = useVoice();
  const [settings, setSettings] = useState(false);
  const [bubble, setBubble] = useState<string | null>(null);

  const last = [...messages].reverse().find((m) => m.role !== "user");

  useEffect(() => {
    if (!last?.text) return undefined;
    setBubble(last.text);
    const t = setTimeout(() => setBubble(null), 8000);
    return () => clearTimeout(t);
  }, [last?.text]);

  const text = v.active && v.caption ? `“${v.caption}”` : bubble || v.error || (!v.active && v.notice);

  return (
    <div data-agent-ignore className="md:hidden">
      <AnimatePresence>
        {text && !settings && (
          <motion.div
            data-testid="mobile-agent-bubble"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`fixed bottom-28 right-5 z-50 max-w-[78vw] rounded-2xl rounded-br-sm border px-4 py-3 text-sm backdrop-blur-xl ${
              v.error && text === v.error
                ? "border-rose-500/30 bg-rose-950/80 text-rose-200"
                : "border-white/10 bg-[#0D1322]/90 text-slate-200"
            }`}
          >
            <span className="line-clamp-4">{text}</span>
            {busy && (
              <span className="mt-1 block font-mono text-[10px] uppercase tracking-wider text-amber-300">
                {status}
              </span>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="fixed bottom-5 right-5 z-50 flex items-end gap-3">
        <button
          type="button"
          data-testid="mobile-settings-btn"
          aria-label="Agent settings"
          onClick={() => setSettings(true)}
          className="grid h-11 w-11 place-items-center rounded-full border border-white/10 bg-[#0D1322]/90 text-slate-300 backdrop-blur-xl hover:text-white"
        >
          <Settings className="h-5 w-5" />
        </button>
        <button
          type="button"
          data-testid="mobile-mic-btn"
          aria-label={v.active ? "Stop voice" : "Start voice"}
          onClick={v.toggle}
          disabled={!v.available[v.provider] || v.state === "connecting"}
          className={`relative grid h-16 w-16 place-items-center rounded-full text-white transition-colors disabled:opacity-40 ${ringFor(
            v,
            busy,
          )}`}
        >
          {v.active && (
            <span className="absolute inset-0 animate-ping rounded-full bg-current opacity-20" />
          )}
          {v.state === "connecting" ? (
            <Loader2 className="h-6 w-6 animate-spin" />
          ) : v.active ? (
            <MicOff className="h-6 w-6" />
          ) : (
            <Mic className="h-6 w-6" />
          )}
        </button>
      </div>

      <AnimatePresence>
        {settings && (
          <motion.div
            data-testid="mobile-settings-sheet"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="fixed inset-0 z-[60] bg-[#0D1322]"
          >
            <SettingsPanel onClose={() => setSettings(false)} testid="mobile-settings" />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
