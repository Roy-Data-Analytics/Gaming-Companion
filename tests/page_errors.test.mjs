import test from "node:test";
import assert from "node:assert/strict";
import {pageError} from "../browser_extension/page_errors.mjs";

test("CDP Uncaught preserves the real page error without a stack dump", () => {
  assert.equal(pageError({text: "Uncaught", exception: {
    description: "Error: Cannot identify exactly one attachment file input\n    at preparePage"
  }}), "Cannot identify exactly one attachment file input");
});
test("exception value and protocol text remain usable", () => {
  assert.equal(pageError({text: "Uncaught", exception: {value: "draft not empty"}}), "draft not empty");
  assert.equal(pageError({text: "Execution context was destroyed"}), "Execution context was destroyed");
});
