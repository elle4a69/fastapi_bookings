// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from "node:assert/strict";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from "node:test";

import { clean, labelFor, refOf, scanPage } from "./scanner.ts";
import { createExecutor } from "./executor.ts";
import { streamChat } from "./stream.ts";
import { executeRpcAction } from "../../pages/admin/business-assistant/rpc/action-catalogue.ts";
import { ONBOARDING_RPC_METHODS } from "../../pages/admin/business-assistant/rpc/rpc-receiver.ts";

// Setup mock DOM environment if running in pure node:test
if (typeof globalThis.window === "undefined") {
  (globalThis as any).window = {
    location: { pathname: "/admin/catalog/services", hostname: "clinic.localhost" },
    getComputedStyle: () => ({ visibility: "visible", display: "block" }),
    dispatchEvent: () => true,
    addEventListener: () => {},
    removeEventListener: () => {},
    innerWidth: 1024,
  };
}
if (typeof globalThis.document === "undefined") {
  (globalThis as any).document = {
    title: "Services Catalog",
    querySelectorAll: () => [],
    querySelector: () => null,
    getElementById: () => null,
    body: { innerText: "Services Catalog Administration" },
  };
}
if (typeof globalThis.localStorage === "undefined") {
  const store = new Map<string, string>();
  (globalThis as any).localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => store.set(k, v),
    removeItem: (k: string) => store.delete(k),
    clear: () => store.clear(),
  };
}
if (typeof (globalThis as any).CSS === "undefined") {
  (globalThis as any).CSS = {
    escape: (s: string) => s,
  };
}

test("clean normalizes whitespace and truncates length", () => {
  const result = clean("   hello    world   fastapi   ", 11);
  assert.equal(result, "hello world");
});

test("refOf returns data-testid when present or tags data-agent-ref", () => {
  const elWithTestId = {
    dataset: { testid: "submit-btn" },
  } as unknown as HTMLElement;
  assert.equal(refOf(elWithTestId), "submit-btn");

  const elWithoutTestId = {
    dataset: {},
  } as unknown as HTMLElement;
  const ref = refOf(elWithoutTestId);
  assert.match(ref, /^e\d+$/);
  assert.equal(elWithoutTestId.dataset.agentRef, ref);
});

test("labelFor extracts accessible aria-label or placeholder", () => {
  const elWithAria = {
    getAttribute: (attr: string) => (attr === "aria-label" ? "Save Service" : null),
    closest: () => null,
  } as unknown as HTMLElement;
  assert.equal(labelFor(elWithAria), "Save Service");

  const elWithPlaceholder = {
    getAttribute: () => null,
    closest: () => null,
    placeholder: "Enter client email",
  } as unknown as HTMLElement;
  assert.equal(labelFor(elWithPlaceholder), "Enter client email");
});

test("scanPage returns a structured snapshot", () => {
  const snapshot = scanPage({ routes: ["/admin/catalog/services"] });
  assert.equal(snapshot.path, "/admin/catalog/services");
  assert.equal(snapshot.title, "Services Catalog");
  assert.ok(Array.isArray(snapshot.elements));
  assert.ok(Array.isArray(snapshot.notifications));
});

test("executor createExecutor correctly handles wait and unknown actions", async () => {
  const logs: string[] = [];
  const mockUI = {
    point: () => {},
    clickPulse: () => {},
    hide: () => {},
    status: (s: string) => logs.push(s),
    speed: () => 0.01,
    aborted: () => false,
  };
  const mockNavigate = (p: string) => logs.push(`NAV:${p}`);

  const exec = createExecutor({ ui: mockUI, navigate: mockNavigate });

  const waitRes = await exec({ type: "wait", ms: 10 });
  assert.equal(waitRes.ok, true);
  assert.match(waitRes.result || "", /Waited 10ms/);

  const unknownRes = await exec({ type: "fly_to_moon" });
  assert.equal(unknownRes.ok, false);
  assert.match(unknownRes.error || "", /Unknown action/);
});

test("streamChat parses delta events and terminal result from SSE chunks", async () => {
  const ssePayload =
    'data: {"type": "delta", "text": "Clicking"}\n\n' +
    'data: {"type": "delta", "text": " button"}\n\n' +
    'data: {"type": "result", "say": "Clicking button", "actions": [{"type": "click", "ref": "b1"}], "continue": false}\n\n';

  let deltas = "";
  const mockFetch = async () => ({
    ok: true,
    headers: new Headers(),
    body: {
      getReader: () => {
        let sent = false;
        return {
          read: async () => {
            if (!sent) {
              sent = true;
              return { done: false, value: new TextEncoder().encode(ssePayload) };
            }
            return { done: true, value: undefined };
          },
        };
      },
    },
  });

  const origFetch = globalThis.fetch;
  try {
    globalThis.fetch = mockFetch as any;
    const result = await streamChat(
      "/api/admin/ui-agent/chat/stream",
      { message: "click button" },
      (chunk) => {
        deltas += chunk;
      },
    );

    assert.equal(deltas, "Clicking button");
    assert.equal(result.say, "Clicking button");
    assert.equal(result.continue, false);
    assert.equal(result.actions.length, 1);
    assert.equal(result.actions[0].ref, "b1");
  } finally {
    globalThis.fetch = origFetch;
  }
});

test("operate_app is registered in ONBOARDING_RPC_METHODS and dispatches UI automation", async () => {
  assert.ok(ONBOARDING_RPC_METHODS.includes("operate_app" as any));

  let dispatchedEvent: CustomEvent | null = null;
  const origDispatch = window.dispatchEvent;
  window.dispatchEvent = (ev: Event) => {
    if (ev.type === "ui-agent:operate") {
      dispatchedEvent = ev as CustomEvent;
    }
    return true;
  };

  try {
    const receipt = await executeRpcAction(
      "operate_app",
      { instruction: "Fill out client form and submit" },
      { callerIdentity: "voice-agent" },
    );

    assert.equal(receipt.status, "saved");
    assert.equal(receipt.action, "operate_app");
    assert.ok(dispatchedEvent !== null);
    assert.equal(
      (dispatchedEvent as unknown as CustomEvent<{ instruction: string }>).detail.instruction,
      "Fill out client form and submit",
    );
  } finally {
    window.dispatchEvent = origDispatch;
  }
});

test("wakeSupported returns boolean based on SpeechRecognition availability", async () => {
  const { wakeSupported } = await import("./wakeWord.ts");
  const initial = wakeSupported();
  assert.equal(typeof initial, "boolean");
});

test("startWakeListener initializes speech recognition and recognizes wake phrase", async () => {
  const { startWakeListener } = await import("./wakeWord.ts");

  let started = false;
  let aborted = false;
  let mockHandler: any = null;

  class MockSpeechRecognition {
    continuous = false;
    interimResults = false;
    lang = "";
    set onresult(fn: any) {
      mockHandler = fn;
    }
    start() {
      started = true;
    }
    abort() {
      aborted = true;
    }
  }

  (globalThis.window as any).SpeechRecognition = MockSpeechRecognition;

  let woke = false;
  const stop = startWakeListener("Hey Aether", () => {
    woke = true;
  }, () => {});

  assert.equal(started, true);

  // Trigger speech match
  mockHandler({
    resultIndex: 0,
    results: [[{ transcript: "Hey Aether please open the services" }]],
  });

  assert.equal(woke, true);
  assert.equal(aborted, true);
  stop();
});

test("VOICE_PROVIDERS includes GPT-Live and Grok Voice with allowed voices", async () => {
  const { VOICE_PROVIDERS, SLEEP_OPTIONS } = await import("./voice/providers.ts");
  assert.equal(VOICE_PROVIDERS.length, 2);
  assert.equal(VOICE_PROVIDERS[0].id, "openai");
  assert.equal(VOICE_PROVIDERS[0].label, "GPT-Live");
  assert.ok(VOICE_PROVIDERS[0].voices.includes("marin"));

  assert.equal(VOICE_PROVIDERS[1].id, "xai");
  assert.equal(VOICE_PROVIDERS[1].label, "Grok Voice");
  assert.ok(VOICE_PROVIDERS[1].voices.includes("eve"));

  assert.deepEqual(SLEEP_OPTIONS, [0, 30, 60, 120, 300]);
});

