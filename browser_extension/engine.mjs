import {UploadTracker} from "./upload_tracker.mjs";
import {pageError} from "./page_errors.mjs";

let config, target, session, active, stopped = true;
let heartbeat;
let runningLoop = false;
let stopRequested = false;
let title = "";
const logs = [];
let networkQueue = Promise.resolve();
function log(message) {
  logs.unshift(`${new Date().toLocaleTimeString()} ${message}`);
  logs.splice(60);
}
export function status() {
  return {running: runningLoop, connected: runningLoop && !stopped,
    tabId: target?.tabId, title, logs: [...logs]};
}
export function stop() {
  stopRequested = true;
  stopped = true;
  failActive("Disconnected; inspect any active screenshot before retrying");
}
async function api(path, body) {
  const response = await fetch(config.url + path, {
    method: "POST", headers: {"Content-Type": "application/json", Authorization: `Bearer ${config.token}`},
    body: JSON.stringify(body), signal: AbortSignal.timeout(22000),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Local bridge HTTP ${response.status}`);
  return data;
}
function command(method, params = {}) {
  if (!target) throw new Error("Browser disconnected");
  return chrome.debugger.sendCommand(target, method, params);
}
async function evaluate(expression, extra = {}) {
  const result = await command("Runtime.evaluate", {expression, returnByValue: true, ...extra});
  if (result.exceptionDetails) throw new Error(pageError(result.exceptionDetails));
  return result.result.value;
}
async function report(job, state, detail = "") {
  log(`${state}: ${detail}`);
  await api("/report", {session, id: job.id, state, detail});
}
function failActive(message) {
  if (!active) return;
  active.error = message;
  active.rejectUpload?.(new Error(message));
}

// Installed only in the selected top-level page, using the debugger transport.
// Locate the message input only; never inspect chat history or Send controls.
function preparePage(id, deadline) {
  const old = window.__gamingCompanionJob;
  if (old && !old.finished) throw new Error("Previous screenshot still active in page");
  old?.cleanup?.();
  const usable = node => {
    if (!(node.isContentEditable || node.tagName === "TEXTAREA")) return false;
    if (node.disabled || node.readOnly || node.getAttribute?.("aria-hidden") === "true") return false;
    if (node.getClientRects && node.getClientRects().length === 0) return false;
    return true;
  };
  let editors = [...document.querySelectorAll('#prompt-textarea')].filter(usable);
  if (editors.length === 0) {
    editors = [...new Set(document.querySelectorAll(
      '[contenteditable="true"][role="textbox"], .ProseMirror[contenteditable="true"], '
      + '[data-testid="composer"] [contenteditable="true"], '
      + '#thread-bottom-container [contenteditable="true"], '
      + 'textarea[placeholder], textarea[aria-label]'
    ))].filter(usable);
    // If nested nodes both qualify, use the editable root instead of counting twice.
    editors = editors.filter(node => !editors.some(other => other !== node && other.contains?.(node)));
  }
  if (editors.length === 0) throw new Error(
    "No visible message input in the selected tab. Open the text conversation; if Voice Mode hides the input, return to text chat first."
  );
  if (editors.length !== 1) throw new Error(
    `Found ${editors.length} possible message inputs. Close extra panels or select the correct conversation.`
  );
  const editor = editors[0];
  if (!(editor.isContentEditable || editor.tagName === "TEXTAREA")) throw new Error("Unsupported editor");
  const form = editor.closest("form")
    || editor.closest('[data-type="unified-composer"]')
    || editor.closest('[data-testid="composer"]')
    || editor.closest('#composer-background')
    || editor.closest('#thread-bottom-container');
  if (!form) throw new Error("Cannot identify the ChatGPT composer container (the page layout may have changed)");
  const text = () => (editor.value ?? editor.innerText ?? "").trim();
  if (text()) throw new Error("Input already contains text; keep this conversation's draft empty");
  if (form.querySelector("img") || form.querySelector('[role="progressbar"], [aria-busy="true"]')) {
    throw new Error("Composer already contains an attachment or active upload");
  }
  const state = {id, editor, form, url: location.href, finished: false, text};
  state.cleanup = () => { state.finished = true; };
  window.__gamingCompanionJob = state;
  return {ok: true};
}

function submitInBackground(id, deadline) {
  const state = window.__gamingCompanionJob;
  if (!state || state.id !== id || state.finished) throw new Error("Screenshot state expired");
  return new Promise(resolve => {
    let clicked = false;
    const finish = result => { observer.disconnect(); clearTimeout(timer); resolve(result); };
    const check = () => {
      if (clicked) return;
      if (location.href !== state.url || state.text()) {
        finish({error: "Conversation or draft changed before sending"});
        return;
      }
      const selectors = 'button[data-testid="send-button"], button#composer-submit-button, '
        + 'button[aria-label="Send prompt"], button[aria-label="Send message"], button[aria-label="Send"], '
        + 'button[aria-label="\u53d1\u9001"], button[aria-label="\u53d1\u9001\u6d88\u606f"], button[aria-label="\u53d1\u9001\u63d0\u793a"]';
      const candidates = [...new Set(state.form.querySelectorAll(selectors))]
        .filter(button => !button.getClientRects || button.getClientRects().length > 0);
      if (candidates.length !== 1) {
        finish({error: `Expected one Send control in this composer; found ${candidates.length}`});
        return;
      }
      const button = candidates[0];
      if (button.disabled || button.getAttribute("aria-disabled") === "true") return;
      // Page DOM action only: no mouse coordinates, key events, tab activation,
      // window focus, or voice-mode changes. Never click twice for the same task.
      clicked = true;
      try {
        button.click();
        finish({triggered: true});
      } catch (error) { finish({error: error.message}); }
    };
    const observer = new MutationObserver(check);
    observer.observe(state.form, {subtree: true, childList: true, attributes: true});
    const timer = setTimeout(() => finish({error: "Image uploaded, but the page kept its Send control disabled"}),
      Math.max(1, deadline - Date.now()));
    check();
  });
}

function pasteScreenshot(id, filename, imageBase64) {
  const state = window.__gamingCompanionJob;
  if (!state || state.id !== id || state.finished || !state.editor.isConnected) {
    throw new Error("Screenshot editor is no longer available");
  }
  if (location.href !== state.url || state.text()) throw new Error("Conversation or draft changed before image paste");
  const bytes = Uint8Array.from(atob(imageBase64), char => char.charCodeAt(0));
  const file = new File([bytes], filename, {type: "image/png"});
  const clipboard = new DataTransfer();
  clipboard.items.add(file);
  state.editor.focus();
  if (document.activeElement !== state.editor) throw new Error("Cannot focus editor for image paste");
  state.editor.dispatchEvent(new ClipboardEvent("paste", {
    bubbles: true, cancelable: true, composed: true, clipboardData: clipboard,
  }));
  // Event dispatch is only an attempt. Network correlation must confirm upload.
  return {attempted: true};
}

chrome.debugger.onEvent.addListener((source, method, params) => {
  if (!target || source.tabId !== target.tabId || !active) return;
  const job = active;
  networkQueue = networkQueue.then(async () => {
    if (active !== job || job.error) return;
    const tracker = job.tracker;
    if (method === "Network.requestWillBeSent") {
      const request = {...params.request};
      if (request.hasPostData && !request.postData && /\/backend-api\/files\/?(?:\?|$)/.test(request.url)) {
        try {
          request.postData = (await command("Network.getRequestPostData", {requestId: params.requestId})).postData;
        } catch { /* The tracker records an unavailable body instead of guessing. */ }
      }
      tracker.request(params.requestId, request);
    }
    if (method === "Network.responseReceived") tracker.response(params.requestId, params.response.status);
    if (method === "Network.loadingFailed") tracker.failed(params.requestId);
    if (method === "Network.loadingFinished") {
      let body;
      const request = tracker.requests.get(params.requestId);
      if (request?.metadata && request.status >= 200 && request.status < 300) {
        try {
          const response = await command("Network.getResponseBody", {requestId: params.requestId});
          body = JSON.parse(response.base64Encoded ? atob(response.body) : response.body);
        } catch {
          throw new Error("Cannot inspect the matching upload response; Enter was not authorized");
        }
      }
      tracker.complete(params.requestId, body);
    }
    if (tracker.ready) {
      job.uploadResolved = true;
      job.resolveUpload();
    }
    if (tracker.error) throw new Error(tracker.error);
    const summary = tracker.summary();
    if (job.uploadingReported && !job.uploadResolved && summary !== job.uploadSummary) {
      job.uploadSummary = summary;
      await report(job, "UPLOADING", summary);
    }
  }).catch(error => {
    if (active === job) failActive(error.message);
  });
});
chrome.debugger.onDetach.addListener(source => {
  if (source.tabId === target?.tabId) {
    failActive("Browser debugger disconnected; inspect chat before retrying");
    stopped = true;
    log("Browser disconnected; automatic reconnection is pending.");
  }
});

async function processJob(payload) {
  const fileSize = payload.imageBase64 ? Math.floor(payload.imageBase64.length * 3 / 4)
    - (payload.imageBase64.endsWith("==") ? 2 : payload.imageBase64.endsWith("=") ? 1 : 0) : null;
  const job = {...payload, tracker: new UploadTracker(payload.filename, fileSize)};
  active = job;
  let timer;
  let stage = "Page setup";
  const upload = new Promise((resolve, reject) => {
    job.resolveUpload = resolve;
    job.rejectUpload = reject;
    timer = setTimeout(() => failActive(`Upload not confirmed: ${job.tracker.summary()}`),
      Math.max(1, payload.deadline - Date.now()));
  });
  // Register a rejection handler immediately while file attachment commands run.
  upload.catch(() => {});
  try {
    const tab = await chrome.tabs.get(target.tabId);
    if (!["chatgpt.com", "chat.openai.com"].includes(new URL(tab.url).hostname)) {
      throw new Error("Selected tab is no longer ChatGPT");
    }
    await report(job, "ATTACHING", "Attaching one screenshot to the selected conversation");
    await evaluate(`(${preparePage.toString()})(${JSON.stringify(job.id)},${job.deadline})`);
    stage = "Image attachment";
    if (job.error) throw new Error(job.error);
    if (!job.imageBase64) throw new Error("Restart the desktop app to enable image paste support");
    await evaluate(`(${pasteScreenshot.toString()})(${JSON.stringify(job.id)},${JSON.stringify(job.filename)},${JSON.stringify(job.imageBase64)})`);
    await report(job, "UPLOADING", "Waiting for this image upload to complete");
    job.uploadingReported = true;
    stage = "Upload confirmation";
    await upload;
    job.uploadResolved = true;
    clearTimeout(timer);
    await report(job, "UPLOAD_CONFIRMED", "Matching file creation and successful image transfer confirmed");
    stage = "Send";
    if (stopped || job.error || Date.now() >= job.deadline) throw new Error(job.error || "Screenshot expired");
    const submitted = await evaluate(`(${submitInBackground.toString()})(${JSON.stringify(job.id)},${job.deadline})`, {awaitPromise: true});
    if (!submitted?.triggered) throw new Error(submitted?.error || "Background Send was not triggered");
    await report(job, "SEND_TRIGGERED", "Image uploaded; the page Send action was triggered in the background.");
  } catch (error) {
    const detail = `${stage}: ${error.message}`;
    await report(job, "ERROR", detail).catch(() => log(`ERROR: ${detail}`));
  } finally {
    clearTimeout(timer);
    await evaluate("window.__gamingCompanionJob?.cleanup?.()").catch(() => {});
    if (active === job) active = null;
  }
}

export async function start(savedConfig, tabId) {
  if (runningLoop) return;
  runningLoop = true;
  stopRequested = false;
  config = savedConfig;
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!["chatgpt.com", "chat.openai.com"].includes(new URL(tab.url).hostname)) throw new Error("Selected tab is not ChatGPT");
    title = tab.title;
    // Check the local app before attaching the debugger, avoiding banners while it is closed.
    session = (await api("/connect", {title: tab.title})).session;
    if (stopRequested) throw new Error("Connection cancelled");
    target = {tabId};
    await chrome.debugger.attach(target, "1.3");
    await command("Network.enable", {maxTotalBufferSize: 2000000, maxResourceBufferSize: 500000});
    if (stopRequested) throw new Error("Connection cancelled");
    stopped = false;
    heartbeat = setInterval(() => {
      api("/heartbeat", {session}).catch(() => {
        stopped = true;
        failActive("Local Python connection lost; inspect the chat before retrying");
      });
    }, 10000);
    log(`Connected: ${tab.title}`);
    while (!stopped) {
      const {job} = await api("/poll", {session});
      if (job && !stopped) await processJob(job);
    }
  } catch (error) { log(`Waiting to reconnect: ${error.message}`); }
  finally {
    stopped = true;
    clearInterval(heartbeat);
    if (target) await chrome.debugger.detach(target).catch(() => {});
    if (session) await api("/disconnect", {session}).catch(() => {});
    target = null;
    session = null;
    runningLoop = false;
  }
}
