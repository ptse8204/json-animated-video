const MATERIALIZATION_BUDGET_PIXELS = 64_000_000;

const toNumber = (value, fallback = 0) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

const toInteger = (value, fallback = 0) => {
  const number = Number.parseInt(value, 10);
  return Number.isFinite(number) ? number : fallback;
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const roundOne = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.round(number * 10) / 10;
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
  videoCoverage: "Shows whether the sampled-frame budget covers the whole clip or only a sparse/partial pass.",
  workload: "Estimated extraction load from duration, resolution, sampled frames, object count, and prior failures.",
  materialization: "Worst-case per-object cutout work before writing preview PNGs and spritesheets.",
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
  let duration = toNumber(snapshot.duration ?? snapshot.videoDuration ?? video.duration ?? metadata.duration, 0);
  const sourceFps = toNumber(
    snapshot.sourceFps ?? snapshot.fps ?? snapshot.frameRate ?? video.sourceFps ?? video.fps ?? video.frameRate ?? metadata.sourceFps ?? metadata.fps,
    0,
  );
  const sourceFrameCount = toInteger(
    snapshot.sourceFrameCount ?? snapshot.frameCount ?? snapshot.totalFrames ?? video.sourceFrameCount ?? video.frameCount ?? video.totalFrames ?? metadata.frameCount,
    0,
  );
  if (duration <= 0 && sourceFps > 0 && sourceFrameCount > 0) {
    duration = sourceFrameCount / sourceFps;
  }
  const byteSize = toInteger(snapshot.byteSize ?? snapshot.fileSize ?? video.byteSize ?? video.fileSize ?? metadata.byteSize, 0);
  const bitrate = toInteger(snapshot.bitrate ?? video.bitrate ?? metadata.bitrate, 0);
  return {
    width,
    height,
    duration,
    sourceFps,
    sourceFrameCount,
    byteSize,
    bitrate,
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

function videoQualityTier(video) {
  if (!video.framePixels) return "unknown";
  if (video.framePixels >= 3840 * 2160) return "uhd";
  if (video.framePixels >= 2560 * 1440) return "qhd";
  if (video.framePixels >= 1920 * 1080) return "full_hd";
  if (video.framePixels >= 1280 * 720) return "hd";
  return "small";
}

function durationTier(duration) {
  if (!duration) return "unknown";
  if (duration <= 15) return "short";
  if (duration <= 45) return "medium";
  if (duration <= 120) return "long";
  return "very_long";
}

function effortSamplingPolicy(effortPreset, { retryingHeavyAssetPrep = false, videoTier = "unknown", preferredDevice = "" } = {}) {
  const base = {
    fast: {
      targetFps: 6,
      retryFps: 4,
      frameBudget: 120,
      retryFrameBudget: 90,
      maxObjects: 12,
      retryMaxObjects: 8,
      pointsPerBatch: 48,
      minUsefulFps: 2,
    },
    balanced: {
      targetFps: 8,
      retryFps: 6,
      frameBudget: 180,
      retryFrameBudget: 120,
      maxObjects: 24,
      retryMaxObjects: 12,
      pointsPerBatch: 64,
      minUsefulFps: 3,
    },
    high_quality: {
      targetFps: 12,
      retryFps: 8,
      frameBudget: preferredDevice === "cuda" ? 420 : 360,
      retryFrameBudget: preferredDevice === "cuda" ? 260 : 220,
      maxObjects: 32,
      retryMaxObjects: 16,
      pointsPerBatch: 64,
      minUsefulFps: 4,
    },
  }[effortPreset] || {};
  const policy = { ...base };
  if (retryingHeavyAssetPrep) {
    policy.targetFps = policy.retryFps || policy.targetFps;
    policy.frameBudget = policy.retryFrameBudget || policy.frameBudget;
    policy.maxObjects = policy.retryMaxObjects || policy.maxObjects;
    policy.pointsPerBatch = Math.min(policy.pointsPerBatch || 64, 32);
  }
  if (videoTier === "uhd") {
    policy.targetFps = roundOne((policy.targetFps || 8) * 0.67);
    policy.frameBudget = Math.min(policy.frameBudget || 120, effortPreset === "high_quality" ? 300 : 180);
    policy.maxObjects = Math.min(policy.maxObjects || 12, effortPreset === "high_quality" ? 20 : 12);
    policy.pointsPerBatch = Math.min(policy.pointsPerBatch || 64, 32);
  } else if (videoTier === "qhd") {
    policy.targetFps = roundOne((policy.targetFps || 8) * 0.8);
    policy.frameBudget = Math.min(policy.frameBudget || 120, effortPreset === "high_quality" ? 320 : 180);
    policy.maxObjects = Math.min(policy.maxObjects || 12, effortPreset === "high_quality" ? 24 : 16);
    policy.pointsPerBatch = Math.min(policy.pointsPerBatch || 64, 48);
  }
  return policy;
}

function sampledFramePlan({ effort, presetId, video, retryingHeavyAssetPrep, preferredDevice }) {
  const tier = videoQualityTier(video);
  const policy = effortSamplingPolicy(effort.effortPreset, { retryingHeavyAssetPrep, videoTier: tier, preferredDevice });
  let targetFps = presetId === "trace_all_objects" ? policy.targetFps : presetId === "text_detector" ? 8 : 12;
  if (video.sourceFps > 0) targetFps = Math.min(targetFps, video.sourceFps);
  targetFps = Math.max(0.1, roundOne(targetFps));
  let maxFrames =
    presetId === "trace_all_objects"
      ? effort.maxFrames
      : presetId === "trace_one_object"
        ? 48
        : presetId === "text_detector"
          ? 32
          : 48;
  let coverageStatus = "unknown";
  let coverageRatio = 0;
  let coverageSeconds = 0;
  const targetFullCoverageFrames =
    video.duration > 0
      ? Math.max(1, Math.ceil(video.duration * targetFps))
      : video.sourceFps > 0 && video.sourceFrameCount > 0
        ? Math.max(1, Math.ceil(video.sourceFrameCount * Math.min(1, targetFps / video.sourceFps)))
        : 0;

  if (presetId === "trace_all_objects" && targetFullCoverageFrames > 0) {
    const frameBudget = Math.max(effort.maxFrames, toInteger(policy.frameBudget, effort.maxFrames));
    if (targetFullCoverageFrames <= frameBudget) {
      maxFrames = targetFullCoverageFrames;
      coverageStatus = "full";
    } else if (video.duration > 0) {
      targetFps = Math.max(0.1, roundOne(frameBudget / video.duration));
      maxFrames = frameBudget;
      coverageStatus = targetFps >= (policy.minUsefulFps || 2) ? "full_lower_density" : "sparse_full";
    } else {
      maxFrames = frameBudget;
      coverageStatus = "capped_unknown_duration";
    }
  } else if (video.duration > 0) {
    maxFrames = Math.max(1, Math.min(maxFrames, Math.ceil(video.duration * targetFps)));
    coverageStatus = "full";
  }

  if (video.duration > 0 && targetFps > 0) {
    coverageSeconds = maxFrames / targetFps;
    coverageRatio = clamp(coverageSeconds / video.duration, 0, 1);
  } else if (targetFullCoverageFrames > 0) {
    coverageRatio = clamp(maxFrames / targetFullCoverageFrames, 0, 1);
  }
  return {
    sampleFps: targetFps,
    maxFrames: Math.max(1, Math.ceil(maxFrames)),
    targetFullCoverageFrames,
    coverageStatus,
    coverageRatio,
    coverageSeconds,
    videoQualityTier: tier,
    durationTier: durationTier(video.duration),
    policy,
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
  const traceEverythingMode = Boolean(snapshot.traceEverythingMode);
  const preferredDevice = String(snapshot.preferredDevice || snapshot.accelerator || "").toLowerCase();
  const samplingPlan = sampledFramePlan({ effort, presetId, video, retryingHeavyAssetPrep, preferredDevice });
  let qualityPreset = traceEverythingMode
    ? "trace_everything"
    : String(snapshot.qualityPreset || (presetId === "trace_all_objects" ? effort.qualityPreset : "clean"));
  let sampleFps = samplingPlan.sampleFps;
  let maxFrames = samplingPlan.maxFrames;
  let maxObjects =
    presetId === "trace_one_object"
      ? 1
      : presetId === "text_detector"
        ? 6
        : presetId === "class_detector" || presetId === "motion_foreground"
          ? 8
          : presetId === "trace_all_objects"
            ? samplingPlan.policy.maxObjects || effort.maxObjects
            : objectDiscoveryDefaults(qualityPreset).maxObjects;
  let device =
    presetId === "trace_all_objects" && providerId === "sam3-local" && preferredDevice === "cuda"
      ? "cuda"
      : String(snapshot.device || "auto") || "auto";
  const budgetPixels = Math.max(1, toInteger(snapshot.materializationBudgetPixels, MATERIALIZATION_BUDGET_PIXELS));

  if (retryingHeavyAssetPrep && presetId === "trace_all_objects") {
    qualityPreset = effort.effortPreset === "high_quality" ? "balanced" : "clean";
    sampleFps = samplingPlan.sampleFps;
    maxFrames = samplingPlan.maxFrames;
    maxObjects = samplingPlan.policy.maxObjects || maxObjects;
    device = providerId === "sam3-local" && preferredDevice === "cuda" ? "cuda" : "auto";
  } else if (samplingPlan.videoQualityTier === "uhd" && presetId === "trace_all_objects") {
    qualityPreset = qualityPreset === "maximum_recall" ? "balanced" : qualityPreset;
    maxObjects = samplingPlan.policy.maxObjects || maxObjects;
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
    pointsPerBatch: { value: samplingPlan.policy.pointsPerBatch || 64, source: "auto" },
  };
  const values = Object.fromEntries(Object.entries(resolved).map(([key, item]) => [key, item.value]));
  const estimatedPixels = video.framePixels > 0 ? video.framePixels * Math.max(1, values.maxFrames) : 0;
  const totalWorkPixels = estimatedPixels * Math.max(1, values.maxObjects);
  const materializationRisk =
    !estimatedPixels ? "unknown" : estimatedPixels > budgetPixels ? "high" : estimatedPixels > budgetPixels * 0.55 ? "watch" : "normal";
  const workloadRisk =
    !totalWorkPixels
      ? "unknown"
      : totalWorkPixels > budgetPixels * 16 || samplingPlan.coverageStatus === "sparse_full"
        ? "high"
        : totalWorkPixels > budgetPixels * 8 || samplingPlan.coverageStatus === "full_lower_density"
          ? "watch"
          : "normal";
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
  const resolutionLabel = video.width && video.height ? `${video.width}x${video.height}` : "unknown size";
  const durationLabel = video.duration ? `${Math.round(video.duration)}s` : "unknown length";
  const sourceFpsLabel = video.sourceFps ? `${roundOne(video.sourceFps)} source fps` : "source fps unknown";
  const coverageLabel =
    samplingPlan.coverageStatus === "full"
      ? "Full clip"
      : samplingPlan.coverageStatus === "full_lower_density"
        ? "Full clip, lower density"
        : samplingPlan.coverageStatus === "sparse_full"
          ? "Sparse full clip"
          : samplingPlan.coverageStatus === "capped_unknown_duration"
            ? "Capped, duration unknown"
            : "Unknown";
  const recommendationReasons = [
    video.duration ? `duration:${roundOne(video.duration)}s` : "duration:unknown",
    video.framePixels ? `resolution:${resolutionLabel}` : "resolution:unknown",
    video.sourceFps ? `sourceFps:${roundOne(video.sourceFps)}` : "sourceFps:unknown",
    `effort:${effort.effortPreset}`,
    retryingHeavyAssetPrep ? `priorFailure:${failureReason}` : "",
    samplingPlan.videoQualityTier === "uhd" || samplingPlan.videoQualityTier === "qhd" ? `resolutionTier:${samplingPlan.videoQualityTier}` : "",
  ].filter(Boolean);
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
      totalWorkEstimatedPixels: totalWorkPixels,
      materializationRisk,
      workloadRisk,
      pointsPerBatch: values.pointsPerBatch,
      videoDurationSeconds: video.duration,
      videoWidth: video.width,
      videoHeight: video.height,
      sourceFps: video.sourceFps,
      sourceFrameCount: video.sourceFrameCount,
      targetFullCoverageFrames: samplingPlan.targetFullCoverageFrames,
      coverageRatio: samplingPlan.coverageRatio,
      coverageSeconds: samplingPlan.coverageSeconds,
      coverageStatus: samplingPlan.coverageStatus,
      videoQualityTier: samplingPlan.videoQualityTier,
      durationTier: samplingPlan.durationTier,
      recommendationReasons,
    },
    sources: Object.fromEntries(Object.entries(resolved).map(([key, item]) => [key, item.source])),
    chips: [
      chip(
        "sampleFps",
        "Sample FPS",
        `${values.sampleFps} fps`,
        `${durationLabel}, ${sourceFpsLabel}; tuned to avoid front-only sampling.`,
      ),
      chip(
        "maxFrames",
        "Max frames",
        String(values.maxFrames),
        retryingHeavyAssetPrep
          ? `Retry keeps ${coverageLabel.toLowerCase()} coverage after the previous asset-prep failure.`
          : `${coverageLabel}; ${samplingPlan.targetFullCoverageFrames || values.maxFrames} frames would cover the target density.`,
      ),
      chip("maxObjects", "Max objects", String(values.maxObjects), "Keeps review and memory bounded."),
      chip("effortPreset", "Effort", effort.label, effort.detail, "auto", effort.effortPreset === "high_quality" ? "warn" : "neutral"),
      chip("qualityPreset", "Scene sweep", qualityLabel, retryingHeavyAssetPrep ? "Safer retry profile." : "Recall balanced against cleanup cost."),
      chip("maskRefinementPreset", "Mask refinement", values.maskRefinementPreset, effort.requireRealTracking ? "Requires real tracking when available." : "Fallback remains diagnostic only.", "auto", effort.requireRealTracking ? "warn" : "neutral"),
      chip(
        "videoCoverage",
        "Video fit",
        coverageLabel,
        `${resolutionLabel}, ${durationLabel}; ${Math.round((samplingPlan.coverageRatio || 0) * 100)}% estimated coverage.`,
        "auto",
        samplingPlan.coverageStatus === "sparse_full" ? "bad" : samplingPlan.coverageStatus === "full_lower_density" ? "warn" : "ready",
      ),
      chip(
        "workload",
        "Workload",
        workloadRisk === "high" ? "High" : workloadRisk === "watch" ? "Watch" : workloadRisk === "unknown" ? "Unknown" : "Normal",
        totalWorkPixels ? `${Math.round(totalWorkPixels / 1_000_000)}M px total estimate across ${values.maxObjects} objects.` : "Video size unknown; inspect the preview metadata.",
        "auto",
        workloadRisk === "high" ? "bad" : workloadRisk === "watch" ? "warn" : "ready",
      ),
      chip("device", "Device", String(values.device || "auto"), providerLabelText, resolved.device.source),
      chip(
        "materialization",
        "Materialization",
        materializationRisk === "high" ? "High risk" : materializationRisk === "watch" ? "Watch" : materializationRisk === "unknown" ? "Unknown" : "Within budget",
        estimatedPixels ? `${Math.round(estimatedPixels / 1_000_000)}M px per object / ${Math.round(budgetPixels / 1_000_000)}M budget.` : `${Math.round(budgetPixels / 1_000_000)}M px budget; video size unknown.`,
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
