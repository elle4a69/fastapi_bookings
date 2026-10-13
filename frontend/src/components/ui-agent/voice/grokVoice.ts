import { getAuthenticatedAdminHeaders } from "../../../lib/api.ts";
import type { LiveConnection } from "./openaiLive.ts";

export interface GrokVoiceOptions {
  api: string;
  greet?: boolean;
  voice?: string;
  onStatus: (status: "connecting" | "listening" | "speaking" | "off") => void;
  onCaption: (caption: string) => void;
  onDelegate: (text: string, reply: (content: string) => void) => void;
  onError: (error: string) => void;
  onEnd: () => void;
}

const toB64 = (u8: Uint8Array): string => {
  let s = "";
  for (let i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
  return btoa(s);
};

const pcm16 = (f: Float32Array): Uint8Array => {
  const out = new Int16Array(f.length);
  for (let i = 0; i < f.length; i++) {
    const x = Math.max(-1, Math.min(1, f[i]));
    out[i] = x < 0 ? x * 32768 : x * 32767;
  }
  return new Uint8Array(out.buffer);
};

const TOOL = {
  type: "function",
  name: "operate_app",
  description:
    "Hand a request to the UI agent that navigates pages, fills forms, clicks and reads data in this app. Returns what the agent did or wants to ask.",
  parameters: {
    type: "object",
    properties: {
      request: {
        type: "string",
        description: "The user's request including every detail they provided",
      },
    },
    required: ["request"],
  },
};

/**
 * Grok Voice: speech-to-speech over WebSocket with operate_app tool delegation
 */
export const startGrok = async ({
  api,
  greet = false,
  voice = "eve",
  onStatus,
  onCaption,
  onDelegate,
  onError,
  onEnd,
}: GrokVoiceOptions): Promise<LiveConnection> => {
  const headers = new Headers(getAuthenticatedAdminHeaders());
  headers.set("Content-Type", "application/json");

  const res = await fetch(`${api}/voice/xai/token`, {
    method: "POST",
    headers,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to obtain xAI realtime token");
  }

  const data = await res.json();
  const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
  const ctx = new AudioContextClass();

  const mic = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });

  const ws = new WebSocket(`wss://api.x.ai/v1/realtime?model=${data.model || "grok-voice-think-fast-2.0"}`, [
    `xai-client-secret.${data.token}`,
  ]);

  const send = (x: unknown) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(x));
      return true;
    }
    return false;
  };

  const sources = new Set<AudioBufferSourceNode>();
  let nextAt = 0;
  let ended = false;

  const play = (b64: string) => {
    try {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const pcm = new Int16Array(bytes.buffer);
      const buf = ctx.createBuffer(1, pcm.length, 24000);
      const ch = buf.getChannelData(0);
      for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 32768;
      const node = ctx.createBufferSource();
      node.buffer = buf;
      node.connect(ctx.destination);
      nextAt = Math.max(nextAt, ctx.currentTime);
      node.start(nextAt);
      nextAt += buf.duration;
      sources.add(node);
      node.onended = () => sources.delete(node);
    } catch (err) {
      console.warn("[Grok Voice] Audio playback failed:", err);
    }
  };

  const stopPlayback = () => {
    sources.forEach((s) => {
      try {
        s.stop();
      } catch {
        // already stopped
      }
    });
    sources.clear();
    nextAt = 0;
  };

  const input = ctx.createMediaStreamSource(mic);
  const proc = ctx.createScriptProcessor(4096, 1, 1);
  const mute = ctx.createGain();
  mute.gain.value = 0;

  proc.onaudioprocess = (e) => {
    send({
      type: "input_audio_buffer.append",
      audio: toB64(pcm16(e.inputBuffer.getChannelData(0))),
    });
  };

  input.connect(proc);
  proc.connect(mute);
  mute.connect(ctx.destination);

  const cleanup = () => {
    if (ended) return;
    ended = true;
    stopPlayback();
    try {
      proc.disconnect();
    } catch {}
    mic.getTracks().forEach((t) => t.stop());
    if (ws.readyState <= WebSocket.OPEN) {
      try {
        ws.close();
      } catch {}
    }
    try {
      ctx.close();
    } catch {}
    onEnd();
  };

  ws.onopen = () => {
    onStatus("listening");
    send({
      type: "session.update",
      session: {
        voice,
        instructions: `${data.instructions || "You are the friendly voice of an AI assistant."} Always call operate_app for any app-related request, then speak its result.`,
        turn_detection: { type: "server_vad" },
        audio: {
          input: {
            format: { type: "audio/pcm", rate: ctx.sampleRate },
            transcription: { model: "grok-transcribe" },
          },
          output: { format: { type: "audio/pcm", rate: 24000 } },
        },
        tools: [TOOL],
      },
    });
    if (greet) {
      send({
        type: "conversation.item.create",
        item: {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: "(I just said the wake word. Greet me in a few words.)" }],
        },
      });
      send({ type: "response.create" });
    }
  };

  ws.onmessage = (e) => {
    try {
      const ev = JSON.parse(String(e.data));
      if (ev.type === "response.output_audio.delta" && ev.delta) {
        onStatus("speaking");
        play(ev.delta);
      } else if (ev.type === "input_audio_buffer.speech_started") {
        stopPlayback();
        onStatus("listening");
      } else if (ev.type?.startsWith("conversation.item.input_audio_transcription")) {
        const t = ev.transcript ?? ev.text;
        if (t) onCaption(t);
      } else if (ev.type === "response.function_call_arguments.done") {
        let args: any = {};
        try {
          args = JSON.parse(ev.arguments || "{}");
        } catch {
          args = {};
        }
        onDelegate(args.request || "", (content) => {
          send({
            type: "conversation.item.create",
            item: {
              type: "function_call_output",
              call_id: ev.call_id,
              output: JSON.stringify({ result: content }),
            },
          });
          send({ type: "response.create" });
        });
      } else if (ev.type === "error") {
        onError(ev.error?.message || "Grok voice error");
      }
    } catch (err) {
      console.warn("[Grok Voice] Parsing message failed:", err);
    }
  };

  ws.onerror = () => onError("Grok voice connection error");
  ws.onclose = cleanup;

  return {
    stop: cleanup,
  };
};
