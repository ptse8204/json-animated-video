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

function queryString(filters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function objectOrEmpty(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function stringOrNull(value) {
  if (value === undefined || value === null) return null;
  const text = String(value).trim();
  return text || null;
}

function boolOr(value, fallback) {
  return typeof value === "boolean" ? value : fallback;
}

function scoreOrNull(value) {
  if (value === undefined || value === null || typeof value === "boolean") return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.max(0, Math.min(1, number));
}

export function normalizeDiscoveryMetadata(value = {}) {
  const metadata = objectOrEmpty(value);
  return {
    candidateId: stringOrNull(metadata.candidateId ?? metadata.candidate_id ?? metadata.id),
    source: stringOrNull(metadata.source) || "unknown",
    providerName: stringOrNull(metadata.providerName ?? metadata.provider_name),
    providerModel: stringOrNull(metadata.providerModel ?? metadata.provider_model ?? metadata.modelName ?? metadata.model),
    qualityPreset: stringOrNull(metadata.qualityPreset ?? metadata.quality_preset),
    candidateScore: scoreOrNull(metadata.candidateScore ?? metadata.candidate_score ?? metadata.confidence ?? metadata.score),
    stabilityScore: scoreOrNull(metadata.stabilityScore ?? metadata.stability_score),
    motionScore: scoreOrNull(metadata.motionScore ?? metadata.motion_score),
    frameCoverageEstimate: scoreOrNull(metadata.frameCoverageEstimate ?? metadata.frame_coverage_estimate ?? metadata.frameCoverage),
    reviewStatus: stringOrNull(metadata.reviewStatus ?? metadata.review_status) || "unknown",
    rejectionReason: stringOrNull(metadata.rejectionReason ?? metadata.rejection_reason),
    selectedForTracking: boolOr(metadata.selectedForTracking ?? metadata.selected_for_tracking, false),
    defaultSelected: boolOr(metadata.defaultSelected ?? metadata.default_selected, false),
    trackConfidence: scoreOrNull(metadata.trackConfidence ?? metadata.track_confidence),
    motionCoverage: scoreOrNull(metadata.motionCoverage ?? metadata.motion_coverage),
    reviewRequired: boolOr(metadata.reviewRequired ?? metadata.review_required, false),
    exportStatus: stringOrNull(metadata.exportStatus ?? metadata.export_status) || "accepted",
    trackingProvider: stringOrNull(metadata.trackingProvider ?? metadata.tracking_provider),
    correctionHistoryRef: stringOrNull(metadata.correctionHistoryRef ?? metadata.correction_history_ref),
    warnings: Array.isArray(metadata.warnings) ? metadata.warnings.map(String) : [],
    filters: objectOrEmpty(metadata.filters),
    artifacts: objectOrEmpty(metadata.artifacts),
    lineage: objectOrEmpty(metadata.lineage),
    raw: metadata
  };
}

export function discoveryMetadataFromCandidate(candidate = {}) {
  const record = objectOrEmpty(candidate);
  const metadata = objectOrEmpty(record.metadata);
  return normalizeDiscoveryMetadata({
    ...metadata,
    candidateId: record.candidateId ?? record.candidate_id ?? record.id ?? metadata.candidateId,
    source: record.source ?? metadata.source,
    providerName: record.providerName ?? record.provider_name ?? metadata.providerName,
    candidateScore: record.confidence ?? record.score ?? metadata.confidence ?? metadata.score,
    reviewStatus: record.reviewStatus ?? record.review_status ?? metadata.reviewStatus,
    rejectionReason: record.rejectionReason ?? record.rejection_reason ?? metadata.rejectionReason,
    defaultSelected: record.defaultSelected ?? record.default_selected ?? metadata.defaultSelected,
    selectedForTracking: record.selectedForTracking ?? record.selected_for_tracking ?? metadata.selectedForTracking
  });
}

export function discoveryMetadataFromMotionJSON(document = {}, objectId) {
  const manifest = objectOrEmpty(document);
  if (manifest.discovery) return normalizeDiscoveryMetadata(manifest.discovery);
  const objects = Array.isArray(manifest.objects) ? manifest.objects : [];
  const object = objectId
    ? objects.find((item) => objectOrEmpty(item).id === objectId || objectOrEmpty(item).objectId === objectId)
    : objects[0];
  return normalizeDiscoveryMetadata(objectOrEmpty(object).discovery);
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

  saveLibraryAsset(projectId, { assetId, type = "saved_asset", title, description = "", tags = [], metadata = {} }) {
    return this.request(`/v1/projects/${encodeURIComponent(projectId)}/library-assets`, {
      method: "POST",
      body: { assetId, type, title, description, tags, metadata }
    });
  }

  listLibraryAssets(filters = {}) {
    return this.request(`/v1/library/assets${queryString(filters)}`);
  }

  getLibraryAsset(libraryAssetId) {
    return this.request(`/v1/library/assets/${encodeURIComponent(libraryAssetId)}`);
  }

  createBrandCollection({ projectId, title, name, description = "", metadata = {} } = {}) {
    return this.request("/v1/library/collections", {
      method: "POST",
      body: { projectId, title: title || name, description, metadata }
    });
  }

  listBrandCollections() {
    return this.request("/v1/library/collections");
  }

  addCollectionAsset(collectionId, { libraryAssetId }) {
    return this.request(`/v1/library/collections/${encodeURIComponent(collectionId)}/assets`, {
      method: "POST",
      body: { libraryAssetId }
    });
  }

  listCollectionAssets(collectionId) {
    return this.request(`/v1/library/collections/${encodeURIComponent(collectionId)}/assets`);
  }

  createCreatorPack({ collectionId, title, name, description = "", libraryAssetIds, metadata = {} } = {}) {
    return this.request("/v1/library/packs", {
      method: "POST",
      body: { collectionId, title: title || name, description, libraryAssetIds, metadata }
    });
  }

  listCreatorPacks() {
    return this.request("/v1/library/packs");
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

  betaStatus() {
    return this.request("/v1/beta/status");
  }

  acceptBetaInvite(inviteToken) {
    return this.request("/v1/beta/accept", { method: "POST", body: { inviteToken } });
  }

  createFeedback({ projectId, type = "general", severity = "normal", subject = "", message = "", context = {} } = {}) {
    return this.request("/v1/feedback", {
      method: "POST",
      body: { projectId, type, severity, subject, message, context }
    });
  }

  createErrorReport({ projectId, jobId, severity = "error", message = "", stackTrace = "", context = {} } = {}) {
    return this.request("/v1/error-reports", {
      method: "POST",
      body: { projectId, jobId, severity, message, stackTrace, context }
    });
  }

  adminDashboard() {
    return this.request("/v1/admin/dashboard");
  }

  createBetaInvite({ email, role = "member", ttlSeconds } = {}) {
    return this.request("/v1/admin/beta/invites", {
      method: "POST",
      body: { email, role, ttlSeconds }
    });
  }

  listBetaInvites({ includeRevoked = false } = {}) {
    const suffix = includeRevoked ? "?includeRevoked=true" : "";
    return this.request(`/v1/admin/beta/invites${suffix}`);
  }

  revokeBetaInvite(inviteId) {
    return this.request(`/v1/admin/beta/invites/${encodeURIComponent(inviteId)}`, { method: "DELETE", body: {} });
  }

  listBetaMembers({ includeDisabled = false } = {}) {
    const suffix = includeDisabled ? "?includeDisabled=true" : "";
    return this.request(`/v1/admin/beta/members${suffix}`);
  }

  listBillingPlans() {
    return this.request("/v1/billing/plans");
  }

  billingStatus() {
    return this.request("/v1/billing/status");
  }

  listFeedback({ includeResolved = false } = {}) {
    const suffix = includeResolved ? "?includeResolved=true" : "";
    return this.request(`/v1/admin/feedback${suffix}`);
  }

  listErrorReports({ includeResolved = false } = {}) {
    const suffix = includeResolved ? "?includeResolved=true" : "";
    return this.request(`/v1/admin/error-reports${suffix}`);
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
