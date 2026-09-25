export interface ApiClientConfig {
  baseUrl?: string
  token?: string
  defaultTimeoutMs?: number
}

export class ApiError extends Error {
  status: number
  data?: any

  constructor(status: number, message: string, data?: any) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export interface RequestOptions extends RequestInit {
  timeoutMs?: number
  params?: Record<string, string | number | boolean | undefined | null>
}

export class ApiClient {
  private baseUrl: string
  private token: string
  private defaultTimeoutMs: number

  constructor(config: ApiClientConfig = {}) {
    this.baseUrl = (config.baseUrl || 'http://127.0.0.1:8100').replace(/\/$/, '')
    this.token = config.token || 'local_secret'
    this.defaultTimeoutMs = config.defaultTimeoutMs ?? 15000
  }

  setToken(token: string) {
    this.token = token
  }

  setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/$/, '')
  }

  getBaseUrl(): string {
    return this.baseUrl
  }

  getToken(): string {
    return this.token
  }

  async request<T = any>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { timeoutMs = this.defaultTimeoutMs, params, headers, ...customConfig } = options

    let url = endpoint.startsWith('http') ? endpoint : `${this.baseUrl}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`

    if (params) {
      const searchParams = new URLSearchParams()
      for (const [key, val] of Object.entries(params)) {
        if (val !== undefined && val !== null) {
          searchParams.append(key, String(val))
        }
      }
      const qs = searchParams.toString()
      if (qs) {
        url += (url.includes('?') ? '&' : '?') + qs
      }
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    const requestHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      Authorization: `Bearer ${this.token}`,
      ...(headers as Record<string, string>)
    }

    try {
      const response = await fetch(url, {
        ...customConfig,
        headers: requestHeaders,
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        let errorData: any
        try {
          errorData = await response.json()
        } catch {
          errorData = await response.text().catch(() => null)
        }

        const errorMessage =
          (typeof errorData === 'object' && errorData !== null && (errorData.detail || errorData.message)) ||
          `HTTP ${response.status}: ${response.statusText}`

        throw new ApiError(response.status, errorMessage, errorData)
      }

      // Handle 204 No Content
      if (response.status === 204) {
        return {} as T
      }

      const data = await response.json().catch(() => ({} as T))
      return data as T
    } catch (err: any) {
      clearTimeout(timeoutId)
      if (err.name === 'AbortError') {
        throw new ApiError(408, `Request timed out after ${timeoutMs}ms`)
      }
      if (err instanceof ApiError) {
        throw err
      }
      throw new ApiError(0, err?.message || 'Network connection failed', err)
    }
  }

  get<T = any>(endpoint: string, params?: Record<string, any>, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET', params })
  }

  post<T = any>(endpoint: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined
    })
  }

  patch<T = any>(endpoint: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined
    })
  }

  put<T = any>(endpoint: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined
    })
  }

  delete<T = any>(endpoint: string, params?: Record<string, any>, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE', params })
  }
}

export const defaultApiClient = new ApiClient()
