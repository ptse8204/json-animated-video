const DEFAULT_BASE_URL = "http://127.0.0.1:8765";

function cleanBaseUrl(baseUrl) {
  return String(baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, "");
}

function jsonBody(value) {
  return value === undefined ? undefined : JSON.stringify(value);
}

function toBase64(bytes) {
  if (typeof bytes === "string") return bytes;
  if (typeof Buffer !== "undefined" && Buffer.isBuffer(bytes)) return bytes.toString("base64");
  const array = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let binary = "";
  for (const byte of array) binary += String.fromCharCode(byte);
  if (typeof btoa === "function") return btoa(binary);
  throw new Error("No base64 encoder is available; pass dataBase64 directly");
}

async function parseResponse(response) {
  const contentType = response.headers?.get?.("content-type") || "";
  if (!response.ok) {
    let message = `${response.status} ${response.statusText || "MotionJSON API error"}`;
    if (contentType.includes("application/json")) {
      const body = await response.json();
      if (body?.error) message = body.error;
    }
    throw new Error(message);
  }
  if (contentType.includes("application/json")) return response.json();
  return response.arrayBuffer();
}

export class MotionJSONClient {
  constructor({ baseUrl = DEFAULT_BASE_URL, apiKey, fetch: fetchImpl } = {}) {
    if (!apiKey) throw new Error("apiKey is required");
    this.baseUrl = cleanBaseUrl(baseUrl);
    this.apiKey = apiKey;
    this.fetch = fetchImpl || globalThis.fetch;
    if (!this.fetch) throw new Error("fetch is required in this environment");
  }

  async request(path, { method = "GET", body, headers = {} } = {}) {
    const response = await this.fetch(`${this.baseUrl}${path}`, {
      method,
      headers: {
        authorization: `Bearer ${this.apiKey}`,
        ...(body === undefined ? {} : { "content-type": "application/json" }),
        ...headers
      },
      body: jsonBody(body)
    });
    return parseResponse(response);
  }

  createProject({ name, description = "" }) {
    return this.request("/v1/projects", { method: "POST", body: { name, description } });
  }

  listProjects() {
    return this.request("/v1/projects");
  }

  getProject(projectId) {
    return this.request(`/v1/projects/${encodeURIComponent(projectId)}`);
  }

  uploadAsset(projectId, { filename, kind = "source_video", contentType, data, dataBase64, metadata = {} }) {
    return this.request(`/v1/projects/${encodeURIComponent(projectId)}/assets`, {
      method: "POST",
      body: {
        filename,
        kind,
        contentType,
        dataBase64: dataBase64 || toBase64(data),
        metadata
      }
    });
  }

  listAssets(projectId, { kind } = {}) {
    const suffix = kind ? `?kind=${encodeURIComponent(kind)}` : "";
    return this.request(`/v1/projects/${encodeURIComponent(projectId)}/assets${suffix}`);
  }

  getAsset(assetId) {
    return this.request(`/v1/assets/${encodeURIComponent(assetId)}`);
  }

  downloadAsset(assetId) {
    return this.request(`/v1/assets/${encodeURIComponent(assetId)}/download`);
  }

  enqueueExtraction(projectId, { assetId, maskProvider = "threshold", maxFrames, sampleFps, rightsContext } = {}) {
    return this.request(`/v1/projects/${encodeURIComponent(projectId)}/extractions`, {
      method: "POST",
      body: { assetId, maskProvider, maxFrames, sampleFps, rightsContext }
    });
  }

  createExtraction(projectId, options = {}) {
    return this.enqueueExtraction(projectId, options);
  }

  enqueueAssetPackage(projectId, { sourceJobId, format = "website-zip" }) {
    return this.request(`/v1/projects/${encodeURIComponent(projectId)}/asset-packages`, {
      method: "POST",
      body: { sourceJobId, format }
    });
  }

  createAssetPackage(projectId, options = {}) {
    return this.enqueueAssetPackage(projectId, options);
  }

  enqueueRender(projectId, { sourceJobId, format = "remotion-plan", objectId, backgroundColor, editorState } = {}) {
    return this.request(`/v1/projects/${encodeURIComponent(projectId)}/renders`, {
      method: "POST",
      body: { sourceJobId, format, objectId, backgroundColor, editorState }
    });
  }

  createRender(projectId, options = {}) {
    return this.enqueueRender(projectId, options);
  }

  getJob(jobId) {
    return this.request(`/v1/jobs/${encodeURIComponent(jobId)}`);
  }

  listProjectJobs(projectId) {
    return this.request(`/v1/projects/${encodeURIComponent(projectId)}/jobs`);
  }

  listJobEvents(jobId) {
    return this.request(`/v1/jobs/${encodeURIComponent(jobId)}/events`);
  }

  createWebhook({ url, eventTypes, description = "" }) {
    return this.request("/v1/webhooks", { method: "POST", body: { url, eventTypes, description } });
  }

  listWebhooks() {
    return this.request("/v1/webhooks");
  }

  deleteWebhook(webhookId) {
    return this.request(`/v1/webhooks/${encodeURIComponent(webhookId)}`, { method: "DELETE", body: {} });
  }

  listWebhookDeliveries({ webhookId } = {}) {
    const suffix = webhookId ? `?webhookId=${encodeURIComponent(webhookId)}` : "";
    return this.request(`/v1/webhook-deliveries${suffix}`);
  }
}

function bytes(value) {
  if (value instanceof Uint8Array) return value;
  return new TextEncoder().encode(String(value));
}

function hex(buffer) {
  return [...new Uint8Array(buffer)].map((value) => value.toString(16).padStart(2, "0")).join("");
}

async function subtleCrypto() {
  if (globalThis.crypto?.subtle) return globalThis.crypto.subtle;
  try {
    const { webcrypto } = await import("node:crypto");
    return webcrypto.subtle;
  } catch {
    return null;
  }
}

async function hmacSha256(secret, body, subtle) {
  const key = await subtle.importKey("raw", bytes(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await subtle.sign("HMAC", key, body));
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let index = 0; index < a.length; index += 1) diff |= a.charCodeAt(index) ^ b.charCodeAt(index);
  return diff === 0;
}

export async function verifyWebhookSignature({ secret, payload, signature }) {
  const parts = Object.fromEntries(String(signature || "").split(",").filter((part) => part.includes("=")).map((part) => part.split("=", 2)));
  if (!secret || !parts.t || !parts.v1) return false;
  const subtle = await subtleCrypto();
  if (!subtle) throw new Error("crypto.subtle is required to verify webhook signatures");
  const body = payload instanceof Uint8Array ? payload : bytes(payload);
  const prefix = bytes(`${parts.t}.`);
  const signed = new Uint8Array(prefix.length + body.length);
  signed.set(prefix, 0);
  signed.set(body, prefix.length);
  const digest = await hmacSha256(secret, signed, subtle);
  return timingSafeEqual(digest, parts.v1);
}
