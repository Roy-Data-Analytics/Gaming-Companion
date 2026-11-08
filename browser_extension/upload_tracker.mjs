// Confirm this screenshot's file creation and successful signed PUT only.
// These are private page endpoints, not a supported API. Unknown flows fail closed.
export class UploadTracker {
  constructor(filename, fileSize = null) {
    this.filename = filename;
    this.fileSize = fileSize;
    this.requests = new Map();
    this.fileId = null;
    this.uploadUrl = null;
    this.error = null;
    this.observed = new Set();
  }
  request(id, request) {
    const url = new URL(request.url);
    const isPage = ["chatgpt.com", "chat.openai.com"].includes(url.hostname);
    const metadata = isPage && request.method === "POST"
      && /^\/backend-api\/files\/?$/.test(url.pathname);
    let matches = false;
    if (metadata) {
      this.observed.add("file-create request observed");
      try {
        const body = JSON.parse(request.postData || "{}");
        matches = body.file_name === this.filename || body.filename === this.filename;
        const size = body.file_size ?? body.size;
        // Clipboard handlers may rename a File. Only accept the exact byte size
        // for the single PNG task; do not treat any upload in the tab as ours.
        if (!matches && this.fileSize > 0 && size === this.fileSize
            && /\.(png)$/i.test(body.file_name || body.filename || "")) {
          matches = true;
          this.observed.add("clipboard filename changed; exact PNG byte size matched");
        }
        if (!matches) this.observed.add(request.postData ? "file identity did not match" : "file-create body unavailable");
      } catch { /* Do not guess when request body is unavailable. */ }
    }
    if (!matches && request.method !== "PUT") return;
    if (this.requests.size > 200) { this.error = "Too many unrelated upload requests"; return; }
    this.requests.set(id, {url: request.url, path: url.pathname, metadata: matches,
      method: request.method, status: null, finished: false});
    if (matches) this.observed.add("matching file-create request");
    if (matches && [...this.requests.values()].filter(item => item.metadata).length > 1) {
      this.error = "Multiple matching file uploads observed; cannot identify the screenshot safely";
    }
  }
  response(id, status) {
    const request = this.requests.get(id);
    if (request) request.status = status;
  }
  complete(id, body) {
    const request = this.requests.get(id);
    if (!request) return;
    request.finished = true;
    if (request.metadata && request.status >= 200 && request.status < 300) {
      if (!body || typeof body.file_id !== "string" || typeof body.upload_url !== "string") {
        this.error = "File-create response has no recognized file_id/upload_url";
        return;
      }
      const upload = new URL(body.upload_url);
      if (upload.protocol !== "https:") { this.error = "Unexpected upload URL scheme"; return; }
      this.fileId = body.file_id;
      this.uploadUrl = body.upload_url;
      this.observed.add("matching file-create response");
    }
  }
  failed(id) {
    const request = this.requests.get(id);
    if (request) request.failed = true;
  }
  get ready() {
    if (this.error) return false;
    let uploaded = false;
    for (const request of this.requests.values()) {
      const put = this.uploadUrl && request.method === "PUT" && request.url === this.uploadUrl;
      if (!(request.metadata || put)) continue;
      if (request.failed || (request.status !== null && request.status >= 400)) {
        this.error = "The screenshot upload request failed";
        return false;
      }
      const success = request.finished && request.status >= 200 && request.status < 300;
      if (put && success) uploaded = true;
    }
    if (uploaded) this.observed.add("image bytes uploaded successfully");
    // A completed successful PUT is positive confirmation that the image bytes
    // reached the upload service. Some ChatGPT variants do not issue /uploaded.
    // Do not require that private endpoint to exist. Observed failures still abort.
    return !!(this.fileId && uploaded);
  }
  summary() {
    return [...this.observed].join(", ") || "No matching file-create request observed";
  }
}
