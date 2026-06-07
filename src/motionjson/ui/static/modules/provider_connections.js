const asArray = (value) => {
  if (value == null) return [];
  return Array.isArray(value) ? value : [value];
};

export const MODEL_CONNECTIONS = [
  {
    id: "sam2-local",
    providerId: "sam2-local",
    productPathId: "sam2_prompt_tracking",
    engine: "sam2",
    locality: "local",
    displayLabel: "SAM2 prompt tracking",
    workflow: "Trace one object",
    title: "SAM2 prompt tracking",
    capabilities: ["point", "box", "tracking"],
    supportedGoals: ["trace_one_object"],
    recommendation: "Recommended runtime path for cutting out one prompted object.",
    nextAction: "Install SAM2 fallback or save checkpoint and config paths",
    profileId: "",
  },
  {
    id: "sam2-hf-auto-masks",
    providerId: "sam2-hf-auto-masks",
    productPathId: "sam2_hf_scene_fallback",
    engine: "sam2",
    locality: "local",
    displayLabel: "SAM2 HF automatic masks fallback",
    workflow: "Find everything fallback",
    title: "SAM2 HF automatic masks fallback",
    capabilities: ["auto_masks", "scene_sweep"],
    supportedGoals: ["trace_all_objects", "auto_object_proposals"],
    recommendation: "Fallback for finding everything in scene when SAM3 Scene Sweep is blocked.",
    nextAction: "Install the SAM2 Transformers fallback and cache facebook/sam2.1-hiera-large",
    profileId: "",
  },
  {
    id: "sam2-hosted:replicate-sam2-video",
    providerId: "sam2-hosted",
    productPathId: "sam2_prompt_tracking",
    profileId: "replicate-sam2-video",
    engine: "sam2",
    locality: "hosted",
    displayLabel: "Replicate SAM2 video",
    workflow: "Trace one object",
    title: "Replicate SAM2 video",
    capabilities: ["point", "box", "tracking", "hosted"],
    supportedGoals: ["trace_one_object"],
    recommendation: "Hosted fallback for promptable SAM2 video tracking when the in-process SAM2 runtime is not ready.",
    nextAction: "Link Replicate API token",
  },
  {
    id: "sam3-local",
    providerId: "sam3-local",
    productPathId: "sam3_tracker_scene_sweep",
    engine: "sam3",
    locality: "local",
    displayLabel: "SAM3 Scene Sweep",
    workflow: "Find everything in scene",
    title: "SAM3 Scene Sweep",
    capabilities: ["scene_sweep", "tracking", "auto_masks"],
    supportedGoals: ["trace_all_objects", "auto_object_proposals"],
    recommendation:
      "Recommended CUDA path for scene-wide object proposals and review before export. Text prompts use a separate hosted or advanced local path.",
    nextAction: "Install scene sweep, check Hugging Face access, then cache facebook/sam3",
    profileId: "",
  },
  {
    id: "sam3-hosted:roboflow-sam3-pcs",
    providerId: "sam3-hosted",
    productPathId: "hosted_sam3_concept_text",
    profileId: "roboflow-sam3-pcs",
    engine: "sam3",
    locality: "hosted",
    displayLabel: "Hosted SAM3 text discovery",
    workflow: "Find objects from text",
    title: "Roboflow SAM3",
    capabilities: ["concept", "hosted"],
    supportedGoals: ["text_detector"],
    recommendation: "Find objects from descriptions using a hosted SAM3 provider. Requires explicit cost/privacy opt-in.",
    nextAction: "Link Roboflow API key",
  },
  {
    id: "sam3-hosted:fal-sam3-image",
    providerId: "sam3-hosted",
    productPathId: "hosted_sam3_concept_text",
    profileId: "fal-sam3-image",
    engine: "sam3",
    locality: "hosted",
    displayLabel: "Hosted SAM3 text discovery",
    workflow: "Find objects from text",
    title: "Fal SAM3 image",
    capabilities: ["concept", "hosted"],
    supportedGoals: ["text_detector"],
    recommendation: "Hosted frame-by-frame concept fallback for sampled images when a Fal workflow is preferred.",
    nextAction: "Link FAL_KEY",
  },
  {
    id: "sam3-hosted:custom-sam3-compatible",
    providerId: "sam3-hosted",
    productPathId: "hosted_sam3_concept_text",
    profileId: "custom-sam3-compatible",
    engine: "sam3",
    locality: "hosted",
    displayLabel: "Hosted SAM3 text discovery",
    workflow: "Custom SAM3",
    title: "Custom hosted SAM3",
    capabilities: ["concept", "box", "tracking", "auto_masks", "hosted"],
    supportedGoals: ["trace_one_object", "trace_all_objects", "auto_object_proposals", "text_detector"],
    recommendation: "Use a SAM3-compatible endpoint when it supports the guided workflow you selected.",
    nextAction: "Link endpoint and API key",
  },
  {
    id: "advanced_local_sam3_concept_exemplar",
    providerId: "sam3-local",
    productPathId: "advanced_local_sam3_concept_exemplar",
    engine: "sam3",
    locality: "local",
    displayLabel: "Advanced local SAM3 concept/exemplar",
    workflow: "Advanced local SAM3",
    title: "Advanced local SAM3 concept/exemplar",
    capabilities: ["concept", "box", "tracking", "advanced"],
    supportedGoals: ["trace_one_object", "text_detector"],
    recommendation: "For advanced users with the official SAM3 package and local checkpoint configured.",
    nextAction: "Configure the official SAM3 package and SAM3_LOCAL_MODEL checkpoint path",
    setupGuide: {
      recommendedFor: "Advanced text/concept or exemplar workflows after the official SAM3 package is installed locally.",
      setupSummary: "Install the official SAM3 package separately, save a local sam3.pt checkpoint path, then run diagnostics before using this advanced path.",
      commands: [
        "conda create -n sam3 python=3.12",
        "git clone <official facebookresearch/sam3 repo> /content/sam3",
        "python -m pip install -e /content/sam3",
        "export SAM3_LOCAL_MODEL=/absolute/path/to/sam3.pt",
      ],
    },
    profileId: "",
    advanced: true,
  },
  {
    id: "no_model_cpu_workflow",
    providerId: "mock",
    productPathId: "no_model_cpu_workflow",
    engine: "no_model",
    locality: "no_model",
    displayLabel: "No-model CPU workflow",
    workflow: "Local fallback",
    title: "No-model CPU workflow",
    capabilities: ["auto_masks", "no_model", "cpu"],
    supportedGoals: ["trace_all_objects"],
    recommendation: "Fast local smoke checks, simple motion/threshold masks, and imported masks. No hosted cost.",
    nextAction: "Use mock for smoke checks, motion foreground for moving objects, or import external masks",
    profileId: "",
  },
];

export const MODEL_FREE_PRESETS = new Set(["motion_foreground", "external_masks", "review_existing"]);

export const MODEL_CONNECTION_PRIORITY = {
  trace_one_object: ["sam2-local", "sam2-hosted:replicate-sam2-video"],
  trace_all_objects: ["sam3-local", "sam2-hf-auto-masks", "no_model_cpu_workflow", "sam3-hosted:custom-sam3-compatible"],
  auto_object_proposals: ["sam2-hf-auto-masks", "sam2-local"],
  text_detector: ["sam3-hosted:roboflow-sam3-pcs", "sam3-hosted:custom-sam3-compatible", "sam3-hosted:fal-sam3-image"],
};

export const ADVANCED_MODEL_CONNECTIONS = {
  trace_one_object: ["advanced_local_sam3_concept_exemplar", "sam3-hosted:custom-sam3-compatible"],
  text_detector: ["advanced_local_sam3_concept_exemplar"],
};

export const MODEL_CONNECTION_ALIASES = {
  sam2_prompt_tracking: "sam2-local",
  sam2_hf_scene_fallback: "sam2-hf-auto-masks",
  sam3_tracker_scene_sweep: "sam3-local",
  hosted_sam3_concept_text: "sam3-hosted:roboflow-sam3-pcs",
};

export function providerIdFromConnectionId(connectionId) {
  const id = String(connectionId || "").trim();
  if (id === "sam2_prompt_tracking") return "sam2-local";
  if (id === "sam2_hf_scene_fallback") return "sam2-hf-auto-masks";
  if (id === "sam3_tracker_scene_sweep") return "sam3-local";
  if (id === "hosted_sam3_concept_text") return "sam3-hosted";
  if (id === "advanced_local_sam3_concept_exemplar") return "sam3-local";
  if (id === "no_model_cpu_workflow") return "mock";
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
    productPathId: connection.productPathId || connection.id,
    displayLabel: connection.displayLabel || connection.title || connection.id,
    providerId: connection.providerId || providerIdFromConnectionId(connection.id),
    profileId: connection.profileId || profileIdFromConnectionId(connection.id),
    engine: connection.engine || engineFromProviderId(connection.providerId || connection.id),
    locality: connection.locality || localityFromProviderId(connection.providerId || connection.id),
    capabilities: asArray(connection.capabilities),
    supportedGoals: asArray(connection.supportedGoals),
  };
}

export function modelConnectionByConnectionId(connectionId) {
  const normalized = MODEL_CONNECTION_ALIASES[String(connectionId || "").trim()] || String(connectionId || "").trim();
  return normalizedModelConnection(MODEL_CONNECTIONS.find((connection) => connection.id === normalized) || null);
}
