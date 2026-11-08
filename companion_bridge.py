"""Authenticated loopback transport for the locally installed browser extension.

No browser credentials or HTTP upload bodies are persisted. Deadlines only abort;
they never authorize Enter. A job is delivered at most once.
"""
from __future__ import annotations

import json
import base64
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class Job:
    payload: dict
    session: str
    delivered: bool = False
    done: threading.Event = field(default_factory=threading.Event)
    state: str = "QUEUED"
    detail: str = ""


class BrowserBridge:
    def __init__(self, folder, port=8765):
        self.folder = Path(folder)
        self.token = secrets.token_urlsafe(32)
        self.port = port
        self.condition = threading.Condition()
        self.session = None
        self.last_seen = 0.0
        self.tab_title = ""
        self.job = None
        self.server = None
        self.browsers = {}
        self.selected_target = None
        self.extension_diagnostic = None
        target_file = self.folder / "browser_target.json"
        if target_file.exists():
            self.selected_target = json.loads(target_file.read_text(encoding="utf-8"))

    def browser_sync(self, browser_id, tabs, selected_tab=None, detail=""):
        with self.condition:
            clean = []
            for tab in tabs[:100]:
                url = str(tab.get("url", ""))
                if urlparse(url).hostname not in {"chatgpt.com", "chat.openai.com"}:
                    continue
                clean.append({"id": int(tab["id"]), "windowId": int(tab.get("windowId", 0)),
                              "title": str(tab.get("title", "ChatGPT"))[:200], "url": url[:2000]})
            self.browsers[browser_id] = {"tabs": clean, "seen": time.monotonic(),
                                          "selected": selected_tab, "detail": str(detail)[:500]}
            wanted = self.selected_target
            if not wanted or wanted["browserId"] != browser_id:
                return {"tabId": None}
            live = next((tab for tab in clean if tab["id"] == selected_tab == wanted.get("tabId")), None)
            if live and self.connected and live["url"] != wanted["url"]:
                wanted.update(url=live["url"], title=live["title"])
                (self.folder / "browser_target.json").write_text(json.dumps(wanted), encoding="utf-8")
            matches = [tab for tab in clean if tab["url"] == wanted["url"]]
            exact = [tab for tab in matches if tab["id"] == wanted.get("tabId")]
            chosen = exact[0] if exact else matches[0] if len(matches) == 1 else None
            return {"tabId": chosen["id"] if chosen else None}

    def available_tabs(self):
        with self.condition:
            return [{**tab, "browserId": browser_id} for browser_id, browser in self.browsers.items()
                    if time.monotonic() - browser["seen"] < 15 for tab in browser["tabs"]]

    def discovery_status(self):
        with self.condition:
            fresh = [browser for browser in self.browsers.values() if time.monotonic() - browser["seen"] < 15]
            if fresh:
                count = sum(len(browser["tabs"]) for browser in fresh)
                return (f"{count} ChatGPT tab(s) available. Select one and click Connect." if count else
                        "Browser extension connected, but no ChatGPT tabs were found in that browser profile. Open ChatGPT in the profile with the extension installed.")
            if self.extension_diagnostic and time.monotonic() - self.extension_diagnostic[0] < 20:
                return "Browser connection error: " + self.extension_diagnostic[1]
            return "No browser extension connection yet. Reload Gaming Companion Bridge in Extensions, then keep ChatGPT open. This is a connection issue, not a window search result."

    def select_target(self, browser_id, tab_id):
        with self.condition:
            if self.job and not self.job.done.is_set():
                raise ValueError("Finish the current screenshot before switching conversations")
            matches = [tab for tab in self.available_tabs()
                       if tab["browserId"] == browser_id and tab["id"] == tab_id]
            if len(matches) != 1:
                raise ValueError("This ChatGPT tab is no longer available. Refresh the list")
            tab = matches[0]
            self.selected_target = {"browserId": browser_id, "tabId": tab_id, "url": tab["url"], "title": tab["title"]}
            (self.folder / "browser_target.json").write_text(json.dumps(self.selected_target), encoding="utf-8")
            # Invalidate the old session before allowing a screenshot in the new one.
            self.disconnect(self.session)
            return tab["title"]

    @property
    def connected(self):
        with self.condition:
            return self.session is not None and time.monotonic() - self.last_seen < 35

    def connect(self, title):
        with self.condition:
            if self.job and not self.job.done.is_set():
                raise ValueError("A screenshot is active; finish or cancel it first")
            self.session = uuid.uuid4().hex
            self.tab_title = str(title)[:200]
            self.last_seen = time.monotonic()
            self.condition.notify_all()
            return self.session

    def poll(self, session):
        with self.condition:
            if session != self.session:
                raise ValueError("Session expired; reconnect the extension")
            self.last_seen = time.monotonic()
            self.condition.wait_for(
                lambda: self.session != session or (
                    self.job and not self.job.delivered and not self.job.done.is_set()
                ), timeout=15,
            )
            if session != self.session:
                raise ValueError("Session disconnected")
            self.last_seen = time.monotonic()
            job = self.job
            if job and not job.delivered and not job.done.is_set():
                job.delivered = True
                return job.payload
            return None

    def report(self, session, job_id, state, detail=""):
        allowed = {"ATTACHING", "UPLOADING", "UPLOAD_CONFIRMED", "SEND_TRIGGERED", "ENTER_SENT", "SENT", "ERROR"}
        with self.condition:
            job = self.job
            if session != self.session or not job or job.payload["id"] != job_id:
                raise ValueError("Unknown session or screenshot")
            self.last_seen = time.monotonic()
            if job.done.is_set():
                return
            if state not in allowed:
                raise ValueError("Unknown screenshot state")
            next_state = {
                "QUEUED": "ATTACHING", "ATTACHING": "UPLOADING",
                "UPLOADING": "UPLOAD_CONFIRMED", "UPLOAD_CONFIRMED": "ENTER_SENT",
                "ENTER_SENT": "SENT",
            }
            if state != "ERROR" and not (state == job.state == "UPLOADING") and not (job.state == "UPLOAD_CONFIRMED" and state == "SEND_TRIGGERED") and next_state.get(job.state) != state:
                raise ValueError("Invalid screenshot state transition")
            job.state, job.detail = state, str(detail)[:500]
            print(f"Browser bridge: {state} {job.detail}")
            if state in {"SEND_TRIGGERED", "ENTER_SENT", "SENT", "ERROR"}:
                job.done.set()
            self.condition.notify_all()

    def heartbeat(self, session):
        with self.condition:
            if session != self.session:
                raise ValueError("Session expired")
            self.last_seen = time.monotonic()

    def submit(self, image, callback=None, timeout=150):
        with self.condition:
            if not self.connected:
                raise RuntimeError("Waiting for ChatGPT auto-connect; ensure ChatGPT is open and the extension is paired")
            if self.job and not self.job.done.is_set():
                raise RuntimeError("Another screenshot is still active")
            job_id = uuid.uuid4().hex
            outbox = self.folder / "debug" / "outbox"
            outbox.mkdir(parents=True, exist_ok=True)
            path = outbox / f"gc_{job_id}.png"
            image.save(path, "PNG")
            self.job = job = Job({
                "id": job_id, "path": str(path.resolve()), "filename": path.name,
                "imageBase64": base64.b64encode(path.read_bytes()).decode("ascii"),
                "deadline": int((time.time() + timeout - 5) * 1000),
            }, self.session)
            self.condition.notify_all()
        # Event.wait is interrupted by reports; elapsed time never means success.
        deadline = time.monotonic() + timeout
        previous = None
        while not job.done.is_set() and time.monotonic() < deadline:
            with self.condition:
                snapshot = (job.state, job.detail)
                if snapshot != previous:
                    if callback:
                        callback(*snapshot)
                    previous = snapshot
                self.condition.wait(timeout=min(1, max(0, deadline - time.monotonic())))
        if not job.done.is_set():
            with self.condition:
                job.state = "ERROR"
                job.detail = "Browser confirmation timed out; do not resend until you inspect the chat"
                job.done.set()
            raise RuntimeError(job.detail)
        if job.state not in {"SEND_TRIGGERED", "ENTER_SENT", "SENT"}:
            raise RuntimeError(job.detail or "Image upload or Enter action failed")
        # The upload completed and Enter was pressed. Chat history is not inspected.
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # Cleanup failure must not turn a confirmed send into a retry prompt.
            print("Upload completed and Enter pressed; temporary image cleanup was unsuccessful")
        return job.payload["id"]

    def disconnect(self, session):
        with self.condition:
            if session == self.session:
                if self.job and not self.job.done.is_set():
                    self.job.state, self.job.detail = "ERROR", "Extension disconnected; inspect chat before retrying"
                    self.job.done.set()
                self.session = None
                self.condition.notify_all()

    def start(self):
        pairing = self.folder / "browser_bridge_pairing.json"
        if pairing.exists():
            saved = json.loads(pairing.read_text(encoding="utf-8"))
            token = saved.get("token", "")
            if not isinstance(token, str) or len(token) < 40:
                raise ValueError("Invalid browser pairing file; restore it or pair again")
            self.token = token
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, data):
                body = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_POST(self):
                # Diagnostics cannot select targets, retrieve data, or authorize sends.
                # They remain usable when the pairing handshake itself has failed.
                if self.path == "/diagnostic":
                    try:
                        origin = self.headers.get("Origin", "")
                        if not origin.startswith("chrome-extension://"):
                            self.reply(403, {"error": "Extension origin required"})
                            return
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 < length <= 2048:
                            raise ValueError("Invalid diagnostic size")
                        data = json.loads(self.rfile.read(length))
                        with bridge.condition:
                            bridge.extension_diagnostic = (time.monotonic(), str(data["message"])[:500])
                        self.reply(200, {"ok": True})
                    except (ValueError, KeyError, TypeError):
                        self.reply(400, {"error": "Invalid diagnostic"})
                    return
                if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + bridge.token):
                    self.reply(401, {"error": "Pairing required"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 16384:
                        raise ValueError("Invalid request size")
                    data = json.loads(self.rfile.read(length))
                    if self.path == "/connect":
                        self.reply(200, {"session": bridge.connect(data.get("title", "ChatGPT"))})
                    elif self.path == "/poll":
                        self.reply(200, {"job": bridge.poll(data["session"])})
                    elif self.path == "/report":
                        bridge.report(data["session"], data["id"], data["state"], data.get("detail", ""))
                        self.reply(200, {"ok": True})
                    elif self.path == "/disconnect":
                        bridge.disconnect(data["session"])
                        self.reply(200, {"ok": True})
                    elif self.path == "/heartbeat":
                        bridge.heartbeat(data["session"])
                        self.reply(200, {"ok": True})
                    elif self.path == "/browser-state":
                        self.reply(200, bridge.browser_sync(data["browserId"], data.get("tabs", []),
                                                           data.get("selected"), data.get("detail", "")))
                    else:
                        self.reply(404, {"error": "Unknown operation"})
                except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                    self.reply(400, {"error": str(exc)})

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        pairing.write_text(json.dumps({
            "url": f"http://127.0.0.1:{self.port}", "token": self.token,
        }, indent=2), encoding="utf-8")
        # Private extension resource: no webpage access and no file picker required.
        extension = self.folder / "browser_extension"
        if extension.is_dir():
            (extension / "local_pairing.json").write_text(pairing.read_text(encoding="utf-8"), encoding="utf-8")
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print(f"Browser bridge listening on 127.0.0.1:{self.port}; pairing file: {pairing}")

    def close(self):
        self.disconnect(self.session)
        if self.server:
            self.server.shutdown()
            self.server.server_close()
