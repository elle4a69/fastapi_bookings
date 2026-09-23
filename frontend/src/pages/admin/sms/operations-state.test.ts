// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from "node:assert/strict";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from "node:test";

import {
  compareConversationOrder,
  conversationStatePresentation,
  getOrCreateManualSendAttempt,
  isAutomationReleaseAllowed,
  matchesConversationFilter,
  shouldApplyConversationResponse,
  type ConversationOperationsState,
} from "./operations-state.ts";

const baseConversation: ConversationOperationsState = {
  id: 1,
  state: "auto-reply",
  ai_enabled: true,
  is_pinned: false,
  customer_address: "synthetic-contact",
  client_name: "Synthetic Client",
  last_activity_at: "2026-09-24T02:00:00Z",
};

test("operations filters distinguish automatic, review, and human takeover states", () => {
  assert.equal(matchesConversationFilter(baseConversation, "automatic", ""), true);
  assert.equal(matchesConversationFilter(baseConversation, "takeover", ""), false);

  const reviewConversation = { ...baseConversation, state: "needs-review", ai_enabled: false };
  assert.equal(matchesConversationFilter(reviewConversation, "review", ""), true);

  const takeoverConversation = { ...baseConversation, state: "taken-over", ai_enabled: false };
  assert.equal(matchesConversationFilter(takeoverConversation, "automatic", ""), false);
  assert.equal(matchesConversationFilter(takeoverConversation, "takeover", ""), true);

  const escalatedConversation = { ...baseConversation, state: "escalated", ai_enabled: false };
  assert.equal(matchesConversationFilter(escalatedConversation, "escalated", ""), true);
  assert.equal(matchesConversationFilter(escalatedConversation, "automatic", ""), false);
});

test("search matches tenant-authorized list data without changing state filtering", () => {
  assert.equal(matchesConversationFilter(baseConversation, "all", "synthetic client"), true);
  assert.equal(matchesConversationFilter(baseConversation, "all", "contact"), true);
  assert.equal(matchesConversationFilter(baseConversation, "all", "missing"), false);
});

test("pinned conversations sort before newer unpinned conversations", () => {
  const pinned = { ...baseConversation, id: 2, is_pinned: true, last_activity_at: "2026-09-24T01:00:00Z" };
  const newer = { ...baseConversation, id: 3, last_activity_at: "2026-09-24T03:00:00Z" };
  assert.equal(compareConversationOrder(pinned, newer) < 0, true);
  assert.equal(compareConversationOrder(newer, pinned) > 0, true);
});

test("automation cannot resume from blocked, review, escalated, or resolved states", () => {
  assert.equal(isAutomationReleaseAllowed({ ...baseConversation, state: "paused", is_blocked: false }), true);
  assert.equal(isAutomationReleaseAllowed({ ...baseConversation, state: "taken-over", is_blocked: false }), true);
  assert.equal(isAutomationReleaseAllowed({ ...baseConversation, state: "paused", is_blocked: true }), false);
  assert.equal(isAutomationReleaseAllowed({ ...baseConversation, state: "paused", needs_review: true }), false);
  assert.equal(isAutomationReleaseAllowed({ ...baseConversation, state: "needs-review", is_blocked: false }), false);
  assert.equal(isAutomationReleaseAllowed({ ...baseConversation, state: "escalated", is_blocked: false }), false);
  assert.equal(isAutomationReleaseAllowed({ ...baseConversation, state: "resolved", is_blocked: false }), false);
});

test("state presentation never labels paused or review conversations as automatic", () => {
  assert.deepEqual(conversationStatePresentation(baseConversation), { label: "Automatic", tone: "automatic" });
  assert.deepEqual(
    conversationStatePresentation({ ...baseConversation, state: "needs-review", ai_enabled: false }),
    { label: "Needs review", tone: "review" },
  );
  assert.deepEqual(
    conversationStatePresentation({ ...baseConversation, state: "paused", ai_enabled: false, needs_review: true }),
    { label: "Needs review", tone: "review" },
  );
  assert.deepEqual(
    conversationStatePresentation({ ...baseConversation, state: "paused", ai_enabled: false }),
    { label: "AI paused", tone: "manual" },
  );
});

test("manual-send retries reuse one idempotency key and changed attempts receive a new key", () => {
  const first = getOrCreateManualSendAttempt(null, 1, "Hello", () => "attempt-0001");
  const retry = getOrCreateManualSendAttempt(first, 1, "Hello", () => "attempt-0002");
  const edited = getOrCreateManualSendAttempt(first, 1, "Hello again", () => "attempt-0002");
  assert.equal(retry.clientRequestId, "attempt-0001");
  assert.equal(edited.clientRequestId, "attempt-0002");
});

test("stale conversation responses cannot replace the currently selected thread", () => {
  assert.equal(shouldApplyConversationResponse(1, 1, 4, 4), true);
  assert.equal(shouldApplyConversationResponse(1, 2, 4, 4), false);
  assert.equal(shouldApplyConversationResponse(1, 1, 3, 4), false);
});
