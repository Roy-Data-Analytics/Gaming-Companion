import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import {readFileSync} from "node:fs";

const source = readFileSync(new URL("../browser_extension/background.js", import.meta.url), "utf8")
  .replace('import * as engine from "./engine.mjs";', "");
const pairing = {url: "http://127.0.0.1:8765", token: "a".repeat(43)};
async function run({missingFile = false, saved = {}, tabs = [], unauthorized = false} = {}) {
  const sent = [];
  const event = () => ({addListener() {}});
  const context = vm.createContext({
    engine: {status: () => ({running: false, connected: false}), stop() {}},
    chrome: {storage: {local: {get: async key => typeof key === "string" ? {[key]: saved[key]} : saved,
      set: async value => Object.assign(saved, value)}},
      tabs: {query: async () => tabs, onCreated: event(), onRemoved: event(), onUpdated: event()},
      alarms: {create: async () => {}, onAlarm: event()},
      runtime: {getURL: name => "chrome-extension://test/" + name, onInstalled: event(), onStartup: event(), onMessage: event()},
      action: {onClicked: event()}},
    crypto: {randomUUID: () => "test-browser"}, AbortSignal, console: {warn() {}},
    setInterval() {}, setTimeout() {},
    fetch: async (url, options) => {
      if (url.startsWith("chrome-extension:")) {
        if (missingFile) throw new Error("resource missing");
        return {ok: true, json: async () => pairing};
      }
      sent.push({url, data: JSON.parse(options.body)});
      return {ok: !unauthorized, json: async () => ({tabId: null})};
    },
  });
  vm.runInContext(source, context);
  await new Promise(setImmediate);
  return sent;
}
test("background startup reports ChatGPT windows before any manual connection", async () => {
  const sent = await run({tabs: [{id: 7, windowId: 3, title: "Game", url: "https://chatgpt.com/c/game"}]});
  const report = sent.find(item => item.url.endsWith("/browser-state"));
  assert.equal(report.data.tabs[0].id, 7);
  assert.equal(report.data.tabs[0].windowId, 3);
});
test("cached pairing recovers if private extension resource cannot be read", async () => {
  const sent = await run({missingFile: true, saved: {config: pairing}});
  assert.ok(sent.some(item => item.url.endsWith("/browser-state")));
});
test("pairing failure reports a diagnostic instead of silently showing no tabs", async () => {
  const sent = await run({missingFile: true});
  assert.match(sent.find(item => item.url.endsWith("/diagnostic")).data.message, /Cannot read local pairing/);
});
test("rejected handshake reports a diagnostic without leaking the token", async () => {
  const sent = await run({unauthorized: true});
  const diagnostic = sent.find(item => item.url.endsWith("/diagnostic"));
  assert.match(diagnostic.data.message, /pairing was not accepted/);
  assert.equal(JSON.stringify(diagnostic).includes(pairing.token), false);
});
