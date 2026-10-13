import React from "react";
import { ArrowLeft, RotateCcw, MoveHorizontal } from "lucide-react";
import { useAgent, type AgentSpeed } from "./AgentProvider.tsx";
import { useVoice, VOICE_PROVIDERS, SLEEP_OPTIONS } from "./VoiceProvider.tsx";

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <section className="space-y-3 border-b border-white/5 px-5 py-5">
    <p className="field-label">{title}</p>
    {children}
  </section>
);

const Pill: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & { on?: boolean }
> = ({ on, children, ...props }) => (
  <button
    type="button"
    {...props}
    className={`rounded-md border px-3 py-2 text-sm transition-colors disabled:opacity-35 ${
      on
        ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-100"
        : "border-white/10 text-slate-400 hover:text-slate-100"
    }`}
  >
    {children}
  </button>
);

export interface SettingsPanelProps {
  onClose: () => void;
  onResetWidth?: () => void;
  testid?: string;
}

export const SettingsPanel: React.FC<SettingsPanelProps> = ({
  onClose,
  onResetWidth,
  testid = "agent-settings",
}) => {
  const { speed, setSpeed, reset } = useAgent();
  const v = useVoice();

  return (
    <div data-testid={testid} className="flex h-full flex-col bg-[#0D1322] text-slate-100">
      <header className="flex items-center gap-2 border-b border-white/5 px-4 py-3">
        <button
          type="button"
          data-testid="agent-settings-close"
          onClick={onClose}
          className="agent-icon-btn"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <p className="font-display text-sm font-bold text-slate-100">Agent settings</p>
      </header>
      <div className="flex-1 overflow-y-auto">
        <Section title="Voice model">
          <div className="flex flex-wrap gap-2">
            {VOICE_PROVIDERS.map((p) => (
              <Pill
                key={p.id}
                data-testid={`voice-provider-${p.id}`}
                on={v.provider === p.id}
                disabled={v.active || !v.available[p.id]}
                onClick={() => v.setProvider(p.id)}
              >
                {p.label}
              </Pill>
            ))}
          </div>
          <label htmlFor="voice-voice-select" className="block pt-2 text-xs text-slate-400">
            Speaking voice ({VOICE_PROVIDERS.find((p) => p.id === v.provider)?.label})
          </label>
          <select
            id="voice-voice-select"
            data-testid="voice-voice-select"
            value={v.voices[v.provider] || (v.provider === "openai" ? "marin" : "eve")}
            disabled={v.active}
            onChange={(e) => v.setVoice(v.provider, e.target.value)}
            className="field-input capitalize disabled:opacity-50"
          >
            {VOICE_PROVIDERS.find((p) => p.id === v.provider)?.voices.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          {v.active && (
            <p className="text-xs text-slate-500">Voice changes apply to the next session.</p>
          )}
          {VOICE_PROVIDERS.filter((p) => !v.available[p.id]).map((p) => (
            <p key={p.id} className="text-xs text-slate-500">
              {p.label}: add <code className="text-slate-400">{p.keyName}</code> to backend environment to enable.
            </p>
          ))}
        </Section>

        <Section title="Wake word">
          <label className="flex cursor-pointer items-center justify-between gap-3">
            <span className="text-sm text-slate-300">Start voice hands-free by saying a phrase</span>
            <button
              type="button"
              role="switch"
              aria-checked={v.wakeEnabled}
              data-testid="wake-word-toggle"
              disabled={!v.wakeSupported}
              onClick={() => v.setWakeEnabled(!v.wakeEnabled)}
              className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-35 ${
                v.wakeEnabled ? "bg-cyan-500" : "bg-white/15"
              }`}
            >
              <span
                className={`absolute left-0 top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                  v.wakeEnabled ? "translate-x-5" : "translate-x-0.5"
                }`}
              />
            </button>
          </label>
          <input
            data-testid="wake-word-input"
            value={v.wakePhrase}
            onChange={(e) => v.setWakePhrase(e.target.value)}
            className="field-input"
            aria-label="Wake phrase"
          />
          <p data-testid="wake-word-status" className="text-xs text-slate-500">
            {!v.wakeSupported
              ? "Wake word needs Chrome, Edge or Safari speech recognition."
              : v.wakeListening
              ? `Listening for “${v.wakePhrase}”…`
              : v.wakeEnabled
              ? "Paused while a voice session is active."
              : "Off"}
          </p>
        </Section>

        <Section title="Auto sleep">
          <p className="text-xs text-slate-500">
            End the voice session after this much silence
            {v.wakeEnabled ? " and go back to listening for the wake word" : ""}.
          </p>
          <div className="flex flex-wrap gap-2">
            {SLEEP_OPTIONS.map((sec) => (
              <Pill
                key={sec}
                data-testid={`auto-sleep-${sec}`}
                on={v.sleepAfter === sec}
                onClick={() => v.setSleepAfter(sec)}
              >
                {sec === 0 ? "Never" : sec < 60 ? `${sec}s` : `${sec / 60}m`}
              </Pill>
            ))}
          </div>
        </Section>

        <Section title="Agent speed">
          <div className="flex gap-2">
            {(["slow", "realistic", "fast"] as AgentSpeed[]).map((s) => (
              <Pill
                key={s}
                data-testid={`agent-speed-${s}`}
                on={speed === s}
                onClick={() => setSpeed(s)}
              >
                {s}
              </Pill>
            ))}
          </div>
        </Section>

        {onResetWidth && (
          <Section title="Panel">
            <p className="flex items-center gap-2 text-xs text-slate-500">
              <MoveHorizontal className="h-3 w-3" /> Drag the panel's left edge to resize it.
            </p>
            <Pill data-testid="panel-width-reset" onClick={onResetWidth}>
              Reset width
            </Pill>
          </Section>
        )}

        <Section title="Session">
          <Pill
            data-testid="settings-new-session"
            onClick={() => {
              reset();
              onClose();
            }}
          >
            <RotateCcw className="mr-2 inline h-3 w-3" />
            Start new session
          </Pill>
        </Section>
      </div>
    </div>
  );
};
