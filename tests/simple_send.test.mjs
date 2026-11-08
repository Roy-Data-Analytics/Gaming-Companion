import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import {readFileSync} from "node:fs";
import {UploadTracker} from "../browser_extension/upload_tracker.mjs";
import {pageError} from "../browser_extension/page_errors.mjs";

const source = readFileSync(new URL("../browser_extension/engine.mjs", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replace(/^export /gm, "");
async function scenario(failed = false) {
  const states = [], keys = [], commands = [];
  let onNetwork;
  const context = vm.createContext({UploadTracker, pageError, URL, AbortSignal, atob,
    setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {},
    chrome: {debugger: {
      onEvent: {addListener: callback => { onNetwork = callback; }},
      onDetach: {addListener() {}},
      sendCommand: async (target, method, params) => {
        commands.push(method);
        if (method === "Network.getResponseBody") return {body: JSON.stringify({file_id: "file-test", upload_url: "https://upload.invalid/test"})};
        if (method === "Input.dispatchKeyEvent") keys.push(params);
        if (method === "Runtime.evaluate") {
          if (params.expression.includes("function submitInBackground")) { commands.push("backgroundSend"); return {result: {value: {triggered: true}}}; }
          if (params.expression.includes("function pasteScreenshot")) {
            const emit = (name, data) => onNetwork({tabId: 1}, "Network." + name, data);
            emit("requestWillBeSent", {requestId: "meta", request: {url: "https://chatgpt.com/backend-api/files", method: "POST", postData: JSON.stringify({file_name: "gc_test.png"})}});
            emit("responseReceived", {requestId: "meta", response: {status: 200}});
            emit("loadingFinished", {requestId: "meta"});
            emit("requestWillBeSent", {requestId: "image", request: {url: "https://upload.invalid/test", method: "PUT"}});
            emit("responseReceived", {requestId: "image", response: {status: failed ? 500 : 201}});
            emit("loadingFinished", {requestId: "image"});
          }
          return {result: {value: true}};
        }
        return {};
      },
    }, tabs: {get: async () => ({url: "https://chatgpt.com/c/game", windowId: 10}),
      update: async () => { commands.push("activateTab"); }},
    windows: {update: async () => { commands.push("activateWindow"); }}},
    fetch: async (url, options) => {
      if (url.endsWith("/report")) states.push(JSON.parse(options.body).state);
      if (url.endsWith("/press-enter")) {
        throw new Error("Native keyboard must never be used");
      }
      return {ok: true, json: async () => ({ok: true})};
    },
  });
  vm.runInContext(source, context);
  vm.runInContext('target = {tabId: 1}; config = {url: "http://127.0.0.1:8765", token: "test"}; stopped = false;', context);
  await context.processJob({id: "test", filename: "gc_test.png", imageBase64: btoa("png"), deadline: Date.now() + 30000});
  return {states, keys, commands};
}
test("successful upload triggers background Send without activating windows or keyboard", async () => {
  const result = await scenario();
  assert.deepEqual(result.states.filter(state => state !== "UPLOADING"), ["ATTACHING", "UPLOAD_CONFIRMED", "SEND_TRIGGERED"]);
  assert.equal(result.commands.filter(command => command === "backgroundSend").length, 1);
  assert.equal(result.commands.includes("activateWindow"), false);
  assert.equal(result.commands.includes("activateTab"), false);
  assert.equal(result.keys.length, 0);
  assert.equal(result.commands.includes("Input.dispatchKeyEvent"), false);
  assert.equal(result.states.includes("SENT"), false);
});
test("failed upload never presses Enter", async () => {
  const result = await scenario(true);
  assert.equal(result.states.at(-1), "ERROR");
  assert.equal(result.keys.length, 0);
});
