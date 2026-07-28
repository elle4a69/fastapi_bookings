import React, { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { BootstrapData, UiConfig, UiError } from '../types';
import { authService } from '../services/authService';

interface TenantContextState {
  subdomain: string;
  bootstrap: BootstrapData | null;
  uiConfig: UiConfig | null;
  isLoading: boolean;
  error: UiError | null;
  retryBootstrap: () => void;
}

const TenantContext = createContext<TenantContextState | undefined>(undefined);

function resolveTenantSubdomain(): string {
  const queryTenant = new URLSearchParams(window.location.search).get('tenant');
  if (queryTenant) return queryTenant;

  const host = window.location.hostname;
  if (host !== 'localhost' && host !== '127.0.0.1') {
    const [subdomain] = host.split('.');
    if (subdomain && subdomain !== 'www') return subdomain;
  }

  return import.meta.env.VITE_TENANT_SUBDOMAIN || 'simplydemo';
}

export const TenantProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [subdomain, setSubdomain] = useState('');
  const [bootstrap, setBootstrap] = useState<BootstrapData | null>(null);
  const [uiConfig, setUiConfig] = useState<UiConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<UiError | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let active = true;

    const initializeTenant = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const resolvedSubdomain = resolveTenantSubdomain();
        setSubdomain(resolvedSubdomain);
        sessionStorage.setItem('tenant_subdomain', resolvedSubdomain);
        localStorage.setItem('tenant_subdomain', resolvedSubdomain);

        const publicApiKey = import.meta.env.VITE_PUBLIC_API_KEY;
        if (!publicApiKey) {
          throw { uiError: { code: 'MISSING_PUBLIC_API_KEY', message: 'VITE_PUBLIC_API_KEY is not configured for the booking frontend.' } };
        }

        const tokenData = await authService.getPublicToken(resolvedSubdomain, publicApiKey);
        localStorage.setItem('public_token', tokenData.token);

        const [bootstrapData, configData] = await Promise.all([
          authService.getBootstrap(),
          authService.getUiConfig(),
        ]);

        if (active) {
          setBootstrap(bootstrapData);
          setUiConfig(configData);
        }
      } catch (err: unknown) {
        if (active) {
          const candidate = err as { uiError?: UiError };
          setError(candidate.uiError || { code: 'BOOTSTRAP_FAILED', message: "We couldn't load this booking page. Please try again." });
        }
      } finally {
        if (active) setIsLoading(false);
      }
    };

    void initializeTenant();
    return () => { active = false; };
  }, [retryCount]);

  return (
    <TenantContext.Provider value={{
      subdomain,
      bootstrap,
      uiConfig,
      isLoading,
      error,
      retryBootstrap: () => setRetryCount((count) => count + 1),
    }}>
      {children}
    </TenantContext.Provider>
  );
};

export const useTenant = () => {
  const context = useContext(TenantContext);
  if (!context) throw new Error('useTenant must be used within a TenantProvider');
  return context;
};
