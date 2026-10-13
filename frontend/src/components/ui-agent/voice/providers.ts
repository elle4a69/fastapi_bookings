import { startOpenAILive, type LiveConnection } from "./openaiLive.ts";
import { startGrok } from "./grokVoice.ts";

export interface VoiceProviderConfig {
  id: "openai" | "xai";
  label: string;
  start: (options: any) => Promise<LiveConnection>;
  keyName: string;
  voices: string[];
}

export const VOICE_PROVIDERS: VoiceProviderConfig[] = [
  {
    id: "openai",
    label: "GPT-Live",
    start: startOpenAILive,
    keyName: "OPENAI_API_KEY",
    voices: [
      "marin",
      "cedar",
      "quartz",
      "ripple",
      "vesper",
      "willow",
      "stone",
      "gleam",
      "meridian",
      "bossa",
      "tempo",
      "beacon",
      "delta",
      "cinder",
    ],
  },
  {
    id: "xai",
    label: "Grok Voice",
    start: startGrok,
    keyName: "XAI_API_KEY",
    voices: ["eve", "ara", "rex", "sal", "leo"],
  },
];

export const SLEEP_OPTIONS = [0, 30, 60, 120, 300];
