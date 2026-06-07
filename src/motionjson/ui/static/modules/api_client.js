export const SAFE_LOCAL_CONTENT_URL_RE =
  /^\/api\/(?:videos|artifacts|assets)\/[A-Za-z0-9._~-]+\/content(?:[?#][^\s]*)?$|^\/api\/jobs\/[A-Za-z0-9._~-]+\/preview-files\/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+(?:[?#][^\s]*)?$/;

export function localApiUrl(value) {
  const path = String(value || "").trim();
  if (!/^\/api(?:[/?#]|$)/.test(path)) return path;
  const loc = globalThis.location;
  if (!loc || !/^https?:$/i.test(String(loc.protocol || ""))) return path;
  const origin = loc.origin || `${loc.protocol}//${loc.host}`;
  let basePath = String(loc.pathname || "/");
  if (basePath.endsWith("/ui")) {
    basePath = `${basePath}/`;
  } else if (!basePath.endsWith("/")) {
    basePath = basePath.replace(/[^/]*$/, "");
  }
  try {
    const url = new URL(`..${path}`, `${origin}${basePath}`);
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return path;
  }
}

export function safeLocalContentUrl(value) {
  const url = String(value || "").trim();
  return SAFE_LOCAL_CONTENT_URL_RE.test(url) ? localApiUrl(url) : "";
}

export function artifactRelPath(artifact = {}) {
  const metadata = artifact.metadata || artifact.metadata_json || {};
  return String(metadata.rel_path || artifact.relPath || artifact.path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

export function previewFileUrl(jobId, relPath) {
  const id = String(jobId || "").trim();
  const path = String(relPath || "")
    .replace(/\\/g, "/")
    .split("/")
    .filter(Boolean)
    .map((part) => encodeURIComponent(part))
    .join("/");
  if (!id || !path) return "";
  return safeLocalContentUrl(`/api/jobs/${encodeURIComponent(id)}/preview-files/${path}`);
}

export function reviewToolUrl(jobId, tool) {
  const base = previewFileUrl(jobId, tool?.relPath);
  if (!base) return "";
  const encodedJobId = encodeURIComponent(jobId);
  const params = new URLSearchParams({
    scene: previewFileUrl(jobId, "scene_graph.json"),
    manifest: previewFileUrl(jobId, "web_asset_manifest.json"),
    jobId: String(jobId || ""),
    review: localApiUrl(`/api/jobs/${encodedJobId}/review`),
    export: localApiUrl(`/api/jobs/${encodedJobId}/exports/motionjson`),
  });
  return `${base}?${params.toString()}`;
}

export async function api(path, options = {}) {
  let response;
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["content-type"] = headers["content-type"] || "application/json";
  }
  try {
    response = await fetch(localApiUrl(path), {
      headers,
      ...options,
    });
  } catch (error) {
    throw new Error(`Runtime API unavailable: ${error.message}`);
  }

  const body = await response.text();
  let payload = {};
  if (body) {
    try {
      payload = JSON.parse(body);
    } catch {
      payload = { error: body.slice(0, 180) };
    }
  }

  if (!response.ok) {
    throw new Error(payload.error || payload.detail || `Request failed: ${response.status}`);
  }
  return payload;
}
