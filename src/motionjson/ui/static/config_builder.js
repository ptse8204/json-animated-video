export const RUN_CONFIG_SCHEMA = "motionjson.extraction_run_config.v0.1";

export const WIZARD_PRESETS = [
  {
    id: "trace_one_object",
    label: "Trace one object",
    discoveryMode: "manual_prompt",
    defaultMaskProvider: "mock",
    requiredTools: ["positive_point", "box"],
  },
  {
    id: "text_detector",
    label: "Find objects from text",
    discoveryMode: "text_detector",
    defaultMaskProvider: "mock",
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
    defaultMaskProvider: "mock",
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

export function buildRunConfig(input) {
  const preset = WIZARD_PRESETS.find((item) => item.id === input.presetId) || WIZARD_PRESETS[0];
  const advanced = { ...DEFAULT_ADVANCED, ...(input.advanced || {}) };
  const objectId = input.objectId || "object_0";
  const label = input.label || "selected_object";
  const video = input.video || {};
  const videoRef = video.id ? `local-ui://assets/${video.id}` : input.videoPath || "local-ui://assets/selected-video";
  const outputDir = input.outputDir || `out/motionjson-ui/${objectId}`;
  const providerName = input.maskProvider || preset.defaultMaskProvider || "mock";
  const prompts = (input.prompts || []).map((prompt) =>
    promptToConfig(prompt, {
      objectId,
      label,
      frameIndex: Number.isFinite(prompt.frameIndex) ? prompt.frameIndex : Number(advanced.keyframe || 0),
    }),
  );
  const discoveryConfig = {};
  const maxCandidates = Number(input.discoveryMaxCandidates || advanced.maxObjects || 12);
  if (preset.id === "text_detector") {
    discoveryConfig.mock = true;
    if (input.discoveryText) {
      discoveryConfig.text = input.discoveryText;
      discoveryConfig.labels = String(input.discoveryText)
        .split(/[,.]/)
        .map((part) => part.trim())
        .filter(Boolean);
      discoveryConfig.box_threshold = Number(advanced.boxThreshold);
      discoveryConfig.text_threshold = Number(advanced.textThreshold);
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
  if (["text_detector", "sam_auto_masks", "motion_foreground"].includes(preset.id)) {
    discoveryConfig.max_candidates = maxCandidates;
  }
  if (preset.id === "sam_auto_masks") {
    discoveryConfig.mock = true;
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
        checkpoint: advanced.model || null,
      },
      cache: {
        enabled: true,
        directory: ".motionjson-cache/masks",
      },
    },
    discovery: {
      mode: preset.discoveryMode,
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
    const discovery = lookup.get(discoveryMode);
    if (discovery && !discovery.available) {
      warnings.push(`${discovery.name}: ${discovery.reasons?.[0] || discovery.status || "discovery unavailable"}`);
    }
  }
  return warnings;
}
