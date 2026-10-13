import React from "react";
import { Mic, MicOff, AudioLines, Ear } from "lucide-react";
import { useVoice } from "./VoiceProvider.tsx";

export const VoiceBar: React.FC = () => {
  const {
    available,
    provider,
    providerLabel,
    voices,
    state,
    caption,
    error,
    notice,
    idleLeft,
    toggle,
    active,
    wakeListening,
    wakePhrase,
  } = useVoice();

  return (
    <div data-testid="voice-control" className="border-t border-white/5 px-3 pt-3">
      <div className="flex items-center gap-2">
        <span
          data-testid="voice-provider-label"
          className="rounded bg-pink-500/10 px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-pink-300"
        >
          {providerLabel} · {voices[provider]}
        </span>
        {wakeListening && (
          <span
            data-testid="wake-word-indicator"
            title={`Say "${wakePhrase}"`}
            className="flex items-center gap-1 font-mono text-[10px] text-cyan-400/80"
          >
            <Ear className="h-3 w-3 animate-pulse" /> “{wakePhrase}”
          </span>
        )}
        <span
          data-testid="voice-status"
          className="ml-auto font-mono text-[10px] uppercase tracking-wider text-slate-400"
        >
          {active && (
            <AudioLines
              className={`mr-1 inline h-3 w-3 animate-pulse ${
                state === "speaking" ? "text-pink-400" : "text-cyan-400"
              }`}
            />
          )}
          {active ? state : "voice off"}
          {active && idleLeft !== null && idleLeft <= 10 && (
            <span data-testid="voice-sleep-countdown" className="ml-1 text-amber-400">
              · sleep {Math.max(idleLeft, 0)}s
            </span>
          )}
        </span>
        <button
          type="button"
          data-testid={active ? "voice-stop-btn" : "voice-start-btn"}
          onClick={toggle}
          disabled={!available[provider] || state === "connecting"}
          title={available[provider] ? "" : "Voice API key not configured"}
          className={`grid h-8 w-8 place-items-center rounded-full text-white transition-colors disabled:opacity-35 ${
            active
              ? "bg-pink-500 shadow-[0_0_16px_rgba(236,72,153,.6)] hover:bg-pink-400"
              : "bg-white/10 hover:bg-white/20"
          }`}
        >
          {active ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </button>
      </div>
      {active && caption && (
        <p data-testid="voice-caption" className="mt-2 line-clamp-2 text-xs italic text-slate-400">
          “{caption}”
        </p>
      )}
      {!active && notice && (
        <p data-testid="voice-notice" className="mt-2 text-xs text-cyan-300/80">
          {notice}
        </p>
      )}
      {error && (
        <p data-testid="voice-error" className="mt-2 text-xs text-rose-400">
          {error}
        </p>
      )}
    </div>
  );
};
