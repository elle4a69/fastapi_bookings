// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict';
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test';

import {
  validateMediaUploadFile,
  formatMediaFileSize,
  getAdminMediaStreamUrl,
  ALLOWED_MIME_TYPES,
  MAX_FILE_SIZE_BYTES,
  listMedia,
  uploadMedia,
  updateMediaEligibility,
  deleteMedia,
} from './media.ts';

const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
const originalLocalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
const originalFetch = globalThis.fetch;

function setupBrowserEnvironment(hostname = 'tenant.localhost', token = 'test-admin-token') {
  const values = new Map<string, string>();
  if (token) {
    values.set('token', token);
  }

  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  };

  const location = {
    hostname,
    pathname: '/admin/media',
    origin: `https://${hostname}`,
    replace: () => {},
  };

  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { location },
  });
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: storage,
  });
}

function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
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

test('media file size formatting', () => {
  assert.equal(formatMediaFileSize(500), '500 B');
  assert.equal(formatMediaFileSize(1024), '1.0 KB');
  assert.equal(formatMediaFileSize(1024 * 512), '512.0 KB');
  assert.equal(formatMediaFileSize(1024 * 1024 * 3.5), '3.5 MB');
});

test('media upload validation rejects invalid files and enforces 25MB limit', () => {
  // @ts-expect-error testing null input
  const nullCheck = validateMediaUploadFile(null);
  assert.equal(nullCheck.valid, false);

  const oversizedFile = {
    name: 'giant_video.mp4',
    size: MAX_FILE_SIZE_BYTES + 1024,
    type: 'video/mp4',
  } as File;
  const oversizedCheck = validateMediaUploadFile(oversizedFile);
  assert.equal(oversizedCheck.valid, false);
  assert.match(oversizedCheck.error ?? '', /exceeds the 25MB limit/);

  const forbiddenFile = {
    name: 'malicious.exe',
    size: 1024,
    type: 'application/x-msdownload',
  } as File;
  const forbiddenCheck = validateMediaUploadFile(forbiddenFile);
  assert.equal(forbiddenCheck.valid, false);
  assert.match(forbiddenCheck.error ?? '', /is not supported/);

  for (const mime of ALLOWED_MIME_TYPES) {
    const validFile = {
      name: 'sample_asset',
      size: 1024 * 1024 * 2,
      type: mime,
    } as File;
    const check = validateMediaUploadFile(validFile);
    assert.equal(check.valid, true, `MIME ${mime} should be accepted`);
  }
});

test('getAdminMediaStreamUrl generates correct streaming URL', () => {
  assert.equal(getAdminMediaStreamUrl(42), '/api/admin/media/42/file');
});

test('listMedia calls backend with eligibility and provider filters', { concurrency: false }, async () => {
  setupBrowserEnvironment();

  let capturedUrl = '';
  let capturedHeaders: Headers | undefined;

  globalThis.fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedHeaders = new Headers(init?.headers);
    return mockResponse(200, {
      ok: true,
      data: [
        {
          id: 1,
          tenant_id: 1,
          provider_id: 2,
          filename: 'test.jpg',
          file_path: 'tenant_1/test.jpg',
          url: '/api/public/media/1/test.jpg',
          content_type: 'image/jpeg',
          file_size: 1024,
          title: 'Test Photo',
          description: null,
          alt_text: null,
          media_type: 'image',
          is_public_website_eligible: true,
          notes: null,
          created_at: '2026-10-08T00:00:00Z',
          updated_at: '2026-10-08T00:00:00Z',
        },
      ],
      total: 1,
    });
  };

  const res = await listMedia({
    is_public_website_eligible: true,
    provider_id: 2,
    limit: 25,
    offset: 0,
  });

  assert.equal(res.ok, true);
  assert.equal(res.total, 1);
  assert.equal(res.data[0].id, 1);
  assert.match(capturedUrl, /\/api\/admin\/media/);
  assert.match(capturedUrl, /is_public_website_eligible=true/);
  assert.match(capturedUrl, /provider_id=2/);
  assert.match(capturedUrl, /limit=25/);
  assert.equal(capturedHeaders?.get('X-Token'), 'test-admin-token');
});

test('uploadMedia sends multipart/form-data and receives created item', { concurrency: false }, async () => {
  setupBrowserEnvironment();

  let capturedMethod = '';
  let capturedUrl = '';
  let capturedBody: any = null;

  globalThis.fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedMethod = init?.method ?? 'GET';
    capturedBody = init?.body;
    return mockResponse(201, {
      ok: true,
      data: {
        id: 10,
        tenant_id: 1,
        provider_id: 3,
        filename: 'upload_test.png',
        file_path: 'tenant_1/upload_test.png',
        url: '/api/public/media/1/upload_test.png',
        content_type: 'image/png',
        file_size: 2048,
        title: 'New Clinic Photo',
        description: 'Front desk reception area',
        alt_text: null,
        media_type: 'image',
        is_public_website_eligible: true,
        notes: 'Confidential interior notes',
        created_at: '2026-10-08T01:00:00Z',
        updated_at: '2026-10-08T01:00:00Z',
      },
    });
  };

  const testFile = new File(['dummy png data'], 'upload_test.png', { type: 'image/png' });

  const res = await uploadMedia({
    file: testFile,
    title: 'New Clinic Photo',
    description: 'Front desk reception area',
    notes: 'Confidential interior notes',
    provider_id: 3,
    is_public_website_eligible: true,
  });

  assert.equal(res.ok, true);
  assert.equal(res.data.id, 10);
  assert.equal(capturedMethod, 'POST');
  assert.match(capturedUrl, /\/api\/admin\/media\/upload/);
  assert.ok(capturedBody instanceof FormData);
  assert.equal(capturedBody.get('title'), 'New Clinic Photo');
  assert.equal(capturedBody.get('provider_id'), '3');
  assert.equal(capturedBody.get('is_public_website_eligible'), 'true');
});

test('updateMediaEligibility updates public website eligibility state', { concurrency: false }, async () => {
  setupBrowserEnvironment();

  let capturedMethod = '';
  let capturedUrl = '';
  let capturedBody: any = null;

  globalThis.fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedMethod = init?.method ?? 'GET';
    capturedBody = JSON.parse(String(init?.body));
    return mockResponse(200, {
      ok: true,
      data: {
        id: 7,
        tenant_id: 1,
        provider_id: null,
        filename: 'studio.jpg',
        file_path: 'tenant_1/studio.jpg',
        url: '/api/public/media/1/studio.jpg',
        content_type: 'image/jpeg',
        file_size: 5000,
        title: 'Studio',
        description: null,
        alt_text: null,
        media_type: 'image',
        is_public_website_eligible: true,
        notes: null,
        created_at: '2026-10-08T00:00:00Z',
        updated_at: '2026-10-08T01:00:00Z',
      },
    });
  };

  const res = await updateMediaEligibility(7, true);

  assert.equal(res.ok, true);
  assert.equal(res.data.is_public_website_eligible, true);
  assert.equal(capturedMethod, 'PATCH');
  assert.match(capturedUrl, /\/api\/admin\/media\/7\/eligibility/);
  assert.deepEqual(capturedBody, { is_public_website_eligible: true });
});

test('deleteMedia removes media asset from backend storage', { concurrency: false }, async () => {
  setupBrowserEnvironment();

  let capturedMethod = '';
  let capturedUrl = '';

  globalThis.fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedMethod = init?.method ?? 'GET';
    return mockResponse(200, {
      ok: true,
      message: 'Media item deleted successfully.',
      id: 15,
    });
  };

  const res = await deleteMedia(15);

  assert.equal(res.ok, true);
  assert.equal(res.id, 15);
  assert.equal(capturedMethod, 'DELETE');
  assert.match(capturedUrl, /\/api\/admin\/media\/15/);
});

test('deleteMedia throws ApiError when media item is not found', { concurrency: false }, async () => {
  setupBrowserEnvironment();

  globalThis.fetch = async () =>
    mockResponse(404, {
      detail: 'Media item 999 not found.',
    });

  await assert.rejects(deleteMedia(999), /Media item 999 not found/);
});
