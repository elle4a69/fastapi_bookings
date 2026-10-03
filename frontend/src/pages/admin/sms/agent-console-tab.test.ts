// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from "node:assert/strict";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import fs from "node:fs";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import path from "node:path";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from "node:test";
// @ts-expect-error Node types are intentionally not part of the app build.
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const componentPath = path.join(__dirname, "agent-console-tab.tsx");

test("coding worker status panel contains no fabricated activity or command controls", () => {
  const content = fs.readFileSync(componentPath, "utf-8");

  assert.match(content, /data-testid="coding-worker-unavailable"/);
  assert.match(content, /No coding worker is available from this screen\./);
  assert.equal(content.includes("setInterval("), false);
  assert.equal(content.includes("INITIAL_LOGS"), false);
  assert.equal(content.includes("Simulated agent turn completed successfully"), false);
  assert.equal(content.includes("Command injected into agent runner"), false);
  assert.equal(content.includes("handleInjectCommand"), false);
});
