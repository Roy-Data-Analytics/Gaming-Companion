import ast
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from companion_bridge import BrowserBridge


class FakeImage:
    def save(self, path, format):
        Path(path).write_bytes(b"test-png")


class BridgeTests(unittest.TestCase):
    def setUp(self):
        # Keep test artifacts inside the writable project workspace.
        self.tmp = tempfile.TemporaryDirectory(prefix="bridge_test_", dir=Path(__file__).parent)
        self.bridge = BrowserBridge(self.tmp.name, port=0)
        self.bridge.start()
        self.url = f"http://127.0.0.1:{self.bridge.port}"

    def tearDown(self):
        self.bridge.close()
        self.tmp.cleanup()

    def post(self, route, body, token=None):
        request = urllib.request.Request(self.url + route,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + (token or self.bridge.token)})
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.load(response)

    def start_job(self, timeout=2):
        result = {}
        def run():
            try:
                result["id"] = self.bridge.submit(FakeImage(), timeout=timeout)
            except RuntimeError as error:
                result["error"] = str(error)
        thread = threading.Thread(target=run)
        thread.start()
        return thread, result

    def test_auth_required(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.post("/connect", {}, token="wrong")
        self.assertEqual(raised.exception.code, 401)

    def test_restart_preserves_pairing_token_but_creates_new_session(self):
        token = self.bridge.token
        old_session = self.bridge.connect("test")
        self.bridge.close()
        self.bridge = BrowserBridge(self.tmp.name, port=0)
        self.bridge.start()
        self.assertEqual(self.bridge.token, token)
        self.assertNotEqual(self.bridge.connect("test"), old_session)
        with self.assertRaises(ValueError):
            self.bridge.poll(old_session)

    def test_desktop_selection_routes_to_exact_browser_and_tab(self):
        tabs = [{"id": 1, "windowId": 10, "title": "Game A", "url": "https://chatgpt.com/c/a"},
                {"id": 2, "windowId": 20, "title": "Game B", "url": "https://chatgpt.com/c/b"}]
        self.assertIsNone(self.bridge.browser_sync("browser-one", tabs)["tabId"])
        self.bridge.browser_sync("browser-two", tabs)
        self.assertEqual(len(self.bridge.available_tabs()), 4)
        self.bridge.select_target("browser-one", 2)
        self.assertEqual(self.bridge.browser_sync("browser-one", tabs)["tabId"], 2)
        self.assertIsNone(self.bridge.browser_sync("browser-two", tabs)["tabId"])

    def test_discovery_distinguishes_no_connection_from_no_tabs(self):
        self.assertIn("No browser extension connection", self.bridge.discovery_status())
        self.bridge.browser_sync("browser", [])
        self.assertIn("extension connected, but no ChatGPT tabs", self.bridge.discovery_status())

    def test_private_extension_pairing_is_written_without_file_import(self):
        extension = Path(self.tmp.name) / "browser_extension"
        extension.mkdir()
        self.bridge.close()
        self.bridge = BrowserBridge(self.tmp.name, port=0)
        self.bridge.start()
        saved = json.loads((extension / "local_pairing.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["token"], self.bridge.token)
        self.assertEqual(saved["url"], f"http://127.0.0.1:{self.bridge.port}")

    def test_window_switch_invalidates_old_session_and_restores_selection(self):
        tabs = [{"id": 1, "title": "A", "url": "https://chatgpt.com/c/a"},
                {"id": 2, "title": "B", "url": "https://chatgpt.com/c/b"}]
        self.bridge.browser_sync("browser", tabs)
        self.bridge.select_target("browser", 1)
        old_session = self.bridge.connect("A")
        self.bridge.select_target("browser", 2)
        with self.assertRaises(ValueError):
            self.bridge.poll(old_session)
        restored = BrowserBridge(self.tmp.name, port=0)
        self.assertEqual(restored.browser_sync("browser", [{**tabs[1], "id": 99}])["tabId"], 99)

    def test_active_screenshot_prevents_switching(self):
        session = self.bridge.connect("test")
        self.bridge.browser_sync("browser", [{"id": 1, "url": "https://chatgpt.com/c/a"}])
        thread, result = self.start_job()
        job = self.bridge.poll(session)
        with self.assertRaisesRegex(ValueError, "Finish the current screenshot"):
            self.bridge.select_target("browser", 1)
        self.bridge.report(session, job["id"], "ERROR", "test cancelled")
        thread.join(2)

    def test_ui_and_extension_fixed_text_are_english(self):
        import re
        paths = [Path("ScreenShot_StableCore.py"), Path("browser_picker.py"), *Path("browser_extension").glob("*.js"),
                 *Path("browser_extension").glob("*.mjs"), Path("browser_extension/control.html")]
        for path in paths:
            self.assertIsNone(re.search(r"[\u4e00-\u9fff]", path.read_text(encoding="utf-8")), str(path))

    def test_success_requires_all_states_and_cleans_only_confirmed_file(self):
        session = self.post("/connect", {"title": "test"})["session"]
        thread, result = self.start_job()
        job = self.post("/poll", {"session": session})["job"]
        self.assertTrue(Path(job["path"]).exists())
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/report", {"session": session, "id": job["id"], "state": "SENT"})
        for state in ["ATTACHING", "UPLOADING", "UPLOAD_CONFIRMED", "ENTER_SENT", "SENT"]:
            self.post("/report", {"session": session, "id": job["id"], "state": state})
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result["id"], job["id"])
        self.assertFalse(Path(job["path"]).exists())

    def test_timeout_never_means_success_and_preserves_image(self):
        session = self.bridge.connect("test")
        thread, result = self.start_job(timeout=.15)
        job = self.bridge.poll(session)
        thread.join(2)
        self.assertIn("timed out", result["error"])
        self.assertTrue(Path(job["path"]).exists())
        self.assertTrue(self.bridge.job.delivered)
        self.assertEqual(self.bridge.job.state, "ERROR")

    def test_disconnect_aborts_without_success(self):
        session = self.bridge.connect("test")
        thread, result = self.start_job()
        job = self.bridge.poll(session)
        self.bridge.disconnect(session)
        thread.join(2)
        self.assertIn("disconnected", result["error"])
        self.assertTrue(Path(job["path"]).exists())

    def test_unconnected_submit_and_stale_session_are_rejected(self):
        with self.assertRaises(RuntimeError):
            self.bridge.submit(FakeImage())
        with self.assertRaises(ValueError):
            self.bridge.poll("stale")

    def test_second_trigger_does_not_deliver_duplicate(self):
        session = self.bridge.connect("test")
        thread, result = self.start_job()
        job = self.bridge.poll(session)
        with self.assertRaises(RuntimeError):
            self.bridge.submit(FakeImage())
        self.bridge.report(session, job["id"], "ERROR", "test cancelled")
        thread.join(2)
        self.assertIn("test cancelled", result["error"])

    def test_background_send_finishes_task_without_chat_history_confirmation(self):
        session = self.bridge.connect("test")
        thread, result = self.start_job()
        job = self.bridge.poll(session)
        for state in ["ATTACHING", "UPLOADING", "UPLOAD_CONFIRMED", "SEND_TRIGGERED"]:
            self.bridge.report(session, job["id"], state)
        thread.join(2)
        self.assertEqual(result["id"], job["id"])
        self.assertTrue(self.bridge.job.done.is_set())

    def test_main_uses_bridge_and_has_no_legacy_sending(self):
        source = Path("ScreenShot_StableCore.py").read_text(encoding="utf-8")
        ast.parse(source)
        for legacy in ("pyautogui", "find_ready_send_button", "wait_for_visual_upload", "CHATGPT_TITLE"):
            self.assertNotIn(legacy, source)
        self.assertIn("browser_bridge.submit", source)


if __name__ == "__main__":
    unittest.main()
