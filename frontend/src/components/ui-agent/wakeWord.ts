const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
// Consonant skeleton so e.g. "hey aether" also matches "hey ether" / "hey either"
const skeleton = (s: string) => norm(s).split(" ").map((w) => (w[0] || "") + w.slice(1).replace(/[aeiouy]/g, "")).join(" ");

export const wakeSupported = (): boolean =>
  typeof window !== "undefined" &&
  !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

export const startWakeListener = (
  phrase: string,
  onWake: () => void,
  onError: (err: string) => void
): (() => void) => {
  if (typeof window === "undefined") return () => {};
  const R = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!R) return () => {};

  const rec = new R();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = "en-US";
  const target = norm(phrase);
  const targetSk = skeleton(phrase).replace(/^[aeiouy]/, "");
  let active = true;

  rec.onresult = (e: any) => {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const heard = e.results[i][0]?.transcript || "";
      if (norm(heard).includes(target) || (targetSk && skeleton(heard).includes(targetSk))) {
        active = false;
        try {
          rec.abort();
        } catch {
          // ignore
        }
        onWake();
        return;
      }
    }
  };

  rec.onerror = (e: any) => {
    if (e.error === "not-allowed" || e.error === "service-not-allowed") {
      active = false;
      onError("Microphone permission is needed for the wake word");
    }
  };

  rec.onend = () => {
    if (active) {
      try {
        rec.start();
      } catch {
        /* already running */
      }
    }
  };

  try {
    rec.start();
  } catch (err: any) {
    onError(err?.message || "Failed to initialize wake listener");
  }

  return () => {
    active = false;
    try {
      rec.abort();
    } catch {
      // ignore
    }
  };
};
