const API_BASE_URL = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000';
const ADMIN_TOKEN_STORAGE_KEY = 'token';
const LOCAL_AUTH_BYPASS_TOKEN = 'local-development-bypass';

function isLocalDevelopmentHost(): boolean {
  if (typeof window === 'undefined') return false;

  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

interface ApiClientOptions extends RequestInit {
  data?: any;
}

/**
 * Resolve the tenant solely from the hostname serving this application.
 * Only tenant.localhost and tenant.<base-domain> are tenant contexts.
 * Cloud platform routing names are not tenant slugs; quick tunnels use the
 * existing development tenant fallback without enabling local auth bypass.
 */
export function getActiveTenantFromHost(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const hostname = window.location.hostname.toLowerCase().replace(/\.$/, '');
  const hostParts = hostname.split('.');
  const tenant = hostParts[0];
  const isTenantLocalhost = hostParts.length === 2 && hostParts[1] === 'localhost';
  const isTenantDomain = hostParts.length >= 3;

  if (
    hostname.endsWith('.run.app') ||
    hostname.endsWith('.trycloudflare.com') ||
    (!isTenantLocalhost && !isTenantDomain) ||
    !tenant ||
    ['www', 'api', 'localhost', '127', '0'].includes(tenant) ||
    hostname.includes(':') ||
    /^(?:\d{1,3}\.){3}\d{1,3}$/.test(hostname) ||
    !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(tenant)
  ) {
    return null;
  }

  return tenant;
}

export function getAdminAccessToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  // If currently on /login, or if user explicitly signed out, do not auto-bypass so login screen displays
  if (window.location.pathname === '/login' || localStorage.getItem('disable_local_auth_bypass') === 'true') {
    return null;
  }

  // The backend only accepts this token when LOCAL_AUTH_BYPASS=true. This is
  // intentionally restricted to browser sessions served from localhost.
  if (isLocalDevelopmentHost()) {
    return LOCAL_AUTH_BYPASS_TOKEN;
  }

  const token = localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY)?.trim();
  if (token === 'mock-admin-token') {
    localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
    return null;
  }

  return token || null;
}

export function setAdminAccessToken(token: string): void {
  localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
  localStorage.removeItem('disable_local_auth_bypass');
}

export function clearAdminAccessToken(): void {
  localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
  localStorage.setItem('disable_local_auth_bypass', 'true');
}

const CLIENT_TOKEN_STORAGE_KEY = 'client_portal_token';

export function getClientAccessToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return localStorage.getItem(CLIENT_TOKEN_STORAGE_KEY)?.trim() || null;
}

export function setClientAccessToken(token: string): void {
  localStorage.setItem(CLIENT_TOKEN_STORAGE_KEY, token);
}

export function clearClientAccessToken(): void {
  localStorage.removeItem(CLIENT_TOKEN_STORAGE_KEY);
  localStorage.removeItem('client_portal_client');
}


export function safePostLoginReturnPath(pathname: unknown): string {
  return typeof pathname === 'string' && /^\/admin(?:\/.*)?$/.test(pathname)
    ? pathname
    : '/admin';
}

type LoginNavigator = (path: string, options: { replace: true }) => void;

export function endAdminSession(navigate: LoginNavigator): void {
  clearAdminAccessToken();
  navigate('/login', { replace: true });
}

function clearUnauthorizedAdminSession(): void {
  if (typeof window === 'undefined') {
    return;
  }

  const { pathname } = window.location;
  if (pathname === '/admin' || pathname.startsWith('/admin/')) {
    endAdminSession((target) => window.location.replace(target));
  }
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = 'ApiError';
  }
}

export function getAuthenticatedAdminHeaders(contentType = 'application/json'): Headers {
  const token = getAdminAccessToken();
  let tenant = getActiveTenantFromHost();
  if (!tenant && typeof window !== 'undefined') {
    const isTest = typeof (globalThis as any).process !== 'undefined' && Boolean((globalThis as any).process?.env?.NODE_ENV === 'test');
    if (!isTest) {
      const h = window.location.hostname.toLowerCase();
      if (h === 'localhost' || h === '127.0.0.1' || h.includes('trycloudflare.com')) {
        tenant = 'simplydemo';
      }
    }
  }

  const headers = new Headers();
  if (contentType) {
    headers.set('Content-Type', contentType);
  }

  if (token) {
    headers.set('X-Token', token);
  }

  if (tenant) {
    headers.set('X-Tenant', tenant);
  }

  return headers;
}

export type UserFacingApiError = {
  code: string;
  message: string;
  requestId: string | null;
  retryable: boolean;
};

const NON_RETRYABLE_ERROR_CODES = new Set([
  'TEXT_CONFIGURATION_REQUIRED',
  'TEXT_CLIENT_UNAVAILABLE',
  'REALTIME_CONFIGURATION_REQUIRED',
  'REALTIME_INVALID_SDP',
  'VALIDATION_ERROR',
  'UNAUTHORIZED',
  'FORBIDDEN',
  'NOT_FOUND',
  'CONFLICT',
]);

export function toUserFacingApiError(error: unknown, fallback: string): UserFacingApiError {
  if (error instanceof ApiError) {
    const payload = error.data?.error;
    const code = typeof payload?.code === 'string' && payload.code
      ? payload.code
      : `HTTP_${error.status}`;
    const message = typeof payload?.message === 'string' && payload.message
      ? payload.message
      : error.message || fallback;
    const requestId = typeof payload?.request_id === 'string' && payload.request_id
      ? payload.request_id
      : null;
    return {
      code,
      message,
      requestId,
      retryable: !NON_RETRYABLE_ERROR_CODES.has(code) && (error.status === 408 || error.status === 429 || error.status >= 500),
    };
  }

  return {
    code: 'NETWORK_ERROR',
    message: error instanceof Error && error.message ? error.message : fallback,
    requestId: null,
    retryable: true,
  };
}

export async function authenticatedAdminFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const headers = getAuthenticatedAdminHeaders('');
  new Headers(options.headers).forEach((value, name) => {
    headers.set(name, value);
  });

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearUnauthorizedAdminSession();
  }

  return response;
}

async function request<T>(endpoint: string, method: HttpMethod, options: ApiClientOptions = {}): Promise<T> {
  const { data, headers: customHeaders, ...customOptions } = options;

  const headers = getAuthenticatedAdminHeaders();

  new Headers(customHeaders).forEach((value, name) => {
    headers.set(name, value);
  });

  const config: RequestInit = {
    method,
    headers,
    ...customOptions,
  };

  if (data) {
    config.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
    const contentType = response.headers.get('content-type');

    let responseData;
    if (contentType && contentType.includes('application/json')) {
      responseData = await response.json();
    } else {
      responseData = await response.text();
    }

    if (!response.ok) {
      if (response.status === 401) {
        clearUnauthorizedAdminSession();
      }

      const errMsg = responseData?.error?.message || responseData?.detail || response.statusText || 'API Error';
      throw new ApiError(
        response.status,
        errMsg,
        responseData
      );
    }

    return responseData;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(error instanceof Error ? error.message : 'Network error');
  }
}

export const apiClient = {
  get: <T>(endpoint: string, options?: ApiClientOptions) => request<T>(endpoint, 'GET', options),
  post: <T>(endpoint: string, data?: any, options?: ApiClientOptions) => request<T>(endpoint, 'POST', { ...options, data }),
  put: <T>(endpoint: string, data?: any, options?: ApiClientOptions) => request<T>(endpoint, 'PUT', { ...options, data }),
  delete: <T>(endpoint: string, options?: ApiClientOptions) => request<T>(endpoint, 'DELETE', options),
  patch: <T>(endpoint: string, data?: any, options?: ApiClientOptions) => request<T>(endpoint, 'PATCH', { ...options, data }),
};

export async function fetchAllPaginated<T = any>(endpoint: string, basePageSize: number = 100): Promise<T[]> {
  const separator = endpoint.includes('?') ? '&' : '?';
  let page = 1;
  let allItems: T[] = [];
  let total = 0;

  do {
    try {
      const res: any = await apiClient.get(`${endpoint}${separator}page=${page}&page_size=${basePageSize}`);
      const items: T[] = Array.isArray(res) ? res : (res?.data || []);
      allItems = allItems.concat(items);
      total = res?.meta?.total ?? allItems.length;
      if (!res?.meta || items.length === 0 || allItems.length >= total) {
        break;
      }
      page++;
    } catch {
      break;
    }
  } while (allItems.length < total);

  return allItems;
}
