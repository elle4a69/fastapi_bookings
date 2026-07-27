const API_BASE_URL = 'http://localhost:8000';

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

  const token = localStorage.getItem('token') || 'mock-admin-token';

  // Determine active tenant subdomain (default to simplydemo)
  let tenant = 'simplydemo';
  if (typeof window !== 'undefined' && window.location) {
    const hostParts = window.location.hostname.split('.');
    if (hostParts.length > 1 && hostParts[hostParts.length - 1] === 'localhost') {
      tenant = hostParts[0];
    }
  }

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'X-Token': token,
    'X-Tenant': tenant,
    ...customHeaders,
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
