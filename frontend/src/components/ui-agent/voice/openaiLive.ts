import { getAuthenticatedAdminHeaders } from "../../../lib/api.ts";

export interface OpenAILiveOptions {
  api: string;
  greet?: boolean;
  voice?: string;
  model?: string;
  onStatus: (status: "connecting" | "listening" | "speaking" | "off") => void;
  onCaption: (caption: string) => void;
  onDelegate: (text: string, reply: (content: string) => void) => void;
  onError: (error: string) => void;
  onEnd: () => void;
}

export interface LiveConnection {
  stop: () => void;
}

const waitIce = (pc: RTCPeerConnection): Promise<void> =>
  new Promise((resolve) => {
    if (pc.iceGatheringState === "complete") return resolve();
    const t = setTimeout(resolve, 3000);
    pc.addEventListener("icegatheringstatechange", () => {
      if (pc.iceGatheringState === "complete") {
        clearTimeout(t);
        resolve();
      }
    });
  });

/**
 * GPT-Live (client delegation):
 * OpenAI Live handles conversational audio streaming over WebRTC.
 * Whenever the user requests an app action, OpenAI Live emits session.delegation.created,
 * delegating the action to our UI Agent. When the UI Agent completes the DOM operations,
 * it returns commentary for GPT-Live to speak aloud to the user.
 */
export const startOpenAILive = async ({
  api,
  greet = false,
  voice = "marin",
  model = "gpt-live-1",
  onStatus,
  onCaption,
  onDelegate,
  onError,
  onEnd,
}: OpenAILiveOptions): Promise<LiveConnection> => {
  const pc = new RTCPeerConnection();
  const audio = typeof Audio !== "undefined" ? new Audio() : ({ autoplay: false, play: async () => {}, srcObject: null } as any);
  audio.autoplay = true;

  pc.ontrack = (e) => {
    if (e.track) {
      audio.srcObject = new MediaStream([e.track]);
      audio.play().catch(() => {});
    }
  };

  const mic = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
  });
  const audioTracks = mic.getAudioTracks();
  if (!audioTracks.length) {
    mic.getTracks().forEach((t) => t.stop());
    throw new Error("No microphone audio track available");
  }
  audioTracks.forEach((t) => pc.addTrack(t, mic));

  const hasAudioSender = pc.getSenders().some((s) => s.track && s.track.kind === "audio");
  if (!hasAudioSender) {
    mic.getTracks().forEach((t) => t.stop());
    throw new Error("Failed to attach microphone audio track to WebRTC connection");
  }

  const dc = pc.createDataChannel("oai-events");
  const send = (ev: unknown) => {
    if (dc.readyState === "open") {
      dc.send(JSON.stringify(ev));
      return true;
    }
    return false;
  };

  let heard = "";
  let ended = false;

  const cleanup = () => {
    if (ended) return;
    ended = true;
    mic.getTracks().forEach((t) => t.stop());
    try {
      dc.close();
    } catch {
      // ignore
    }
    try {
      pc.close();
    } catch {
      // ignore
    }
    audio.srcObject = null;
    onEnd();
  };

  dc.onmessage = ({ data }) => {
    try {
      const ev = JSON.parse(String(data));
      if (ev.type === "session.started") {
        onStatus("listening");
        if (greet) {
          send({
            type: "session.instructions.append",
            event_id: "wake_greet",
            delegation_id: null,
            content: "The user just said the wake word. Greet them in a few words, like 'Hi, how can I help?'",
          });
        }
      } else if (ev.type === "session.input_transcript.delta") {
        heard += ev.delta || "";
        onCaption(heard);
        onStatus("listening");
      } else if (ev.type === "session.output_transcript.delta") {
        onStatus("speaking");
      } else if (ev.type === "session.delegation.created") {
        const id = ev.delegation?.id;
        setTimeout(() => {
          const text = heard.trim();
          heard = "";
          onDelegate(text, (content) => {
            send({
              type: "session.commentary.append",
              event_id: `res_${Date.now()}`,
              delegation_id: id,
              content: content.slice(0, 1800),
            });
          });
        }, 600);
      } else if (ev.type === "session.closed") {
        cleanup();
      } else if (ev.type === "error" || ev.type === "session.error") {
        onError(ev.error?.message || "GPT-Live error received");
      }
    } catch (err: any) {
      console.warn("[GPT-Live WebRTC] Message parsing failed:", err);
    }
  };

  dc.onclose = cleanup;

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  await waitIce(pc);

  const localSdp = pc.localDescription?.sdp;
  if (!localSdp || !localSdp.includes("m=audio")) {
    cleanup();
    throw new Error("WebRTC offer does not contain a valid audio stream (m=audio missing)");
  }

  const headers = new Headers(getAuthenticatedAdminHeaders());
  headers.set("Content-Type", "application/json");

  const res = await fetch(`${api}/voice/openai/session`, {
    method: "POST",
    headers,
    body: JSON.stringify({ sdp: localSdp, voice, model }),
  });

  if (!res.ok) {
    cleanup();
    let errorDetail = `GPT-Live session failed (${res.status})`;
    try {
      const errData = await res.json();
      if (errData?.detail) {
        errorDetail = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
      } else if (errData?.error?.message) {
        errorDetail = errData.error.message;
      } else if (errData?.message) {
        errorDetail = errData.message;
      }
    } catch {
      if (res.statusText) {
        errorDetail = `GPT-Live session failed (${res.status}: ${res.statusText})`;
      }
    }
    throw new Error(errorDetail);
  }

  const result = await res.json();
  const remoteSdp = result.transport?.sdp || result.sdp;
  if (!remoteSdp) {
    cleanup();
    throw new Error("Invalid SDP answer received from voice service");
  }

  await pc.setRemoteDescription({ type: "answer", sdp: remoteSdp });

  return {
    stop: () => {
      if (!send({ type: "session.close" })) {
        cleanup();
      }
      setTimeout(cleanup, 4000);
    },
  };
};
