const API_BASE_URL = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

export interface ApiClientOptions extends RequestInit {
  data?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
  skipAuth?: boolean;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = 'ApiError';
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

export function getActiveTenant(): string {
  if (typeof window === 'undefined') return 'simplydemo';
  const stored = localStorage.getItem('tenant') || sessionStorage.getItem('tenant');
  if (stored && stored.trim()) {
    return stored.trim();
  }
  if (window.location && window.location.hostname) {
    const hostParts = window.location.hostname.split('.');
    if (hostParts.length > 1 && hostParts[hostParts.length - 1] === 'localhost' && !['www', 'api', 'localhost', '127'].includes(hostParts[0])) {
      return hostParts[0];
    }
  }
  return 'simplydemo';
}

export function setActiveTenant(tenant: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('tenant', tenant.trim());
}

export function getAdminToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('token') || sessionStorage.getItem('token') || null;
}

export function setAdminToken(token: string, remember: boolean = true): void {
  if (typeof window === 'undefined') return;
  if (remember) {
    localStorage.setItem('token', token);
  } else {
    sessionStorage.setItem('token', token);
  }
}

export function clearAdminToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  sessionStorage.removeItem('token');
}

export function logoutAdmin(): void {
  clearAdminToken();
  if (typeof window !== 'undefined') {
    window.location.href = '/login';
  }
}

export interface AdminLoginCredentials {
  company?: string;
  login: string;
  password: string;
}

export interface AdminLoginResponse {
  ok: boolean;
  data: {
    access_token: string;
    token_type: string;
  };
}

export async function executeRequest<T = any>(
  endpoint: string,
  method: HttpMethod,
  options: ApiClientOptions = {},
  isPublicClient: boolean = false
): Promise<T> {
  const { data, headers: customHeaders, skipAuth, ...customOptions } = options;

  const tenant = getActiveTenant();
  const shouldSkipAuth = isPublicClient || skipAuth || endpoint.startsWith('/api/public') || endpoint.startsWith('/public');
  const token = shouldSkipAuth ? null : getAdminToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(tenant ? { 'X-Tenant': tenant } : {}),
    ...(token ? { 'X-Token': token } : {}),
    ...((customHeaders as Record<string, string>) || {}),
  };

  const config: RequestInit = {
    method,
    headers,
    ...customOptions,
  };

  if (data !== undefined) {
    config.body = typeof data === 'string' ? data : JSON.stringify(data);
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
    const contentType = response.headers.get('content-type');

    let responseData: any;
    if (contentType && contentType.includes('application/json')) {
      responseData = await response.json();
    } else {
      responseData = await response.text();
    }

    if (!response.ok) {
      if (response.status === 401 && !shouldSkipAuth) {
        clearAdminToken();
      }
      const errMsg = responseData?.detail || responseData?.error?.message || responseData?.message || response.statusText || 'API Error';
      throw new ApiError(response.status, errMsg, responseData);
    }

    return responseData as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(error instanceof Error ? error.message : 'Network error');
  }
}

export const publicApiClient = {
  get: <T = any>(endpoint: string, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'GET', options, true),
  post: <T = any>(endpoint: string, data?: unknown, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'POST', { ...options, data }, true),
  put: <T = any>(endpoint: string, data?: unknown, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'PUT', { ...options, data }, true),
  delete: <T = any>(endpoint: string, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'DELETE', options, true),
  patch: <T = any>(endpoint: string, data?: unknown, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'PATCH', { ...options, data }, true),
};

export const adminApiClient = {
  get: <T = any>(endpoint: string, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'GET', options, false),
  post: <T = any>(endpoint: string, data?: unknown, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'POST', { ...options, data }, false),
  put: <T = any>(endpoint: string, data?: unknown, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'PUT', { ...options, data }, false),
  delete: <T = any>(endpoint: string, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'DELETE', options, false),
  patch: <T = any>(endpoint: string, data?: unknown, options?: ApiClientOptions) => executeRequest<T>(endpoint, 'PATCH', { ...options, data }, false),
};

export const apiClient = adminApiClient;

export async function loginAdmin(credentials: AdminLoginCredentials, remember: boolean = true): Promise<AdminLoginResponse> {
  const tenant = credentials.company?.trim() || getActiveTenant();
  const payload = {
    company: tenant,
    login: credentials.login,
    password: credentials.password,
  };

  let responseData: AdminLoginResponse;
  try {
    responseData = await publicApiClient.post<AdminLoginResponse>('/api/admin/auth', payload, {
      headers: { 'X-Tenant': tenant },
    });
  } catch (err: unknown) {
    if (err instanceof ApiError && err.status === 404) {
      responseData = await publicApiClient.post<AdminLoginResponse>('/api/admin/auth/login', payload, {
        headers: { 'X-Tenant': tenant },
      });
    } else {
      throw err;
    }
  }

  const token = responseData?.data?.access_token || (responseData as any)?.access_token;
  if (token) {
    setAdminToken(token, remember);
    setActiveTenant(tenant);
  }
  return responseData;
}

export async function fetchAllPaginated<T = any>(
  endpoint: string,
  basePageSize: number = 100,
  client: { get: <R = any>(url: string, opts?: ApiClientOptions) => Promise<R> } = adminApiClient
): Promise<T[]> {
  const separator = endpoint.includes('?') ? '&' : '?';
  let page = 1;
  let allItems: T[] = [];
  let total = 0;

  do {
    const res: any = await client.get(`${endpoint}${separator}page=${page}&page_size=${basePageSize}`);
    const items: T[] = Array.isArray(res) ? res : (res?.data || []);
    allItems = allItems.concat(items);
    total = typeof res?.meta?.total === 'number' ? res.meta.total : allItems.length;
    if (!res?.meta || items.length === 0 || allItems.length >= total) {
      break;
    }
    page++;
  } while (allItems.length < total);

  return allItems;
}
