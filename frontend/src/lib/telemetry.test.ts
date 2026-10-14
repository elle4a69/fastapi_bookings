// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict';
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test';

import { initFrontendTelemetry, isBrowserExtensionSource } from './telemetry.ts';

test('isBrowserExtensionSource detects extension schemas and content scripts', () => {
  assert.equal(isBrowserExtensionSource('chrome-extension://abcdef/content.js'), true);
  assert.equal(isBrowserExtensionSource('moz-extension://1234-5678/inject.js'), true);
  assert.equal(isBrowserExtensionSource('safari-web-extension://9876/bundle.js'), true);
  assert.equal(isBrowserExtensionSource('https://example.com/contentScript.js'), true);
  assert.equal(isBrowserExtensionSource('Error: fail\n    at eval (chrome-extension://foo/bar.js:10:5)'), true);

  assert.equal(isBrowserExtensionSource(''), false);
  assert.equal(isBrowserExtensionSource(null), false);
  assert.equal(isBrowserExtensionSource(undefined), false);
  assert.equal(isBrowserExtensionSource('https://example.com/assets/index-B123.js'), false);
  assert.equal(isBrowserExtensionSource('/src/components/Calendar.tsx'), false);
});

test('initFrontendTelemetry filters out browser extension errors and rejections', () => {
  type Listener = (event: unknown) => void;
  const listeners: Record<string, Listener[]> = {
    error: [],
    unhandledrejection: [],
  };

  const requests: { url: string; body: unknown }[] = [];

  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;

  // Setup fake window and fetch
  const fakeWindow = {
    location: { pathname: '/admin/bookings' },
    addEventListener: (type: string, listener: Listener) => {
      listeners[type]?.push(listener);
    },
  };

  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: fakeWindow,
  });

  globalThis.fetch = (async (url: string, init?: { body?: string }) => {
    requests.push({
      url,
      body: init?.body ? JSON.parse(init.body) : null,
    });
    return { ok: true } as Response;
  }) as unknown as typeof fetch;

  try {
    initFrontendTelemetry();

    assert.equal(listeners.error.length, 1);
    assert.equal(listeners.unhandledrejection.length, 1);

    const errorHandler = listeners.error[0];
    const rejectionHandler = listeners.unhandledrejection[0];

    // 1. Valid app error should be dispatched
    requests.length = 0;
    errorHandler({
      filename: 'https://example.com/assets/app.js',
      error: new Error('App crash'),
    });
    assert.equal(requests.length, 1);
    assert.equal((requests[0].body as { event_type: string }).event_type, 'js_error');

    // 2. Chrome extension error filtered
    requests.length = 0;
    errorHandler({
      filename: 'chrome-extension://invalid-id/page.js',
      error: new Error('Extension error'),
    });
    assert.equal(requests.length, 0);

    // 3. Firefox extension error filtered
    requests.length = 0;
    errorHandler({
      filename: 'moz-extension://invalid-id/bundle.js',
      error: new Error('Extension error'),
    });
    assert.equal(requests.length, 0);

    // 4. Safari extension error filtered
    requests.length = 0;
    errorHandler({
      filename: 'safari-web-extension://invalid-id/bar.js',
      error: new Error('Extension error'),
    });
    assert.equal(requests.length, 0);

    // 5. contentScript filename filtered
    requests.length = 0;
    errorHandler({
      filename: 'https://cdn.thirdparty.com/contentScript-bundle.js',
      error: new Error('Extension content script error'),
    });
    assert.equal(requests.length, 0);

    // 6. Stack trace originating in chrome-extension filtered
    requests.length = 0;
    const extensionStackError = new Error('Injected failure');
    extensionStackError.stack = 'Error: Injected failure\n    at chrome-extension://bad/helper.js:12:4';
    errorHandler({
      filename: '',
      error: extensionStackError,
    });
    assert.equal(requests.length, 0);

    // 7. Legitimate unhandled rejection dispatched
    requests.length = 0;
    rejectionHandler({
      reason: new Error('API failure'),
    });
    assert.equal(requests.length, 1);
    assert.equal((requests[0].body as { event_type: string }).event_type, 'unhandled_rejection');

    // 8. Extension unhandled rejection filtered by stack
    requests.length = 0;
    const extRejectionError = new Error('Extension rejected');
    extRejectionError.stack = 'Error: Extension rejected\n    at moz-extension://uuid/contentScript.js:4:1';
    rejectionHandler({
      reason: extRejectionError,
    });
    assert.equal(requests.length, 0);

    // 9. Extension unhandled rejection filtered by string reason
    requests.length = 0;
    rejectionHandler({
      reason: 'Failed to execute chrome-extension://xyz background task',
    });
    assert.equal(requests.length, 0);
  } finally {
    if (originalWindow !== undefined) {
      Object.defineProperty(globalThis, 'window', {
        configurable: true,
        value: originalWindow,
      });
    } else {
      delete (globalThis as { window?: unknown }).window;
    }
    globalThis.fetch = originalFetch;
  }
});
