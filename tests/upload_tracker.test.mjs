import test from "node:test";
import assert from "node:assert/strict";
import {UploadTracker} from "../browser_extension/upload_tracker.mjs";

const filename = "gc_unique.png";
const uploadUrl = "https://example.invalid/upload?signature=TEST";
function metadata(tracker, name = filename) {
  tracker.request("meta", {url: "https://chatgpt.com/backend-api/files", method: "POST",
    postData: JSON.stringify({file_name: name})});
  tracker.response("meta", 200);
  tracker.complete("meta", {file_id: "file-123", upload_url: uploadUrl});
}
function put(tracker, status = 201) {
  tracker.request("put", {url: uploadUrl, method: "PUT"});
  tracker.response("put", status);
  tracker.complete("put");
}
function commit(tracker, id = "file-123", status = 200) {
  tracker.request("commit", {url: `https://chatgpt.com/backend-api/files/${id}/uploaded`, method: "POST"});
  tracker.response("commit", status);
  tracker.complete("commit");
}

test("thumbnail/creation alone never authorizes Enter", () => {
  const tracker = new UploadTracker(filename);
  metadata(tracker);
  assert.equal(tracker.ready, false);
  put(tracker);
  assert.equal(tracker.ready, true);
  commit(tracker);
  assert.equal(tracker.ready, true);
});
test("unrelated filename cannot authorize Enter", () => {
  const tracker = new UploadTracker(filename);
  metadata(tracker, "different.png"); put(tracker); commit(tracker);
  assert.equal(tracker.ready, false);
});
test("renamed clipboard PNG matches by exact byte size and completed upload", () => {
  const tracker = new UploadTracker(filename, 1234);
  tracker.request("meta", {url: "https://chatgpt.com/backend-api/files", method: "POST",
    postData: JSON.stringify({file_name: "image.png", file_size: 1234})});
  tracker.response("meta", 200);
  tracker.complete("meta", {file_id: "file-123", upload_url: uploadUrl});
  put(tracker);
  assert.equal(tracker.ready, true);
  commit(tracker);
  assert.equal(tracker.ready, true);
});
test("renamed PNG with different size does not match", () => {
  const tracker = new UploadTracker(filename, 1234);
  tracker.request("meta", {url: "https://chatgpt.com/backend-api/files", method: "POST",
    postData: JSON.stringify({file_name: "image.png", file_size: 999})});
  assert.match(tracker.summary(), /identity did not match/);
  assert.equal(tracker.ready, false);
});
test("unrelated file's completion cannot authorize Enter", () => {
  const tracker = new UploadTracker(filename);
  metadata(tracker); commit(tracker, "file-other");
  assert.equal(tracker.ready, false);
});
test("failed transfer prevents sending", () => {
  const tracker = new UploadTracker(filename);
  metadata(tracker); put(tracker, 500);
  assert.equal(tracker.ready, false);
  assert.ok(tracker.error);
});
test("out-of-order event processing preserves correlation", () => {
  const tracker = new UploadTracker(filename);
  put(tracker); commit(tracker); metadata(tracker);
  assert.equal(tracker.ready, true);
});
test("upload HTTP headers alone are insufficient; image transfer must finish", () => {
  const tracker = new UploadTracker(filename);
  metadata(tracker);
  tracker.request("put", {url: uploadUrl, method: "PUT"});
  tracker.response("put", 201);
  assert.equal(tracker.ready, false);
  tracker.complete("put");
  assert.equal(tracker.ready, true);
});
test("unknown response schema, missing body and non-HTTPS upload fail closed", () => {
  for (const body of [{id: "other"}, undefined, {file_id: "file-123", upload_url: "http://example.invalid"}]) {
    const tracker = new UploadTracker(filename);
    tracker.request("meta", {url: "https://chatgpt.com/backend-api/files", method: "POST",
      postData: JSON.stringify({file_name: filename})});
    tracker.response("meta", 200); tracker.complete("meta", body);
    assert.equal(tracker.ready, false);
    assert.ok(tracker.error);
  }
});
test("network loading failure prevents sending", () => {
  const tracker = new UploadTracker(filename);
  metadata(tracker); put(tracker); tracker.failed("put"); commit(tracker);
  assert.equal(tracker.ready, false);
});
test("unknown endpoint never authorizes Enter", () => {
  const tracker = new UploadTracker(filename);
  tracker.request("meta", {url: "https://chatgpt.com/backend-api/new-upload", method: "POST",
    postData: JSON.stringify({file_name: filename})});
  tracker.response("meta", 200);
  tracker.complete("meta", {file_id: "file-123", upload_url: uploadUrl});
  put(tracker); commit(tracker);
  assert.equal(tracker.ready, false);
});
