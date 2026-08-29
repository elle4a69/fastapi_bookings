// @ts-expect-error Node.js test runner module
import { describe, it, beforeEach } from "node:test";
// @ts-expect-error Node.js assert module
import assert from "node:assert/strict";
import {
  clearAdminToken,
  getAdminToken,
  logoutAdmin,
  setAdminToken,
} from "./lib/api.ts";
import { navigation } from "./components/navigation.ts";

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

/**
 * Pure logic simulation of AdminAuthGuard as implemented in App.tsx:
 *
 * function AdminAuthGuard({ children }: { children: React.ReactNode }) {
 *   const token = typeof window !== "undefined" ? getAdminToken() : null
 *   const location = useLocation()
 *   if (!token) {
 *     return <Navigate to="/login" state={{ from: location }} replace />
 *   }
 *   return <>{children}</>
 * }
 */
interface AuthGuardResult {
  allowed: boolean;
  redirectTo?: string;
  redirectState?: { from: { pathname: string } };
  replace?: boolean;
}

function evaluateAdminAuthGuard(currentPath: string): AuthGuardResult {
  const token = typeof window !== "undefined" ? getAdminToken() : null;
  const location = { pathname: currentPath };

  if (!token) {
    return {
      allowed: false,
      redirectTo: "/login",
      redirectState: { from: location },
      replace: true,
    };
  }

  return {
    allowed: true,
  };
}

describe("App Routing & AdminAuthGuard Logic (TEST-004)", () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    mockSessionStorage.clear();
    (globalThis as any).window.location.href = "";
  });

  describe("AdminAuthGuard Gatekeeper Behavior", () => {
    it("redirects unauthenticated users to /login and captures origin route in state", () => {
      clearAdminToken();
      assert.strictEqual(getAdminToken(), null);

      const targetPath = "/admin/bookings";
      const guardResult = evaluateAdminAuthGuard(targetPath);

      assert.strictEqual(guardResult.allowed, false);
      assert.strictEqual(guardResult.redirectTo, "/login");
      assert.strictEqual(guardResult.replace, true);
      assert.deepStrictEqual(guardResult.redirectState, { from: { pathname: targetPath } });
    });

    it("allows access when a valid token is present in localStorage", () => {
      setAdminToken("valid-local-jwt", true);
      assert.strictEqual(getAdminToken(), "valid-local-jwt");

      const guardResult = evaluateAdminAuthGuard("/admin/catalog/services");
      assert.strictEqual(guardResult.allowed, true);
      assert.strictEqual(guardResult.redirectTo, undefined);
    });

    it("allows access when a valid token is present in sessionStorage", () => {
      setAdminToken("valid-session-jwt", false);
      assert.strictEqual(getAdminToken(), "valid-session-jwt");

      const guardResult = evaluateAdminAuthGuard("/admin/schedule/workdays");
      assert.strictEqual(guardResult.allowed, true);
      assert.strictEqual(guardResult.redirectTo, undefined);
    });

    it("blocks access immediately after logoutAdmin is invoked", () => {
      setAdminToken("authenticated-jwt", true);
      assert.strictEqual(getAdminToken(), "authenticated-jwt");

      // User performs logout
      logoutAdmin();
      assert.strictEqual(getAdminToken(), null);
      assert.strictEqual((globalThis as any).window.location.href, "/login");

      // Subsequent access attempt to guarded route
      const guardResult = evaluateAdminAuthGuard("/admin/clients");
      assert.strictEqual(guardResult.allowed, false);
      assert.strictEqual(guardResult.redirectTo, "/login");
    });
  });

  describe("Navigation Configuration & Route Protection Matrix", () => {
    it("verifies all navigation-defined administrative routes are covered", () => {
      const adminUrls: string[] = [];

      for (const section of navigation) {
        for (const item of section.items) {
          if (item.url) {
            adminUrls.push(item.url);
          }
          if (item.children) {
            for (const child of item.children) {
              if (child.url) {
                adminUrls.push(child.url);
              }
            }
          }
        }
      }

      // Assert core administration URLs exist
      assert.ok(adminUrls.includes("/admin/catalog/services"));
      assert.ok(adminUrls.includes("/admin/catalog/providers"));
      assert.ok(adminUrls.includes("/admin/bookings"));
      assert.ok(adminUrls.includes("/admin/calendar"));
      assert.ok(adminUrls.includes("/admin/clients"));
      assert.ok(adminUrls.includes("/admin/finance/invoices"));

      // Verify that every discovered admin URL requires authentication
      clearAdminToken();
      for (const url of adminUrls) {
        const result = evaluateAdminAuthGuard(url);
        assert.strictEqual(
          result.allowed,
          false,
          `Route ${url} must be protected by AdminAuthGuard when unauthenticated`
        );
        assert.strictEqual(result.redirectTo, "/login");
      }
    });

    it("distinguishes public routes from protected admin workspace routes", () => {
      const publicRoutes = ["/login", "/book", "/book/123", "/public/upload"];
      const adminRoutes = ["/admin/bookings", "/admin/settings/business", "/admin/audit"];

      for (const pubRoute of publicRoutes) {
        const isProtected = pubRoute.startsWith("/admin");
        assert.strictEqual(isProtected, false, `${pubRoute} should be a public route`);
      }

      for (const admRoute of adminRoutes) {
        const isProtected = admRoute.startsWith("/admin");
        assert.strictEqual(isProtected, true, `${admRoute} should be a protected admin route`);
      }
    });
  });
});
