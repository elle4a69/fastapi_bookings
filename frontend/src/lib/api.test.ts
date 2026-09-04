// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict';
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test';

type StorageMock = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
};

const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
const originalLocalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
const originalFetch = globalThis.fetch;
let importSequence = 0;

function installBrowser(
  hostname: string,
  pathname = '/',
  storedToken: string | null = null,
): { storage: StorageMock; redirects: string[] } {
  const values = new Map<string, string>();
  if (storedToken) {
    values.set('token', storedToken);
  }

  const redirects: string[] = [];
  const storage: StorageMock = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  const location = {
    hostname,
    pathname,
    origin: `https://${hostname}`,
    replace: (target: string) => redirects.push(target),
  };

  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { location },
  });
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: storage,
  });

  return { storage, redirects };
}

async function loadApi() {
  importSequence += 1;
  return import(`./api.ts?test=${importSequence}`);
}

function response(status: number, body: unknown = { detail: 'test response' }): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'test response',
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

test.after(() => {
  if (originalWindow) {
    Object.defineProperty(globalThis, 'window', originalWindow);
  } else {
    Reflect.deleteProperty(globalThis, 'window');
  }
  if (originalLocalStorage) {
    Object.defineProperty(globalThis, 'localStorage', originalLocalStorage);
  } else {
    Reflect.deleteProperty(globalThis, 'localStorage');
  }
  globalThis.fetch = originalFetch;
});

test('recognizes only permitted tenant hostnames', { concurrency: false }, async () => {
  for (const [hostname, expectedTenant] of [
    ['tenant.localhost', 'tenant'],
    ['tenant.example.com', 'tenant'],
    ['localhost', null],
    ['example.com', null],
    ['127.0.0.1', null],
    ['api.example.com', null],
    ['tenant.run.app', null],
  ] as const) {
    installBrowser(hostname);
    const { getActiveTenantFromHost } = await loadApi();
    assert.equal(getActiveTenantFromHost(), expectedTenant, hostname);
  }
});

test('clears the retired mock admin token', { concurrency: false }, async () => {
  const { storage } = installBrowser('tenant.localhost', '/', 'mock-admin-token');
  const { getAdminAccessToken } = await loadApi();

  assert.equal(getAdminAccessToken(), null);
  assert.equal(storage.getItem('token'), null);
});

test('accepts only safe admin return paths', { concurrency: false }, async () => {
  installBrowser('tenant.localhost');
  const { safePostLoginReturnPath } = await loadApi();

  for (const pathname of ['/admin', '/admin/bookings', '/admin/settings/business'] as const) {
    assert.equal(safePostLoginReturnPath(pathname), pathname);
  }

  for (const pathname of [undefined, '', '/', '/administrator', '/admin?next=/book', '//example.com'] as const) {
    assert.equal(safePostLoginReturnPath(pathname), '/admin');
  }
});

test('ending an admin session clears the token and replaces the current route', { concurrency: false }, async () => {
  const { storage } = installBrowser('tenant.localhost', '/admin', 'test-token-only');
  const { endAdminSession } = await loadApi();
  const calls: Array<[string, { replace: true }]> = [];

  endAdminSession((path: string, options: { replace: true }) => calls.push([path, options]));

  assert.equal(storage.getItem('token'), null);
  assert.deepEqual(calls, [['/login', { replace: true }]]);
});

test('adds tenant and token headers only when each context is valid', { concurrency: false }, async () => {
  let capturedHeaders: Headers | undefined;
  globalThis.fetch = async (_input, init) => {
    capturedHeaders = new Headers(init?.headers);
    return response(200, { ok: true });
  };

  installBrowser('tenant.example.com', '/', 'test-token-only');
  const tenantApi = await loadApi();
  await tenantApi.apiClient.get('/test');
  assert.equal(capturedHeaders?.get('X-Tenant'), 'tenant');
  assert.equal(capturedHeaders?.get('X-Token'), 'test-token-only');

  installBrowser('example.com');
  const rootApi = await loadApi();
  await rootApi.apiClient.get('/test');
  assert.equal(capturedHeaders?.get('X-Tenant'), null);
  assert.equal(capturedHeaders?.get('X-Token'), null);
});

test('admin 401 clears the session and redirects to login', { concurrency: false }, async () => {
  const { storage, redirects } = installBrowser('tenant.localhost', '/admin/settings', 'test-token-only');
  globalThis.fetch = async () => response(401);
  const { apiClient } = await loadApi();

  await assert.rejects(apiClient.get('/protected'));
  assert.equal(storage.getItem('token'), null);
  assert.deepEqual(redirects, ['/login']);
});

test('public-path 401 leaves the session and location unchanged', { concurrency: false }, async () => {
  const { storage, redirects } = installBrowser('tenant.localhost', '/bookings', 'test-token-only');
  globalThis.fetch = async () => response(401);
  const { apiClient } = await loadApi();

  await assert.rejects(apiClient.get('/public'));
  assert.equal(storage.getItem('token'), 'test-token-only');
  assert.deepEqual(redirects, []);
});
