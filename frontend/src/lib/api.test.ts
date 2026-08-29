// @ts-expect-error Node.js test runner module
import { describe, it, beforeEach } from "node:test";
// @ts-expect-error Node.js assert module
import assert from "node:assert/strict";
import {
  ApiError,
  adminApiClient,
  clearAdminToken,
  fetchAllPaginated,
  getActiveTenant,
  getAdminToken,
  loginAdmin,
  publicApiClient,
  setActiveTenant,
  setAdminToken,
} from "./api.ts";

// Simple in-memory Storage mock for Node test environment
class MockStorage implements Storage {
  private store: Map<string, string> = new Map();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}

// Setup simulated browser globals
const mockLocalStorage = new MockStorage();
const mockSessionStorage = new MockStorage();

(globalThis as any).localStorage = mockLocalStorage;
(globalThis as any).sessionStorage = mockSessionStorage;
(globalThis as any).window = {
  location: {
    origin: "http://localhost:8000",
    hostname: "simplydemo.localhost",
    href: "",
  },
};

describe("Frontend API Client & Auth Separation (FE-001, FE-002, FE-003)", () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    mockSessionStorage.clear();
    (globalThis as any).window.location.hostname = "simplydemo.localhost";
  });

  it("resolves active tenant from storage or hostname, and returns empty string when neither is present (AUTH-002)", () => {
    // 1. Hostname with valid subdomain
    (globalThis as any).window.location.hostname = "simplydemo.localhost";
    assert.strictEqual(getActiveTenant(), "simplydemo");

    // 2. Explicit tenant in storage overrides hostname
    setActiveTenant("tenant-alpha");
    assert.strictEqual(getActiveTenant(), "tenant-alpha");

    // 3. Different hostname subdomain
    mockLocalStorage.clear();
    (globalThis as any).window.location.hostname = "custom-tenant.localhost";
    assert.strictEqual(getActiveTenant(), "custom-tenant");

    // 4. Naked localhost (no subdomain) and empty storage -> returns empty string (no 'simplydemo' fallback)
    mockLocalStorage.clear();
    (globalThis as any).window.location.hostname = "localhost";
    assert.strictEqual(getActiveTenant(), "");

    // 5. Excluded hostname prefix (e.g. www, api, 127) -> returns empty string
    (globalThis as any).window.location.hostname = "www.localhost";
    assert.strictEqual(getActiveTenant(), "");

    (globalThis as any).window.location.hostname = "api.localhost";
    assert.strictEqual(getActiveTenant(), "");
  });

  it("manages admin token in localStorage and sessionStorage", () => {
    assert.strictEqual(getAdminToken(), null);

    setAdminToken("sample-jwt-token-remember", true);
    assert.strictEqual(mockLocalStorage.getItem("token"), "sample-jwt-token-remember");
    assert.strictEqual(getAdminToken(), "sample-jwt-token-remember");

    setAdminToken("sample-session-token", false);
    assert.strictEqual(mockSessionStorage.getItem("token"), "sample-session-token");

    clearAdminToken();
    assert.strictEqual(getAdminToken(), null);
  });

  it("FE-002: publicApiClient NEVER attaches admin X-Token even if present in storage", async () => {
    setAdminToken("secret-admin-token");
    setActiveTenant("simplydemo");

    let capturedHeaders: Record<string, string> = {};
    (globalThis as any).fetch = async (_url: string, init: RequestInit) => {
      capturedHeaders = init.headers as Record<string, string>;
      return new Response(JSON.stringify({ ok: true, data: { public: true } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    const res = await publicApiClient.get<{ ok: boolean }>("/api/public/bootstrap");
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedHeaders["X-Tenant"], "simplydemo");
    assert.strictEqual(capturedHeaders["X-Token"], undefined, "Public client must never attach X-Token");
  });

  it("adminApiClient attaches X-Token and X-Tenant when authenticated", async () => {
    setAdminToken("valid-admin-jwt");
    setActiveTenant("simplydemo");

    let capturedHeaders: Record<string, string> = {};
    (globalThis as any).fetch = async (_url: string, init: RequestInit) => {
      capturedHeaders = init.headers as Record<string, string>;
      return new Response(JSON.stringify({ ok: true, data: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await adminApiClient.get("/api/admin/services");
    assert.strictEqual(capturedHeaders["X-Tenant"], "simplydemo");
    assert.strictEqual(capturedHeaders["X-Token"], "valid-admin-jwt");
  });

  it("clears admin token on 401 Unauthorized responses from admin endpoints", async () => {
    setAdminToken("expired-token");

    (globalThis as any).fetch = async () => {
      return new Response(JSON.stringify({ detail: "Token expired" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });
    };

    await assert.rejects(
      async () => {
        await adminApiClient.get("/api/admin/bookings");
      },
      (err: unknown) => {
        if (err instanceof ApiError) {
          assert.strictEqual(err.status, 401);
          assert.strictEqual(err.message, "Token expired");
          return true;
        }
        return false;
      }
    );

    assert.strictEqual(getAdminToken(), null, "401 response must clear stored token");
  });

  it("FE-003: fetchAllPaginated propagates ApiError rather than swallowing failures", async () => {
    (globalThis as any).fetch = async () => {
      return new Response(JSON.stringify({ detail: "Database connection failed" }), {
        status: 500,
        headers: { "content-type": "application/json" },
      });
    };

    await assert.rejects(
      async () => {
        await fetchAllPaginated("/api/admin/clients");
      },
      (err: unknown) => {
        if (err instanceof ApiError) {
          assert.strictEqual(err.status, 500);
          assert.strictEqual(err.message, "Database connection failed");
          return true;
        }
        return false;
      },
      "fetchAllPaginated must not swallow errors into empty array"
    );
  });

  it("fetchAllPaginated iterates multiple pages successfully", async () => {
    let callCount = 0;
    (globalThis as any).fetch = async (url: string) => {
      callCount++;
      const urlObj = new URL(url);
      const page = Number(urlObj.searchParams.get("page") || "1");
      const pageSize = Number(urlObj.searchParams.get("page_size") || "2");

      if (page === 1) {
        return new Response(
          JSON.stringify({
            data: [{ id: 1 }, { id: 2 }],
            meta: { total: 3, page: 1, page_size: pageSize },
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      } else {
        return new Response(
          JSON.stringify({
            data: [{ id: 3 }],
            meta: { total: 3, page: 2, page_size: pageSize },
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      }
    };

    const results = await fetchAllPaginated<{ id: number }>("/api/admin/items", 2);
    assert.strictEqual(results.length, 3);
    assert.deepStrictEqual(results, [{ id: 1 }, { id: 2 }, { id: 3 }]);
    assert.strictEqual(callCount, 2);
  });

  it("FE-001: loginAdmin authenticates against backend and persists token", async () => {
    let capturedBody: any = null;
    let capturedHeaders: Record<string, string> = {};

    (globalThis as any).fetch = async (_url: string, init: RequestInit) => {
      capturedHeaders = init.headers as Record<string, string>;
      capturedBody = JSON.parse(init.body as string);

      return new Response(
        JSON.stringify({
          ok: true,
          data: {
            access_token: "jwt-fresh-admin-token",
            token_type: "bearer",
          },
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      );
    };

    const res = await loginAdmin(
      {
        company: "simplydemo",
        login: "admin",
        password: "secretpassword",
      },
      true
    );

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedHeaders["X-Tenant"], "simplydemo");
    assert.strictEqual(capturedBody.company, "simplydemo");
    assert.strictEqual(capturedBody.login, "admin");
    assert.strictEqual(capturedBody.password, "secretpassword");
    assert.strictEqual(getAdminToken(), "jwt-fresh-admin-token");
  });
});
