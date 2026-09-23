// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from "node:assert/strict";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from "node:test";

import {
  compareConversationOrder,
  matchesConversationFilter,
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

  const reviewConversation = { ...baseConversation, needs_review: true };
  assert.equal(matchesConversationFilter(reviewConversation, "review", ""), true);

  const takeoverConversation = { ...baseConversation, state: "taken-over", ai_enabled: false };
  assert.equal(matchesConversationFilter(takeoverConversation, "automatic", ""), false);
  assert.equal(matchesConversationFilter(takeoverConversation, "takeover", ""), true);
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
