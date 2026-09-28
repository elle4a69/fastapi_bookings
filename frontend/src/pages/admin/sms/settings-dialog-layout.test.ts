// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from "node:test";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from "node:assert/strict";
import {
  KNOWLEDGE_EDITOR_CLASS,
  PROMPT_EDITOR_CLASS,
  SMS_SETTINGS_DIALOG_BODY_CLASS,
  SMS_SETTINGS_DIALOG_CLASS,
} from "./settings-dialog-layout.ts";

test("SMS settings dialogs stay desktop-wide and viewport-bounded", () => {
  assert.match(SMS_SETTINGS_DIALOG_CLASS, /sm:max-w-4xl/);
  assert.match(SMS_SETTINGS_DIALOG_CLASS, /max-h-\[calc\(100dvh-2rem\)\]/);
  assert.match(SMS_SETTINGS_DIALOG_BODY_CLASS, /overflow-y-auto/);
});

test("SMS settings editors use fixed-size, scrollable, vertically resizable textareas", () => {
  for (const editorClass of [KNOWLEDGE_EDITOR_CLASS, PROMPT_EDITOR_CLASS]) {
    assert.match(editorClass, /field-sizing-fixed/);
    assert.match(editorClass, /overflow-y-auto/);
    assert.match(editorClass, /resize-y/);
    assert.match(editorClass, /max-h-\[50vh\]/);
  }
});
