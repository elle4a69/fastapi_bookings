import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { getAuthenticatedAdminHeaders } from "../../lib/api.ts";
import { useAgent } from "./AgentProvider.tsx";
import { startWakeListener, wakeSupported } from "./wakeWord.ts";
import {
  VOICE_PROVIDERS,
  SLEEP_OPTIONS,
  type VoiceProviderConfig,
} from "./voice/providers.ts";
import type { LiveConnection } from "./voice/openaiLive.ts";

export { VOICE_PROVIDERS, SLEEP_OPTIONS, type VoiceProviderConfig };

export interface VoiceContextValue {
  voices: Record<string, string>;
  setVoice: (id: string, voice: string) => void;
  sleepAfter: number;
  setSleepAfter: (seconds: number) => void;
  idleLeft: number | null;
  notice: string;
  available: Record<string, boolean>;
  provider: "openai" | "xai";
  setProvider: (p: "openai" | "xai") => void;
  state: "connecting" | "listening" | "speaking" | "off";
  caption: string;
  error: string;
  start: (options?: { greet?: boolean }) => Promise<void>;
  stop: () => void;
  toggle: () => void;
  active: boolean;
  wakeEnabled: boolean;
  setWakeEnabled: (enabled: boolean) => void;
  wakePhrase: string;
  setWakePhrase: (phrase: string) => void;
  wakeListening: boolean;
  wakeSupported: boolean;
  providerLabel: string;
}

const VoiceCtx = createContext<VoiceContextValue | null>(null);

export const useVoice = (): VoiceContextValue => {
  const ctx = useContext(VoiceCtx);
  if (!ctx) {
    throw new Error("useVoice must be used within a VoiceProvider");
  }
  return ctx;
};

const load = <T,>(k: string, d: T): T => {
  if (typeof window === "undefined") return d;
  try {
    const item = localStorage.getItem(k);
    return item ? (JSON.parse(item) as T) : d;
  } catch {
    return d;
  }
};

const usePersisted = <T,>(key: string, init: T): [T, (val: T) => void] => {
  const [v, setV] = useState<T>(() => load(key, init));
  const set = useCallback(
    (x: T) => {
      setV(x);
      if (typeof window !== "undefined") {
        localStorage.setItem(key, JSON.stringify(x));
      }
    },
    [key],
  );
  return [v, set];
};

export interface VoiceProviderProps {
  children: React.ReactNode;
  apiEndpoint?: string;
}

export const VoiceProvider: React.FC<VoiceProviderProps> = ({
  children,
  apiEndpoint = "/api/admin/ui-agent",
}) => {
  const { send, busy } = useAgent();
  const [available, setAvailable] = useState<Record<string, boolean>>({
    openai: true,
    xai: true,
  });
  const [provider, setProvider] = usePersisted<"openai" | "xai">("voice_provider", "openai");
  const [wakeEnabled, setWakeEnabled] = usePersisted("wake_enabled", false);
  const [wakePhrase, setWakePhrase] = usePersisted("wake_phrase", "Hey Aether");
  const [voices, setVoices] = usePersisted<Record<string, string>>("voice_voices", {
    openai: "marin",
    xai: "eve",
  });
  const [sleepAfter, setSleepAfter] = usePersisted("voice_sleep_after", 60);
  const [idleLeft, setIdleLeft] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  const lastActive = useRef(Date.now());
  const touch = useCallback(() => {
    lastActive.current = Date.now();
  }, []);

  const [state, setState] = useState<"connecting" | "listening" | "speaking" | "off">("off");
  const [caption, setCaption] = useState("");
  const [error, setError] = useState("");
  const [wakeListening, setWakeListening] = useState(false);

  const conn = useRef<LiveConnection | null>(null);
  const sendRef = useRef(send);
  sendRef.current = send;

  useEffect(() => {
    const headers = new Headers(getAuthenticatedAdminHeaders());
    fetch(`${apiEndpoint}/voice/providers`, { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setAvailable(data);
          if (!data[provider]) {
            const alt = VOICE_PROVIDERS.find((p) => data[p.id]);
            if (alt) setProvider(alt.id as "openai" | "xai");
          }
        }
      })
      .catch(() => {});

    return () => {
      conn.current?.stop();
    };
  }, [apiEndpoint]); // eslint-disable-line react-hooks/exhaustive-deps

  const onDelegate = useCallback(async (text: string, reply: (content: string) => void) => {
    if (!text || !text.trim()) {
      return reply("I didn't catch a request. Could you repeat that?");
    }
    setCaption("");
    const said = await sendRef.current(text, { source: "voice" });
    reply(said === null ? "I'm still working on the previous request." : said || "Done.");
  }, []);

  const start = useCallback(
    async ({ greet = false } = {}) => {
      if (conn.current) return;
      setError("");
      setNotice("");
      setState("connecting");
      touch();
      try {
        const p = VOICE_PROVIDERS.find((x) => x.id === provider);
        if (!p) throw new Error("Voice provider not found");
        conn.current = await p.start({
          api: apiEndpoint,
          greet,
          voice: voices[provider] || (provider === "openai" ? "marin" : "eve"),
          onDelegate,
          onError: setError,
          onCaption: (c: string) => {
            touch();
            setCaption(c);
          },
          onStatus: (st: "connecting" | "listening" | "speaking" | "off") => {
            touch();
            setState(st);
          },
          onEnd: () => {
            conn.current = null;
            setState("off");
            setCaption("");
          },
        });
      } catch (e: any) {
        conn.current = null;
        setError(e?.message || "Failed to start voice connection");
        setState("off");
      }
    },
    [provider, voices, onDelegate, touch, apiEndpoint],
  );

  const stop = useCallback(() => {
    conn.current?.stop();
  }, []);

  const toggle = useCallback(() => {
    if (conn.current) {
      stop();
    } else {
      start();
    }
  }, [start, stop]);

  useEffect(() => {
    if (!wakeEnabled || state !== "off" || !available[provider] || !wakeSupported()) {
      setWakeListening(false);
      return undefined;
    }
    const stopWake = startWakeListener(
      wakePhrase,
      () => start({ greet: true }),
      (m) => {
        setError(m);
        setWakeEnabled(false);
      },
    );
    setWakeListening(true);
    return () => {
      stopWake();
      setWakeListening(false);
    };
  }, [wakeEnabled, wakePhrase, state, provider, available, start, setWakeEnabled]);

  useEffect(() => {
    if (busy) touch();
  }, [busy, touch]);

  useEffect(() => {
    if (state === "off" || state === "connecting" || !sleepAfter) {
      setIdleLeft(null);
      return undefined;
    }
    const t = setInterval(() => {
      if (busy) touch();
      const left = Math.ceil(sleepAfter - (Date.now() - lastActive.current) / 1000);
      setIdleLeft(left);
      if (left <= 0) {
        clearInterval(t);
        conn.current?.stop();
        setNotice(
          wakeEnabled
            ? `Voice went to sleep. Say “${wakePhrase}” to wake it.`
            : "Voice went to sleep after inactivity.",
        );
      }
    }, 1000);
    return () => clearInterval(t);
  }, [state, sleepAfter, busy, touch, wakeEnabled, wakePhrase]);

  const value: VoiceContextValue = {
    voices,
    setVoice: (id: string, voice: string) => setVoices({ ...voices, [id]: voice }),
    sleepAfter,
    setSleepAfter,
    idleLeft,
    notice,
    available,
    provider,
    setProvider,
    state,
    caption,
    error,
    start,
    stop,
    toggle,
    active: state !== "off",
    wakeEnabled,
    setWakeEnabled,
    wakePhrase,
    setWakePhrase,
    wakeListening,
    wakeSupported: wakeSupported(),
    providerLabel: VOICE_PROVIDERS.find((p) => p.id === provider)?.label || "Voice",
  };

  return <VoiceCtx.Provider value={value}>{children}</VoiceCtx.Provider>;
};
