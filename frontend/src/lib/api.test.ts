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
  logoutAdmin,
  publicApiClient,
  setActiveTenant,
  setAdminToken,
} from "./api.ts";

// In-memory Storage mock for Node test environment
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

describe("Frontend API Client & Auth Separation (FE-001, FE-002, FE-003, TEST-004)", () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    mockSessionStorage.clear();
    (globalThis as any).window.location.hostname = "simplydemo.localhost";
    (globalThis as any).window.location.href = "";
  });

  describe("Tenant Resolution & Management (AUTH-002)", () => {
    it("resolves active tenant from storage or hostname, and returns empty string when neither is present", () => {
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

      // 4. Naked localhost (no subdomain) and empty storage -> returns empty string
      mockLocalStorage.clear();
      (globalThis as any).window.location.hostname = "localhost";
      assert.strictEqual(getActiveTenant(), "");

      // 5. Excluded hostname prefix (e.g. www, api, 127) -> returns empty string
      (globalThis as any).window.location.hostname = "www.localhost";
      assert.strictEqual(getActiveTenant(), "");

      (globalThis as any).window.location.hostname = "api.localhost";
      assert.strictEqual(getActiveTenant(), "");

      (globalThis as any).window.location.hostname = "127.0.0.1";
      assert.strictEqual(getActiveTenant(), "");
    });

    it("resolves tenant from sessionStorage if localStorage is empty", () => {
      mockLocalStorage.clear();
      mockSessionStorage.setItem("tenant", "session-tenant");
      (globalThis as any).window.location.hostname = "localhost";
      assert.strictEqual(getActiveTenant(), "session-tenant");
    });
  });

  describe("Token Storage Persistence & Session Isolation (FE-001, TEST-004)", () => {
    it("manages admin token in localStorage when remember is true", () => {
      assert.strictEqual(getAdminToken(), null);

      setAdminToken("sample-jwt-token-remember", true);
      assert.strictEqual(mockLocalStorage.getItem("token"), "sample-jwt-token-remember");
      assert.strictEqual(mockSessionStorage.getItem("token"), null);
      assert.strictEqual(getAdminToken(), "sample-jwt-token-remember");
    });

    it("manages admin token in sessionStorage when remember is false", () => {
      assert.strictEqual(getAdminToken(), null);

      setAdminToken("sample-session-token", false);
      assert.strictEqual(mockSessionStorage.getItem("token"), "sample-session-token");
      assert.strictEqual(mockLocalStorage.getItem("token"), null);
      assert.strictEqual(getAdminToken(), "sample-session-token");
    });

    it("clearAdminToken clears both localStorage and sessionStorage", () => {
      mockLocalStorage.setItem("token", "local-token");
      mockSessionStorage.setItem("token", "session-token");

      clearAdminToken();
      assert.strictEqual(mockLocalStorage.getItem("token"), null);
      assert.strictEqual(mockSessionStorage.getItem("token"), null);
      assert.strictEqual(getAdminToken(), null);
    });

    it("logoutAdmin clears tokens and updates window location to /login", () => {
      setAdminToken("active-token", true);
      (globalThis as any).window.location.href = "/admin/bookings";

      logoutAdmin();
      assert.strictEqual(getAdminToken(), null);
      assert.strictEqual((globalThis as any).window.location.href, "/login");
    });
  });

  describe("API Client Header Isolation & Auth Enforcement (FE-002, TEST-004)", () => {
    it("FE-002: publicApiClient NEVER attaches admin X-Token even if present in storage", async () => {
      setAdminToken("secret-admin-token", true);
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

    it("publicApiClient HTTP methods (POST, PUT, DELETE, PATCH) maintain header isolation", async () => {
      setAdminToken("admin-secret", true);
      setActiveTenant("simplydemo");

      const methods = ["POST", "PUT", "DELETE", "PATCH"] as const;
      for (const method of methods) {
        let capturedMethod = "";
        let capturedHeaders: Record<string, string> = {};

        (globalThis as any).fetch = async (_url: string, init: RequestInit) => {
          capturedMethod = init.method ?? "";
          capturedHeaders = init.headers as Record<string, string>;
          return new Response(JSON.stringify({ success: true }), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        };

        if (method === "POST") await publicApiClient.post("/api/public/submit", { name: "test" });
        if (method === "PUT") await publicApiClient.put("/api/public/update", { name: "test" });
        if (method === "DELETE") await publicApiClient.delete("/api/public/delete");
        if (method === "PATCH") await publicApiClient.patch("/api/public/patch", { name: "test" });

        assert.strictEqual(capturedMethod, method);
        assert.strictEqual(capturedHeaders["X-Token"], undefined, `publicApiClient.${method} must not send X-Token`);
        assert.strictEqual(capturedHeaders["X-Tenant"], "simplydemo");
      }
    });

    it("adminApiClient attaches X-Token and X-Tenant when authenticated", async () => {
      setAdminToken("valid-admin-jwt", true);
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

    it("adminApiClient omits X-Token if skipAuth option is provided or route starts with /api/public", async () => {
      setAdminToken("valid-admin-jwt", true);
      setActiveTenant("simplydemo");

      let capturedHeaders: Record<string, string> = {};
      (globalThis as any).fetch = async (_url: string, init: RequestInit) => {
        capturedHeaders = init.headers as Record<string, string>;
        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      };

      // 1. With skipAuth option
      await adminApiClient.get("/api/admin/health", { skipAuth: true });
      assert.strictEqual(capturedHeaders["X-Token"], undefined);

      // 2. With public endpoint
      await adminApiClient.get("/api/public/config");
      assert.strictEqual(capturedHeaders["X-Token"], undefined);
    });

    it("clears admin token on 401 Unauthorized responses from admin endpoints", async () => {
      setAdminToken("expired-token", true);

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

    it("does NOT clear admin token on 401 Unauthorized if request was public / skipped auth", async () => {
      setAdminToken("valid-admin-token", true);

      (globalThis as any).fetch = async () => {
        return new Response(JSON.stringify({ detail: "Public 401" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        });
      };

      await assert.rejects(
        async () => {
          await publicApiClient.get("/api/public/protected-guest");
        },
        (err: unknown) => err instanceof ApiError && err.status === 401
      );

      assert.strictEqual(getAdminToken(), "valid-admin-token", "Public 401 must not clear admin token");
    });
  });

  describe("Admin Login Workflow (FE-001, TEST-004)", () => {
    it("FE-001: loginAdmin authenticates against backend and persists token to localStorage when remember is true", async () => {
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
      assert.strictEqual(mockLocalStorage.getItem("token"), "jwt-fresh-admin-token");
      assert.strictEqual(mockSessionStorage.getItem("token"), null);
      assert.strictEqual(getAdminToken(), "jwt-fresh-admin-token");
    });

    it("loginAdmin persists token to sessionStorage when remember is false", async () => {
      (globalThis as any).fetch = async () => {
        return new Response(
          JSON.stringify({
            ok: true,
            data: {
              access_token: "jwt-session-token",
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
        false
      );

      assert.strictEqual(res.ok, true);
      assert.strictEqual(mockSessionStorage.getItem("token"), "jwt-session-token");
      assert.strictEqual(mockLocalStorage.getItem("token"), null);
      assert.strictEqual(getAdminToken(), "jwt-session-token");
    });

    it("loginAdmin falls back to /api/admin/auth/login when /api/admin/auth returns 404", async () => {
      const endpointsCalled: string[] = [];

      (globalThis as any).fetch = async (url: string) => {
        endpointsCalled.push(url);
        if (url.endsWith("/api/admin/auth")) {
          return new Response(JSON.stringify({ detail: "Not found" }), {
            status: 404,
            headers: { "content-type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({
            ok: true,
            data: {
              access_token: "jwt-fallback-token",
              token_type: "bearer",
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      };

      const res = await loginAdmin({
        company: "simplydemo",
        login: "admin",
        password: "secretpassword",
      });

      assert.strictEqual(res.ok, true);
      assert.strictEqual(endpointsCalled.length, 2);
      assert.ok(endpointsCalled[0].endsWith("/api/admin/auth"));
      assert.ok(endpointsCalled[1].endsWith("/api/admin/auth/login"));
      assert.strictEqual(getAdminToken(), "jwt-fallback-token");
    });

    it("loginAdmin propagates credential error (401)", async () => {
      (globalThis as any).fetch = async () => {
        return new Response(JSON.stringify({ detail: "Invalid username or password" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        });
      };

      await assert.rejects(
        async () => {
          await loginAdmin({
            company: "simplydemo",
            login: "admin",
            password: "wrong-password",
          });
        },
        (err: unknown) => {
          return err instanceof ApiError && err.status === 401 && err.message === "Invalid username or password";
        }
      );
    });
  });

  describe("Pagination & Error Handling (FE-003, TEST-004)", () => {
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

    it("fetchAllPaginated handles existing query parameters correctly", async () => {
      let capturedUrl = "";
      (globalThis as any).fetch = async (url: string) => {
        capturedUrl = url;
        return new Response(
          JSON.stringify({
            data: [{ id: 1 }],
            meta: { total: 1, page: 1, page_size: 10 },
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      };

      await fetchAllPaginated("/api/admin/services?status=active", 10);
      assert.ok(capturedUrl.includes("status=active&page=1&page_size=10"));
    });

    it("fetchAllPaginated terminates if response is raw array without metadata", async () => {
      let callCount = 0;
      (globalThis as any).fetch = async () => {
        callCount++;
        return new Response(
          JSON.stringify([{ id: 1 }, { id: 2 }]),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      };

      const results = await fetchAllPaginated<{ id: number }>("/api/admin/simple-list");
      assert.strictEqual(results.length, 2);
      assert.strictEqual(callCount, 1, "Must terminate after single request if no pagination meta");
    });
  });
});

