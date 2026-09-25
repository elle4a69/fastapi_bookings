import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  getClientAccessToken,
  setClientAccessToken,
  clearClientAccessToken,
  getActiveTenantFromHost,
} from "@/lib/api";

export interface ClientProfile {
  id: number;
  tenant_id: number;
  name: string | null;
  email: string | null;
  phone: string | null;
  address_line1?: string | null;
  city?: string | null;
  timezone?: string | null;
}

interface ClientPortalContextType {
  client: ClientProfile | null;
  clientToken: string | null;
  tenantSlug: string;
  isAuthenticated: boolean;
  isLoading: boolean;
  sendOtp: (phoneOrEmail: string) => Promise<{
    ok: boolean;
    message: string;
    demo_code?: string;
    active_code?: string;
  }>;
  verifyOtp: (
    phoneOrEmail: string,
    code: string
  ) => Promise<{ ok: boolean; client?: ClientProfile; error?: string }>;
  logout: () => void;
  refreshClient: () => Promise<void>;
  clientApi: <T = any>(
    endpoint: string,
    options?: RequestInit & { data?: any }
  ) => Promise<T>;
}

const ClientPortalContext = createContext<ClientPortalContextType | undefined>(
  undefined
);

export const ClientPortalProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [clientToken, setClientTokenState] = useState<string | null>(() =>
    getClientAccessToken()
  );
  const [client, setClient] = useState<ClientProfile | null>(() => {
    if (typeof window === "undefined") return null;
    const raw = localStorage.getItem("client_portal_client");
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const tenantSlug = getActiveTenantFromHost() || "simplydemo";

  const clientApi = useCallback(
    async <T = any,>(
      endpoint: string,
      options: RequestInit & { data?: any } = {}
    ): Promise<T> => {
      const { data, headers: customHeaders, ...customOptions } = options;
      const token = getClientAccessToken();

      const headers = new Headers({
        "Content-Type": "application/json",
      });

      new Headers(customHeaders).forEach((value, name) => {
        headers.set(name, value);
      });

      if (token) {
        headers.set("X-Token", token);
      }
      headers.set("X-Tenant", tenantSlug);

      const config: RequestInit = {
        ...customOptions,
        headers,
      };

      if (data) {
        config.body = JSON.stringify(data);
      }

      const response = await fetch(endpoint, config);
      const contentType = response.headers.get("content-type");
      let resData: any;
      if (contentType && contentType.includes("application/json")) {
        resData = await response.json();
      } else {
        resData = await response.text();
      }

      if (!response.ok) {
        const errorMsg =
          resData && typeof resData === "object" && resData.detail
            ? resData.detail
            : `Request failed with status ${response.status}`;
        throw new Error(errorMsg);
      }

      return resData as T;
    },
    [tenantSlug]
  );

  const refreshClient = useCallback(async () => {
    const token = getClientAccessToken();
    if (!token) {
      setClient(null);
      setIsLoading(false);
      return;
    }
    try {
      const profile = await clientApi<ClientProfile>("/api/portal/me");
      setClient(profile);
      localStorage.setItem("client_portal_client", JSON.stringify(profile));
    } catch (err) {
      console.warn("Could not fetch client profile:", err);
      clearClientAccessToken();
      setClientTokenState(null);
      setClient(null);
    } finally {
      setIsLoading(false);
    }
  }, [clientApi]);

  useEffect(() => {
    refreshClient();
  }, [refreshClient]);

  const sendOtp = async (phoneOrEmail: string) => {
    const res = await clientApi<{
      ok: boolean;
      message: string;
      demo_code?: string;
      active_code?: string;
    }>("/api/portal/auth/send-otp", {
      method: "POST",
      data: { phone_or_email: phoneOrEmail },
    });
    return res;
  };

  const verifyOtp = async (phoneOrEmail: string, code: string) => {
    try {
      const res = await clientApi<{
        ok: boolean;
        message: string;
        data: {
          access_token: string;
          client: ClientProfile;
        };
      }>("/api/portal/auth/verify-otp", {
        method: "POST",
        data: { phone_or_email: phoneOrEmail, code },
      });

      if (res.ok && res.data) {
        setClientAccessToken(res.data.access_token);
        setClientTokenState(res.data.access_token);
        setClient(res.data.client);
        localStorage.setItem(
          "client_portal_client",
          JSON.stringify(res.data.client)
        );
        return { ok: true, client: res.data.client };
      }
      return { ok: false, error: res.message || "Failed to verify code" };
    } catch (err: any) {
      return { ok: false, error: err.message || "Verification error" };
    }
  };

  const logout = () => {
    clearClientAccessToken();
    setClientTokenState(null);
    setClient(null);
  };

  return (
    <ClientPortalContext.Provider
      value={{
        client,
        clientToken,
        tenantSlug,
        isAuthenticated: !!clientToken && !!client,
        isLoading,
        sendOtp,
        verifyOtp,
        logout,
        refreshClient,
        clientApi,
      }}
    >
      {children}
    </ClientPortalContext.Provider>
  );
};

export function useClientPortal() {
  const context = useContext(ClientPortalContext);
  if (!context) {
    throw new Error(
      "useClientPortal must be used within a ClientPortalProvider"
    );
  }
  return context;
}
