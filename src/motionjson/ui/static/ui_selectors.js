const MATERIALIZATION_BUDGET_PIXELS = 64_000_000;

const toNumber = (value, fallback = 0) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

const toInteger = (value, fallback = 0) => {
  const number = Number.parseInt(value, 10);
  return Number.isFinite(number) ? number : fallback;
};

export const OPTION_HELP_TEXT = {
  sceneSweepQuality: "Balances object recall against speed, memory, and noisy background fragments.",
  sampleFps: "How many source frames per second are sampled before tracking. Lower values improve stability on long or high-resolution videos.",
  maxFrames: "Upper bound on sampled frames. Lower this when scene sweep stalls, runs out of memory, or produces too many artifacts.",
  maxObjects: "Maximum object candidates allowed into review. Lower values reduce memory pressure and keep review usable.",
  traceEverythingMode: "Keeps many raw auto-mask segments for review. Export stays blocked until objects are reviewed.",
  device: "Auto is conservative for SAM runtimes. Choose GPU to explicitly request CUDA when diagnostics show it is available.",
  exportPreset: "Controls package size and debug detail. Compact is the normal handoff; debug keeps extra inspection artifacts.",
  partialResultRecovery: "Completed objects can remain reviewable even when a later object or frame fails.",
};

export function objectDiscoveryDefaults(qualityPreset) {
  const defaults = {
    clean: {
      intent: "discover_objects_clean",
      keyframePolicy: "scene_changes",
      maxKeyframes: 3,
      frameInterval: null,
      maxCandidatesPerKeyframe: 32,
      maxObjects: 12,
      minMaskArea: 96,
      maxMaskAreaRatio: 0.45,
      dedupeIou: 0.78,
      stabilityThreshold: 0.86,
      trackSelectedOnly: true,
      trackTopCandidates: false,
      requireExplicitCostWarning: false,
    },
    balanced: {
      intent: "discover_objects_balanced",
      keyframePolicy: "scene_changes",
      maxKeyframes: 5,
      frameInterval: null,
      maxCandidatesPerKeyframe: 64,
      maxObjects: 24,
      minMaskArea: 64,
      maxMaskAreaRatio: 0.6,
      dedupeIou: 0.84,
      stabilityThreshold: 0.78,
      trackSelectedOnly: true,
      trackTopCandidates: false,
      requireExplicitCostWarning: false,
    },
    maximum_recall: {
      intent: "discover_objects_maximum_recall",
      keyframePolicy: "scene_changes",
      maxKeyframes: 8,
      frameInterval: 24,
      maxCandidatesPerKeyframe: 128,
      maxObjects: 64,
      minMaskArea: 32,
      maxMaskAreaRatio: 0.75,
      dedupeIou: 0.9,
      stabilityThreshold: 0.7,
      trackSelectedOnly: true,
      trackTopCandidates: false,
      requireExplicitCostWarning: false,
    },
    trace_everything: {
      intent: "trace_everything",
      keyframePolicy: "uniform_interval",
      maxKeyframes: 8,
      frameInterval: 24,
      maxCandidatesPerKeyframe: 128,
      maxObjects: 64,
      minMaskArea: 32,
      maxMaskAreaRatio: 0.75,
      dedupeIou: 0.9,
      stabilityThreshold: 0.7,
      trackSelectedOnly: false,
      trackTopCandidates: true,
      requireExplicitCostWarning: true,
    },
  };
  return defaults[qualityPreset] || defaults.clean;
}

export function effortPresetDefaults(effortPreset = "balanced") {
  const presets = {
    fast: {
      effortPreset: "fast",
      sampleFps: 6,
      maxFrames: 36,
      qualityPreset: "clean",
      maxObjects: 12,
      maskRefinementPreset: "fast",
      useTransformersTracker: false,
      requireRealTracking: false,
      label: "Fast",
      detail: "Lower load; static fallback can remain diagnostic output.",
    },
    balanced: {
      effortPreset: "balanced",
      sampleFps: 8,
      maxFrames: 48,
      qualityPreset: "balanced",
      maxObjects: 24,
      maskRefinementPreset: "balanced",
      useTransformersTracker: true,
      requireRealTracking: false,
      label: "Balanced",
      detail: "Default reviewable quality without flooding the workspace.",
    },
    high_quality: {
      effortPreset: "high_quality",
      sampleFps: 12,
      maxFrames: 96,
      qualityPreset: "maximum_recall",
      maxObjects: 32,
      maskRefinementPreset: "precise",
      useTransformersTracker: true,
      requireRealTracking: true,
      label: "High quality",
      detail: "Slower and higher GPU memory use; blocks silent static fallback.",
    },
  };
  return presets[effortPreset] || presets.balanced;
}

function providerLabel(providerId, profileId = "") {
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

function overrideFlagsFromSnapshot(snapshot = {}) {
  const source = snapshot.userOverrides || snapshot.overrideFlags || snapshot.overrides || {};
  if (source instanceof Set) return Object.fromEntries([...source].map((key) => [key, true]));
  if (Array.isArray(source)) return Object.fromEntries(source.map((key) => [key, true]));
  if (source && typeof source === "object") return { ...source };
  return {};
}

function videoFactsFromSnapshot(snapshot = {}) {
  const video = snapshot.video || snapshot.videoPreview || snapshot.preview || {};
  const metadata = video.metadata || snapshot.videoMetadata || {};
  const width = toInteger(snapshot.width ?? snapshot.videoWidth ?? video.width ?? metadata.width, 0);
  const height = toInteger(snapshot.height ?? snapshot.videoHeight ?? video.height ?? metadata.height, 0);
  const duration = toNumber(snapshot.duration ?? snapshot.videoDuration ?? video.duration ?? metadata.duration, 0);
  return {
    width,
    height,
    duration,
    framePixels: width > 0 && height > 0 ? width * height : 0,
  };
}

function priorFailureReasonFromSnapshot(snapshot = {}) {
  return String(
    snapshot.priorFailureReason ||
      snapshot.reasonCode ||
      snapshot.failureReason ||
      snapshot.failure?.reasonCode ||
      snapshot.lifecycle?.failure?.reasonCode ||
      "",
  ).toLowerCase();
}

function adaptiveSourceValue(key, automaticValue, snapshot, overrideFlags) {
  const current = snapshot.currentValues || snapshot;
  const override = Boolean(overrideFlags[key]);
  const rawValue = current[key] ?? snapshot[key];
  if (key === "device" || key === "qualityPreset") {
    return {
      value: override && rawValue !== undefined && rawValue !== "" ? String(rawValue) : automaticValue,
      source: override ? "user_override" : "auto",
    };
  }
  const numeric = key === "sampleFps" ? toNumber(rawValue, automaticValue) : toInteger(rawValue, automaticValue);
  return {
    value: override ? numeric : automaticValue,
    source: override ? "user_override" : "auto",
  };
}

export function adaptiveRunDefaultsFromSnapshot(snapshot = {}) {
  const presetId = snapshot.selectedPreset || snapshot.preset || snapshot.goal || "trace_one_object";
  const providerId = String(snapshot.providerId || snapshot.providerName || snapshot.maskProvider || "");
  const providerLabelText = snapshot.providerLabel || snapshot.displayLabel || providerLabel(providerId) || "Auto provider";
  const effort = effortPresetDefaults(String(snapshot.effortPreset || "balanced"));
  const failureReason = priorFailureReasonFromSnapshot(snapshot);
  const retryingHeavyAssetPrep = ["asset_preparation_stalled", "asset_preparation_frame_timeout", "worker_heartbeat_stale"].includes(failureReason);
  const video = videoFactsFromSnapshot(snapshot);
  const largeVideo = video.framePixels >= 1920 * 1080;
  const traceEverythingMode = Boolean(snapshot.traceEverythingMode);
  let qualityPreset = traceEverythingMode
    ? "trace_everything"
    : String(snapshot.qualityPreset || (presetId === "trace_all_objects" ? effort.qualityPreset : "clean"));
  let sampleFps = presetId === "trace_all_objects" ? effort.sampleFps : presetId === "text_detector" ? 8 : 12;
  let maxFrames = presetId === "trace_all_objects" ? effort.maxFrames : presetId === "trace_one_object" ? 48 : presetId === "text_detector" ? 32 : 48;
  let maxObjects =
    presetId === "trace_one_object"
      ? 1
      : presetId === "text_detector"
        ? 6
        : presetId === "class_detector" || presetId === "motion_foreground"
          ? 8
          : presetId === "trace_all_objects"
            ? effort.maxObjects
            : objectDiscoveryDefaults(qualityPreset).maxObjects;
  const preferredDevice = String(snapshot.preferredDevice || snapshot.accelerator || "").toLowerCase();
  let device =
    presetId === "trace_all_objects" && providerId === "sam3-local" && preferredDevice === "cuda"
      ? "cuda"
      : String(snapshot.device || "auto") || "auto";
  const budgetPixels = Math.max(1, toInteger(snapshot.materializationBudgetPixels, MATERIALIZATION_BUDGET_PIXELS));

  if (retryingHeavyAssetPrep && presetId === "trace_all_objects") {
    qualityPreset = "clean";
    sampleFps = 6;
    maxFrames = 32;
    maxObjects = 12;
    device = providerId === "sam3-local" && preferredDevice === "cuda" ? "cuda" : "auto";
  } else if (largeVideo && presetId === "trace_all_objects") {
    qualityPreset = qualityPreset === "maximum_recall" ? "balanced" : qualityPreset;
    sampleFps = Math.min(sampleFps, 6);
    maxFrames = Math.min(maxFrames, 36);
    maxObjects = Math.min(maxObjects, 18);
  }

  if (video.duration > 0) {
    maxFrames = Math.max(1, Math.min(maxFrames, Math.ceil(video.duration * sampleFps)));
  }

  const overrideFlags = overrideFlagsFromSnapshot(snapshot);
  const resolved = {
    sampleFps: adaptiveSourceValue("sampleFps", sampleFps, snapshot, overrideFlags),
    maxFrames: adaptiveSourceValue("maxFrames", maxFrames, snapshot, overrideFlags),
    maxObjects: adaptiveSourceValue("maxObjects", maxObjects, snapshot, overrideFlags),
    qualityPreset: adaptiveSourceValue("qualityPreset", qualityPreset, snapshot, overrideFlags),
    device: adaptiveSourceValue("device", device, snapshot, overrideFlags),
    effortPreset: { value: effort.effortPreset, source: "auto" },
    maskRefinementPreset: { value: effort.maskRefinementPreset, source: "auto" },
  };
  const values = Object.fromEntries(Object.entries(resolved).map(([key, item]) => [key, item.value]));
  const estimatedPixels = video.framePixels > 0 ? video.framePixels * Math.max(1, values.maxFrames) * Math.max(1, Math.min(values.maxObjects, 4)) : 0;
  const materializationRisk =
    !estimatedPixels ? "unknown" : estimatedPixels > budgetPixels ? "high" : estimatedPixels > budgetPixels * 0.55 ? "watch" : "normal";
  const qualityLabel = {
    clean: "Clean",
    balanced: "Balanced",
    maximum_recall: "Maximum recall",
    trace_everything: "Trace everything",
  }[values.qualityPreset] || values.qualityPreset;
  const chip = (id, label, value, detail, source = resolved[id]?.source || "auto", tone = "neutral") => ({
    id,
    label,
    value,
    detail,
    source,
    tone,
    help: OPTION_HELP_TEXT[id] || "",
  });
  return {
    format: "motionjson.local_ui_adaptive_parameters.v0.1",
    presetId,
    providerId,
    failureReason,
    values: {
      ...values,
      traceEverythingMode,
      useTransformersTracker: effort.useTransformersTracker,
      requireRealTracking: effort.requireRealTracking,
      materializationBudgetPixels: budgetPixels,
      materializationEstimatedPixels: estimatedPixels,
      materializationRisk,
    },
    sources: Object.fromEntries(Object.entries(resolved).map(([key, item]) => [key, item.source])),
    chips: [
      chip("sampleFps", "Sample FPS", `${values.sampleFps} fps`, "Sampling load tuned for this goal."),
      chip("maxFrames", "Max frames", String(values.maxFrames), retryingHeavyAssetPrep ? "Reduced after the previous asset-prep failure." : "Capped before tracking starts."),
      chip("maxObjects", "Max objects", String(values.maxObjects), "Keeps review and memory bounded."),
      chip("effortPreset", "Effort", effort.label, effort.detail, "auto", effort.effortPreset === "high_quality" ? "warn" : "neutral"),
      chip("qualityPreset", "Scene sweep", qualityLabel, retryingHeavyAssetPrep ? "Safer retry profile." : "Recall balanced against cleanup cost."),
      chip("maskRefinementPreset", "Mask refinement", values.maskRefinementPreset, effort.requireRealTracking ? "Requires real tracking when available." : "Fallback remains diagnostic only.", "auto", effort.requireRealTracking ? "warn" : "neutral"),
      chip("device", "Device", String(values.device || "auto"), providerLabelText, resolved.device.source),
      chip(
        "materialization",
        "Materialization",
        materializationRisk === "high" ? "High risk" : materializationRisk === "watch" ? "Watch" : materializationRisk === "unknown" ? "Unknown" : "Within budget",
        estimatedPixels ? `${Math.round(estimatedPixels / 1_000_000)}M px worst-case / ${Math.round(budgetPixels / 1_000_000)}M budget.` : `${Math.round(budgetPixels / 1_000_000)}M px budget; video size unknown.`,
        "auto",
        materializationRisk === "high" ? "bad" : materializationRisk === "watch" ? "warn" : "ready",
      ),
    ],
  };
}

export function projectShellStateFromSnapshot(snapshot = {}) {
  const selectedProject = snapshot.selectedProject || snapshot.project || {};
  const projectName = String(snapshot.projectName || selectedProject.name || "").trim();
  const drawerOpen = snapshot.drawerOpen ?? snapshot.projectDrawerOpen ?? !Boolean(snapshot.sidebarCollapsed);
  return {
    format: "motionjson.local_ui_project_shell.v0.1",
    drawerOpen: Boolean(drawerOpen),
    sidebarCollapsed: !Boolean(drawerOpen),
    sidebarAriaHidden: String(!drawerOpen),
    sidebarContentAriaHidden: String(!drawerOpen),
    sidebarContentInert: !drawerOpen,
    projectButtonExpanded: String(Boolean(drawerOpen)),
    projectButtonLabel: projectName || "Project",
    projectButtonAriaLabel: projectName ? `Open project drawer for ${projectName}` : "Open project drawer",
    closeButtonText: "Close",
    closeButtonAriaLabel: "Close project drawer",
  };
}

export function reviewExportScreenStateFromSnapshot(snapshot = {}) {
  const mode = snapshot.mode === "export" || snapshot.reviewExportSubscreen === "export" ? "export" : "review";
  const rowCount = toInteger(snapshot.rowCount ?? snapshot.objectCount ?? snapshot.trackCount, 0);
  const reviewedCount = toInteger(snapshot.reviewedCount ?? snapshot.exportIncludedCount ?? snapshot.includedCount, 0);
  const movingReviewedCount = toInteger(snapshot.movingReviewedCount, 0);
  const exportStageValue = String(snapshot.exportStageValue || snapshot.exportStage?.value || "Package");
  const reviewStatusLabel = String(
    snapshot.reviewStatusLabel ||
      snapshot.reviewPrimaryLabel ||
      (snapshot.nextStatus === "done" ? "Ready" : snapshot.nextValue || "Needs review"),
  );
  const reviewNote = String(snapshot.reviewNote || snapshot.reviewReason || snapshot.nextDetail || "Review, correct, and export reviewed object tracks.");
  const exportNote = String(snapshot.exportNote || "Validate package readiness, included objects, rights notes, and handoff links before writing MotionJSON.");
  if (mode === "export") {
    return {
      format: "motionjson.local_ui_review_export_screen.v0.1",
      mode,
      kicker: "Export",
      title: "Export MotionJSON",
      guideTitle: "Export reviewed package",
      statusLabel: exportStageValue,
      note: exportNote,
      summary: "Validate the package, included objects, rights notes, and handoff links before writing files.",
      primaryLabel: snapshot.exportValidated ? "Export MotionJSON" : "Validate export",
      primaryAction: snapshot.exportValidated ? "export_reviewed" : "validate_export",
    };
  }
  return {
    format: "motionjson.local_ui_review_export_screen.v0.1",
    mode,
    kicker: "Review",
    title: "Review all objects",
    guideTitle: "Review before export",
    statusLabel: reviewStatusLabel,
    note: reviewNote,
    summary: rowCount
      ? movingReviewedCount
        ? `${movingReviewedCount} moving track${movingReviewedCount === 1 ? "" : "s"} ready for MotionJSON export`
        : `${reviewedCount} reviewed object${reviewedCount === 1 ? "" : "s"} ready`
      : "Object masks appear here after a run completes.",
    primaryLabel: snapshot.exportValidated ? "Continue to export" : "Validate reviewed objects",
    primaryAction: snapshot.exportValidated ? "continue_to_export" : "validate_export",
  };
}
