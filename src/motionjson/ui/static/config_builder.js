export const RUN_CONFIG_SCHEMA = "motionjson.extraction_run_config.v0.1";

export const WIZARD_PRESETS = [
  {
    id: "auto_object_proposals",
    label: "Discover objects",
    discoveryMode: "auto_object_proposals",
    defaultMaskProvider: "sam2-local",
    requiredTools: ["keyframe"],
  },
  {
    id: "trace_one_object",
    label: "Trace one object",
    discoveryMode: "manual_prompt",
    defaultMaskProvider: "sam2-local",
    requiredTools: ["positive_point", "box"],
  },
  {
    id: "text_detector",
    label: "Find objects from text",
    discoveryMode: "text_detector",
    defaultMaskProvider: "sam2-local",
    requiredTools: ["label"],
  },
  {
    id: "class_detector",
    label: "Find known classes",
    discoveryMode: "class_detector",
    defaultMaskProvider: "sam2-local",
    requiredTools: ["label"],
  },
  {
    id: "motion_foreground",
    label: "Find moving objects",
    discoveryMode: "motion_foreground",
    defaultMaskProvider: "motion",
    requiredTools: ["keyframe"],
  },
  {
    id: "sam_auto_masks",
    label: "Propose all visible segments",
    discoveryMode: "sam_auto_masks",
    defaultMaskProvider: "sam2-local",
    requiredTools: ["keyframe"],
  },
  {
    id: "external_masks",
    label: "Import external masks",
    discoveryMode: "external_masks",
    defaultMaskProvider: "external",
    requiredTools: ["mask"],
  },
];

export const DEFAULT_ADVANCED = {
  sampleFps: 12,
  maxFrames: 48,
  minArea: 100,
  maxAreaRatio: 0.65,
  stabilityThreshold: 0.82,
  overlapThreshold: 0.72,
  boxThreshold: 0.35,
  textThreshold: 0.25,
  motionSensitivity: 32,
  maxObjects: 12,
  qualityPreset: "clean",
  traceEverythingMode: false,
  traceEverythingAcknowledged: false,
  classPreset: "common_objects",
  simplify: 0.006,
  lowerHsv: [0, 80, 80],
  upperHsv: [12, 255, 255],
  keyframe: 0,
  device: "cpu",
  model: "",
  externalMaskDir: "",
  outputMode: "authoring",
};

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function clientPointToVideoPoint({ clientX, clientY, rect, videoWidth, videoHeight }) {
  if (!rect || !videoWidth || !videoHeight || !rect.width || !rect.height) {
    return { x: 0, y: 0, insideVideo: false };
  }
  const scale = Math.min(rect.width / videoWidth, rect.height / videoHeight);
  const displayedWidth = videoWidth * scale;
  const displayedHeight = videoHeight * scale;
  const offsetX = (rect.width - displayedWidth) / 2;
  const offsetY = (rect.height - displayedHeight) / 2;
  const localX = clientX - rect.left - offsetX;
  const localY = clientY - rect.top - offsetY;
  const insideVideo = localX >= 0 && localY >= 0 && localX <= displayedWidth && localY <= displayedHeight;
  return {
    x: Math.round(clamp(localX / scale, 0, videoWidth - 1)),
    y: Math.round(clamp(localY / scale, 0, videoHeight - 1)),
    insideVideo,
  };
}

export function boxFromPoints(start, end) {
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  return {
    x,
    y,
    w: Math.max(1, Math.abs(end.x - start.x)),
    h: Math.max(1, Math.abs(end.y - start.y)),
  };
}

export function parseKeyframes(value) {
  const values = Array.isArray(value)
    ? value
    : value instanceof Set
      ? [...value]
      : String(value ?? "")
          .split(/[,\s]+/)
          .filter(Boolean);
  return [...new Set(values.map((item) => Number.parseInt(item, 10)).filter((number) => Number.isFinite(number) && number >= 0))].sort(
    (a, b) => a - b,
  );
}

export function promptToConfig(prompt, { objectId, label, frameIndex }) {
  if (prompt.kind === "box") {
    return {
      kind: "box",
      frame_index: frameIndex,
      object_id: objectId,
      label,
      data: { x: prompt.x, y: prompt.y, w: prompt.w, h: prompt.h },
    };
  }
  if (prompt.kind === "mask") {
    return {
      kind: "mask",
      frame_index: frameIndex,
      object_id: objectId,
      label,
      data: { strokes: prompt.strokes || [], radius: prompt.radius || 12, mode: prompt.mode || "paint" },
    };
  }
  return {
    kind: prompt.kind,
    frame_index: frameIndex,
    object_id: objectId,
    label,
    data: { x: prompt.x, y: prompt.y },
  };
}

export function objectDiscoveryConfig(input, advanced) {
  const qualityPreset = advanced.traceEverythingMode ? "trace_everything" : advanced.qualityPreset || input.qualityPreset || "clean";
  const keyframes = parseKeyframes(advanced.keyframe ?? advanced.keyframes ?? input.keyframes ?? 0);
  const presets = {
    clean: {
      intent: "discover_objects_clean",
      keyframePolicy: "scene_changes",
      maxKeyframes: 3,
      frameInterval: null,
      maxCandidatesPerKeyframe: 32,
      maxObjects: Number(advanced.maxObjects || 12),
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
  const preset = presets[qualityPreset] || presets.clean;
  return {
    mock: Boolean(input.debugMockMode),
    qualityPreset,
    intent: preset.intent,
    providerPreference: input.debugMockMode ? "mock" : "sam2-local",
    sam2Checkpoint: input.localSam2CheckpointPath || advanced.localSam2CheckpointPath || null,
    sam2ModelConfig: input.localSam2ModelConfigPath || advanced.localSam2ModelConfigPath || null,
    sam2Device: input.localSam2Device || advanced.localSam2Device || advanced.device || "auto",
    keyframePolicy: preset.keyframePolicy,
    keyframes,
    maxKeyframes: preset.maxKeyframes,
    frameInterval: preset.frameInterval,
    maxCandidatesPerKeyframe: preset.maxCandidatesPerKeyframe,
    maxObjects: preset.maxObjects,
    minMaskArea: preset.minMaskArea,
    maxMaskAreaRatio: preset.maxMaskAreaRatio,
    dedupeIou: preset.dedupeIou,
    stabilityThreshold: preset.stabilityThreshold,
    motionScoreWeight: 0.35,
    rejectWholeFrame: true,
    rejectBackgroundLike: true,
    trackSelectedOnly: preset.trackSelectedOnly,
    trackTopCandidates: preset.trackTopCandidates,
    requireReview: true,
    writeRejectedCandidates: true,
    requireExplicitCostWarning: preset.requireExplicitCostWarning,
    ...(qualityPreset === "trace_everything" ? { costWarningAcknowledged: advanced.traceEverythingAcknowledged === true } : {}),
  };
}

export function buildRunConfig(input) {
  const preset = WIZARD_PRESETS.find((item) => item.id === input.presetId) || WIZARD_PRESETS[0];
  const advanced = { ...DEFAULT_ADVANCED, ...(input.advanced || {}) };
  const objectId = input.objectId || "object_0";
  const label = input.label || "selected_object";
  const video = input.video || {};
  const videoRef = video.id ? `local-ui://assets/${video.id}` : input.videoPath || "local-ui://assets/selected-video";
  const outputDir = input.outputDir || `out/motionjson-ui/${objectId}`;
  const providerName = input.maskProvider || preset.defaultMaskProvider || (input.debugMockMode ? "mock" : "sam2-local");
  let discoveryMode = preset.discoveryMode;
  if (preset.id === "text_detector" && ["sam3-local", "sam3-hosted"].includes(input.textDiscoveryProvider)) {
    discoveryMode = "sam3_concept";
  }
  const prompts = (input.prompts || []).map((prompt) =>
    promptToConfig(prompt, {
      objectId,
      label,
      frameIndex: Number.isFinite(prompt.frameIndex) ? prompt.frameIndex : Number(advanced.keyframe || 0),
    }),
  );
  const discoveryConfig = {};
  const maxCandidates = Number(input.discoveryMaxCandidates || advanced.maxObjects || 12);
  if (preset.id === "auto_object_proposals") {
    Object.assign(discoveryConfig, objectDiscoveryConfig(input, advanced));
  }
  if (preset.id === "text_detector") {
    if (input.discoveryText) {
      discoveryConfig.text = input.discoveryText;
      discoveryConfig.labels = String(input.discoveryText)
        .split(/[,.]/)
        .map((part) => part.trim())
        .filter(Boolean);
      discoveryConfig.box_threshold = Number(advanced.boxThreshold);
      discoveryConfig.text_threshold = Number(advanced.textThreshold);
    }
    if (["sam3-local", "sam3-hosted"].includes(input.textDiscoveryProvider)) {
      const hosted = input.textDiscoveryProvider === "sam3-hosted";
      discoveryConfig.concept = input.discoveryText || "";
      discoveryConfig.providerPreference = hosted ? "sam3-hosted" : "sam3-local";
      discoveryConfig.hosted = hosted;
      discoveryConfig.hostedProfile = hosted ? input.hostedSam3ProfileId || "roboflow-sam3-pcs" : null;
      discoveryConfig.model = hosted ? input.hostedSam3Model || null : input.localSam3ModelPath || advanced.localSam3ModelPath || null;
      discoveryConfig.sam3ModelPath = input.localSam3ModelPath || advanced.localSam3ModelPath || null;
      discoveryConfig.sam3Device = input.localSam3Device || advanced.localSam3Device || advanced.device || "cuda";
      discoveryConfig.allowNetwork = hosted ? Boolean(input.hostedSam3AllowHosted) : false;
      discoveryConfig.acknowledgeCostPrivacy = hosted ? Boolean(input.hostedSam3AllowHosted) : false;
      discoveryConfig.mock = false;
    } else {
      discoveryConfig.mock = Boolean(input.debugMockMode);
    }
  }
  if (input.discoveryClasses) {
    discoveryConfig.classes = Array.isArray(input.discoveryClasses)
      ? input.discoveryClasses
      : String(input.discoveryClasses)
          .split(/[,.]/)
          .map((part) => part.trim())
          .filter(Boolean);
  }
  if (preset.id === "class_detector") {
    discoveryConfig.mock = Boolean(input.debugMockMode);
    discoveryConfig.class_preset = input.classPreset || advanced.classPreset || "common_objects";
    discoveryConfig.confidence_threshold = Number(advanced.boxThreshold);
  }
  if (["text_detector", "class_detector", "sam_auto_masks", "motion_foreground"].includes(preset.id)) {
    discoveryConfig.max_candidates = maxCandidates;
  }
  if (preset.id === "sam_auto_masks") {
    discoveryConfig.mock = Boolean(input.debugMockMode);
    discoveryConfig.providerPreference = input.debugMockMode ? "mock" : "sam2-local";
    discoveryConfig.sam2Checkpoint = input.localSam2CheckpointPath || advanced.localSam2CheckpointPath || null;
    discoveryConfig.sam2ModelConfig = input.localSam2ModelConfigPath || advanced.localSam2ModelConfigPath || null;
    discoveryConfig.sam2Device = input.localSam2Device || advanced.localSam2Device || advanced.device || "auto";
    discoveryConfig.min_area = Number(advanced.minArea);
    discoveryConfig.max_area_ratio = Number(advanced.maxAreaRatio);
    discoveryConfig.stability_threshold = Number(advanced.stabilityThreshold);
    discoveryConfig.overlap_threshold = Number(advanced.overlapThreshold);
    discoveryConfig.reject_background = true;
  }
  if (preset.id === "motion_foreground") {
    discoveryConfig.threshold = Number(advanced.motionSensitivity);
    discoveryConfig.min_area = Number(advanced.minArea);
  }
  if (preset.id === "external_masks" && advanced.externalMaskDir) {
    discoveryConfig.mask_dirs = { [objectId]: advanced.externalMaskDir };
  }
  return {
    schema: RUN_CONFIG_SCHEMA,
    input: { path: videoRef },
    output: { directory: outputDir },
    objects: [
      {
        object_id: objectId,
        label,
        ...(preset.id === "external_masks" && advanced.externalMaskDir ? { mask_dir: advanced.externalMaskDir } : {}),
      },
    ],
    sampling: {
      sample_fps: Number(advanced.sampleFps),
      max_frames: Number(advanced.maxFrames),
    },
    provider: {
      name: providerName,
      threshold: {
        lower_hsv: advanced.lowerHsv,
        upper_hsv: advanced.upperHsv,
      },
      external: {
        mask_dir: advanced.externalMaskDir || null,
      },
      sam2: {
        device: advanced.device || "cpu",
        prompt_frame: Number(advanced.keyframe || 0),
        checkpoint: input.localSam2CheckpointPath || advanced.localSam2CheckpointPath || advanced.model || null,
        model_config: input.localSam2ModelConfigPath || advanced.localSam2ModelConfigPath || null,
        hosted_config:
          providerName === "sam2-hosted"
            ? {
                profile: input.hostedSam2ProfileId || "replicate-sam2-video",
                hostedProfile: input.hostedSam2ProfileId || "replicate-sam2-video",
                ...(advanced.model && advanced.model !== "auto" ? { model: advanced.model } : {}),
              }
            : {},
        hosted_allow_network: providerName === "sam2-hosted" ? Boolean(input.hostedSam2AllowHosted) : false,
      },
      cache: {
        enabled: true,
        directory: ".motionjson-cache/masks",
      },
    },
    discovery: {
      mode: discoveryMode,
      config: discoveryConfig,
    },
    prompts,
    filters: {
      min_area: Number(advanced.minArea),
      simplify_ratio: Number(advanced.simplify),
    },
    export: {
      output_mode: advanced.outputMode,
      feather: 0,
      layer_padding: 4,
      sprite_format: "webp",
      production_avif: false,
    },
    debug: {
      benchmark: false,
      benchmark_iterations: 3,
    },
    rights: {
      source_type: "user_upload",
      source_uri: videoRef,
      display_text: "Local UI source video",
      license: "user_uploaded_unverified",
      license_name: "User uploaded - rights unverified",
      license_scope: "unknown",
      creator_approved: false,
      commercial_use: false,
    },
  };
}

export function validateRunConfigShape(config) {
  const errors = [];
  if (config.schema !== RUN_CONFIG_SCHEMA) errors.push("schema must be MotionJSON extraction run config v0.1");
  if (!config.input?.path) errors.push("input.path is required");
  if (!config.output?.directory) errors.push("output.directory is required");
  if (!Array.isArray(config.objects) || config.objects.length === 0) errors.push("at least one object is required");
  if (config.provider?.name === "external" && !config.provider?.external?.mask_dir && !config.objects?.some((item) => item.mask_dir)) {
    errors.push("external masks require a mask directory");
  }
  for (const prompt of config.prompts || []) {
    if (["point", "positive_point", "negative_point"].includes(prompt.kind)) {
      if (!Number.isInteger(prompt.data?.x) || !Number.isInteger(prompt.data?.y)) {
        errors.push(`${prompt.kind} prompt requires native x/y coordinates`);
      }
    }
    if (prompt.kind === "box" && (!Number.isInteger(prompt.data?.w) || prompt.data.w <= 0 || !Number.isInteger(prompt.data?.h) || prompt.data.h <= 0)) {
      errors.push("box prompt requires positive native width and height");
    }
  }
  return errors;
}

export function providerWarnings(config, capabilities) {
  const providers = capabilities?.providers || [];
  const lookup = new Map(providers.map((provider) => [provider.name, provider]));
  const warnings = [];
  const provider = lookup.get(config.provider?.name);
  if (provider && !provider.available) {
    warnings.push(`${provider.name}: ${provider.reasons?.[0] || provider.status || "provider unavailable"}`);
  }
  const discoveryMode = config.discovery?.mode;
  if (discoveryMode) {
    const preference = config.discovery?.config?.providerPreference;
    const discoveryName = preference === "sam3-hosted" || preference === "sam3-local" ? preference : discoveryMode;
    const discovery = lookup.get(discoveryName) || lookup.get(String(discoveryMode).replaceAll("_", "-"));
    if (discovery && !discovery.available) {
      warnings.push(`${discovery.name}: ${discovery.reasons?.[0] || discovery.status || "discovery unavailable"}`);
    }
  }
  if (config.provider?.name === "sam2-hosted" && !config.provider?.sam2?.hosted_allow_network) {
    warnings.push("sam2-hosted needs hosted cost/privacy confirmation before extraction can send video frames.");
  }
  if (config.discovery?.config?.providerPreference === "sam3-hosted" && !config.discovery?.config?.allowNetwork) {
    warnings.push("sam3-hosted needs hosted cost/privacy confirmation before discovery can send sampled frames.");
  }
  return warnings;
}
