import * as engine from "./engine.mjs";

let syncing = false;
let note = "Waiting for the desktop app";
async function reconcile() {
  if (syncing) return;
  syncing = true;
  try {
    let {browserId} = await chrome.storage.local.get("browserId");
    if (!browserId) {
      browserId = crypto.randomUUID();
      await chrome.storage.local.set({browserId});
    }
    // This private file is written by the desktop app. It is not web-accessible.
    let config;
    try {
      const pairing = await fetch(chrome.runtime.getURL("local_pairing.json"), {cache: "no-store"});
      if (!pairing.ok) throw new Error("Private pairing resource is unavailable");
      config = await pairing.json();
      await chrome.storage.local.set({config});
    } catch {
      config = (await chrome.storage.local.get("config")).config;
      if (!config) throw new Error("Cannot read local pairing. Start the desktop app, then reload the extension once.");
    }
    if (config.url !== "http://127.0.0.1:8765" || !/^[A-Za-z0-9_-]{40,}$/.test(config.token)) throw new Error("Invalid local pairing");
    const tabs = await chrome.tabs.query({url: ["https://chatgpt.com/*", "https://chat.openai.com/*"]});
    const state = engine.status();
    const response = await fetch(config.url + "/browser-state", {
      method: "POST", headers: {"Content-Type": "application/json", Authorization: `Bearer ${config.token}`},
      body: JSON.stringify({browserId, tabs: tabs.map(tab => ({id: tab.id, windowId: tab.windowId,
        title: tab.title, url: tab.url})), selected: state.connected ? state.tabId : null, detail: note}),
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) throw new Error("Desktop pairing was not accepted");
    const wanted = await response.json();
    if (state.running) {
      if (state.tabId !== undefined && wanted.tabId !== state.tabId) engine.stop();
      return;
    }
    if (!wanted.tabId) { note = "Select a ChatGPT window in the desktop app"; return; }
    note = "Connecting to the selected ChatGPT window";
    engine.start(config, wanted.tabId).finally(() => {
      note = "Waiting to reconnect to the selected ChatGPT window";
      setTimeout(reconcile, 500);
    });
  } catch (error) {
    note = error.message;
    console.warn("Gaming Companion discovery:", note);
    // Never include a pairing token, request headers, or signed URL in diagnostics.
    await fetch("http://127.0.0.1:8765/diagnostic", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: note}), signal: AbortSignal.timeout(2000),
    }).catch(() => {});
  }
  finally { syncing = false; }
}
async function ensureAlarm() {
  await chrome.alarms.create("reconnect", {periodInMinutes: 0.5});
  await reconcile();
}
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === "reconnect") reconcile(); });
chrome.runtime.onInstalled.addListener(ensureAlarm);
chrome.runtime.onStartup.addListener(ensureAlarm);
chrome.tabs.onCreated.addListener(() => reconcile());
chrome.tabs.onRemoved.addListener(() => reconcile());
chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.status === "complete" || change.url) reconcile();
});
chrome.action.onClicked.addListener(() => {
  chrome.action.setTitle({title: "Select the ChatGPT window in Gaming Companion on your desktop"});
  reconcile();
});
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id === chrome.runtime.id && message.type === "STATUS") {
    respond({...engine.status(), note});
  }
});
// Inventory polling also receives desktop window-selection changes. It never
// authorizes screenshot submission; the upload state machine still does that.
setInterval(reconcile, 2000);
ensureAlarm();
