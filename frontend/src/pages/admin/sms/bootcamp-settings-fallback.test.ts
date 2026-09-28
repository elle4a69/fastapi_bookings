// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from "node:test";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from "node:assert/strict";
// @ts-expect-error Node types are intentionally not part of the app build.
import fs from "node:fs";
// @ts-expect-error Node types are intentionally not part of the app build.
import path from "node:path";
// @ts-expect-error Node types are intentionally not part of the app build.
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const source = fs.readFileSync(path.join(__dirname, "bootcamp-settings-tab.tsx"), "utf-8");

test("Bootcamp settings normalizes incomplete style profiles before rendering", () => {
  assert.match(source, /export function normalizeBootcampSettings/);
  assert.match(source, /active_profile:\s*\{\s*\.\.\.DEFAULT_STYLE_PROFILE/s);
  assert.match(source, /setSettings\(normalizedSettings\)/);
});

test("Bootcamp style preview safely falls back when profiles are absent", () => {
  assert.match(source, /settings\?\.active_profile \?\? DEFAULT_STYLE_PROFILE/);
  assert.match(source, /activeProfile\?\.\[key\] \?\? 0/);
  assert.match(source, /previousProfile\?\.\[key\] \?\? null/);
});
