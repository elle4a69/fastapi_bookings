// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from "node:assert/strict";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import { readFile } from "node:fs/promises";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from "node:test";

const pageSource = await readFile(
  new URL("../pages/admin/sms-assistant.tsx", import.meta.url),
  "utf8",
);

const retiredPanelComponents = [
  "SmsInboxTab",
  "SmsAccountsTab",
  "SmsSettingsTab",
  "SmsSimulatorTab",
  "SmsDiagnosticsTab",
  "SmsChatwootTab",
] as const;

test("does not load or render retired local messaging panels", () => {
  assert.doesNotMatch(pageSource, /from\s+["']\.\/sms(?:\/|["'])/);

  for (const component of retiredPanelComponents) {
    assert.doesNotMatch(pageSource, new RegExp(`<\\s*${component}\\b`), component);
  }
});

test("does not introduce API or fetch effects on the containment page", () => {
  assert.doesNotMatch(pageSource, /from\s+["']@\/lib\/api["']/);
  assert.doesNotMatch(pageSource, /\bapiClient\b/);
  assert.doesNotMatch(pageSource, /\bfetch\s*\(/);
});

test("keeps the approved static containment notice visible", () => {
  assert.match(pageSource, /Staff messaging is managed in Chatwoot/);
  assert.match(
    pageSource,
    /FastAPI automated and\s+local outbound messaging remain disabled until the authenticated Chatwoot integration\s+packages are complete\./,
  );
});
