import type { UiError } from '../types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
const MOCK_MODE = import.meta.env.VITE_MOCK_API === 'true';

export class ApiError extends Error {
  public readonly uiError: UiError;
  public readonly status?: number;
  public readonly requestId?: string;

  constructor(uiError: UiError, status?: number, requestId?: string) {
    super(uiError.message);
    this.name = 'ApiError';
    this.uiError = uiError;
    this.status = status;
    this.requestId = requestId;
  }
}

interface ErrorEnvelope {
  ok?: boolean;
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    request_id?: string;
  };
  detail?: string | Array<{ loc?: unknown[]; msg?: string; type?: string }>;
  request_id?: string;
}

function getTenant(): string | null {
  return sessionStorage.getItem('tenant_subdomain') || localStorage.getItem('tenant_subdomain');
}

function endpointUrl(endpoint: string): string {
  if (/^https?:\/\//i.test(endpoint)) return endpoint;
  return `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
}

function validationMessage(detail: ErrorEnvelope['detail']): string | undefined {
  if (typeof detail === 'string') return detail;
  if (!Array.isArray(detail)) return undefined;
  return detail.map((entry) => entry.msg).filter(Boolean).join('; ') || undefined;
}

function toUiError(payload: ErrorEnvelope | null, status: number): UiError {
  const nested = payload?.error;
  return {
    code: nested?.code || (status === 401 ? 'UNAUTHENTICATED' : status === 403 ? 'FORBIDDEN' : status === 404 ? 'NOT_FOUND' : status === 422 ? 'VALIDATION_ERROR' : 'REQUEST_FAILED'),
    message: nested?.message || validationMessage(payload?.detail) || `Request failed with status ${status}.`,
    details: nested?.details,
  } as UiError;
}

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  if (MOCK_MODE) {
    throw new ApiError({ code: 'MOCK_API_DISABLED', message: 'The legacy mock API is no longer embedded in the production client.' });
  }

  const headers = new Headers(options.headers);
  const tenant = getTenant();
  const adminToken = localStorage.getItem('admin_token');
  const publicToken = localStorage.getItem('public_token');
  const clientToken = localStorage.getItem('client_token');

  if (tenant && !headers.has('X-Tenant')) headers.set('X-Tenant', tenant);
  if (endpoint.startsWith('/api/admin/') && adminToken && !headers.has('X-Token')) headers.set('X-Token', adminToken);
  else if (endpoint.startsWith('/api/public/clients/') && clientToken && !headers.has('X-Token')) headers.set('X-Token', clientToken);
  else if (endpoint.startsWith('/api/public/') && publicToken && !headers.has('X-Token')) headers.set('X-Token', publicToken);

  if (options.body != null && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');

  let response: Response;
  try {
    response = await fetch(endpointUrl(endpoint), { ...options, headers });
  } catch {
    throw new ApiError({
      code: 'NETWORK_ERROR',
      message: 'The API could not be reached. Check that the FastAPI server is running and try again.',
    });
  }

  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text().catch(() => '');

  if (!response.ok) {
    const envelope = payload && typeof payload === 'object' ? payload as ErrorEnvelope : null;
    const requestId = envelope?.error?.request_id || envelope?.request_id || response.headers.get('x-request-id') || undefined;
    throw new ApiError(toUiError(envelope, response.status), response.status, requestId);
  }

  if (payload && typeof payload === 'object' && 'ok' in payload) {
    const envelope = payload as { ok: boolean; data?: T; error?: ErrorEnvelope['error'] };
    if (!envelope.ok) {
      throw new ApiError(toUiError({ ok: false, error: envelope.error }, response.status), response.status, envelope.error?.request_id);
    }
    return envelope.data as T;
  }

  return payload as T;
}
