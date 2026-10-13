import { getAuthenticatedAdminHeaders } from "../../lib/api.ts";

export interface StreamEventResult {
  say: string;
  actions: any[];
  continue: boolean;
  [key: string]: unknown;
}

export const streamChat = async (
  url: string,
  body: Record<string, unknown>,
  onDelta: (chunk: string) => void,
  headersInit?: HeadersInit,
): Promise<StreamEventResult> => {
  const defaultHeaders = getAuthenticatedAdminHeaders();
  const headers = new Headers(defaultHeaders);
  if (headersInit) {
    new Headers(headersInit).forEach((val, key) => headers.set(key, val));
  }
  headers.set("Content-Type", "application/json");

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}`;
    try {
      const json = await res.json();
      if (json && json.detail) errorDetail = json.detail;
    } catch {
      // Ignore json parse error
    }
    throw new Error(errorDetail);
  }

  if (!res.body) {
    throw new Error("Response body is null");
  }

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let result: StreamEventResult | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, i);
      buf = buf.slice(i + 2);
      if (!line.startsWith("data: ")) continue;
      const rawJson = line.slice(6).trim();
      if (!rawJson) continue;
      try {
        const ev = JSON.parse(rawJson);
        if (ev.type === "delta" && typeof ev.text === "string") {
          onDelta(ev.text);
        } else if (ev.type === "result") {
          result = ev;
        } else if (ev.type === "error") {
          throw new Error(ev.detail || "UI Agent stream error");
        }
      } catch (err) {
        if ((err as Error).message.includes("UI Agent stream error")) throw err;
      }
    }
  }

  if (!result) {
    throw new Error("Agent stream ended unexpectedly");
  }
  return result;
};
