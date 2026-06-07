const asArray = (value) => {
  if (value == null) return [];
  return Array.isArray(value) ? value : [value];
};

export const MODEL_CONNECTIONS = [
  {
    id: "sam2-local",
    providerId: "sam2-local",
    engine: "sam2",
    locality: "local",
    displayLabel: "SAM2 prompt tracking",
    workflow: "Trace one object",
    title: "SAM2 prompt tracking",
    capabilities: ["point", "box", "tracking"],
    recommendation: "Recommended runtime path for cutting out one prompted object.",
    nextAction: "Install SAM2 fallback or save checkpoint and config paths",
    profileId: "",
  },
  {
    id: "sam2-hf-auto-masks",
    providerId: "sam2-hf-auto-masks",
    engine: "sam2",
    locality: "local",
    displayLabel: "SAM2 HF automatic masks",
    workflow: "Find everything fallback",
    title: "SAM2 HF automatic masks",
    capabilities: ["auto_masks", "scene_sweep"],
    recommendation: "Fallback for finding everything in scene when SAM3 Scene Sweep is blocked.",
    nextAction: "Install the SAM2 Transformers fallback and cache facebook/sam2.1-hiera-large",
    profileId: "",
  },
  {
    id: "sam2-hosted:replicate-sam2-video",
    providerId: "sam2-hosted",
    profileId: "replicate-sam2-video",
    engine: "sam2",
    locality: "hosted",
    displayLabel: "Replicate SAM2 video",
    workflow: "Trace one object",
    title: "Replicate SAM2 video",
    capabilities: ["point", "box", "tracking", "hosted"],
    recommendation: "Hosted fallback for promptable SAM2 video tracking when the in-process SAM2 runtime is not ready.",
    nextAction: "Link Replicate API token",
  },
  {
    id: "sam3-local",
    providerId: "sam3-local",
    engine: "sam3",
    locality: "local",
    displayLabel: "SAM3 Scene Sweep",
    workflow: "Find everything in scene",
    title: "SAM3 Scene Sweep",
    capabilities: ["scene_sweep", "concept", "box", "tracking", "auto_masks"],
    recommendation:
      "Recommended CUDA runtime path for finding everything in the scene with SAM3 Tracker masks and video tracking. Text prompts require hosted SAM3 concept setup or the advanced official SAM3 concept adapter.",
    nextAction: "Install scene sweep, check Hugging Face access, then cache facebook/sam3",
    profileId: "",
  },
  {
    id: "sam3-hosted:roboflow-sam3-pcs",
    providerId: "sam3-hosted",
    profileId: "roboflow-sam3-pcs",
    engine: "sam3",
    locality: "hosted",
    displayLabel: "Roboflow SAM3",
    workflow: "Find objects from text",
    title: "Roboflow SAM3",
    capabilities: ["concept", "hosted"],
    recommendation: "Recommended hosted concept segmentation provider for prompts like red ball or person in white.",
    nextAction: "Link Roboflow API key",
  },
  {
    id: "sam3-hosted:fal-sam3-image",
    providerId: "sam3-hosted",
    profileId: "fal-sam3-image",
    engine: "sam3",
    locality: "hosted",
    displayLabel: "Fal SAM3 image",
    workflow: "Find objects from text",
    title: "Fal SAM3 image",
    capabilities: ["concept", "hosted"],
    recommendation: "Hosted frame-by-frame concept fallback for sampled images when a Fal workflow is preferred.",
    nextAction: "Link FAL_KEY",
  },
  {
    id: "sam3-hosted:custom-sam3-compatible",
    providerId: "sam3-hosted",
    profileId: "custom-sam3-compatible",
    engine: "sam3",
    locality: "hosted",
    displayLabel: "Custom SAM3 endpoint",
    workflow: "Custom SAM3",
    title: "Custom hosted SAM3",
    capabilities: ["concept", "box", "tracking", "auto_masks", "hosted"],
    recommendation: "Use a SAM3-compatible endpoint when it supports the guided workflow you selected.",
    nextAction: "Link endpoint and API key",
  },
];

export const MODEL_FREE_PRESETS = new Set(["motion_foreground", "external_masks", "review_existing"]);

export const MODEL_CONNECTION_PRIORITY = {
  trace_one_object: ["sam2-local", "sam2-hosted:replicate-sam2-video"],
  trace_all_objects: ["sam3-local", "sam2-hf-auto-masks", "sam3-hosted:custom-sam3-compatible"],
  auto_object_proposals: ["sam2-hf-auto-masks", "sam2-local"],
  text_detector: ["sam3-hosted:roboflow-sam3-pcs", "sam3-hosted:custom-sam3-compatible", "sam3-hosted:fal-sam3-image"],
};

export const ADVANCED_MODEL_CONNECTIONS = {
  trace_one_object: ["sam3-local", "sam3-hosted:custom-sam3-compatible"],
  text_detector: ["sam3-local"],
};

export function providerIdFromConnectionId(connectionId) {
  const id = String(connectionId || "").trim();
  if (id.startsWith("sam2-hosted:")) return "sam2-hosted";
  if (id.startsWith("sam3-hosted:")) return "sam3-hosted";
  return id;
}

export function profileIdFromConnectionId(connectionId) {
  const parts = String(connectionId || "").split(":");
  return parts.length > 1 ? parts.slice(1).join(":") : "";
}

export function engineFromProviderId(providerId) {
  const id = String(providerId || "");
  if (id.includes("sam3")) return "sam3";
  if (id.includes("sam2")) return "sam2";
  if (id.includes("motion")) return "motion";
  if (id.includes("external")) return "external_masks";
  return id ? "no_model" : "";
}

export function localityFromProviderId(providerId) {
  const id = String(providerId || "");
  if (id.includes("hosted")) return "hosted";
  if (MODEL_FREE_PRESETS.has(id) || ["mock", "threshold", "motion", "external"].includes(id)) return "no_model";
  return id ? "local" : "";
}

export function providerLabel(providerId, profileId = "") {
  if (providerId === "sam2-local") return "SAM2 local";
  if (providerId === "sam2-hf-auto-masks") return "SAM2 HF automatic masks";
  if (providerId === "sam2-hosted" && profileId === "replicate-sam2-video") return "Replicate SAM2 video";
  if (providerId === "sam2-hosted") return "Hosted SAM2";
  if (providerId === "sam3-local") return "SAM3 Scene Sweep runtime";
  if (providerId === "sam3-hosted" && profileId === "roboflow-sam3-pcs") return "Roboflow SAM3";
  if (providerId === "sam3-hosted" && profileId === "fal-sam3-image") return "Fal SAM3 image";
  if (providerId === "sam3-hosted") return "Custom SAM3 endpoint";
  return {
    mock: "Mock no-model",
    threshold: "Color threshold",
    motion: "Motion foreground",
    external: "Imported masks",
    motion_foreground: "Motion foreground",
    external_masks: "Imported masks",
  }[providerId] || providerId || "No model";
}

export function normalizedModelConnection(connection) {
  if (!connection) return null;
  return {
    ...connection,
    connectionId: connection.id,
    displayLabel: connection.displayLabel || connection.title || connection.id,
    providerId: connection.providerId || providerIdFromConnectionId(connection.id),
    profileId: connection.profileId || profileIdFromConnectionId(connection.id),
    engine: connection.engine || engineFromProviderId(connection.providerId || connection.id),
    locality: connection.locality || localityFromProviderId(connection.providerId || connection.id),
    capabilities: asArray(connection.capabilities),
  };
}

export function modelConnectionByConnectionId(connectionId) {
  const normalized = String(connectionId || "").trim();
  return normalizedModelConnection(MODEL_CONNECTIONS.find((connection) => connection.id === normalized) || null);
}
