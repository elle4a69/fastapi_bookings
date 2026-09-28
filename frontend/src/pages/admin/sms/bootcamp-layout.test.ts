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

test("Bootcamp component does not include the hardcoded warmth prefix", () => {
  const filePath = path.join(__dirname, "assistant-bootcamp-page.tsx");
  const content = fs.readFileSync(filePath, "utf-8");

  // Ensure 'We really care about taking great care of you!' is nowhere in the file
  assert.equal(
    content.includes("We really care about taking great care of you!"),
    false,
    "Hardcoded warmth prefix should be completely removed"
  );
});

test("Bootcamp left column controls use compact vertical layout and theme tokens", () => {
  const filePath = path.join(__dirname, "assistant-bootcamp-page.tsx");
  const content = fs.readFileSync(filePath, "utf-8");

  // Turns per thread is compact inline row
  assert.match(content, /Turns\/Thread:\s*<span className="font-mono font-bold text-primary">/);

  // Autonomy level uses segmented L1 Review, L2 Semi, L3 Full buttons
  assert.match(content, /L1 Review/);
  assert.match(content, /L2 Semi/);
  assert.match(content, /L3 Full/);

  // Primary theme tokens used instead of hardcoded indigo
  assert.equal(
    content.includes("accent-indigo-600"),
    false,
    "Should use accent-primary instead of accent-indigo-600"
  );
  assert.match(content, /accent-primary/);
  assert.match(content, /text-primary/);
});

test("AI correction dialog permits saving when ideal wording is provided and uses primary theme tokens", () => {
  const threadPanelPath = path.join(__dirname, "assistant-thread-panel.tsx");
  const threadContent = fs.readFileSync(threadPanelPath, "utf-8");

  // Disabled check supports either reason or wording
  assert.match(
    threadContent,
    /disabled=\{\(!correctionReason\.trim\(\) && !correctedWording\.trim\(\)\) \|\| submittingCorrection\}/,
    "Save Correction button must be enabled when either reason or corrected wording is provided"
  );

  // Fallback reason when omitted
  assert.match(
    threadContent,
    /const finalReason = correctionReason\.trim\(\) \|\| "Manual response correction"/,
    "Should provide a fallback reason if reason is omitted"
  );

  // Button uses theme tokens
  assert.match(
    threadContent,
    /bg-primary hover:bg-primary\/90/,
    "Save Correction button should use primary theme tokens"
  );

  const bootcampPath = path.join(__dirname, "assistant-bootcamp-page.tsx");
  const bootcampContent = fs.readFileSync(bootcampPath, "utf-8");

  // Robust ID matching with String coercion
  assert.match(
    bootcampContent,
    /String\(m\.id\) === String\(target\.messageId\)/,
    "Message ID matching must use string coercion to handle number/string ID mismatches"
  );
});
