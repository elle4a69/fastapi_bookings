const SELECTOR =
  'a[href],button,input,select,textarea,[role="button"],[role="link"],[role="tab"],[role="checkbox"],[role="switch"],[role="radio"],[role="combobox"],[role="option"],[role="menuitem"],[contenteditable="true"]';

let counter = 0;

export interface ScannedElement {
  ref: string;
  tag: string;
  label: string;
  type?: string;
  role?: string;
  name?: string;
  value?: string;
  checked?: boolean;
  options?: Array<{ value: string; label: string }>;
  href?: string | null;
  kind?: string;
  expanded?: boolean;
  required?: boolean;
  disabled?: boolean;
}

export interface PageSnapshot {
  path: string;
  title: string;
  routes: Array<{ path: string; title?: string } | string>;
  page_text: string;
  notifications: string[];
  elements: ScannedElement[];
}

export const isVisible = (el: HTMLElement): boolean => {
  if ((el as HTMLInputElement).type === "hidden") return false;
  const r = el.getBoundingClientRect();
  const s = window.getComputedStyle(el);
  return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
};

export const clean = (t?: string | null, n = 80): string =>
  (t || "").replace(/\s+/g, " ").trim().slice(0, n);

export const labelFor = (el: HTMLElement): string => {
  if (el.getAttribute("aria-label")) return el.getAttribute("aria-label") || "";
  if (el.getAttribute("aria-labelledby")) {
    const l = document.getElementById(el.getAttribute("aria-labelledby") || "");
    if (l) return clean(l.innerText);
  }
  if (el.id) {
    const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`) as HTMLElement | null;
    if (l) return clean(l.innerText);
  }
  const wrap = el.closest("label") as HTMLElement | null;
  if (wrap) return clean(wrap.innerText);

  const inputEl = el as HTMLInputElement;
  return clean(inputEl.placeholder || el.innerText || inputEl.value || inputEl.name || el.title);
};

export const refOf = (el: HTMLElement): string => {
  if (el.dataset.testid) return el.dataset.testid;
  if (!el.dataset.agentRef) el.dataset.agentRef = `e${++counter}`;
  return el.dataset.agentRef;
};

export const findByRef = (ref: string): HTMLElement | null => {
  if (!ref) return null;
  try {
    return (
      (document.querySelector(`[data-testid="${CSS.escape(ref)}"]`) as HTMLElement | null) ||
      (document.querySelector(`[data-agent-ref="${CSS.escape(ref)}"]`) as HTMLElement | null)
    );
  } catch {
    return null;
  }
};

const describe = (el: HTMLElement): ScannedElement => {
  const tag = el.tagName.toLowerCase();
  const d: ScannedElement = { ref: refOf(el), tag, label: labelFor(el) };

  const inputEl = el as HTMLInputElement;
  const selectEl = el as HTMLSelectElement;

  if (inputEl.type && tag === "input") d.type = inputEl.type;
  if (el.getAttribute("role")) d.role = el.getAttribute("role") || undefined;
  if (inputEl.name) d.name = inputEl.name;

  if (["input", "textarea", "select"].includes(tag) && !["checkbox", "radio"].includes(inputEl.type)) {
    d.value = inputEl.value;
  }
  if (["checkbox", "radio"].includes(inputEl.type)) {
    d.checked = inputEl.checked;
    d.value = inputEl.value;
  }
  if (el.getAttribute("aria-checked")) {
    d.checked = el.getAttribute("aria-checked") === "true";
  }
  if (tag === "select") {
    d.options = [...selectEl.options].map((o) => ({ value: o.value, label: clean(o.text) }));
  }
  if (tag === "a") {
    d.href = el.getAttribute("href");
  }
  if (el.dataset.agentKind) {
    d.kind = el.dataset.agentKind;
  }
  if (d.role === "combobox" || d.kind) {
    d.value = clean(el.innerText);
    d.expanded = el.getAttribute("aria-expanded") === "true";
  }
  if ((el as HTMLInputElement).required) d.required = true;
  if ((el as HTMLInputElement).disabled) d.disabled = true;

  return d;
};

export interface ScanPageOptions {
  routes?: Array<{ path: string; title?: string } | string>;
  contentSelector?: string;
}

export const scanPage = ({ routes = [], contentSelector = "main" }: ScanPageOptions = {}): PageSnapshot => {
  if (typeof document === "undefined") {
    return {
      path: "",
      title: "",
      routes,
      page_text: "",
      notifications: [],
      elements: [],
    };
  }

  const elements = ([...document.querySelectorAll(SELECTOR)] as HTMLElement[])
    .filter((el) => !el.closest('[data-agent-ignore],[aria-hidden="true"]') && isVisible(el))
    .slice(0, 200)
    .map(describe);

  const content = (document.querySelector(contentSelector) as HTMLElement | null) || document.body;
  return {
    path: window.location.pathname,
    title: document.title,
    routes,
    page_text: clean(content.innerText, 5000),
    notifications: ([...document.querySelectorAll('[data-sonner-toast],[role="alert"],[role="status"]')] as HTMLElement[])
      .map((n) => clean(n.innerText, 200))
      .filter(Boolean),
    elements,
  };
};
