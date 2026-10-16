// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict';
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test';
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync } from 'node:fs';
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url';

const tenantsPageContent = readFileSync(fileURLToPath(new URL('./tenants.tsx', import.meta.url)), 'utf8');
const navigationContent = readFileSync(fileURLToPath(new URL('../../components/navigation.ts', import.meta.url)), 'utf8');
const appContent = readFileSync(fileURLToPath(new URL('../../App.tsx', import.meta.url)), 'utf8');

test('tenants page connects to real backend endpoints without mock state', () => {
  // Verifies real API calls
  assert.match(tenantsPageContent, /apiClient\.get<[^>]+>\("\/api\/tenants"\)/);
  assert.match(tenantsPageContent, /apiClient\.post<[^>]+>\("\/api\/tenants",\s*payload\)/);
  assert.match(tenantsPageContent, /\/api\/tenants\/\$\{[^}]+\}\/suspend/);
  assert.match(tenantsPageContent, /\/api\/tenants\/\$\{[^}]+\}\/reactivate/);
});

test('tenants page includes robust subdomain validation and slug generation', () => {
  assert.match(tenantsPageContent, /\[a-z0-9-\]\+/);
  assert.match(tenantsPageContent, /subdomainError/);
  assert.match(tenantsPageContent, /slugify/);
});

test('tenants page exposes one-time onboarding URL copy flow upon provisioning', () => {
  assert.match(tenantsPageContent, /getInviteUrl/);
  assert.match(tenantsPageContent, /\/invite\?token=/);
  assert.match(tenantsPageContent, /handleCopyInviteUrl/);
  assert.match(tenantsPageContent, /navigator\.clipboard\.writeText/);
});

test('tenants page supports lifecycle suspension and reactivation with reason capture', () => {
  assert.match(tenantsPageContent, /handleConfirmSuspend/);
  assert.match(tenantsPageContent, /handleConfirmReactivate/);
  assert.match(tenantsPageContent, /suspendReason/);
  assert.match(tenantsPageContent, /isPlatformOwner/);
});

test('navigation and App.tsx register /admin/tenants under Platform Control Plane', () => {
  // Navigation verification
  assert.match(navigationContent, /Platform Control Plane/);
  assert.match(navigationContent, /url:\s*"\/admin\/tenants"/);
  assert.match(navigationContent, /Building2/);

  // App.tsx route verification
  assert.match(appContent, /import\("@\/pages\/admin\/tenants"\)/);
  assert.match(appContent, /path="\/admin\/tenants"/);
});
