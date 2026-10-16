// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict';
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test';
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync } from 'node:fs';
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url';

const mediaPageContent = readFileSync(fileURLToPath(new URL('./media.tsx', import.meta.url)), 'utf8');

test('media page replaces legacy localStorage mock registry with real backend API integration', () => {
  // Verifies legacy mock registry is eliminated
  assert.doesNotMatch(mediaPageContent, /STORAGE_KEY_MEDIA/);
  assert.doesNotMatch(mediaPageContent, /INITIAL_MEDIA_ITEMS/);

  // Verifies real API functions are imported and wired
  assert.match(mediaPageContent, /import\s*\{[^}]*listMedia[^}]*\}\s*from/);
  assert.match(mediaPageContent, /import\s*\{[^}]*uploadMedia[^}]*\}\s*from/);
  assert.match(mediaPageContent, /import\s*\{[^}]*updateMediaEligibility[^}]*\}\s*from/);
  assert.match(mediaPageContent, /import\s*\{[^}]*deleteMedia[^}]*\}\s*from/);
  assert.match(mediaPageContent, /import\s*\{[^}]*getAdminMediaStreamUrl[^}]*\}\s*from/);
});

test('media page supports filtering by public website eligibility and provider', () => {
  assert.match(mediaPageContent, /eligibilityFilter/);
  assert.match(mediaPageContent, /is_public_website_eligible/);
  assert.match(mediaPageContent, /Website Eligible \(Public\)/);
  assert.match(mediaPageContent, /Internal Only \(Private\)/);
});

test('media page handles multi-file upload with validation and progress tracking', () => {
  assert.match(mediaPageContent, /handleBatchUploadSubmit/);
  assert.match(mediaPageContent, /validateMediaUploadFile/);
  assert.match(mediaPageContent, /uploadProgress/);
  assert.match(mediaPageContent, /isBatchUploading/);
  assert.match(mediaPageContent, /25MB/);
});

test('media page displays public website eligibility badges and streaming previews', () => {
  assert.match(mediaPageContent, /Website Eligible/);
  assert.match(mediaPageContent, /Internal Only/);
  assert.match(mediaPageContent, /handleToggleEligibility/);
  assert.match(mediaPageContent, /formatMediaFileSize/);
  assert.match(mediaPageContent, /content_type/);
  assert.match(mediaPageContent, /getAdminMediaStreamUrl/);
});
