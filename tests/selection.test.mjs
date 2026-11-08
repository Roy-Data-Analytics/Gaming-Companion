import test from "node:test";
import assert from "node:assert/strict";
import {chooseTab} from "../browser_extension/selection.mjs";

const a = {id: 1, url: "https://chatgpt.com/c/a"};
const b = {id: 2, url: "https://chatgpt.com/c/b"};
test("restored conversation is selected even if tab id changes", () => {
  const restored = {...a, id: 99};
  assert.equal(chooseTab([b, restored], a.url), restored);
});
test("only one open ChatGPT tab connects without manual selection", () => {
  assert.equal(chooseTab([a], null), a);
  assert.equal(chooseTab([a], b.url), a);
});
test("multiple or duplicate conversations never guess a target", () => {
  assert.equal(chooseTab([a, b], null), null);
  assert.equal(chooseTab([a, {...a, id: 3}], a.url), null);
});
test("other websites, closed tabs, and malformed URLs are ignored", () => {
  assert.equal(chooseTab([{id: 1, url: "https://example.com"}, {id: 2}], null), null);
  assert.equal(chooseTab([], a.url), null);
});
