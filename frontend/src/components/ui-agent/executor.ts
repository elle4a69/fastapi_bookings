import { findByRef, labelFor } from "./scanner.ts";
import { authenticatedAdminFetch } from "../../lib/api.ts";

export const scrubClientPII = (val: string): string => {
  if (!val) return "";
  return val
    // credit cards
    .replace(/\b(?:\d[ -]?){13,19}\b/g, "[REDACTED_CARD]")
    // emails
    .replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g, "[REDACTED_EMAIL]")
    // phones: Australian and international
    .replace(/(?:\+?61\s*|0)[2-478](?:[ -]?\d){7,8}\b/g, "[REDACTED_PHONE]")
    .replace(/\b(?:\+?1[-.]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g, "[REDACTED_PHONE]")
    .replace(/(?<!\w)\+\d[\d\s().-]{7,}\d(?!\w)/g, "[REDACTED_PHONE]")
    // bearer / api keys
    .replace(/\b(?:Bearer\s+[A-Za-z0-9._~+\-/]+=*|sk-[A-Za-z0-9_-]{12,}|(?:api[_-]?key|secret|password|token)\s*[:=]\s*\S+)\b/gi, "[REDACTED_SECRET]");
};

const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

const protoFor = (el: HTMLElement) =>
  el.tagName === "TEXTAREA"
    ? HTMLTextAreaElement.prototype
    : el.tagName === "SELECT"
    ? HTMLSelectElement.prototype
    : HTMLInputElement.prototype;

export const setNativeValue = (el: HTMLElement, value: string): void => {
  const descriptor = Object.getOwnPropertyDescriptor(protoFor(el), "value");
  if (descriptor && descriptor.set) {
    descriptor.set.call(el, value);
  } else {
    (el as HTMLInputElement).value = value;
  }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
};

// Full pointer/mouse sequence so headless libs (Radix, etc.) that listen to pointerdown/up react like a real click
export const realClick = (el: HTMLElement): void => {
  const r = el.getBoundingClientRect();
  const o = {
    bubbles: true,
    cancelable: true,
    composed: true,
    clientX: r.left + r.width / 2,
    clientY: r.top + r.height / 2,
    button: 0,
    buttons: 1,
    pointerId: 1,
    pointerType: "mouse",
    isPrimary: true,
    view: window,
  };
  el.dispatchEvent(new PointerEvent("pointermove", o));
  el.dispatchEvent(new PointerEvent("pointerdown", o));
  el.dispatchEvent(new MouseEvent("mousedown", o));
  el.dispatchEvent(new PointerEvent("pointerup", { ...o, buttons: 0 }));
  el.dispatchEvent(new MouseEvent("mouseup", { ...o, buttons: 0 }));
  el.click();
};

export const pressEnter = (el: HTMLElement): void => {
  el.focus();
  ["keydown", "keyup"].forEach((t) =>
    el.dispatchEvent(new KeyboardEvent(t, { key: "Enter", code: "Enter", bubbles: true, cancelable: true })),
  );
};

const norm = (t?: string | null): string => (t || "").replace(/\s+/g, " ").trim().toLowerCase();
const visible = (el: HTMLElement): boolean => {
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
};

const popupRoot = (): HTMLElement | undefined =>
  ([
    ...document.querySelectorAll(
      '[data-radix-popper-content-wrapper],[role="dialog"],[role="listbox"]',
    ),
  ] as HTMLElement[])
    .filter(visible)
    .pop();

const parseCaption = (root: HTMLElement): { y: number; m: number } | null => {
  const node = ([...root.querySelectorAll("*")] as HTMLElement[]).find(
    (n) => n.children.length === 0 && /^[A-Za-z]+\s+\d{4}$/.test((n.textContent || "").trim()),
  );
  if (!node || !node.textContent) return null;
  const d = new Date(`${node.textContent.trim()} 1`);
  return isNaN(d.getTime()) ? null : { y: d.getFullYear(), m: d.getMonth() };
};

const navButton = (root: HTMLElement, dir: string): HTMLButtonElement | undefined =>
  ([...root.querySelectorAll("button")] as HTMLButtonElement[]).find((b) =>
    new RegExp(dir, "i").test(`${b.getAttribute("aria-label") || ""} ${b.name || ""}`),
  );

export interface UIController {
  point: (el: HTMLElement, label?: string) => void;
  clickPulse: () => void;
  hide: () => void;
  status: (s: string) => void;
  speed: () => number;
  aborted: () => boolean;
}

export interface AgentAction {
  type: "navigate" | "click" | "type" | "select" | "pick_date" | "check" | "scroll" | "wait" | string;
  ref?: string;
  path?: string;
  text?: string;
  value?: string;
  date?: string;
  checked?: boolean;
  ms?: number;
  [key: string]: unknown;
}

export interface ActionResult {
  action: AgentAction;
  label?: string;
  ok: boolean;
  result?: string;
  error?: string;
}

export interface CreateExecutorOptions {
  ui: UIController;
  navigate: (path: string) => void;
}

export const createExecutor = ({ ui, navigate }: CreateExecutorOptions) => {
  const wait = (ms: number) => sleep(ms * ui.speed());

  const show = async (el: HTMLElement, label?: string) => {
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    await wait(300);
    ui.point(el, label);
    await wait(500);
  };

  const target = async (ref: string, label?: string): Promise<HTMLElement> => {
    const el = findByRef(ref);
    if (!el) throw new Error(`Element "${ref}" not found`);
    await show(el, label);
    return el;
  };

  const press = async (el: HTMLElement) => {
    ui.clickPulse();
    await wait(120);
    realClick(el);
  };

  const pickOption = async (value: string): Promise<string> => {
    const v = norm(value);
    const opts = ([...document.querySelectorAll('[role="option"],[role="menuitem"]')] as HTMLElement[]).filter(visible);
    const opt =
      opts.find((o) => norm(o.textContent) === v || norm(o.dataset.value) === v) ||
      opts.find((o) => norm(o.textContent).includes(v));

    if (!opt) {
      throw new Error(
        `Option "${value}" not found (available: ${opts.map((o) => (o.textContent || "").trim()).join(", ")})`,
      );
    }
    const label = (opt.textContent || "").trim();
    await show(opt, `Choosing "${label}"`);
    await press(opt);
    await wait(250);
    if (opt.isConnected && visible(opt)) pressEnter(opt);
    return label;
  };

  const handlers: Record<string, (action: AgentAction) => Promise<string>> = {
    navigate: async ({ path }) => {
      if (!path) throw new Error("Missing navigate path");
      ui.status("NAVIGATING");
      ui.hide();
      navigate(path);
      await wait(700);
      return `Navigated to ${path}`;
    },
    click: async ({ ref }) => {
      if (!ref) throw new Error("Missing click ref");
      ui.status("CLICKING");
      const el = await target(ref, "Clicking");
      await press(el);
      await wait(400);
      return `Clicked ${ref}`;
    },
    type: async ({ ref, text = "" }) => {
      if (!ref) throw new Error("Missing type ref");
      ui.status("TYPING");
      const el = await target(ref, `Typing "${String(text).slice(0, 24)}"`);
      el.focus();
      const inputEl = el as HTMLInputElement;
      if (["date", "time", "number"].includes(inputEl.type)) {
        setNativeValue(el, String(text));
      } else {
        setNativeValue(el, "");
        let cur = "";
        for (const ch of String(text)) {
          if (ui.aborted()) break;
          cur += ch;
          setNativeValue(el, cur);
          await wait(35);
        }
      }
      await wait(150);
      el.blur();
      return `Typed "${text}" into ${ref}`;
    },
    select: async ({ ref, value }) => {
      if (!ref) throw new Error("Missing select ref");
      if (value === undefined || value === null) throw new Error("Missing select value");
      ui.status("SELECTING");
      const el = await target(ref, `Selecting "${value}"`);
      if (el.tagName === "SELECT") {
        const selectEl = el as HTMLSelectElement;
        const v = norm(value);
        const opt =
          [...selectEl.options].find((o) => norm(o.value) === v || norm(o.text) === v) ||
          [...selectEl.options].find((o) => norm(o.text).includes(v));
        if (!opt) throw new Error(`Option "${value}" not found`);
        ui.clickPulse();
        setNativeValue(el, opt.value);
        await wait(300);
        return `Selected "${opt.text}" in ${ref}`;
      }
      if (el.getAttribute("aria-expanded") !== "true") {
        await press(el);
        await wait(450);
      }
      const picked = await pickOption(String(value));
      await wait(300);
      return `Selected "${picked}" in ${ref}`;
    },
    pick_date: async ({ ref, date }) => {
      if (!ref) throw new Error("Missing pick_date ref");
      ui.status("PICKING DATE");
      const [y, m, d] = String(date).split("-").map(Number);
      if (!y || !m || !d) throw new Error(`Invalid date "${date}", use YYYY-MM-DD`);
      const el = await target(ref, `Picking ${date}`);
      await press(el);
      await wait(450);
      let root = popupRoot();
      if (!root) throw new Error("Calendar did not open");
      for (let i = 0; i < 240; i++) {
        const cap = parseCaption(root);
        if (!cap) throw new Error("Could not read calendar month");
        const diff = y * 12 + (m - 1) - (cap.y * 12 + cap.m);
        if (diff === 0) break;
        const btn = navButton(root, diff > 0 ? "next" : "prev");
        if (!btn) throw new Error("Calendar navigation not found");
        ui.point(btn, diff > 0 ? "Next month" : "Previous month");
        await press(btn);
        await wait(Math.abs(diff) > 3 ? 60 : 250);
        root = popupRoot();
        if (!root) throw new Error("Calendar closed unexpectedly");
      }
      const day = ([...root.querySelectorAll('button[name="day"],[role="gridcell"] button,button[role="gridcell"]')] as HTMLButtonElement[]).find(
        (b) => (b.textContent || "").trim() === String(d) && !b.className.includes("outside") && !b.disabled,
      );
      if (!day) throw new Error(`Day ${d} not found`);
      await show(day, `Day ${d}`);
      await press(day);
      await wait(350);
      return `Picked ${date} in ${ref}`;
    },
    check: async ({ ref, checked = true }) => {
      if (!ref) throw new Error("Missing check ref");
      ui.status("CLICKING");
      const el = await target(ref, checked ? "Checking" : "Unchecking");
      const inputEl = el as HTMLInputElement;
      const cur = inputEl.checked ?? el.getAttribute("aria-checked") === "true";
      if (cur !== checked) await press(el);
      await wait(300);
      return `${checked ? "Checked" : "Unchecked"} ${ref}`;
    },
    scroll: async ({ ref }) => {
      if (!ref) throw new Error("Missing scroll ref");
      ui.status("SCROLLING");
      await target(ref, "Scrolling");
      return `Scrolled to ${ref}`;
    },
    wait: async ({ ms = 500 }) => {
      await sleep(Math.min(ms, 5000));
      return `Waited ${ms}ms`;
    },
    create_support_ticket: async (action) => {
      ui.status("FILING TICKET");
      const title = scrubClientPII(
        (action.title as string) ||
        `Onboarding assistance requested on ${typeof window !== "undefined" ? window.location.pathname : "portal"}`
      );
      const description = scrubClientPII(
        (action.description as string) ||
        (action.reason as string) ||
        (typeof action.error === "string" ? action.error : "User requested support assistance during onboarding session.")
      );
      const category = (action.category as string) || "general";
      const rawContext = (action.error_context as Record<string, unknown>) || {};
      const error_context = {
        route: typeof rawContext.route === "string" ? scrubClientPII(rawContext.route) : (typeof window !== "undefined" ? window.location.pathname : undefined),
        action_attempted: typeof rawContext.action_attempted === "string" ? scrubClientPII(rawContext.action_attempted) : ((action.action_attempted as string) || undefined),
        error_code: typeof rawContext.error_code === "string" ? scrubClientPII(rawContext.error_code) : ((action.error_code as string) || undefined),
        error_message: typeof rawContext.error_message === "string" ? scrubClientPII(rawContext.error_message) : scrubClientPII((action.error_message as string) || (typeof action.error === "string" ? action.error : "")),
        client_timestamp: (rawContext.client_timestamp as string) || new Date().toISOString(),
      };

      const res = await authenticatedAdminFetch("/api/support/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          description,
          category,
          error_context,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to submit support ticket (${res.status})`);
      }

      const data = await res.json();
      const ticketId = data.id || "created";
      return `Support ticket #${ticketId} created. Don't worry, our team has received your ticket and is investigating it.`;
    },
  };

  return async (action: AgentAction): Promise<ActionResult> => {
    const h = handlers[action.type];
    if (!h) return { action, ok: false, error: `Unknown action ${action.type}` };
    const el = action.ref ? findByRef(action.ref) : null;
    const label = el ? labelFor(el) : undefined;
    try {
      return { action, label, ok: true, result: await h(action) };
    } catch (e) {
      return { action, label, ok: false, error: (e as Error).message };
    }
  };
};
