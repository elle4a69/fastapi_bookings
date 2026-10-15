// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from "node:test";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from "node:assert/strict";
import { COLOR_THEMES, isValidColorTheme } from "./theme-constants.ts";

test("COLOR_THEMES includes Logto Violet with correct brand tokens", () => {
  const logtoTheme = COLOR_THEMES.find((t) => t.id === "logto");
  assert.ok(logtoTheme, "Logto theme should be defined in COLOR_THEMES");
  assert.equal(logtoTheme!.name, "Logto Violet");
  assert.equal(logtoTheme!.description, "Electric Purple & Obsidian Dark");
  assert.equal(logtoTheme!.previewColor, "#6c47ff");
});

test("COLOR_THEMES contains all 4 supported luxury color themes", () => {
  const ids = COLOR_THEMES.map((t) => t.id);
  assert.deepEqual(ids, ["midnight", "emerald", "crimson", "logto"]);
});

test("isValidColorTheme properly validates stored theme values including logto", () => {
  assert.equal(isValidColorTheme("logto"), true);
  assert.equal(isValidColorTheme("midnight"), true);
  assert.equal(isValidColorTheme("emerald"), true);
  assert.equal(isValidColorTheme("crimson"), true);
  assert.equal(isValidColorTheme("random-theme"), false);
  assert.equal(isValidColorTheme(null), false);
  assert.equal(isValidColorTheme(""), false);
});
