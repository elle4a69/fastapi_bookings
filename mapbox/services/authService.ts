import { apiFetch } from './apiClient';
import type { AuthUser, BootstrapData, UiConfig } from '../types';

interface AccessTokenData {
  access_token: string;
  token_type: string;
}

function decodeJwtPayload(token: string): Record<string, unknown> {
  try {
    const payload = token.split('.')[1];
    if (!payload) return {};
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')));
  } catch {
    return {};
  }
}

export const authService = {
  async adminLogin(company: string, login: string, password: string): Promise<AuthUser> {
    const data = await apiFetch<AccessTokenData>('/api/admin/auth', {
      method: 'POST',
      body: JSON.stringify({ company, login, password }),
    });
    const claims = decodeJwtPayload(data.access_token);
    return {
      token: data.access_token,
      role: (claims.role as AuthUser['role']) || 'staff',
      permission_keys: [],
    };
  },

  async getPublicToken(company: string, apiKey: string): Promise<{ token: string; tenant_subdomain: string }> {
    const data = await apiFetch<AccessTokenData>('/api/public/auth/token', {
      method: 'POST',
      body: JSON.stringify({ company, key: apiKey }),
    });
    return { token: data.access_token, tenant_subdomain: company };
  },

  async getBootstrap(): Promise<BootstrapData> {
    return apiFetch<BootstrapData>('/api/public/bootstrap', { method: 'GET' });
  },

  async getUiConfig(): Promise<UiConfig> {
    return apiFetch<UiConfig>('/api/public/ui-config', { method: 'GET' });
  },
};
