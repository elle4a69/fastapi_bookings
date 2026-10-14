/**
 * telemetry.ts – Privacy-safe frontend telemetry forwarder.
 *
 * Captures structural error metadata and Web Vitals across both public
 * booking pages and admin UI, stripping all query strings, hashes, and PII.
 */

const TELEMETRY_ENDPOINT = '/api/public/diagnostics/telemetry';

interface TelemetryEvent {
  event_type: string;
  error_class?: string;
  route?: string;
  component?: string;
  duration_ms?: number;
  vital_name?: string;
}

/** Return URL pathname only – strip query params and hash */
function safeRoute(): string {
  try {
    return window.location.pathname.split('?')[0].split('#')[0];
  } catch {
    return '';
  }
}

async function sendTelemetry(event: TelemetryEvent): Promise<void> {
  try {
    const body: TelemetryEvent = {
      ...event,
      route: (event.route ?? safeRoute()).split('?')[0].split('#')[0].slice(0, 150),
    };

    await fetch(TELEMETRY_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
  } catch {
    // Fail silently – never disrupt UI or user interaction
  }
}

function extractErrorClass(err: unknown): string {
  if (err instanceof Error) {
    const name = err.constructor.name || 'Error';
    return name.replace(/[^a-zA-Z0-9_.-]/g, '').slice(0, 100);
  }
  return 'UnknownError';
}

/** Helper to detect whether an error or stack originated from browser extensions */
export function isBrowserExtensionSource(source?: string | null): boolean {
  if (!source) return false;
  return (
    source.startsWith('chrome-extension://') ||
    source.startsWith('moz-extension://') ||
    source.startsWith('safari-web-extension://') ||
    source.includes('chrome-extension://') ||
    source.includes('moz-extension://') ||
    source.includes('safari-web-extension://') ||
    source.includes('contentScript')
  );
}

/** Register global error and unhandled rejection listeners */
export function initFrontendTelemetry(): void {
  if (typeof window === 'undefined') return;

  window.addEventListener('error', (event: ErrorEvent) => {
    const filename = event.filename || '';
    if (
      filename.startsWith('chrome-extension://') ||
      filename.startsWith('moz-extension://') ||
      filename.startsWith('safari-web-extension://') ||
      filename.includes('contentScript') ||
      (event.error instanceof Error && isBrowserExtensionSource(event.error.stack))
    ) {
      return;
    }

    sendTelemetry({
      event_type: 'js_error',
      error_class: extractErrorClass(event.error),
      component: event.filename ? (event.filename.split('/').pop()?.split('?')[0] ?? '').slice(0, 100) : '',
    });
  });

  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    const reason = event.reason;
    if (reason && typeof reason === 'object') {
      const reasonObj = reason as { stack?: unknown; fileName?: unknown; message?: unknown };
      if (typeof reasonObj.stack === 'string' && isBrowserExtensionSource(reasonObj.stack)) {
        return;
      }
      if (typeof reasonObj.fileName === 'string' && isBrowserExtensionSource(reasonObj.fileName)) {
        return;
      }
      if (typeof reasonObj.message === 'string' && isBrowserExtensionSource(reasonObj.message)) {
        return;
      }
    } else if (typeof reason === 'string' && isBrowserExtensionSource(reason)) {
      return;
    }

    sendTelemetry({
      event_type: 'unhandled_rejection',
      error_class: extractErrorClass(event.reason),
    });
  });
}

/** Record a Web Vital metric (LCP, FCP, CLS, FID, TTFB) */
export function recordWebVital(name: string, value: number): void {
  sendTelemetry({
    event_type: 'web_vital',
    vital_name: name,
    duration_ms: value,
  });
}

/** Record a React component error (called from ErrorBoundary) */
export function recordComponentError(errorClass: string, component: string): void {
  sendTelemetry({
    event_type: 'component_error',
    error_class: extractErrorClass(errorClass),
    component: component.slice(0, 100),
  });
}
