// @ts-expect-error Node.js test runner module
import { describe, it, beforeEach } from "node:test";
// @ts-expect-error Node.js assert module
import assert from "node:assert/strict";
import {
  ApiError,
  getActiveTenant,
  getAdminToken,
  loginAdmin,
  setAdminToken,
} from "../../lib/api.ts";

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
 * Pure state machine / handler simulation of LoginPage (src/pages/login.tsx):
 */
interface LoginFormState {
  company: string;
  login: string;
  password: string;
  rememberMe: boolean;
}

interface LoginSubmitResult {
  success: boolean;
  errorMessage: string | null;
  navigatedTo?: string;
}

async function simulateLoginSubmit(
  formState: LoginFormState,
  locationState?: { from?: { pathname?: string } }
): Promise<LoginSubmitResult> {
  const { company, login, password, rememberMe } = formState;

  // Validation step 1: login check
  if (!login.trim()) {
    return {
      success: false,
      errorMessage: "Please enter your username or email address.",
    };
  }

  // Validation step 2: password check
  if (!password) {
    return {
      success: false,
      errorMessage: "Please enter your password.",
    };
  }

  try {
    const tenantToUse = company.trim() || getActiveTenant();
    await loginAdmin(
      {
        company: tenantToUse,
        login: login.trim(),
        password,
      },
      rememberMe
    );

    const from = locationState?.from?.pathname || "/admin";
    return {
      success: true,
      errorMessage: null,
      navigatedTo: from,
    };
  } catch (err: unknown) {
    let msg = "An unexpected authentication error occurred.";
    if (err instanceof ApiError) {
      if (err.status === 401) {
        msg = "Incorrect credentials. Please verify your username and password.";
      } else if (err.status === 404) {
        msg = `Tenant '${company}' was not found.`;
      } else {
        msg = err.message || "Failed to authenticate. Please try again.";
      }
    } else if (err instanceof Error) {
      msg = err.message;
    }
    return {
      success: false,
      errorMessage: msg,
    };
  }
}

describe("LoginPage Workflow & State Machine (TEST-004)", () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    mockSessionStorage.clear();
    (globalThis as any).window.location.hostname = "simplydemo.localhost";
    (globalThis as any).window.location.href = "";
  });

  describe("Form Validation & Input Guarding", () => {
    it("rejects empty or whitespace-only login with friendly validation error", async () => {
      const result = await simulateLoginSubmit({
        company: "simplydemo",
        login: "   ",
        password: "securepassword",
        rememberMe: true,
      });

      assert.strictEqual(result.success, false);
      assert.strictEqual(result.errorMessage, "Please enter your username or email address.");
      assert.strictEqual(getAdminToken(), null);
    });

    it("rejects empty password with friendly validation error", async () => {
      const result = await simulateLoginSubmit({
        company: "simplydemo",
        login: "admin",
        password: "",
        rememberMe: true,
      });

      assert.strictEqual(result.success, false);
      assert.strictEqual(result.errorMessage, "Please enter your password.");
      assert.strictEqual(getAdminToken(), null);
    });
  });

  describe("Tenant Company & Remember Me Variations", () => {
    it("resolves default company from hostname when left blank", async () => {
      (globalThis as any).window.location.hostname = "mycompany.localhost";
      let capturedPayload: any = null;

      (globalThis as any).fetch = async (_url: string, init: RequestInit) => {
        capturedPayload = JSON.parse(init.body as string);
        return new Response(
          JSON.stringify({
            ok: true,
            data: { access_token: "tok-tenant-auto", token_type: "bearer" },
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      };

      const result = await simulateLoginSubmit({
        company: "",
        login: "admin",
        password: "secretpassword",
        rememberMe: true,
      });

      assert.strictEqual(result.success, true);
      assert.strictEqual(capturedPayload.company, "mycompany");
      assert.strictEqual(mockLocalStorage.getItem("token"), "tok-tenant-auto");
      assert.strictEqual(result.navigatedTo, "/admin");
    });

    it("stores token in sessionStorage when rememberMe is false", async () => {
      (globalThis as any).fetch = async () => {
        return new Response(
          JSON.stringify({
            ok: true,
            data: { access_token: "tok-session-only", token_type: "bearer" },
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      };

      const result = await simulateLoginSubmit({
        company: "simplydemo",
        login: "admin",
        password: "secretpassword",
        rememberMe: false,
      });

      assert.strictEqual(result.success, true);
      assert.strictEqual(mockSessionStorage.getItem("token"), "tok-session-only");
      assert.strictEqual(mockLocalStorage.getItem("token"), null);
      assert.strictEqual(getAdminToken(), "tok-session-only");
    });
  });

  describe("Navigation & Return Path Preserving", () => {
    it("navigates to location.state.from.pathname on successful login", async () => {
      (globalThis as any).fetch = async () => {
        return new Response(
          JSON.stringify({
            ok: true,
            data: { access_token: "tok-redirect", token_type: "bearer" },
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      };

      const result = await simulateLoginSubmit(
        {
          company: "simplydemo",
          login: "admin",
          password: "secretpassword",
          rememberMe: true,
        },
        { from: { pathname: "/admin/calendar" } }
      );

      assert.strictEqual(result.success, true);
      assert.strictEqual(result.navigatedTo, "/admin/calendar");
    });

    it("defaults navigation to /admin when no from state is present", async () => {
      (globalThis as any).fetch = async () => {
        return new Response(
          JSON.stringify({
            ok: true,
            data: { access_token: "tok-default-admin", token_type: "bearer" },
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      };

      const result = await simulateLoginSubmit({
        company: "simplydemo",
        login: "admin",
        password: "secretpassword",
        rememberMe: true,
      });

      assert.strictEqual(result.success, true);
      assert.strictEqual(result.navigatedTo, "/admin");
    });
  });

  describe("Error Code to Message Mapping", () => {
    it("maps 401 response to credentials error message", async () => {
      (globalThis as any).fetch = async () => {
        return new Response(
          JSON.stringify({ detail: "Unauthorized credentials" }),
          { status: 401, headers: { "content-type": "application/json" } }
        );
      };

      const result = await simulateLoginSubmit({
        company: "simplydemo",
        login: "admin",
        password: "badpassword",
        rememberMe: true,
      });

      assert.strictEqual(result.success, false);
      assert.strictEqual(
        result.errorMessage,
        "Incorrect credentials. Please verify your username and password."
      );
      assert.strictEqual(getAdminToken(), null);
    });

    it("maps 404 response to tenant not found message", async () => {
      (globalThis as any).fetch = async () => {
        return new Response(
          JSON.stringify({ detail: "Tenant missing" }),
          { status: 404, headers: { "content-type": "application/json" } }
        );
      };

      const result = await simulateLoginSubmit({
        company: "nonexistent-tenant",
        login: "admin",
        password: "secretpassword",
        rememberMe: true,
      });

      assert.strictEqual(result.success, false);
      assert.strictEqual(
        result.errorMessage,
        "Tenant 'nonexistent-tenant' was not found."
      );
    });

    it("maps 500 or general server error to API error message", async () => {
      (globalThis as any).fetch = async () => {
        return new Response(
          JSON.stringify({ detail: "Internal database failure" }),
          { status: 500, headers: { "content-type": "application/json" } }
        );
      };

      const result = await simulateLoginSubmit({
        company: "simplydemo",
        login: "admin",
        password: "secretpassword",
        rememberMe: true,
      });

      assert.strictEqual(result.success, false);
      assert.strictEqual(result.errorMessage, "Internal database failure");
    });
  });

  describe("Already Authenticated Redirection", () => {
    it("detects existing admin token and signals immediate redirect to /admin", () => {
      setAdminToken("pre-existing-token", true);
      assert.strictEqual(getAdminToken(), "pre-existing-token");

      // In login.tsx:
      // React.useEffect(() => {
      //   if (getAdminToken()) {
      //     navigate("/admin", { replace: true })
      //   }
      // }, [navigate])
      const shouldRedirect = Boolean(getAdminToken());
      assert.strictEqual(shouldRedirect, true);
    });
  });
});
