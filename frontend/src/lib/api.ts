const API_BASE_URL = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000';

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

interface ApiClientOptions extends RequestInit {
  data?: any;
}

class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = 'ApiError';
  }
}

async function request<T>(endpoint: string, method: HttpMethod, options: ApiClientOptions = {}): Promise<T> {
  const { data, headers: customHeaders, ...customOptions } = options;

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  // Determine active tenant subdomain
  let tenant = typeof window !== 'undefined' ? localStorage.getItem('tenant') : null;
  if (!tenant && typeof window !== 'undefined' && window.location) {
    const hostParts = window.location.hostname.split('.');
    if (hostParts.length > 1 && hostParts[hostParts.length - 1] === 'localhost' && !['www', 'api', 'localhost', '127'].includes(hostParts[0])) {
      tenant = hostParts[0];
    }
  }
  if (!tenant) {
    tenant = 'simplydemo';
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(tenant ? { 'X-Tenant': tenant } : {}),
    ...(token ? { 'X-Token': token } : {}),
    ...(customHeaders as Record<string, string> || {}),
  };

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
      if (response.status === 401 && typeof window !== 'undefined') {
        localStorage.removeItem('token');
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
