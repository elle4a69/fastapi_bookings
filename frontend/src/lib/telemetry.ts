/**
 * telemetry.ts – Privacy-safe frontend telemetry forwarder.
 *
 * Captures JS errors and unhandled promise rejections, strips all personal
 * data, and forwards only structural metadata (error class, route template,
 * component name) to the backend diagnostics endpoint.
 *
 * NEVER sends: message body, SMS content, phone numbers, names, tokens,
 * customer data, query parameters, or anything identifying.
 */

const TELEMETRY_ENDPOINT = '/api/admin/system/diagnostics/telemetry';

interface TelemetryEvent {
  event_type: string;
  error_class?: string;
  route?: string;
  component?: string;
  duration_ms?: number;
  vital_name?: string;
  session_id?: string;
}

/** Return URL pathname only – strip query params and hash */
function safeRoute(): string {
  try {
    return window.location.pathname;
  } catch {
    return '';
  }
}

/** Get anonymous session ID (generated once per page load, not stored) */
const _sessionId: string = Math.random().toString(36).slice(2, 10);

async function sendTelemetry(event: TelemetryEvent): Promise<void> {
  try {
    const token = typeof localStorage !== 'undefined' ? (localStorage.getItem('token') || '') : '';
    if (!token) return; // only send when admin session is active

    const body: TelemetryEvent = {
      ...event,
      route: event.route ?? safeRoute(),
      session_id: _sessionId,
    };

    await fetch(TELEMETRY_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Token': token,
      },
      body: JSON.stringify(body),
    });
  } catch {
    // Silently ignore – never let telemetry break the app
  }
}

function extractErrorClass(err: unknown): string {
  if (err instanceof Error) return err.constructor.name || 'Error';
  if (typeof err === 'string') return 'StringError';
  return 'UnknownError';
}

/** Register global error and unhandled rejection listeners */
export function initFrontendTelemetry(): void {
  if (typeof window === 'undefined') return;

  window.addEventListener('error', (event: ErrorEvent) => {
    sendTelemetry({
      event_type: 'js_error',
      error_class: extractErrorClass(event.error),
      // Only the first line of the source file – never the message (may contain PII)
      component: event.filename ? event.filename.split('/').pop()?.split('?')[0] ?? '' : '',
    });
  });

  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
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
    error_class: errorClass,
    component,
  });
}
