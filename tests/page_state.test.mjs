import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import {readFileSync} from "node:fs";

// Execute the exact page functions used by Runtime.evaluate against DOM doubles.
// These exercise message/draft state; they do not claim compatibility with live ChatGPT.
const source = readFileSync(new URL("../browser_extension/engine.mjs", import.meta.url), "utf8");
const functions = source.slice(source.indexOf("function preparePage("), source.indexOf("chrome.debugger.onEvent"));
function page({draft = "", existingImages = 0, inputs = 1, primaryMissing = false, fallbackCount = 1, hidden = false} = {}) {
  const model = {images: Array(existingImages).fill({}), users: []};
  model.button = {disabled: false, getAttribute: () => null, click: () => { model.clicks = (model.clicks || 0) + 1; }};
  const form = {
    querySelector: selector => selector === "img" ? model.images[0] : model.busy ? {} : null,
    querySelectorAll: selector => selector === "img" ? model.images : selector.startsWith("button[") ? [model.button] : [],
    addEventListener() {}, removeEventListener() {},
  };
  const editor = {isContentEditable: true, isConnected: true, innerText: draft,
    getClientRects: () => hidden ? [] : [{}],
    dispatchEvent: event => { model.paste = event; return true; },
    closest: () => form, focus: () => { document.activeElement = editor; }};
  const document = {
    documentElement: {}, activeElement: null,
    querySelectorAll: selector => {
      if (selector === "#prompt-textarea") return primaryMissing ? [] : [editor];
      if (selector.includes('[contenteditable="true"][role="textbox"]')) {
        return Array.from({length: fallbackCount}, (_, i) => i ? {...editor} : editor);
      }
      if (selector === 'input[type="file"]') return Array(inputs).fill({accept: "image/png"});
      if (selector === '[data-message-author-role="user"]') return model.users;
      throw new Error(`Unhandled test selector: ${selector}`);
    },
  };
  const window = {};
  const context = vm.createContext({document, window, location: {href: "https://chatgpt.com/c/test"},
    atob,
    File: class { constructor(parts, name, options) { this.parts = parts; this.name = name; this.type = options.type; } },
    DataTransfer: class { constructor() { this.files = []; this.items = {add: file => this.files.push(file)}; } },
    ClipboardEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
    MutationObserver: class { constructor(callback) { model.mutate = callback; } observe() {} disconnect() {} },
    setTimeout, clearTimeout});
  vm.runInContext(functions, context);
  return {model, window, editor, context,
    prepare: () => context.preparePage("job1", Date.now() + 10000),
    submit: () => context.submitInBackground("job1", Date.now() + 10000)};
}
test("drafts and existing attachments are refused before paste", () => {
  for (const options of [{draft: "my draft"}, {existingImages: 1}]) assert.throws(page(options).prepare);
});
test("paste uses the exact editor and preserves the screenshot identity", () => {
  const p = page({inputs: 0}); p.prepare();
  p.context.pasteScreenshot("job1", "gc_job1.png", btoa("test-png"));
  assert.equal(p.model.paste.type, "paste");
  assert.equal(p.model.paste.clipboardData.files[0].name, "gc_job1.png");
  assert.equal(p.model.paste.clipboardData.files[0].type, "image/png");
  assert.equal(p.window.__gamingCompanionJob.confirmation, undefined);
  assert.equal(p.context.document.activeElement, p.editor);
  p.window.__gamingCompanionJob.cleanup();
});
test("visible textbox works without the legacy id or a file input", () => {
  const p = page({primaryMissing: true, inputs: 0});
  assert.equal(p.prepare().ok, true);
  p.window.__gamingCompanionJob.cleanup();
});
test("missing, hidden and ambiguous editors report specific errors", () => {
  assert.throws(page({primaryMissing: true, fallbackCount: 0}).prepare, /No visible message input/);
  assert.throws(page({hidden: true}).prepare, /No visible message input/);
  assert.throws(page({primaryMissing: true, fallbackCount: 2}).prepare, /Found 2 possible/);
});
test("changing conversations prevents background Send", async () => {
  const p = page(); p.prepare();
  p.context.location.href = "https://chatgpt.com/c/other";
  assert.match((await p.submit()).error, /Conversation or draft changed/);
  assert.equal(p.model.clicks, undefined);
});
test("enabled Send is clicked once without focusing the editor", async () => {
  const p = page(); p.prepare();
  assert.equal((await p.submit()).triggered, true);
  assert.equal(p.model.clicks, 1);
  assert.equal(p.context.document.activeElement, null);
});
test("disabled Send waits for an actual DOM state change", async () => {
  const p = page(); p.prepare(); p.model.button.disabled = true;
  const result = p.submit();
  assert.equal(p.model.clicks, undefined);
  p.model.button.disabled = false;
  p.model.mutate(); p.model.mutate();
  assert.equal((await result).triggered, true);
  assert.equal(p.model.clicks, 1);
});
test("no system key events or window activation exist in the sending code", () => {
  for (const text of ["chrome.windows.update", "chrome.tabs.update", "Input.dispatchKeyEvent", "/press-enter", "data-message-author-role"]) {
    assert.equal(source.includes(text), false, text);
  }
});
