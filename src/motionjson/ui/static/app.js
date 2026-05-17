const MotionJSONUI = (() => {
  const API_ROUTES = [
    "/api/health",
    "/api/capabilities",
    "/api/projects",
    "/api/run-config/defaults",
    "/api/run-config/validate",
    "/api/videos",
    "/api/videos/{videoId}/content",
    "/api/jobs",
    "/api/jobs/{jobId}",
    "/api/jobs/{jobId}/events",
    "/api/jobs/{jobId}/artifacts",
    "/api/jobs/{jobId}/review",
    "/api/jobs/{jobId}/corrections",
    "/api/jobs/{jobId}/track-edits",
    "/api/jobs/{jobId}/validate",
    "/api/jobs/{jobId}/exports",
    "/api/progress",
    "/api/artifacts",
    "/api/exports/formats",
    "/api/projects/{projectId}/imports/motionjson",
  ];

  const RUN_CONFIG_SCHEMA = "motionjson.extraction_run_config.v0.1";
  const CORRECTION_STATE_FORMAT = "motionjson.local_ui_corrections.v0.1";
  const TERMINAL_JOB_STATUSES = new Set(["succeeded", "failed", "canceled", "cancelled"]);
  const LOCAL_JOB_PROVIDERS = new Set(["mock", "threshold", "external"]);
  const TRACK_COLORS = ["#10a37f", "#2f80ed", "#9a6a12", "#6046a5", "#b42318", "#0f766e"];
  const EXPORT_PRESET_DEFAULTS = {
    compact: { includeMasks: false, includeContours: false, includePreview: true },
    debug: { includeMasks: true, includeContours: true, includePreview: true },
    "vector-heavy": { includeMasks: false, includeContours: true, includePreview: true },
    "raster-fallback": { includeMasks: true, includeContours: false, includePreview: true },
  };

  const PRESETS = {
    trace_one_object: {
      label: "Trace one object",
      discoveryMode: "manual_prompt",
      maskProvider: null,
      outputMode: "authoring",
    },
    text_detector: {
      label: "Find objects from text",
      discoveryMode: "text_detector",
      maskProvider: "mock",
      outputMode: "authoring",
    },
    sam_auto_masks: {
      label: "Propose all visible segments",
      discoveryMode: "sam_auto_masks",
      maskProvider: "mock",
      outputMode: "authoring",
    },
    motion_foreground: {
      label: "Find moving objects",
      discoveryMode: "motion_foreground",
      maskProvider: "motion",
      outputMode: "authoring",
    },
    external_masks: {
      label: "Import external masks",
      discoveryMode: "external_masks",
      maskProvider: "external",
      outputMode: "authoring",
    },
    review_existing: {
      label: "Review existing result",
      discoveryMode: "manual_prompt",
      maskProvider: "mock",
      outputMode: "authoring",
    },
  };

  const EMPTY_SAM2 = {
    checkpoint: null,
    model_config: null,
    device: null,
    prompt_frame: 0,
    endpoint: null,
    auth_env: "HOSTED_SEGMENTATION_API_KEY",
    endpoint_env: "HOSTED_SEGMENTATION_URL",
    hosted_config: {},
    hosted_allow_network: false,
  };

  const emptyCorrectionState = (jobId = "") => ({
    format: CORRECTION_STATE_FORMAT,
    jobId,
    trackEdits: {},
    syntheticTracks: [],
    history: [],
    mergeSuggestions: [],
    loaded: false,
    persistenceStatus: "not_loaded",
    persistenceMessage: "Correction state has not been loaded yet.",
  });

  const defaultState = () => ({
    health: null,
    capabilities: null,
    runDefaults: null,
    exportFormats: null,
    projects: [],
    selectedProjectId: "",
    videos: [],
    selectedVideoId: "",
    jobs: [],
    selectedJobId: "",
    selectedJob: null,
    jobReview: null,
    jobEvents: [],
    jobArtifacts: [],
    reviewTracks: [],
    trackVisibility: {},
    correctionState: emptyCorrectionState(),
    exportValidation: null,
    exportResult: null,
    importStatus: "",
    selectedCorrectionTrackId: "",
    mergeSelection: new Set(),
    runConfigsByJob: {},
    lastRunConfig: null,
    polling: false,
    errors: {},
    selectedPreset: "trace_one_object",
    activeTool: "point",
    pointKind: "positive_point",
    prompts: [],
    strokes: [],
    keyframes: new Set([0]),
    selectedPromptId: "",
    pointer: null,
    draftBox: null,
    activeStroke: null,
    previewObjectUrl: "",
    video: {
      width: 0,
      height: 0,
      duration: 0,
      currentFrame: 0,
      loadedName: "",
    },
  });

  const state = defaultState();

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const toNumber = (value, fallback = 0) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  };

  const toInteger = (value, fallback = 0) => {
    const number = Number.parseInt(value, 10);
    return Number.isFinite(number) ? number : fallback;
  };

  const roundPixel = (value) => Math.max(0, Math.round(value));

  const asArray = (value) => {
    if (value == null) return [];
    return Array.isArray(value) ? value : [value];
  };

  const escapeHtml = (value) =>
    String(value).replace(
      /[&<>"']/g,
      (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]),
    );

  const escapeAttribute = escapeHtml;

  function slugObjectId(value, fallback = "object_0") {
    const slug = String(value || "")
      .trim()
      .replace(/[^A-Za-z0-9_-]+/g, "_")
      .replace(/^_+|_+$/g, "");
    return /^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(slug) ? slug : fallback;
  }

  function parseCsv(value) {
    return String(value || "")
      .split(/[,.]/)
      .map((part) => part.trim())
      .filter(Boolean);
  }

  function parseKeyframes(value) {
    if (value instanceof Set) return [...value].map((item) => Math.max(0, Math.round(Number(item) || 0))).sort((a, b) => a - b);
    return String(value || "")
      .split(/[,\s]+/)
      .map((part) => Number.parseInt(part, 10))
      .filter((number) => Number.isFinite(number) && number >= 0)
      .sort((a, b) => a - b);
  }

  function containedVideoRect(containerWidth, containerHeight, videoWidth, videoHeight) {
    if (!containerWidth || !containerHeight || !videoWidth || !videoHeight) {
      return { x: 0, y: 0, width: 0, height: 0, scale: 1 };
    }
    const scale = Math.min(containerWidth / videoWidth, containerHeight / videoHeight);
    const width = videoWidth * scale;
    const height = videoHeight * scale;
    return {
      x: (containerWidth - width) / 2,
      y: (containerHeight - height) / 2,
      width,
      height,
      scale,
    };
  }

  function mapClientPointToVideo(clientX, clientY, bounds, videoWidth, videoHeight) {
    const view = containedVideoRect(bounds.width, bounds.height, videoWidth, videoHeight);
    const localX = clientX - bounds.left;
    const localY = clientY - bounds.top;
    const inside =
      view.width > 0 &&
      view.height > 0 &&
      localX >= view.x &&
      localY >= view.y &&
      localX <= view.x + view.width &&
      localY <= view.y + view.height;
    const x = clamp((localX - view.x) / view.scale, 0, Math.max(0, videoWidth - 1));
    const y = clamp((localY - view.y) / view.scale, 0, Math.max(0, videoHeight - 1));
    return { x: roundPixel(x), y: roundPixel(y), inside, view };
  }

  function videoPointToCanvas(point, view) {
    return {
      x: view.x + point.x * view.scale,
      y: view.y + point.y * view.scale,
    };
  }

  function normalizePrompt(prompt, fallbackObjectId, fallbackLabel) {
    const kind = String(prompt.kind || "point");
    const data = prompt.data || {};
    const base = {
      id: prompt.id || `prompt_${Date.now()}_${Math.random().toString(16).slice(2)}`,
      kind,
      frame_index: Math.max(0, toInteger(prompt.frame_index ?? prompt.frameIndex, 0)),
      object_id: slugObjectId(prompt.object_id ?? prompt.objectId ?? fallbackObjectId, fallbackObjectId),
      label: String(prompt.label || fallbackLabel || "selected_object"),
      data: {},
    };
    if (kind === "box") {
      base.data = {
        x: roundPixel(data.x),
        y: roundPixel(data.y),
        w: Math.max(1, roundPixel(data.w)),
        h: Math.max(1, roundPixel(data.h)),
      };
    } else if (kind === "mask") {
      base.data = { ...data };
    } else {
      base.data = {
        x: roundPixel(data.x),
        y: roundPixel(data.y),
      };
    }
    return base;
  }

  function promptForConfig(prompt) {
    return {
      kind: prompt.kind,
      frame_index: prompt.frame_index,
      object_id: prompt.object_id,
      label: prompt.label,
      data: { ...prompt.data },
    };
  }

  function buildMaskPrompt(strokes, objectId, label, frameIndex) {
    if (!strokes.length) return null;
    return {
      kind: "mask",
      frame_index: frameIndex,
      object_id: objectId,
      label,
      data: {
        strokes: strokes.map((stroke) => ({
          mode: stroke.mode,
          brush_size: stroke.brush_size,
          points: stroke.points.map((point) => ({ x: point.x, y: point.y })),
        })),
      },
    };
  }

  function buildDiscoveryConfig(input, promptsForConfig) {
    const keyframes = parseKeyframes(input.keyframes);
    if (input.discoveryMode === "text_detector") {
      return {
        text: input.textPrompt || "",
        labels: parseCsv(input.textPrompt),
        box_threshold: toNumber(input.boxThreshold, 0.35),
        text_threshold: toNumber(input.textThreshold, 0.25),
        keyframes,
        max_candidates: toInteger(input.maxObjects, 12),
        deduplicate: true,
        send_candidates_to_sam: input.sendCandidatesToSam !== false,
        mock: true,
      };
    }
    if (input.discoveryMode === "sam_auto_masks") {
      return {
        keyframes,
        min_area: toNumber(input.minArea, 100),
        max_area_ratio: toNumber(input.maxAreaRatio, 0.65),
        stability_threshold: toNumber(input.stabilityThreshold, 0.82),
        overlap_threshold: toNumber(input.overlapThreshold, 0.72),
        max_candidates: toInteger(input.maxObjects, 12),
        reject_background: true,
        mock: true,
      };
    }
    if (input.discoveryMode === "motion_foreground") {
      return {
        threshold: toInteger(input.motionSensitivity, 32),
        min_area: toNumber(input.minArea, 100),
        max_candidates: toInteger(input.maxObjects, 12),
        morph_open: 3,
        morph_close: 5,
        keyframes,
      };
    }
    if (input.discoveryMode === "external_masks") {
      return {
        objects: [
          {
            object_id: input.objectId,
            label: input.objectLabel,
            mask_dir: input.externalMaskDir || "masks/object_0",
            z_index: 10,
          },
        ],
        manifest: input.externalManifest || null,
      };
    }
    if (input.discoveryMode === "class_detector") {
      return {
        classes: parseCsv(input.classList),
        confidence_threshold: toNumber(input.boxThreshold, 0.35),
        max_candidates: toInteger(input.maxObjects, 12),
        keyframes,
        mock: true,
      };
    }
    return {
      prompts: promptsForConfig,
      keyframes,
    };
  }

  function buildRunConfig(input) {
    const preset = PRESETS[input.preset] || PRESETS.trace_one_object;
    const objectId = slugObjectId(input.objectId, "object_0");
    const objectLabel = String(input.objectLabel || objectId || "selected_object").trim() || objectId;
    const discoveryMode = input.discoveryMode || preset.discoveryMode || "manual_prompt";
    const maskProvider = input.maskProvider || preset.maskProvider || "threshold";
    const frameIndex = Math.max(0, toInteger(input.currentFrame, 0));
    const normalizedPrompts = asArray(input.prompts).map((prompt) => normalizePrompt(prompt, objectId, objectLabel));
    const maskPrompt = buildMaskPrompt(asArray(input.strokes), objectId, objectLabel, frameIndex);
    const promptsForConfig = [...normalizedPrompts.map(promptForConfig), ...(maskPrompt ? [maskPrompt] : [])];
    const externalMaskDir = input.externalMaskDir || "masks/object_0";
    const outputDirectory = input.outputDirectory || `out/ui-runs/${input.projectId || "local"}`;
    const videoPath = input.videoPath || input.sourcePath || input.previewName || "examples/demo_red_ball.mp4";
    const keyframes = parseKeyframes(input.keyframes);
    const device = input.device && input.device !== "auto" ? input.device : null;
    const modelName = input.modelName && input.modelName !== "auto" ? input.modelName : null;
    const objects = [
      {
        object_id: objectId,
        label: objectLabel,
        ...(discoveryMode === "external_masks" || maskProvider === "external" ? { mask_dir: externalMaskDir } : {}),
      },
    ];

    return {
      schema: RUN_CONFIG_SCHEMA,
      input: { path: videoPath },
      output: { directory: outputDirectory },
      objects,
      sampling: {
        sample_fps: toNumber(input.sampleFps, 12),
        max_frames: toInteger(input.maxFrames, 48),
      },
      provider: {
        name: maskProvider,
        threshold: {
          lower_hsv: [0, 80, 80],
          upper_hsv: [12, 255, 255],
        },
        external: {
          mask_dir: maskProvider === "external" ? externalMaskDir : null,
        },
        sam2: {
          ...EMPTY_SAM2,
          device,
          prompt_frame: frameIndex,
          hosted_config: modelName ? { model: modelName } : {},
        },
        cache: {
          enabled: true,
          directory: ".motionjson-cache/masks",
        },
        fallback_mask_provider: maskProvider === "mock" || maskProvider === "threshold" ? null : "threshold",
      },
      discovery: {
        mode: discoveryMode,
        config: buildDiscoveryConfig(
          {
            ...input,
            discoveryMode,
            objectId,
            objectLabel,
            externalMaskDir,
            keyframes: keyframes.length ? keyframes : [frameIndex],
          },
          promptsForConfig,
        ),
      },
      prompts: promptsForConfig,
      filters: {
        min_area: toNumber(input.minArea, 100),
        simplify_ratio: 0.006,
      },
      export: {
        output_mode: input.outputMode || preset.outputMode || "authoring",
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
        source_uri: videoPath,
        source_asset_id: input.videoId || null,
        display_text: "User uploaded source video",
        license: "user_uploaded_unverified",
        license_name: "User uploaded - rights unverified",
        license_url: null,
        license_scope: "unknown",
        creator_approved: false,
        creator_approval_status: null,
        commercial_use: false,
        commercial_use_status: null,
      },
    };
  }

  function statusClass(status, available) {
    const normalized = String(status || "").toLowerCase();
    if (/missing|unavailable|not available|failed|error|invalid|not found|unconfigured/.test(normalized)) return "is-bad";
    if (available === true || /ready|healthy|\bavailable\b|ok|enabled|complete|succeeded/.test(normalized)) return "is-ready";
    if (/mock|no-model|optional|disabled|local|cpu/.test(normalized)) return "is-neutral";
    return "is-warn";
  }

  function statusChip(label, status, available) {
    return `<span class="status-chip ${statusClass(status || label, available)}">${escapeHtml(label)}</span>`;
  }

  function detailChip(label) {
    return `<span class="status-chip is-muted">${escapeHtml(label)}</span>`;
  }

  function isActiveJob(job) {
    const status = String(job.status || "").toLowerCase();
    return /queued|pending|running|working|started/.test(status);
  }

  function jobIdentifier(job) {
    return String(job?.id || job?.jobId || "");
  }

  function eventMetadata(event) {
    return event?.metadata || event?.metadata_json || {};
  }

  function eventProgress(event) {
    const metadata = eventMetadata(event);
    return metadata.progress || event?.progress || {};
  }

  function latestProgressEvent(job) {
    const events = asArray(job?.events);
    for (let index = events.length - 1; index >= 0; index -= 1) {
      const progress = eventProgress(events[index]);
      if (typeof progress.overallRatio === "number" || typeof progress.ratio === "number") {
        return events[index];
      }
    }
    return null;
  }

  function normalizeProgress(job) {
    const progressEvent = latestProgressEvent(job);
    const eventRatio = eventProgress(progressEvent);
    const eventDirect = eventRatio.overallRatio ?? eventRatio.ratio;
    if (typeof eventDirect === "number" && Number.isFinite(eventDirect)) {
      return Math.max(0, Math.min(100, eventDirect <= 1 ? Math.round(eventDirect * 100) : Math.round(eventDirect)));
    }
    const direct = job.progress ?? job.percent ?? job.percentage;
    if (typeof direct === "number" && Number.isFinite(direct)) {
      return Math.max(0, Math.min(100, direct <= 1 ? Math.round(direct * 100) : Math.round(direct)));
    }
    const completedFrames = job.completedFrames ?? job.completed_frames;
    const totalFrames = job.totalFrames ?? job.total_frames;
    if (typeof completedFrames === "number" && typeof totalFrames === "number" && totalFrames > 0) {
      return Math.max(0, Math.min(100, Math.round((completedFrames / totalFrames) * 100)));
    }
    const status = String(job.status || "").toLowerCase();
    if (/complete|succeeded/.test(status)) return 100;
    if (/running|working|started/.test(status)) return 25;
    return 0;
  }

  function latestStageLabel(job) {
    const event = latestProgressEvent(job);
    const metadata = eventMetadata(event);
    return metadata.stage || event?.stage || event?.message || job.status || "queued";
  }

  function jobConfig(job) {
    const id = jobIdentifier(job);
    return state.runConfigsByJob[id] || state.lastRunConfig || null;
  }

  function selectedJob() {
    const id = state.selectedJobId;
    return state.selectedJob || state.jobs.find((job) => jobIdentifier(job) === id) || null;
  }

  async function api(path, options = {}) {
    let response;
    try {
      response = await fetch(path, {
        headers: { "content-type": "application/json", ...(options.headers || {}) },
        ...options,
      });
    } catch (error) {
      throw new Error(`Local API unavailable: ${error.message}`);
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

  function selectedVideo() {
    return state.videos.find((video) => video.id === state.selectedVideoId) || null;
  }

  function selectedVideoPath() {
    const video = selectedVideo();
    if (video?.id) {
      return `local-ui://assets/${video.id}`;
    }
    return (
      video?.metadata?.rights_context?.source_uri ||
      video?.metadata?.source_uri ||
      video?.metadata?.filename ||
      video?.filename ||
      document.querySelector("#videoPath")?.value ||
      state.video.loadedName ||
      "examples/demo_red_ball.mp4"
    );
  }

  function collectFormState($) {
    const preset = PRESETS[state.selectedPreset] || PRESETS.trace_one_object;
    const frameIndex = state.video.currentFrame || toInteger($("#frameSlider").value, 0);
    return {
      preset: state.selectedPreset,
      discoveryMode: preset.discoveryMode,
      projectId: state.selectedProjectId,
      videoId: state.selectedVideoId,
      sourcePath: selectedVideoPath(),
      videoPath: selectedVideoPath(),
      previewName: state.video.loadedName,
      outputDirectory: `out/ui-runs/${state.selectedProjectId || "local"}`,
      objectLabel: $("#objectLabel").value.trim(),
      objectId: $("#objectId").value.trim(),
      currentFrame: frameIndex,
      keyframes: state.keyframes,
      prompts: state.prompts,
      strokes: state.strokes,
      maskProvider: $("#maskProviderSelect").value || preset.maskProvider || state.runDefaults?.defaults?.maskProvider || "threshold",
      device: $("#deviceSelect").value,
      sampleFps: $("#sampleFps").value,
      maxFrames: $("#maxFrames").value,
      minArea: $("#minArea").value,
      maxAreaRatio: $("#maxAreaRatio").value,
      stabilityThreshold: $("#stabilityThreshold").value,
      overlapThreshold: $("#overlapThreshold").value,
      boxThreshold: $("#boxThreshold").value,
      textThreshold: $("#textThreshold").value,
      motionSensitivity: $("#motionSensitivity").value,
      maxObjects: $("#maxObjects").value,
      modelName: $("#modelName").value.trim(),
      outputMode: $("#outputMode").value,
      textPrompt: $("#textPrompt").value.trim(),
      classList: $("#classList").value.trim(),
      externalMaskDir: $("#externalMaskDir").value.trim(),
    };
  }

  function providerByName(name, kind = null) {
    return asArray(state.capabilities?.providers).find((provider) => provider.name === name && (!kind || provider.kind === kind));
  }

  function selectedCapabilityWarnings(config, $) {
    const warnings = [];
    const discovery = providerByName(config.discovery.mode, "discovery_provider");
    const mask = providerByName(config.provider.name, "mask_provider");
    const device = $("#deviceSelect").value;
    const hasPointOrBox = config.prompts.some((prompt) => ["point", "positive_point", "box"].includes(prompt.kind));

    for (const provider of [discovery, mask].filter(Boolean)) {
      if (!provider.available) {
        const reasons = asArray(provider.reasons).join(" ");
        warnings.push(
          `${provider.name}: ${provider.status || "unavailable"}${reasons ? ` - ${reasons}` : ""}${
            provider.mockAvailable ? " Mock/no-model mode is available for UI checks." : ""
          }`,
        );
      }
    }

    const cudaDevices = asArray(state.capabilities?.environment?.cuda?.devices);
    if (device && device !== "auto") {
      const deviceInfo = cudaDevices.find((item) => item.name === device);
      if (deviceInfo && !deviceInfo.available) {
        warnings.push(`${device} device is unavailable on this machine.`);
      }
    }

    if (["sam2", "sam2-local", "sam2-hosted"].includes(config.provider.name) && !hasPointOrBox) {
      warnings.push(`${config.provider.name} requires at least one positive point or box prompt.`);
    }

    if (state.selectedPreset === "text_detector" && !String(config.discovery.config.text || "").trim()) {
      warnings.push("text_detector needs at least one text label.");
    }

    if (config.provider.name === "external" && !config.provider.external.mask_dir) {
      warnings.push("external provider needs a mask directory.");
    }

    return warnings;
  }

  function clampBox(box, width, height) {
    const w = Math.max(1, roundPixel(box.w ?? box.width ?? 1));
    const h = Math.max(1, roundPixel(box.h ?? box.height ?? 1));
    const x = clamp(roundPixel(box.x ?? 0), 0, Math.max(0, width - 1));
    const y = clamp(roundPixel(box.y ?? 0), 0, Math.max(0, height - 1));
    return {
      x,
      y,
      w: Math.min(w, Math.max(1, width - x)),
      h: Math.min(h, Math.max(1, height - y)),
    };
  }

  function boxFromPrompt(prompt, width, height, index = 0) {
    if (prompt?.kind === "box") {
      return clampBox(prompt.data || {}, width, height);
    }

    if (prompt?.kind === "mask") {
      const points = asArray(prompt.data?.strokes).flatMap((stroke) => asArray(stroke.points));
      if (points.length) {
        const xs = points.map((point) => toNumber(point.x, width / 2));
        const ys = points.map((point) => toNumber(point.y, height / 2));
        const minX = Math.min(...xs);
        const minY = Math.min(...ys);
        const maxX = Math.max(...xs);
        const maxY = Math.max(...ys);
        return clampBox({ x: minX - 16, y: minY - 16, w: maxX - minX + 32, h: maxY - minY + 32 }, width, height);
      }
    }

    if (prompt?.data && Number.isFinite(Number(prompt.data.x)) && Number.isFinite(Number(prompt.data.y))) {
      const size = Math.max(36, Math.min(width, height) * 0.14);
      return clampBox({ x: prompt.data.x - size / 2, y: prompt.data.y - size / 2, w: size, h: size }, width, height);
    }

    const size = Math.max(44, Math.min(width, height) * 0.18);
    const offset = index * Math.max(20, size * 0.28);
    return clampBox({ x: width / 2 - size / 2 + offset, y: height / 2 - size / 2 + offset * 0.4, w: size, h: size }, width, height);
  }

  function normalizeApiTrack(track, index = 0) {
    const frames = asArray(track.frames);
    const objectId = String(track.objectId || track.object_id || track.id || `object_${index}`);
    return {
      id: objectId,
      objectId,
      label: track.label || objectId,
      source: track.source || track.providerName || track.provider_name || "api_result",
      confidence: typeof track.confidence === "number" ? track.confidence : null,
      frameCount: toInteger(track.frameCount ?? track.frame_count ?? frames.length, frames.length),
      visibleFrameCount: toInteger(track.visibleFrameCount ?? track.visible_frame_count ?? frames.length, frames.length),
      frameStart: toInteger(frames[0]?.frame ?? frames[0]?.frameIndex ?? 0, 0),
      frameEnd: toInteger(frames[frames.length - 1]?.frame ?? frames[frames.length - 1]?.frameIndex ?? frames.length - 1, frames.length - 1),
      warnings: asArray(track.warnings).map(String),
      exportStatus: track.exportStatus || track.export_status || "accepted",
      providerName: track.providerName || track.provider_name || null,
      color: TRACK_COLORS[index % TRACK_COLORS.length],
      frames: frames.map((frame) => ({
        frame: toInteger(frame.frame ?? frame.frameIndex ?? frame.out_index, 0),
        bbox: frame.bbox ? clampBox({ x: frame.bbox[0], y: frame.bbox[1], w: frame.bbox[2], h: frame.bbox[3] }, state.video.width || 1920, state.video.height || 1080) : null,
        polygon: frame.polygon || null,
        visible: frame.visible !== false,
      })),
      reviewSource: "api-result",
    };
  }

  function configReviewTracks(config, job, artifacts) {
    if (!config) return [];
    const width = state.video.width || 1920;
    const height = state.video.height || 1080;
    const maxFrames = Math.max(1, toInteger(config.sampling?.max_frames, 48));
    const providerName = config.provider?.name || job?.payload?.mask_provider || "mock";
    const discoveryMode = config.discovery?.mode || "manual_prompt";
    const prompts = asArray(config.prompts);
    const objects = asArray(config.objects).length ? asArray(config.objects) : [{ object_id: "object_0", label: "selected_object" }];
    const trackArtifact = artifacts.some((artifact) => artifact.kind === "track_summary");

    return objects.map((object, index) => {
      const objectId = slugObjectId(object.object_id || object.objectId || `object_${index}`, `object_${index}`);
      const prompt = prompts.find((item) => (item.object_id || item.objectId) === objectId) || prompts[index] || prompts[0] || null;
      const baseBox = boxFromPrompt(prompt, width, height, index);
      const frameCount = Math.max(1, Math.min(maxFrames, 48));
      const frames = Array.from({ length: frameCount }, (_, frame) => {
        const drift = providerName === "mock" ? frame * Math.max(1, Math.round(width * 0.002)) : 0;
        return {
          frame,
          visible: true,
          bbox: clampBox({ ...baseBox, x: baseBox.x + drift, y: baseBox.y + drift * 0.25 }, width, height),
        };
      });
      const warnings = [];
      if (!prompt && discoveryMode === "manual_prompt") warnings.push("no_prompt_review_estimate");
      if (trackArtifact) warnings.push("track_summary_artifact_available");
      if (providerName !== "mock" && !trackArtifact) warnings.push("awaiting_track_artifact");
      return {
        id: objectId,
        objectId,
        label: object.label || objectId,
        source: `${providerName}/${discoveryMode}`,
        confidence: providerName === "mock" ? 0.92 : 0.72,
        frameCount,
        visibleFrameCount: frameCount,
        frameStart: 0,
        frameEnd: frameCount - 1,
        warnings,
        exportStatus: warnings.includes("awaiting_track_artifact") ? "review_pending" : "included",
        providerName,
        color: TRACK_COLORS[index % TRACK_COLORS.length],
        frames,
        reviewSource: providerName === "mock" ? "mock-config" : "config-estimate",
      };
    });
  }

  function buildReviewTracks({ job, config, artifacts, review }) {
    const reviewTracks = asArray(review?.tracks);
    if (reviewTracks.length) {
      return reviewTracks.map(normalizeApiTrack);
    }

    const result = job?.result || {};
    const status = String(job?.status || "").toLowerCase();
    const hasVectorUnavailableReview = Boolean(
      review?.rasterFallback ||
        review?.vectorUnavailableReason ||
        review?.failure ||
        asArray(review?.fallbackDiagnostics).length,
    );
    const canUseSyntheticTracks = !TERMINAL_JOB_STATUSES.has(status) && !hasVectorUnavailableReview;
    const apiTracks =
      asArray(result.tracks).length
        ? asArray(result.tracks)
        : asArray(result.trackSummary?.tracks).length
          ? asArray(result.trackSummary.tracks)
          : asArray(result.scene?.tracks);
    if (apiTracks.length) {
      return apiTracks.map(normalizeApiTrack);
    }

    const count = toInteger(result.scene?.objects ?? result.objects, 0);
    if (canUseSyntheticTracks && !config && count > 0) {
      return Array.from({ length: count }, (_, index) =>
        normalizeApiTrack(
          {
            objectId: `object_${index}`,
            label: `object_${index}`,
            source: "job_result",
            confidence: 0.7,
            frameCount: toInteger(result.scene?.frames ?? result.frames, 1),
            visibleFrameCount: toInteger(result.scene?.frames ?? result.frames, 1),
            frames: [{ frame: 0, bbox: [80 + index * 24, 60 + index * 18, 120, 90], visible: true }],
            warnings: ["result_has_counts_only"],
            exportStatus: "review_pending",
          },
          index,
        ),
      );
    }

    return canUseSyntheticTracks ? configReviewTracks(config, job, artifacts) : [];
  }

  function trackFrameForDisplay(track, frameIndex) {
    const frames = asArray(track.frames).filter((frame) => frame.visible !== false && frame.bbox);
    if (!frames.length) return null;
    return frames.find((frame) => frame.frame === frameIndex) || frames.reduce((nearest, frame) => {
      if (!nearest) return frame;
      return Math.abs(frame.frame - frameIndex) < Math.abs(nearest.frame - frameIndex) ? frame : nearest;
    }, null);
  }

  function trackCoverageLabel(track) {
    const count = Math.max(1, toInteger(track.frameCount, asArray(track.frames).length || 1));
    const visible = clamp(toInteger(track.visibleFrameCount, count), 0, count);
    return `${track.frameStart ?? 0}-${track.frameEnd ?? Math.max(0, count - 1)} (${Math.round((visible / count) * 100)}%)`;
  }

  function correctionRoute(jobId) {
    return `/api/jobs/${encodeURIComponent(jobId)}/corrections`;
  }

  function trackEditRoute(jobId) {
    return `/api/jobs/${encodeURIComponent(jobId)}/track-edits`;
  }

  function normalizedActionType(action) {
    const raw = String(action.type || action.action || action.kind || "correction").replace(/-/g, "_");
    const aliases = {
      hide_track: "set_track_visibility",
      show_track: "set_track_visibility",
      rename_track: "relabel_track",
      update_label: "relabel_track",
      include_in_export: "set_export_inclusion",
      set_track_export: "set_export_inclusion",
      exclude_track: "set_export_inclusion",
      remove_track: "delete_track",
    };
    return aliases[raw] || raw;
  }

  function correctionTrackId(value) {
    return String(value?.trackId || value?.track_id || value?.objectId || value?.object_id || value?.id || "");
  }

  function normalizeHistoryEntry(entry, index = 0) {
    const type = normalizedActionType(entry);
    return {
      ...entry,
      id: entry.id || entry.correctionId || entry.correction_id || `correction_${index}`,
      type,
      trackId: correctionTrackId(entry),
      createdAt: entry.createdAt || entry.created_at || entry.timestamp || new Date().toISOString(),
      actor: entry.actor || "local_ui",
      persistenceStatus: entry.persistenceStatus || entry.persistence_status || "loaded",
    };
  }

  function normalizeTrackEditRecord(record, fallbackId = "") {
    const trackId = correctionTrackId(record) || fallbackId;
    const exportStatus = String(record.exportStatus || record.export_status || "");
    const edit = { trackId };
    if (record.label != null) edit.label = String(record.label);
    if (record.visible != null) edit.visible = record.visible !== false;
    if (record.hidden != null) edit.visible = record.hidden !== true;
    if (record.exportIncluded != null) edit.exportIncluded = record.exportIncluded !== false;
    if (record.includeInExport != null) edit.exportIncluded = record.includeInExport !== false;
    if (record.include_in_export != null) edit.exportIncluded = record.include_in_export !== false;
    if (exportStatus) {
      edit.exportIncluded = !/excluded|deleted|rejected|failed/.test(exportStatus);
    }
    if (record.deleted != null) edit.deleted = record.deleted === true;
    if (record.mergedInto || record.merged_into) edit.mergedInto = record.mergedInto || record.merged_into;
    if (record.splitFrom || record.split_from) edit.splitFrom = record.splitFrom || record.split_from;
    if (record.repairRequested || record.repair_requested) edit.repairRequested = true;
    return edit;
  }

  function applyActionToTrackEdits(edits, action) {
    const type = normalizedActionType(action);
    const trackId = correctionTrackId(action);
    const ensure = (id) => {
      if (!id) return null;
      edits[id] = { trackId: id, ...(edits[id] || {}) };
      return edits[id];
    };

    if (type === "relabel_track") {
      const edit = ensure(trackId);
      if (edit) edit.label = String(action.label || action.value || "").trim();
    } else if (type === "set_track_visibility") {
      const edit = ensure(trackId);
      if (edit) edit.visible = action.visible != null ? action.visible !== false : action.hidden !== true;
    } else if (type === "set_export_inclusion") {
      const edit = ensure(trackId);
      if (edit) edit.exportIncluded = action.included != null ? action.included !== false : action.exportIncluded !== false;
    } else if (type === "delete_track") {
      const edit = ensure(trackId);
      if (edit) {
        edit.deleted = true;
        edit.visible = false;
        edit.exportIncluded = false;
      }
    } else if (type === "merge_tracks") {
      const trackIds = asArray(action.trackIds || action.track_ids).map(String).filter(Boolean);
      const keepTrackId = String(action.keepTrackId || action.keep_track_id || trackIds[0] || "");
      for (const id of trackIds) {
        const edit = ensure(id);
        if (!edit || id === keepTrackId) continue;
        edit.deleted = true;
        edit.visible = false;
        edit.exportIncluded = false;
        edit.mergedInto = keepTrackId;
      }
    } else if (type === "repair_track") {
      const edit = ensure(trackId);
      if (edit) edit.repairRequested = true;
    }
  }

  function trackEditsFromRecords(records, history) {
    const edits = {};
    if (Array.isArray(records)) {
      for (const record of records) {
        if (!record || typeof record !== "object") continue;
        const edit = normalizeTrackEditRecord(record);
        if (edit.trackId) edits[edit.trackId] = { ...(edits[edit.trackId] || {}), ...edit };
      }
    } else if (records && typeof records === "object") {
      for (const [id, record] of Object.entries(records)) {
        if (record && typeof record === "object") {
          const edit = normalizeTrackEditRecord(record, id);
          if (edit.trackId) edits[edit.trackId] = { ...(edits[edit.trackId] || {}), ...edit };
        }
      }
    }
    for (const entry of asArray(history)) applyActionToTrackEdits(edits, entry);
    return edits;
  }

  function normalizeCorrectionState(payload, jobId = "") {
    const raw = payload?.correctionState || payload?.state || payload?.projectState || {};
    const history = asArray(
      raw.history ||
        payload?.history ||
        payload?.correctionHistory ||
        (Array.isArray(payload?.corrections) ? payload.corrections : []),
    ).map(normalizeHistoryEntry);
    const trackRecords = raw.trackEdits || raw.track_states || raw.trackStates || raw.tracks || payload?.trackEdits || payload?.trackStates || {};
    const serverTracks = Array.isArray(payload?.tracks)
      ? payload.tracks
      : Array.isArray(raw.tracks) && raw.tracks.some((track) => track?.frames || track?.frameCount || track?.frame_count)
        ? raw.tracks
        : [];
    return {
      ...emptyCorrectionState(jobId),
      ...raw,
      jobId: raw.jobId || raw.job_id || payload?.jobId || payload?.job_id || jobId,
      trackEdits: trackEditsFromRecords(trackRecords, history),
      syntheticTracks: asArray(raw.syntheticTracks || raw.synthetic_tracks || payload?.syntheticTracks),
      serverTracks,
      history,
      mergeSuggestions: asArray(raw.mergeSuggestions || raw.merge_suggestions || payload?.mergeSuggestions || payload?.review?.mergeSuggestions),
      loaded: true,
      persistenceStatus: "loaded",
      persistenceMessage: "Correction history loaded from the local backend.",
    };
  }

  function cloneTrack(track) {
    return {
      ...track,
      warnings: [...asArray(track.warnings)],
      frames: asArray(track.frames).map((frame) => ({ ...frame, bbox: frame.bbox ? { ...frame.bbox } : null })),
    };
  }

  function correctionRequestOperations(prompts, frameRange = null) {
    const operations = [];
    for (const prompt of asArray(prompts)) {
      const frame = Math.max(1, toInteger(prompt.frame_index ?? prompt.frameIndex, 0) + 1);
      if (prompt.kind === "box") {
        operations.push({
          type: "box",
          frame,
          x: roundPixel(prompt.data?.x),
          y: roundPixel(prompt.data?.y),
          w: Math.max(1, roundPixel(prompt.data?.w)),
          h: Math.max(1, roundPixel(prompt.data?.h)),
          mode: "constrain",
        });
      } else if (prompt.kind === "mask") {
        for (const stroke of asArray(prompt.data?.strokes)) {
          operations.push({
            type: "brush",
            frame,
            radius: Math.max(1, toInteger(stroke.brush_size, 10)),
            mode: stroke.mode === "erase" ? "remove" : "add",
            points: asArray(stroke.points).map((point) => [roundPixel(point.x), roundPixel(point.y)]),
          });
        }
      } else if (prompt.kind === "negative_point") {
        operations.push({
          type: "remove_point",
          frame,
          x: roundPixel(prompt.data?.x),
          y: roundPixel(prompt.data?.y),
          radius: 10,
        });
      } else {
        operations.push({
          type: "add_point",
          frame,
          x: roundPixel(prompt.data?.x),
          y: roundPixel(prompt.data?.y),
          radius: 10,
        });
      }
    }
    return operations.map((operation) => (frameRange ? { ...operation, propagate: true } : operation));
  }

  function buildCorrectionRequestFromPrompts(objectId, prompts, frameRange = null) {
    const schemaRange = frameRange ? frameRange.map((frame) => Math.max(1, toInteger(frame, 0) + 1)) : null;
    return {
      schema: "motionjson.correction_request.v0.1",
      objectId,
      operations: correctionRequestOperations(prompts, schemaRange),
      propagation: {
        enabled: Boolean(schemaRange),
        mode: schemaRange ? "same_coordinates" : "none",
        ...(schemaRange ? { frameRange: schemaRange } : {}),
      },
      temporalSmoothing: { enabled: false, radius: 1, threshold: 0.5 },
      aiUsage: "none",
    };
  }

  function syntheticTrackFromPromptAction(action, index = 0) {
    const prompts = asArray(action.prompts);
    const prompt = prompts[0] || null;
    const width = state.video.width || 1920;
    const height = state.video.height || 1080;
    const frameRange = asArray(action.frameRange).length === 2 ? action.frameRange : [state.video.currentFrame, state.video.currentFrame];
    const start = Math.max(0, toInteger(frameRange[0], 0));
    const end = Math.max(start, toInteger(frameRange[1], start));
    const id = slugObjectId(action.objectId || action.trackId || `added_object_${index}`, `added_object_${index}`);
    const box = boxFromPrompt(prompt, width, height, index);
    return {
      id,
      objectId: id,
      label: action.label || prompt?.label || id,
      source: "correction/add_object",
      confidence: null,
      frameCount: end - start + 1,
      visibleFrameCount: end - start + 1,
      frameStart: start,
      frameEnd: end,
      warnings: ["pending_backend_correction"],
      exportStatus: "included",
      providerName: "correction",
      color: TRACK_COLORS[(index + 2) % TRACK_COLORS.length],
      frames: Array.from({ length: end - start + 1 }, (_, offset) => ({
        frame: start + offset,
        visible: true,
        bbox: box,
      })),
      reviewSource: "correction-local",
      exportIncluded: true,
      visible: true,
    };
  }

  function splitTrackFromAction(sourceTrack, action, index = 0) {
    const frameRange = asArray(action.frameRange).length === 2 ? action.frameRange : [state.video.currentFrame, state.video.currentFrame];
    const start = Math.max(0, toInteger(frameRange[0], 0));
    const end = Math.max(start, toInteger(frameRange[1], start));
    const frames = asArray(sourceTrack.frames).filter((frame) => frame.frame >= start && frame.frame <= end);
    return {
      ...cloneTrack(sourceTrack),
      id: slugObjectId(action.newTrackId || `${sourceTrack.id}_split_${start}_${end}`, `${sourceTrack.id}_split_${start}_${end}`),
      objectId: slugObjectId(action.newTrackId || `${sourceTrack.objectId}_split_${start}_${end}`, `${sourceTrack.objectId}_split_${start}_${end}`),
      label: action.label || `${sourceTrack.label || sourceTrack.objectId} split ${start}-${end}`,
      source: `${sourceTrack.source || "track"}/split`,
      frameCount: Math.max(1, frames.length),
      visibleFrameCount: frames.filter((frame) => frame.visible !== false).length || frames.length,
      frameStart: start,
      frameEnd: end,
      warnings: [...asArray(sourceTrack.warnings), "pending_backend_split"],
      frames: frames.length ? frames : [trackFrameForDisplay(sourceTrack, start)].filter(Boolean),
      reviewSource: "correction-local",
      exportIncluded: true,
      visible: true,
    };
  }

  function applyCorrectionStateToTracks(baseTracks, correctionState) {
    const serverTracks = asArray(correctionState?.serverTracks);
    const sourceTracks = serverTracks.length ? serverTracks.map(normalizeApiTrack) : asArray(baseTracks).map(cloneTrack);
    const tracks = sourceTracks.map((track) => {
      const edit = correctionState?.trackEdits?.[track.id] || correctionState?.trackEdits?.[track.objectId] || {};
      const next = { ...track };
      if (edit.label) next.label = edit.label;
      if (edit.visible != null) next.visible = edit.visible !== false;
      if (edit.exportIncluded != null) next.exportIncluded = edit.exportIncluded !== false;
      if (edit.deleted) next.deleted = true;
      if (edit.mergedInto) next.mergedInto = edit.mergedInto;
      next.warnings = [...asArray(track.warnings)];
      if (next.visible === false && !next.warnings.includes("hidden_by_user")) next.warnings.push("hidden_by_user");
      if (next.exportIncluded === false && !next.warnings.includes("excluded_from_export")) next.warnings.push("excluded_from_export");
      if (next.deleted && !next.warnings.includes("deleted_by_user")) next.warnings.push("deleted_by_user");
      if (next.mergedInto && !next.warnings.includes(`merged_into_${next.mergedInto}`)) next.warnings.push(`merged_into_${next.mergedInto}`);
      if (edit.repairRequested && !next.warnings.includes("repair_requested")) next.warnings.push("repair_requested");
      if (next.deleted) next.exportStatus = "deleted";
      else if (next.exportIncluded === false) next.exportStatus = "excluded";
      return next;
    });

    const ids = new Set(tracks.map((track) => track.id));
    const history = asArray(correctionState?.history);
    for (const entry of history) {
      const type = normalizedActionType(entry);
      if (type === "split_track") {
        const source = tracks.find((track) => track.id === entry.trackId || track.objectId === entry.trackId);
        if (!source) continue;
        const split = splitTrackFromAction(source, entry, ids.size);
        if (!ids.has(split.id)) {
          ids.add(split.id);
          tracks.push(split);
        }
      }
      if (type === "add_object") {
        const added = syntheticTrackFromPromptAction(entry, ids.size);
        if (!ids.has(added.id)) {
          ids.add(added.id);
          tracks.push(added);
        }
      }
    }
    for (const synthetic of asArray(correctionState?.syntheticTracks)) {
      const track = normalizeApiTrack(synthetic, ids.size);
      if (!ids.has(track.id)) {
        ids.add(track.id);
        tracks.push(track);
      }
    }
    return tracks;
  }

  function isTrackVisibleInReview(track) {
    if (track.deleted || track.visible === false) return false;
    return state.trackVisibility[track.id] !== false;
  }

  function isTrackExportIncluded(track) {
    if (track.deleted || track.exportIncluded === false) return false;
    if (track.exportIncluded === true) return true;
    return !/deleted|excluded|rejected|failed|fallback_raster|review_pending/.test(String(track.exportStatus || ""));
  }

  function trackObjectId(track) {
    return String(track?.objectId || track?.id || "").trim();
  }

  function uniqueIds(ids) {
    const seen = new Set();
    const result = [];
    for (const value of asArray(ids)) {
      const id = String(value || "").trim();
      if (!id || seen.has(id)) continue;
      seen.add(id);
      result.push(id);
    }
    return result;
  }

  function buildExportPanelSummary({ exportState = {}, reviewExport = {}, reviewTracks = [], reviewObjects = [] } = {}) {
    const materializedIds = new Set(
      asArray(reviewObjects)
        .map((object) => String(object?.objectId || object?.id || "").trim())
        .filter(Boolean),
    );
    const reviewIncludedIds = uniqueIds(
      asArray(reviewExport.includedObjectIds).length
        ? reviewExport.includedObjectIds
        : asArray(reviewTracks).filter(isTrackExportIncluded).map(trackObjectId),
    );
    const authoritativeIncludedIds = uniqueIds(exportState.includedObjectIds);
    const includedIds = authoritativeIncludedIds.length
      ? authoritativeIncludedIds
      : reviewIncludedIds.filter((id) => materializedIds.has(id));
    const pendingIds = reviewIncludedIds.filter((id) => !materializedIds.has(id));
    const authoritativeExcludedIds = uniqueIds(exportState.excludedObjectIds);
    const excludedIds = authoritativeExcludedIds.length
      ? authoritativeExcludedIds
      : uniqueIds([...asArray(reviewExport.excludedObjectIds), ...pendingIds]);
    return { includedIds, excludedIds, pendingIds, materializedIds };
  }

  function correctionDiagnosticMessages(entry) {
    const messages = [];
    const repair = entry?.repairDiagnostics || {};
    const partial = entry?.partialRerun || repair.partialRerun || {};
    if (repair.status && repair.status !== "available") {
      messages.push(`repair ${repair.status}`);
    }
    for (const diagnostic of asArray(repair.diagnostics)) {
      const code = diagnostic.code || "repair_provider_unavailable";
      const provider = diagnostic.provider ? ` (${diagnostic.provider})` : "";
      const message = diagnostic.message || asArray(diagnostic.suggestedFixes).join(" ");
      messages.push(`${code}${provider}${message ? `: ${message}` : ""}`);
    }
    if (partial.available === false || partial.status === "not_enqueued") {
      messages.push(`partial rerun unavailable: ${partial.reason || partial.status || "not available in this local backend"}`);
    }
    return messages.filter(Boolean);
  }

  function correctionResponseMessage(response) {
    const messages = [];
    messages.push(...correctionDiagnosticMessages(response || {}));
    if (response?.repairDiagnostics) {
      messages.push(...correctionDiagnosticMessages({ repairDiagnostics: response.repairDiagnostics }));
    }
    if (response?.partialRerun) {
      messages.push(...correctionDiagnosticMessages({ partialRerun: response.partialRerun }));
    }
    return messages.filter(Boolean).join(" - ");
  }

  function collectDiagnostics(job, events, artifacts, tracks, review) {
    const diagnostics = [];
    const push = (kind, message, severity = "warn") => {
      if (!message) return;
      const key = `${kind}:${message}`;
      if (!diagnostics.some((item) => item.key === key)) diagnostics.push({ key, kind, message, severity });
    };

    const jobStatus = String(job?.status || "").toLowerCase();
    const jobMessage = job?.error || job?.reason || (jobStatus === "failed" ? job?.message : "");
    push("job", jobMessage, jobStatus === "failed" ? "bad" : "warn");
    if (!jobMessage && /fallback|raster|unavailable|diagnostic/.test(String(job?.message || ""))) {
      push("job", job.message, "warn");
    }
    for (const event of asArray(events)) {
      const metadata = eventMetadata(event);
      const eventKey = `${event.event_type || ""} ${event.status || ""} ${event.stage || ""} ${metadata.reasonCode || ""} ${event.message || ""}`;
      if (/(^|\b)(failed|error|fallback|raster|unavailable|diagnostic|whole_frame|too_large)(\b|$)/.test(eventKey)) {
        push(metadata.reasonCode || event.event_type || event.stage, metadata.message || event.message, /(^|\b)(failed|error|whole_frame|too_large)(\b|$)/.test(eventKey) ? "bad" : "warn");
        push(metadata.reasonCode, asArray(metadata.suggestedFixes).join(" "), "warn");
      }
    }
    for (const artifact of asArray(artifacts)) {
      if (artifact.kind === "fallback_diagnostics") {
        push("fallback_diagnostics", "Raster/vector fallback diagnostics were written for this run. Open fallback_diagnostics.json from the artifact list for reason codes and suggested fixes.", "warn");
      }
      if (artifact.kind === "failure_diagnostics") {
        push("failure_diagnostics", "Failure diagnostics were written for this run. The log stream above includes the user-facing failure message.", "bad");
      }
      if (artifact.kind === "track_summary") {
        push("track_summary", "Track summary artifact is available; the local UI API currently exposes its metadata for review.", "ready");
      }
    }
    for (const track of asArray(tracks)) {
      for (const warning of asArray(track.warnings)) {
        if (/fallback|whole|raster|failed|too_large|unavailable|rejected/.test(warning)) {
          push(track.objectId, `${track.label || track.objectId}: ${warning}`, /failed|rejected|whole|too_large/.test(warning) ? "bad" : "warn");
        }
      }
    }
    for (const item of asArray(review?.fallbackDiagnostics)) {
      push(item.reasonCode || item.code || "fallback", item.message || item.reason || item.summary || "Vector/object tracks were unavailable for part of this run.", /failed|error/.test(String(item.severity || "")) ? "bad" : "warn");
      push(item.reasonCode || item.code || "fallback_fix", asArray(item.suggestedFixes).join(" "), "warn");
    }
    push("vector_unavailable", review?.vectorUnavailableReason, "warn");
    push("raster_fallback", review?.rasterFallbackReason, "warn");
    push("failure", review?.failure?.message, "bad");
    if (!diagnostics.length && job) push("status", "No fallback or failure diagnostics reported for the selected run.", "ready");
    return diagnostics;
  }

  function setFacts(element, facts) {
    element.innerHTML = Object.entries(facts)
      .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value ?? "not reported")}</dd>`)
      .join("");
  }

  function init() {
    const $ = (selector) => document.querySelector(selector);
    const elements = {
      canvas: $("#overlayCanvas"),
      stage: $("#viewerStage"),
      video: $("#previewVideo"),
    };
    const ctx = elements.canvas.getContext("2d");
    let pollTimer = null;
    let pollInFlight = false;

    function renderApiStatus(kind, label) {
      const chip = $("#apiStatus");
      chip.className = `status-chip ${kind}`;
      chip.textContent = label;
    }

    function renderHealth() {
      const routes = asArray(state.health?.routes);
      if (!state.health) {
        setFacts($("#healthStatus"), {
          status: state.errors.health || "not connected",
          version: "not reported",
          local: "expected",
          mock: "not reported",
        });
      } else {
        setFacts($("#healthStatus"), {
          status: state.health.status,
          version: state.health.version,
          local: state.health.localFirst ? "yes" : "not reported",
          mock: state.health.mockMode ? "on" : state.health.mockModeAvailable ? "available" : "unavailable",
        });
      }

      $("#routeList").innerHTML = (routes.length ? routes : API_ROUTES)
        .map((route) => {
          const routeState = routes.length ? "reported by local API" : "expected local API route";
          return `<div class="route-row"><strong>${escapeHtml(route)}</strong><span class="row-meta">${routeState}</span></div>`;
        })
        .join("");
    }

    function providerDetails(provider) {
      const details = [];
      if (provider.kind) details.push(provider.kind);
      if (provider.device) details.push(`device: ${provider.device}`);
      if (provider.optionalExtra) details.push(`extra: ${provider.optionalExtra}`);
      if (provider.noModelSafe === true) details.push("no-model safe");
      if (provider.mockAvailable === true) details.push("mock available");
      return details;
    }

    function renderCapabilities() {
      const list = $("#capabilityList");
      if (!state.capabilities) {
        list.innerHTML = `<div class="error-state">${escapeHtml(state.errors.capabilities || "No capability data available.")}</div>`;
        return;
      }

      const priority = new Set(["mock", "threshold", "motion", "external", "sam2-local", "text_detector", "sam_auto_masks", "motion_foreground"]);
      const providers = asArray(state.capabilities.providers)
        .filter((provider) => priority.has(provider.name))
        .sort((a, b) => a.name.localeCompare(b.name));

      list.innerHTML = providers.length
        ? providers
            .map((provider) => {
              const reasons = asArray(provider.reasons).join(" ");
              const details = providerDetails(provider);
              const status = provider.status || (provider.available ? "available" : "not available");
              return `
                <div class="capability-row">
                  <strong>${escapeHtml(provider.name)}</strong>
                  ${statusChip(status, status, provider.available)}
                  <span class="row-meta">${escapeHtml(reasons || "No diagnostics reported.")}</span>
                  <div class="provider-detail">
                    ${details.map((detail) => detailChip(detail)).join("")}
                  </div>
                </div>
              `;
            })
            .join("")
        : `<div class="empty-state">The local API returned no provider records.</div>`;
    }

    function renderFirstRunChecklist() {
      const list = $("#firstRunChecklist");
      if (!state.capabilities) {
        list.innerHTML = `<div class="error-state">${escapeHtml(state.errors.capabilities || "Run diagnostics to load setup status.")}</div>`;
        return;
      }

      const dependencies = asArray(state.capabilities.environment?.dependencies);
      const requiredDeps = new Set(["numpy", "opencv-python", "Pillow", "tqdm", "jsonschema"]);
      const dependencyByName = new Map(dependencies.map((item) => [item.name, item]));
      const baseReady = [...requiredDeps].every((name) => dependencyByName.get(name)?.available === true);
      const readyNoModelProviders = ["mock", "threshold", "motion", "external"]
        .map((name) => providerByName(name, "mask_provider"))
        .filter(Boolean)
        .filter((provider) => provider.available === true);
      const optionalMissing = asArray(state.capabilities.providers)
        .filter((provider) => provider.optionalExtra && !provider.available)
        .map((provider) => {
          const reasons = asArray(provider.reasons).join(" ");
          return `${provider.optionalExtra} (${provider.name}${reasons ? `: ${reasons}` : ""})`;
        })
        .filter((detail, index, values) => values.indexOf(detail) === index)
        .slice(0, 4);
      const ffmpeg = state.capabilities.environment?.ffmpeg || {};
      const steps = [
        {
          label: "Base install",
          status: baseReady ? "ready" : "missing",
          available: baseReady,
          detail: baseReady ? "Core Python dependencies imported." : "Install base package dependencies, then refresh diagnostics.",
        },
        {
          label: "Local UI",
          status: state.health && !state.errors.health ? "ready" : "check",
          available: Boolean(state.health && !state.errors.health),
          detail: state.health?.mockMode ? "Mock mode is on for no-model checks." : "Use motionjson ui or module launch.",
        },
        {
          label: "No-model smoke",
          status: readyNoModelProviders.length >= 3 ? "ready" : "limited",
          available: readyNoModelProviders.length >= 3,
          detail: "Use examples/demo_red_ball.mp4 with mock, threshold, motion, or external masks.",
        },
        {
          label: "Optional models",
          status: optionalMissing.length ? "optional" : "ready",
          available: !optionalMissing.length,
          detail: optionalMissing.length
            ? `Optional provider setup: ${optionalMissing.join("; ")}. Install extras only when needed.`
            : "Configured optional providers reported ready.",
        },
        {
          label: "Exports",
          status: ffmpeg.available ? "ready" : "optional",
          available: Boolean(ffmpeg.available),
          detail: ffmpeg.available ? "FFmpeg is available for video exports." : "MotionJSON export works; MP4/WebM encoding needs FFmpeg.",
        },
      ];

      list.innerHTML = steps
        .map(
          (step) => `
            <div class="first-run-row">
              <strong>${escapeHtml(step.label)}</strong>
              ${statusChip(step.status, step.status, step.available)}
              <span class="row-meta">${escapeHtml(step.detail)}</span>
            </div>
          `,
        )
        .join("");
    }

    function renderRunDefaults() {
      if (!state.runDefaults) {
        setFacts($("#runDefaults"), {
          status: state.errors.runDefaults || "not loaded",
          mask: "not reported",
          discovery: "not reported",
          output: "not reported",
        });
        return;
      }
      const defaults = state.runDefaults.defaults || {};
      setFacts($("#runDefaults"), {
        mask: defaults.maskProvider,
        discovery: defaults.discoveryProvider,
        fps: defaults.sampleFps,
        frames: defaults.maxFrames,
        output: defaults.outputMode,
      });
    }

    function renderProjects() {
      const select = $("#projectSelect");
      $("#projectCount").textContent = `${state.projects.length} project${state.projects.length === 1 ? "" : "s"}`;
      if (!state.projects.length) {
        select.innerHTML = `<option value="">${escapeHtml(state.errors.projects || "No local projects yet")}</option>`;
        state.selectedProjectId = "";
        return;
      }
      if (!state.selectedProjectId || !state.projects.some((project) => project.id === state.selectedProjectId)) {
        state.selectedProjectId = state.projects[0].id;
      }
      select.innerHTML = state.projects
        .map((project) => `<option value="${escapeAttribute(project.id)}">${escapeHtml(project.name)}</option>`)
        .join("");
      select.value = state.selectedProjectId;
    }

    function renderVideos() {
      const select = $("#videoSelect");
      $("#videoCount").textContent = `${state.videos.length} video${state.videos.length === 1 ? "" : "s"}`;
      if (state.errors.videos) {
        select.innerHTML = `<option value="">Video unavailable</option>`;
        $("#videoList").innerHTML = `<div class="error-state">${escapeHtml(state.errors.videos)}</div>`;
        return;
      }
      if (!state.videos.length) {
        state.selectedVideoId = "";
        select.innerHTML = `<option value="">No local videos yet</option>`;
      } else {
        if (!state.selectedVideoId || !state.videos.some((video) => video.id === state.selectedVideoId)) {
          state.selectedVideoId = state.videos[0].id;
        }
        select.innerHTML = state.videos
          .map((video) => {
            const filename = video.metadata?.filename || video.filename || video.path || video.id;
            return `<option value="${escapeAttribute(video.id)}">${escapeHtml(filename)}</option>`;
          })
          .join("");
        select.value = state.selectedVideoId;
      }
      $("#videoList").innerHTML = state.videos.length
        ? state.videos
            .map((video) => {
              const filename = video.metadata?.filename || video.filename || video.path || video.id;
              const detail = video.content_type || video.contentType || "source_video";
              const active = video.id === state.selectedVideoId;
              return `
                <button class="artifact-row video-choice ${active ? "is-selected" : ""}" type="button" data-video-id="${escapeAttribute(video.id)}" aria-pressed="${active}">
                  <strong>${escapeHtml(filename)}</strong>
                  <span class="row-meta">${escapeHtml(active ? `${detail} - selected` : detail)}</span>
                </button>
              `;
            })
            .join("")
        : `<div class="empty-state">Add a local video path after creating a project.</div>`;
      loadSelectedVideoPreview();
      renderConfigPreview();
    }

    function renderJobs() {
      const activeCount = state.jobs.filter(isActiveJob).length;
      $("#jobSummary").textContent = `${activeCount} active`;

      if (state.errors.jobs) {
        $("#jobList").innerHTML = `<div class="error-state">${escapeHtml(state.errors.jobs)}</div>`;
        return;
      }

      $("#jobList").innerHTML = state.jobs.length
        ? state.jobs
            .map((job) => {
              const id = jobIdentifier(job);
              const progress = normalizeProgress(job);
              const status = job.status || "unknown";
              const selected = id && id === state.selectedJobId;
              const diagnostics = [
                job.error,
                job.reason,
                job.message,
                job.vectorUnavailableReason,
                job.vector_unavailable_reason,
                job.rasterOnlyReason,
                job.raster_only_reason,
              ].filter(Boolean);
              return `
                <button class="artifact-row job-choice ${selected ? "is-selected" : ""}" type="button" data-job-id="${escapeAttribute(id)}" aria-pressed="${selected}">
                  <strong>${escapeHtml(job.type || "job")}</strong>
                  ${statusChip(status, status, /complete|succeeded/.test(String(status).toLowerCase()))}
                  <span class="row-meta">${escapeHtml(id || "no id reported")} - ${escapeHtml(latestStageLabel(job))}</span>
                  <div class="job-progress" role="group" aria-label="${escapeAttribute(`${job.type || "job"} progress`)}">
                    <div class="job-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}">
                      <div class="job-progress-bar" style="--progress: ${progress}%"></div>
                    </div>
                    <span class="job-progress-text">${progress}% complete${diagnostics.length ? ` - ${escapeHtml(diagnostics.join(" "))}` : ""}</span>
                  </div>
                </button>
              `;
            })
            .join("")
        : `<div class="empty-state">Jobs will appear here with status, progress, and export diagnostics.</div>`;
    }

    function renderSelectedJobFacts() {
      const job = selectedJob();
      const statusChipElement = $("#runStatus");
      if (!job) {
        statusChipElement.textContent = "No run";
        statusChipElement.className = "status-chip is-muted";
        setFacts($("#selectedJobFacts"), {
          status: "select or start a run",
          provider: "not reported",
          progress: "0%",
          updated: "not reported",
        });
        return;
      }

      const status = job.status || "unknown";
      statusChipElement.textContent = status;
      statusChipElement.className = `status-chip ${statusClass(status, /succeeded|complete/.test(String(status).toLowerCase()))}`;
      const payload = job.payload || {};
      const result = job.result || {};
      setFacts($("#selectedJobFacts"), {
        id: jobIdentifier(job),
        type: job.type || "job",
        provider: payload.mask_provider || jobConfig(job)?.provider?.name || "not reported",
        progress: `${normalizeProgress({ ...job, events: state.jobEvents })}%`,
        artifacts: state.jobArtifacts.length,
        objects: result.scene?.objects ?? result.objects ?? state.reviewTracks.length,
        updated: job.updated_at || job.updatedAt || "not reported",
      });
    }

    function renderEventLog() {
      $("#eventCount").textContent = `${state.jobEvents.length} event${state.jobEvents.length === 1 ? "" : "s"}`;
      $("#jobEventLog").innerHTML = state.jobEvents.length
        ? state.jobEvents
            .slice()
            .reverse()
            .map((event) => {
              const metadata = eventMetadata(event);
              const progress = eventProgress(event);
              const ratio = progress.overallRatio ?? progress.ratio;
              const progressText = typeof ratio === "number" ? ` - ${Math.round((ratio <= 1 ? ratio : ratio / 100) * 100)}%` : "";
              const label = event.event_type || event.type || event.stage || "event";
              const message = event.message || metadata.message || event.stage || "job event";
              return `
                <div class="event-row">
                  <strong>${escapeHtml(label)}</strong>
                  <span class="event-time">${escapeHtml(event.created_at || event.createdAt || event.timestamp || "")}</span>
                  <span class="row-meta">${escapeHtml(message + progressText)}</span>
                </div>
              `;
            })
            .join("")
        : `<div class="empty-state">No job events have been reported yet.</div>`;
    }

    function renderArtifactBrowser() {
      $("#artifactCount").textContent = `${state.jobArtifacts.length} file${state.jobArtifacts.length === 1 ? "" : "s"}`;
      $("#artifactBrowser").innerHTML = state.jobArtifacts.length
        ? state.jobArtifacts
            .map((artifact) => {
              const relPath = artifact.metadata?.rel_path || artifact.path || artifact.filename || artifact.id;
              const detail = [
                artifact.content_type || artifact.contentType,
                artifact.byte_size || artifact.byteSize ? `${artifact.byte_size || artifact.byteSize} bytes` : "",
                artifact.object_id || artifact.objectId ? `object: ${artifact.object_id || artifact.objectId}` : "",
              ]
                .filter(Boolean)
                .join(" - ");
              const contentLink = artifact.contentUrl
                ? `<a class="artifact-link" href="${escapeAttribute(artifact.contentUrl)}" target="_blank" rel="noreferrer">Open</a>`
                : "";
              return `
                <div class="artifact-row">
                  <strong>${escapeHtml(relPath || "artifact")}</strong>
                  ${statusChip(artifact.kind || "artifact", artifact.kind || "artifact", true)}
                  <span class="row-meta">${escapeHtml(detail || artifact.id || "metadata only")}</span>
                  ${contentLink}
                </div>
              `;
            })
            .join("")
        : `<div class="empty-state">Artifacts appear here after the worker registers output files.</div>`;
    }

    function renderTrackList() {
      $("#trackCount").textContent = `${state.reviewTracks.length} track${state.reviewTracks.length === 1 ? "" : "s"}`;
      $("#trackList").innerHTML = state.reviewTracks.length
        ? state.reviewTracks
            .map((track) => {
              const visible = isTrackVisibleInReview(track);
              const exportIncluded = isTrackExportIncluded(track);
              const selectedForMerge = state.mergeSelection.has(track.id);
              const confidence = typeof track.confidence === "number" ? `${Math.round(track.confidence * 100)}%` : "not reported";
              const warnings = asArray(track.warnings);
              return `
                <div class="track-row ${visible ? "" : "is-muted"} ${track.deleted ? "is-deleted" : ""}" style="--track-color: ${escapeAttribute(track.color)}">
                  <div class="track-topline">
                    <span class="track-meta"><span class="track-swatch" aria-hidden="true"></span><strong>${escapeHtml(track.label || track.objectId)}</strong></span>
                    ${statusChip(track.exportStatus || "review", track.exportStatus || "review", !/rejected|failed|pending/.test(String(track.exportStatus || "")))}
                  </div>
                  <div class="track-meta">
                    <span>${escapeHtml(track.source || "unknown source")}</span>
                    <span>confidence ${escapeHtml(confidence)}</span>
                    <span>frames ${escapeHtml(trackCoverageLabel(track))}</span>
                  </div>
                  <div class="track-actions">
                    <label class="track-toggle">
                      <input type="checkbox" data-track-visible="${escapeAttribute(track.id)}" data-track-visibility="${escapeAttribute(track.id)}" ${visible ? "checked" : ""} ${track.deleted ? "disabled" : ""} />
                      <span>show</span>
                    </label>
                    <label class="track-toggle">
                      <input type="checkbox" data-track-export="${escapeAttribute(track.id)}" ${exportIncluded ? "checked" : ""} ${track.deleted ? "disabled" : ""} />
                      <span>export</span>
                    </label>
                    <label class="track-toggle">
                      <input type="checkbox" data-track-merge="${escapeAttribute(track.id)}" ${selectedForMerge ? "checked" : ""} ${track.deleted ? "disabled" : ""} />
                      <span>merge</span>
                    </label>
                    <button class="mini-action" type="button" data-track-edit="${escapeAttribute(track.id)}">Edit</button>
                    <button class="mini-action danger-action" type="button" data-track-delete="${escapeAttribute(track.id)}" ${track.deleted ? "disabled" : ""}>Delete</button>
                    ${detailChip(track.reviewSource || "review")}
                    ${warnings.map((warning) => detailChip(warning)).join("")}
                  </div>
                </div>
              `;
            })
            .join("")
        : `<div class="empty-state">Start or select a run to review object tracks.</div>`;
    }

    function renderCorrectionPanel() {
      const status = state.correctionState.persistenceStatus || "not_loaded";
      const statusLabel = status === "loaded" ? "Loaded" : status === "saved" ? "Saved" : status === "saving" ? "Saving" : status === "failed" ? "Save failed" : status === "unavailable" ? "Route unavailable" : "Not loaded";
      $("#correctionStatus").textContent = statusLabel;
      $("#correctionStatus").className = `status-chip ${statusClass(statusLabel, status === "loaded" || status === "saved")}`;
      $("#correctionPersistenceMessage").textContent = state.correctionState.persistenceMessage || "Correction edits will be saved through the local backend correction API.";

      const selectableTracks = state.reviewTracks.filter((track) => !track.deleted);
      if (!state.selectedCorrectionTrackId || !selectableTracks.some((track) => track.id === state.selectedCorrectionTrackId)) {
        state.selectedCorrectionTrackId = selectableTracks[0]?.id || "";
      }
      $("#correctionTrackSelect").innerHTML = selectableTracks.length
        ? selectableTracks
            .map((track) => `<option value="${escapeAttribute(track.id)}">${escapeHtml(track.label || track.objectId)}</option>`)
            .join("")
        : `<option value="">No editable tracks</option>`;
      $("#correctionTrackSelect").value = state.selectedCorrectionTrackId;
      const selected = state.reviewTracks.find((track) => track.id === state.selectedCorrectionTrackId);
      if (document.activeElement !== $("#correctionLabelInput")) {
        $("#correctionLabelInput").value = selected?.label || "";
      }
      const promptCount = allPromptsForDisplay().length;
      $("#correctionPromptCount").textContent = `${promptCount} prompt${promptCount === 1 ? "" : "s"}`;
      $("#mergeSelectionCount").textContent = `${state.mergeSelection.size} selected`;
      $("#mergeTracksButton").disabled = state.mergeSelection.size < 2;
      $("#repairTrackButton").disabled = !state.selectedCorrectionTrackId || promptCount === 0;
      $("#splitTrackButton").disabled = !state.selectedCorrectionTrackId;
      $("#addObjectButton").disabled = promptCount === 0;

      const suggestions = asArray(state.correctionState.mergeSuggestions);
      $("#mergeSuggestionList").innerHTML = suggestions.length
        ? suggestions
            .map((item) => {
              const keep = item.keepObjectId || item.keep_object_id || item.keepTrackId || item.keep_track_id;
              const merge = item.mergeObjectId || item.merge_object_id || item.mergeTrackId || item.merge_track_id;
              const score = typeof item.meanIou === "number" ? `IoU ${item.meanIou.toFixed(2)}` : item.reason || "duplicate candidate";
              return `
                <button class="suggestion-row" type="button" data-merge-suggestion="${escapeAttribute([keep, merge].filter(Boolean).join(","))}">
                  <strong>${escapeHtml([keep, merge].filter(Boolean).join(" + ") || "merge suggestion")}</strong>
                  <span class="row-meta">${escapeHtml(score)}</span>
                </button>
              `;
            })
            .join("")
        : `<div class="empty-state">No duplicate-track merge suggestions reported for this run.</div>`;
    }

    function renderCorrectionHistory() {
      const history = asArray(state.correctionState.history);
      $("#correctionHistoryCount").textContent = `${history.length} edit${history.length === 1 ? "" : "s"}`;
      $("#correctionHistory").innerHTML = history.length
        ? history
            .slice()
            .reverse()
            .map((entry) => {
              const label = entry.label || entry.trackId || asArray(entry.trackIds).join(", ") || entry.objectId || entry.type;
              const diagnostics = correctionDiagnosticMessages(entry);
              const detail = [
                entry.frameRange ? `frames ${entry.frameRange.join("-")}` : "",
                entry.persistenceStatus || state.correctionState.persistenceStatus,
                entry.createdAt || "",
                ...diagnostics,
              ]
                .filter(Boolean)
                .join(" - ");
              return `
                <div class="history-row">
                  <strong>${escapeHtml(entry.type)}</strong>
                  <span class="row-meta">${escapeHtml(label)}</span>
                  <span class="row-meta">${escapeHtml(detail || "pending")}</span>
                </div>
              `;
            })
            .join("")
        : `<div class="empty-state">Track edits will appear here after relabel, hide/show, export, merge, split, add-object, or repair actions.</div>`;
    }

    function exportPayloadFromControls() {
      return {
        preset: $("#exportPresetSelect").value || "compact",
        includeMasks: $("#exportIncludeMasks").checked,
        includeContours: $("#exportIncludeContours").checked,
        includePreview: $("#exportIncludePreview").checked,
      };
    }

    function applyExportPresetDefaults() {
      const presetId = $("#exportPresetSelect").value || "compact";
      const apiPreset = asArray(state.exportFormats?.presets).find((preset) => preset.id === presetId);
      const defaults = apiPreset || EXPORT_PRESET_DEFAULTS[presetId] || EXPORT_PRESET_DEFAULTS.compact;
      $("#exportIncludeMasks").checked = defaults.includeMasks === true;
      $("#exportIncludeContours").checked = defaults.includeContours === true;
      $("#exportIncludePreview").checked = defaults.includePreview !== false;
      renderExportPanel();
    }

    function renderExportPresetOptions() {
      const select = $("#exportPresetSelect");
      const current = select.value || "compact";
      const presets = asArray(state.exportFormats?.presets);
      if (presets.length) {
        select.innerHTML = presets
          .map((preset) => `<option value="${escapeAttribute(preset.id)}">${escapeHtml(preset.id)}</option>`)
          .join("");
      }
      select.value = presets.some((preset) => preset.id === current) || EXPORT_PRESET_DEFAULTS[current] ? current : "compact";
    }

    function exportIssueRows(issues) {
      return asArray(issues)
        .slice(0, 4)
        .map((issue) => {
          const path = issue.path || "export";
          const message = issue.message || issue.reason || "validation issue";
          return `<div class="diagnostic-row is-bad"><strong>${escapeHtml(path)}</strong><span class="row-meta">${escapeHtml(message)}</span></div>`;
        })
        .join("");
    }

    function renderExportPanel() {
      const job = selectedJob();
      const validation = state.exportValidation?.jobId === state.selectedJobId ? state.exportValidation : null;
      const exported = state.exportResult?.jobId === state.selectedJobId ? state.exportResult : null;
      const storedExportArtifacts = state.jobArtifacts.filter((artifact) =>
        ["validated_motionjson_scene", "final_export_manifest", "export_validation_report", "preview_overlay", "contours_boxes", "motionjson_export_zip"].includes(artifact.kind),
      );
      const storedValidationArtifact = storedExportArtifacts
        .slice()
        .reverse()
        .find((artifact) => artifact.kind === "export_validation_report" && artifact.metadata?.validation);
      const exportState = exported || validation || {};
      const reviewExport = state.jobReview?.export || {};
      const { includedIds, excludedIds, pendingIds } = buildExportPanelSummary({
        exportState,
        reviewExport,
        reviewTracks: state.reviewTracks,
        reviewObjects: state.jobReview?.objects,
      });
      const status = exported?.validation || validation?.validation || storedValidationArtifact?.metadata?.validation;
      const ok = status?.ok === true;
      $("#exportStatus").textContent = !job ? "No run" : ok ? "Valid" : status ? "Needs review" : "Not validated";
      $("#exportStatus").className = `status-chip ${!job ? "is-muted" : ok ? "is-ready" : status ? "is-warn" : "is-muted"}`;
      $("#validateExportButton").disabled = !job;
      $("#exportMotionJsonButton").disabled = !job || includedIds.length === 0;

      const exportArtifacts = asArray(exported?.assets).length ? asArray(exported?.assets) : storedExportArtifacts;
      const artifactLinks = exportArtifacts
        .filter((asset) => asset.contentUrl)
        .map((asset) => {
          const relPath = asset.metadata?.rel_path || asset.path || asset.kind || asset.id;
          return `<a class="artifact-link" href="${escapeAttribute(asset.contentUrl)}" target="_blank" rel="noreferrer">${escapeHtml(relPath)}</a>`;
        })
        .join("");
      const issueRows = exportIssueRows(status?.issues);
      $("#exportSummary").innerHTML = job
        ? `
            <div class="diagnostic-row is-${ok ? "ready" : status ? "warn" : "warn"}">
              <strong>${escapeHtml(includedIds.length ? `${includedIds.length} included` : "no included tracks")}</strong>
              <span class="row-meta">${escapeHtml(excludedIds.length ? `${excludedIds.length} excluded from export` : "no excluded tracks reported")}</span>
            </div>
            ${
              pendingIds.length
                ? `<div class="diagnostic-row is-warn"><strong>pending corrections</strong><span class="row-meta">${escapeHtml(`${pendingIds.length} track${pendingIds.length === 1 ? "" : "s"} need materialized assets before export`)}</span></div>`
                : ""
            }
            ${
              status
                ? `<div class="diagnostic-row is-${ok ? "ready" : "bad"}"><strong>validation</strong><span class="row-meta">${escapeHtml(`${status.issueCount || 0} issue${status.issueCount === 1 ? "" : "s"} across ${status.checked || 0} document${status.checked === 1 ? "" : "s"}`)}</span></div>`
                : ""
            }
            ${issueRows}
            ${artifactLinks ? `<div class="artifact-row"><strong>Export artifacts</strong><span class="row-meta">${artifactLinks}</span></div>` : ""}
          `
        : `<div class="empty-state">Select a completed run before validating or exporting MotionJSON.</div>`;
    }

    function renderFallbackDiagnostics() {
      const diagnostics = collectDiagnostics(selectedJob(), state.jobEvents, state.jobArtifacts, state.reviewTracks, state.jobReview);
      $("#fallbackDiagnostics").innerHTML = diagnostics.length
        ? diagnostics
            .map((diagnostic) => `
              <div class="diagnostic-row is-${escapeAttribute(diagnostic.severity || "warn")}">
                <strong>${escapeHtml(diagnostic.kind || "diagnostic")}</strong>
                <span class="row-meta">${escapeHtml(diagnostic.message)}</span>
              </div>
            `)
            .join("")
        : `<div class="empty-state">No selected run diagnostics.</div>`;
    }

    function renderJobReview() {
      renderSelectedJobFacts();
      renderEventLog();
      renderArtifactBrowser();
      renderTrackList();
      renderExportPanel();
      renderCorrectionPanel();
      renderCorrectionHistory();
      renderFallbackDiagnostics();
      drawOverlay();
    }

    function renderMaskProviderOptions() {
      const select = $("#maskProviderSelect");
      const defaults = state.runDefaults?.defaults || {};
      const providerNames = state.runDefaults?.maskProviders || ["external", "mock", "motion", "sam2", "sam2-hosted", "sam2-local", "threshold"];
      const current =
        select.dataset.userSelected === "true"
          ? select.value
          : PRESETS[state.selectedPreset]?.maskProvider || defaults.maskProvider || "threshold";
      select.innerHTML = providerNames
        .map((provider) => {
          const capability = providerByName(provider, "mask_provider");
          const suffix = capability && !capability.available ? ` (${capability.status})` : "";
          return `<option value="${escapeAttribute(provider)}">${escapeHtml(provider + suffix)}</option>`;
        })
        .join("");
      select.value = providerNames.includes(current) ? current : defaults.maskProvider || providerNames[0] || "threshold";
    }

    function renderPresetFields() {
      const preset = PRESETS[state.selectedPreset] || PRESETS.trace_one_object;
      $("#presetSummary").textContent = preset.label;
      $("#presetSummary").className = "status-chip is-neutral";
      $("#textPromptField").classList.toggle("is-hidden", state.selectedPreset !== "text_detector");
      $("#classListField").classList.toggle("is-hidden", state.selectedPreset !== "class_detector");
      $("#externalMaskField").classList.toggle("is-hidden", state.selectedPreset !== "external_masks");
      $("#outputMode").value = preset.outputMode || "authoring";
    }

    function allPromptsForDisplay() {
      const rows = [...state.prompts];
      if (state.strokes.length) {
        rows.push({
          id: "mask_prompt",
          kind: "mask",
          frame_index: state.video.currentFrame,
          object_id: slugObjectId($("#objectId").value, "object_0"),
          label: $("#objectLabel").value || "selected_object",
          data: { strokes: state.strokes },
        });
      }
      return rows;
    }

    function renderPromptList() {
      const prompts = allPromptsForDisplay();
      $("#promptCount").textContent = `${prompts.length} prompt${prompts.length === 1 ? "" : "s"}`;
      $("#promptList").innerHTML = prompts.length
        ? prompts
            .map((prompt) => {
              const detail =
                prompt.kind === "box"
                  ? `frame ${prompt.frame_index} - x:${prompt.data.x}, y:${prompt.data.y}, w:${prompt.data.w}, h:${prompt.data.h}`
                  : prompt.kind === "mask"
                    ? `frame ${prompt.frame_index} - ${state.strokes.length} brush stroke(s)`
                    : `frame ${prompt.frame_index} - x:${prompt.data.x}, y:${prompt.data.y}`;
              const selected = prompt.id === state.selectedPromptId;
              return `
                <button class="prompt-row ${selected ? "is-selected" : ""}" type="button" data-prompt-id="${escapeAttribute(prompt.id)}" aria-pressed="${selected}">
                  <strong>${escapeHtml(prompt.label || prompt.object_id)}</strong>
                  ${statusChip(prompt.kind, prompt.kind, prompt.kind === "negative_point" ? false : true)}
                  <span class="row-meta">${escapeHtml(detail)}</span>
                </button>
              `;
            })
            .join("")
        : `<div class="empty-state">No prompts on the current config.</div>`;
    }

    function renderVideoMetrics() {
      const video = elements.video;
      const fps = Math.max(0.1, toNumber($("#sampleFps").value, 12));
      const frame = video.duration ? Math.round(video.currentTime * fps) : state.video.currentFrame;
      state.video.currentFrame = Math.max(0, frame);
      const frameCount = video.duration ? Math.max(0, Math.round(video.duration * fps)) : Math.max(state.video.currentFrame, 0);
      $("#frameSlider").max = String(frameCount);
      $("#frameSlider").value = String(clamp(state.video.currentFrame, 0, frameCount));
      $("#frameReadout").textContent = `frame ${state.video.currentFrame}`;
      $("#videoMetricReadout").textContent =
        state.video.width && state.video.height
          ? `${state.video.width}x${state.video.height} px`
          : "video pixels unavailable";
    }

    function loadSelectedVideoPreview() {
      const video = selectedVideo();
      const contentUrl = video?.contentUrl || video?.content_url;
      if (!contentUrl || elements.video.getAttribute("src") === contentUrl) return;
      if (state.previewObjectUrl) {
        URL.revokeObjectURL(state.previewObjectUrl);
        state.previewObjectUrl = "";
      }
      state.video.loadedName = video.metadata?.filename || video.filename || video.id || "registered video";
      elements.video.src = contentUrl;
      elements.video.load();
    }

    function resizeCanvas() {
      const rect = elements.stage.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const width = Math.max(1, Math.round(rect.width * dpr));
      const height = Math.max(1, Math.round(rect.height * dpr));
      if (elements.canvas.width !== width || elements.canvas.height !== height) {
        elements.canvas.width = width;
        elements.canvas.height = height;
      }
      elements.canvas.style.width = `${Math.round(rect.width)}px`;
      elements.canvas.style.height = `${Math.round(rect.height)}px`;
      return { width: rect.width, height: rect.height, dpr };
    }

    function drawPoint(point, color, label, view) {
      const canvasPoint = videoPointToCanvas(point, view);
      ctx.beginPath();
      ctx.arc(canvasPoint.x, canvasPoint.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();
      ctx.fillStyle = "#ffffff";
      ctx.font = "12px ui-sans-serif, system-ui, sans-serif";
      ctx.fillText(label, canvasPoint.x + 9, canvasPoint.y - 9);
    }

    function drawBox(box, color, label, view) {
      const start = videoPointToCanvas({ x: box.x, y: box.y }, view);
      const end = videoPointToCanvas({ x: box.x + box.w, y: box.y + box.h }, view);
      ctx.lineWidth = 2;
      ctx.strokeStyle = color;
      ctx.strokeRect(start.x, start.y, end.x - start.x, end.y - start.y);
      ctx.fillStyle = "rgba(15, 118, 110, 0.12)";
      ctx.fillRect(start.x, start.y, end.x - start.x, end.y - start.y);
      ctx.fillStyle = "#ffffff";
      ctx.font = "12px ui-sans-serif, system-ui, sans-serif";
      ctx.fillText(label, start.x + 6, Math.max(14, start.y - 7));
    }

    function drawTrackBox(track, frame, view) {
      const box = frame?.bbox;
      if (!box) return;
      const start = videoPointToCanvas({ x: box.x, y: box.y }, view);
      const end = videoPointToCanvas({ x: box.x + box.w, y: box.y + box.h }, view);
      ctx.save();
      ctx.lineWidth = 3;
      ctx.strokeStyle = track.color || "#10a37f";
      ctx.fillStyle = `${track.color || "#10a37f"}26`;
      ctx.strokeRect(start.x, start.y, end.x - start.x, end.y - start.y);
      ctx.fillRect(start.x, start.y, end.x - start.x, end.y - start.y);
      ctx.fillStyle = "rgba(20, 28, 32, 0.86)";
      const label = `${track.label || track.objectId} - ${track.reviewSource || "track"}`;
      ctx.font = "12px ui-sans-serif, system-ui, sans-serif";
      const textWidth = Math.min(ctx.measureText(label).width + 14, Math.max(60, view.width - start.x - 8));
      const labelY = Math.max(view.y + 18, start.y - 24);
      ctx.fillRect(start.x, labelY, textWidth, 20);
      ctx.fillStyle = "#ffffff";
      ctx.fillText(label, start.x + 7, labelY + 14, textWidth - 12);
      ctx.restore();
    }

    function drawStroke(stroke, view) {
      if (!stroke.points.length) return;
      ctx.save();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.lineWidth = Math.max(2, stroke.brush_size * view.scale);
      ctx.strokeStyle = stroke.mode === "erase" ? "rgba(180, 35, 24, 0.64)" : "rgba(96, 70, 165, 0.64)";
      ctx.beginPath();
      stroke.points.forEach((point, index) => {
        const canvasPoint = videoPointToCanvas(point, view);
        if (index === 0) ctx.moveTo(canvasPoint.x, canvasPoint.y);
        else ctx.lineTo(canvasPoint.x, canvasPoint.y);
      });
      ctx.stroke();
      ctx.restore();
    }

    function drawOverlay() {
      const size = resizeCanvas();
      ctx.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
      ctx.clearRect(0, 0, size.width, size.height);
      if (!state.video.width || !state.video.height) return;

      const view = containedVideoRect(size.width, size.height, state.video.width, state.video.height);
      ctx.save();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.36)";
      ctx.lineWidth = 1;
      ctx.strokeRect(view.x, view.y, view.width, view.height);
      ctx.restore();

      state.strokes.forEach((stroke) => drawStroke(stroke, view));
      if (state.activeStroke) drawStroke(state.activeStroke, view);

      state.prompts.forEach((prompt) => {
        if (prompt.kind === "box") {
          drawBox(prompt.data, "#1fb7a9", prompt.label || prompt.object_id, view);
        } else {
          drawPoint(prompt.data, prompt.kind === "negative_point" ? "#e3483d" : "#10a37f", prompt.label || prompt.object_id, view);
        }
      });

      if (state.draftBox) {
        drawBox(state.draftBox.data, "#e5be5f", "box draft", view);
      }

      state.reviewTracks.forEach((track) => {
        if (!isTrackVisibleInReview(track)) return;
        drawTrackBox(track, trackFrameForDisplay(track, state.video.currentFrame), view);
      });

      if (state.pointer?.inside) {
        const canvasPoint = videoPointToCanvas(state.pointer, view);
        ctx.save();
        ctx.strokeStyle = "rgba(255, 255, 255, 0.62)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(canvasPoint.x - 10, canvasPoint.y);
        ctx.lineTo(canvasPoint.x + 10, canvasPoint.y);
        ctx.moveTo(canvasPoint.x, canvasPoint.y - 10);
        ctx.lineTo(canvasPoint.x, canvasPoint.y + 10);
        ctx.stroke();
        ctx.restore();
      }
    }

    function renderConfigPreview() {
      let config;
      try {
        config = buildRunConfig(collectFormState($));
      } catch (error) {
        $("#configStatus").textContent = "Invalid";
        $("#configStatus").className = "status-chip is-bad";
        $("#configPreview").textContent = error.message;
        return;
      }

      const warnings = selectedCapabilityWarnings(config, $);
      const warningBox = $("#providerWarning");
      if (warnings.length) {
        warningBox.textContent = warnings.join(" ");
        warningBox.className = warnings.some((warning) => /requires|needs|unavailable|missing|not_configured/.test(warning)) ? "warning-box is-bad" : "warning-box";
      } else {
        warningBox.textContent = "Selected providers are ready or no-model safe.";
        warningBox.className = "warning-box is-ready";
      }

      const configWarnings = [];
      if (config.discovery.mode === "manual_prompt" && !config.prompts.length && config.provider.name !== "mock") {
        configWarnings.push("manual prompt config has no point, box, or mask prompt yet");
      }

      $("#configStatus").textContent = configWarnings.length ? "Needs prompt" : warnings.length ? "Warn" : "Valid";
      $("#configStatus").className = `status-chip ${configWarnings.length || warnings.length ? "is-warn" : "is-ready"}`;
      $("#configPreview").textContent = JSON.stringify(config, null, 2);
      renderPromptList();
      renderCorrectionPanel();
      drawOverlay();
    }

    function renderBackendValidation(validation) {
      const errors = asArray(validation.errors).map((item) => item.message || String(item));
      const warnings = asArray(validation.warnings).map((item) => {
        const reasons = asArray(item.reasons).join(" ");
        return [item.message || String(item), reasons, item.installHint].filter(Boolean).join(" ");
      });
      const valid = validation.valid === true && !errors.length;

      $("#configStatus").textContent = valid ? (warnings.length ? "Valid with warnings" : "Validated") : "Invalid";
      $("#configStatus").className = `status-chip ${valid ? (warnings.length ? "is-warn" : "is-ready") : "is-bad"}`;

      if (errors.length || warnings.length) {
        $("#providerWarning").innerHTML = [...errors.map((message) => `Error: ${message}`), ...warnings].map(escapeHtml).join("<br />");
        $("#providerWarning").className = `warning-box ${errors.length ? "is-bad" : "is-warn"}`;
      } else {
        $("#providerWarning").textContent = "Backend validation accepted this config and reported no provider warnings.";
        $("#providerWarning").className = "warning-box is-ready";
      }

      $("#configPreview").textContent = JSON.stringify(validation.runConfig || buildRunConfig(collectFormState($)), null, 2);
    }

    async function validateConfigWithBackend() {
      let config;
      try {
        config = buildRunConfig(collectFormState($));
      } catch (error) {
        $("#configStatus").textContent = "Invalid";
        $("#configStatus").className = "status-chip is-bad";
        $("#configPreview").textContent = error.message;
        return;
      }

      $("#configStatus").textContent = "Validating";
      $("#configStatus").className = "status-chip is-neutral";
      try {
        renderBackendValidation(
          await api("/api/run-config/validate", {
            method: "POST",
            body: JSON.stringify({ runConfig: config }),
          }),
        );
      } catch (error) {
        $("#configStatus").textContent = "Validation failed";
        $("#configStatus").className = "status-chip is-bad";
        $("#providerWarning").textContent = error.message;
        $("#providerWarning").className = "warning-box is-bad";
      }
    }

    function configForLocalJob(forceMock = false) {
      const config = buildRunConfig(collectFormState($));
      if (forceMock) {
        config.provider.name = "mock";
        config.provider.fallback_mask_provider = null;
      }
      if (!LOCAL_JOB_PROVIDERS.has(config.provider.name)) {
        throw new Error(`${config.provider.name} cannot run in the local UI worker yet. Use Start mock job for a no-model smoke run.`);
      }
      return config;
    }

    function rememberJobConfig(job, config) {
      const id = jobIdentifier(job);
      if (!id) return;
      state.selectedJobId = id;
      state.selectedJob = job;
      state.lastRunConfig = config;
      state.runConfigsByJob[id] = config;
    }

    async function loadJobReview(jobId) {
      if (!jobId) {
        state.selectedJob = null;
        state.jobReview = null;
        state.jobEvents = [];
        state.jobArtifacts = [];
        state.reviewTracks = [];
        state.correctionState = emptyCorrectionState();
        renderJobReview();
        return;
      }

      const [jobBody, eventsBody, artifactsBody, correctionsBody] = await Promise.all([
        api(`/api/jobs/${encodeURIComponent(jobId)}`),
        api(`/api/jobs/${encodeURIComponent(jobId)}/events`),
        api(`/api/jobs/${encodeURIComponent(jobId)}/artifacts`),
        api(correctionRoute(jobId)).catch((error) => ({ correctionStateError: error.message })),
      ]);

      state.selectedJob = jobBody.job || null;
      state.jobEvents = asArray(eventsBody.events);
      state.jobArtifacts = asArray(artifactsBody.artifacts);
      state.jobReview = artifactsBody.review || null;
      state.correctionState = correctionsBody.correctionStateError
        ? {
            ...emptyCorrectionState(jobId),
            loaded: false,
            persistenceStatus: "unavailable",
            persistenceMessage: correctionsBody.correctionStateError,
          }
        : normalizeCorrectionState(correctionsBody, jobId);
      const baseTracks = buildReviewTracks({
        job: state.selectedJob,
        config: jobConfig(state.selectedJob),
        artifacts: state.jobArtifacts,
        review: state.jobReview,
      });
      state.reviewTracks = applyCorrectionStateToTracks(baseTracks, state.correctionState);
      for (const track of state.reviewTracks) {
        if (!(track.id in state.trackVisibility)) {
          state.trackVisibility[track.id] = true;
        }
      }
      renderJobs();
      renderJobReview();
    }

    function stopJobPolling() {
      if (pollTimer) {
        window.clearInterval(pollTimer);
        pollTimer = null;
      }
      state.polling = false;
    }

    async function pollSelectedJob() {
      if (!state.selectedProjectId || !state.selectedJobId || pollInFlight) return;
      pollInFlight = true;
      try {
        const progressBody = await api(`/api/progress?projectId=${encodeURIComponent(state.selectedProjectId)}`);
        state.jobs = asArray(progressBody.progress);
        await loadJobReview(state.selectedJobId);
        if (!isActiveJob(selectedJob())) {
          stopJobPolling();
        }
      } catch (error) {
        $("#providerWarning").textContent = error.message;
        $("#providerWarning").className = "warning-box is-bad";
      } finally {
        pollInFlight = false;
      }
    }

    function startJobPolling() {
      stopJobPolling();
      state.polling = true;
      pollTimer = window.setInterval(pollSelectedJob, 2000);
    }

    async function startRunFromConfig({ forceMock = false } = {}) {
      if (!state.selectedProjectId) {
        $("#providerWarning").textContent = "Create or select a project before starting a run.";
        $("#providerWarning").className = "warning-box is-bad";
        return;
      }
      if (!state.selectedVideoId) {
        $("#providerWarning").textContent = "Register or select a video before starting a run.";
        $("#providerWarning").className = "warning-box is-bad";
        return;
      }

      let config;
      try {
        config = configForLocalJob(forceMock);
      } catch (error) {
        $("#providerWarning").textContent = error.message;
        $("#providerWarning").className = "warning-box is-bad";
        return;
      }

      $("#runStatus").textContent = "Starting";
      $("#runStatus").className = "status-chip is-neutral";
      try {
        const jobPayload = {
          projectId: state.selectedProjectId,
          videoId: state.selectedVideoId,
          runConfig: config,
          run: true,
        };
        const response = await api("/api/jobs", {
          method: "POST",
          body: JSON.stringify(jobPayload),
        });
        rememberJobConfig(response.job, config);
        await refreshProjectData();
        await loadJobReview(state.selectedJobId);
        if (isActiveJob(selectedJob())) {
          startJobPolling();
        }
      } catch (error) {
        $("#runStatus").textContent = "Failed";
        $("#runStatus").className = "status-chip is-bad";
        $("#providerWarning").textContent = error.message;
        $("#providerWarning").className = "warning-box is-bad";
      }
    }

    function applyPreset(presetName, options = {}) {
      state.selectedPreset = PRESETS[presetName] ? presetName : "trace_one_object";
      document.querySelectorAll(".goal").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.preset === state.selectedPreset);
      });
      if (!options.keepProvider) {
        $("#maskProviderSelect").dataset.userSelected = "false";
      }
      renderPresetFields();
      renderMaskProviderOptions();
      const preset = PRESETS[state.selectedPreset];
      if (!options.keepProvider && preset.maskProvider && $("#maskProviderSelect").querySelector(`option[value="${preset.maskProvider}"]`)) {
        $("#maskProviderSelect").value = preset.maskProvider;
      }
      renderConfigPreview();
    }

    function updatePointKind(kind) {
      state.pointKind = kind;
      document.querySelectorAll("[data-point-kind]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.pointKind === kind);
        button.setAttribute("aria-pressed", String(button.dataset.pointKind === kind));
      });
    }

    function updateTool(tool) {
      state.activeTool = tool;
      document.querySelectorAll("[data-tool]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.tool === tool);
        button.setAttribute("aria-pressed", String(button.dataset.tool === tool));
      });
    }

    function currentObjectIdentity() {
      const objectId = slugObjectId($("#objectId").value, "object_0");
      const label = $("#objectLabel").value.trim() || objectId;
      return { objectId, label };
    }

    function addPointPrompt(point) {
      const { objectId, label } = currentObjectIdentity();
      state.prompts.push(
        normalizePrompt(
          {
            kind: state.pointKind,
            frame_index: state.video.currentFrame,
            object_id: objectId,
            label,
            data: point,
          },
          objectId,
          label,
        ),
      );
      renderConfigPreview();
    }

    function markKeyframe(frame = state.video.currentFrame) {
      state.keyframes.add(Math.max(0, Math.round(frame)));
      renderConfigPreview();
    }

    function nearestPrompt(point) {
      let nearest = null;
      let distance = Infinity;
      for (const prompt of state.prompts) {
        if (prompt.kind === "box") {
          const box = prompt.data;
          const center = { x: box.x + box.w / 2, y: box.y + box.h / 2 };
          const currentDistance = Math.hypot(point.x - center.x, point.y - center.y);
          if (currentDistance < distance) {
            nearest = prompt;
            distance = currentDistance;
          }
        } else {
          const currentDistance = Math.hypot(point.x - prompt.data.x, point.y - prompt.data.y);
          if (currentDistance < distance) {
            nearest = prompt;
            distance = currentDistance;
          }
        }
      }
      return distance <= 28 ? nearest : null;
    }

    function labelNearestPrompt(point) {
      const prompt = nearestPrompt(point);
      if (!prompt) return;
      const { objectId, label } = currentObjectIdentity();
      prompt.object_id = objectId;
      prompt.label = label;
      state.selectedPromptId = prompt.id;
      renderConfigPreview();
    }

    function canvasPointFromEvent(event) {
      const rect = elements.canvas.getBoundingClientRect();
      return mapClientPointToVideo(event.clientX, event.clientY, rect, state.video.width, state.video.height);
    }

    function onCanvasPointerDown(event) {
      if (!state.video.width || !state.video.height) return;
      elements.canvas.setPointerCapture(event.pointerId);
      const point = canvasPointFromEvent(event);
      if (!point.inside) return;
      state.pointer = point;
      if (state.activeTool === "point") {
        addPointPrompt({ x: point.x, y: point.y });
      } else if (state.activeTool === "box") {
        const { objectId, label } = currentObjectIdentity();
        state.draftBox = {
          id: `draft_${Date.now()}`,
          kind: "box",
          frame_index: state.video.currentFrame,
          object_id: objectId,
          label,
          start: { x: point.x, y: point.y },
          data: { x: point.x, y: point.y, w: 1, h: 1 },
        };
      } else if (state.activeTool === "brush" || state.activeTool === "eraser") {
        state.activeStroke = {
          mode: state.activeTool === "eraser" ? "erase" : "paint",
          frame_index: state.video.currentFrame,
          brush_size: toInteger($("#brushSize").value, 18),
          points: [{ x: point.x, y: point.y }],
        };
      } else if (state.activeTool === "label") {
        labelNearestPrompt(point);
      } else if (state.activeTool === "keyframe") {
        markKeyframe(state.video.currentFrame);
      }
      drawOverlay();
    }

    function onCanvasPointerMove(event) {
      if (!state.video.width || !state.video.height) return;
      const point = canvasPointFromEvent(event);
      state.pointer = point;
      $("#coordinateReadout").textContent = point.inside ? `x: ${point.x}, y: ${point.y}` : "x: -, y: -";
      if (state.draftBox && point.inside) {
        const start = state.draftBox.start;
        const x0 = Math.min(start.x, point.x);
        const y0 = Math.min(start.y, point.y);
        const x1 = Math.max(start.x, point.x);
        const y1 = Math.max(start.y, point.y);
        state.draftBox.data = { x: x0, y: y0, w: Math.max(1, x1 - x0), h: Math.max(1, y1 - y0) };
      }
      if (state.activeStroke && point.inside) {
        const last = state.activeStroke.points[state.activeStroke.points.length - 1];
        if (!last || Math.hypot(last.x - point.x, last.y - point.y) >= 2) {
          state.activeStroke.points.push({ x: point.x, y: point.y });
        }
      }
      drawOverlay();
    }

    function onCanvasPointerUp(event) {
      if (state.draftBox) {
        const { objectId, label } = currentObjectIdentity();
        state.prompts.push(normalizePrompt(state.draftBox, objectId, label));
        state.draftBox = null;
        renderConfigPreview();
      }
      if (state.activeStroke) {
        state.strokes.push(state.activeStroke);
        state.activeStroke = null;
        renderConfigPreview();
      }
      try {
        elements.canvas.releasePointerCapture(event.pointerId);
      } catch {
        // Pointer capture may already be released by the browser.
      }
      drawOverlay();
    }

    function seekToFrame(frame) {
      const fps = Math.max(0.1, toNumber($("#sampleFps").value, 12));
      const nextFrame = Math.max(0, Math.round(frame));
      if (Number.isFinite(elements.video.duration) && elements.video.duration > 0) {
        elements.video.currentTime = clamp(nextFrame / fps, 0, elements.video.duration);
      }
      state.video.currentFrame = nextFrame;
      renderVideoMetrics();
      renderConfigPreview();
    }

    function applyLoadedConfig(config) {
      const presetEntry = Object.entries(PRESETS).find(([, preset]) => preset.discoveryMode === config.discovery?.mode);
      applyPreset(presetEntry?.[0] || "trace_one_object", { keepProvider: true });
      $("#objectId").value = config.objects?.[0]?.object_id || "object_0";
      $("#objectLabel").value = config.objects?.[0]?.label || "selected_object";
      $("#sampleFps").value = config.sampling?.sample_fps ?? 12;
      $("#maxFrames").value = config.sampling?.max_frames ?? 48;
      $("#minArea").value = config.filters?.min_area ?? 100;
      $("#outputMode").value = config.export?.output_mode || "authoring";
      $("#maskProviderSelect").value = config.provider?.name || $("#maskProviderSelect").value;
      $("#externalMaskDir").value = config.provider?.external?.mask_dir || config.objects?.[0]?.mask_dir || "masks/object_0";
      $("#textPrompt").value = config.discovery?.config?.text || $("#textPrompt").value;
      $("#classList").value = asArray(config.discovery?.config?.classes).join(", ") || $("#classList").value;
      $("#deviceSelect").value = config.provider?.sam2?.device || "auto";
      $("#modelName").value = config.provider?.sam2?.hosted_config?.model || "auto";
      state.prompts = [];
      state.strokes = [];
      for (const prompt of asArray(config.prompts)) {
        if (prompt.kind === "mask") {
          state.strokes.push(...asArray(prompt.data?.strokes));
        } else {
          state.prompts.push(normalizePrompt(prompt, $("#objectId").value, $("#objectLabel").value));
        }
      }
      state.keyframes = new Set(parseKeyframes(config.discovery?.config?.keyframes || asArray(config.prompts).map((prompt) => prompt.frame_index).join(",")));
      if (!state.keyframes.size) state.keyframes.add(0);
      renderVideoMetrics();
      renderConfigPreview();
    }

    async function loadRootData() {
      const capabilityParams = new URLSearchParams();
      const videoPath = $("#videoPath")?.value?.trim();
      if (videoPath) capabilityParams.set("video", videoPath);
      capabilityParams.set("outputDir", "out");
      const capabilityRoute = capabilityParams.toString() ? `/api/capabilities?${capabilityParams}` : "/api/capabilities";
      const entries = await Promise.all(
        [
          ["health", "/api/health"],
          ["capabilities", capabilityRoute],
          ["runDefaults", "/api/run-config/defaults"],
          ["exportFormats", "/api/exports/formats"],
          ["projects", "/api/projects"],
        ].map(async ([key, route]) => {
          try {
            return [key, await api(route), null];
          } catch (error) {
            return [key, null, error.message];
          }
        }),
      );

      state.errors = {};
      for (const [key, payload, error] of entries) {
        if (error) state.errors[key] = error;
        if (key === "health") state.health = payload;
        if (key === "capabilities") state.capabilities = payload;
        if (key === "runDefaults") state.runDefaults = payload;
        if (key === "exportFormats") state.exportFormats = payload;
        if (key === "projects") state.projects = payload?.projects || [];
      }
    }

    function mergeProgressJobs(jobs, progress) {
      const lookup = new Map(asArray(progress).map((job) => [jobIdentifier(job), job]));
      return asArray(jobs).map((job) => ({ ...job, ...(lookup.get(jobIdentifier(job)) || {}) }));
    }

    function ensureSelectedJob() {
      if (state.selectedJobId && state.jobs.some((job) => jobIdentifier(job) === state.selectedJobId)) return;
      const active = state.jobs.find(isActiveJob);
      state.selectedJobId = jobIdentifier(active || state.jobs[0] || {});
      state.selectedJob = state.jobs.find((job) => jobIdentifier(job) === state.selectedJobId) || null;
    }

    async function refreshSelectedJobReview() {
      if (!state.selectedJobId) {
        state.selectedJob = null;
        state.jobReview = null;
        state.jobEvents = [];
        state.jobArtifacts = [];
        state.reviewTracks = [];
        state.correctionState = emptyCorrectionState();
        renderJobReview();
        return;
      }

      const id = state.selectedJobId;
      const [jobResult, eventsResult, artifactsResult, artifactsAliasResult, correctionsResult] = await Promise.all(
        [
          ["job", `/api/jobs/${encodeURIComponent(id)}`],
          ["events", `/api/jobs/${encodeURIComponent(id)}/events`],
          ["artifacts", `/api/jobs/${encodeURIComponent(id)}/artifacts`],
          ["artifactsAlias", `/api/artifacts?jobId=${encodeURIComponent(id)}`],
          ["corrections", correctionRoute(id)],
        ].map(async ([key, route]) => {
          try {
            return [key, await api(route), null];
          } catch (error) {
            return [key, null, error.message];
          }
        }),
      );

      state.selectedJob = jobResult[1]?.job || state.jobs.find((job) => jobIdentifier(job) === id) || null;
      state.jobEvents = eventsResult[1]?.events || [];
      const artifacts = artifactsResult[1]?.artifacts || artifactsAliasResult[1]?.artifacts || [];
      state.jobArtifacts = artifacts;
      state.jobReview = artifactsResult[1]?.review || artifactsAliasResult[1]?.review || null;
      state.errors.selectedJob = [jobResult[2], eventsResult[2], artifactsResult[2], artifactsAliasResult[2]].filter(Boolean).join(" ");
      state.correctionState = correctionsResult[2]
        ? {
            ...emptyCorrectionState(id),
            loaded: false,
            persistenceStatus: "unavailable",
            persistenceMessage: correctionsResult[2],
          }
        : normalizeCorrectionState(correctionsResult[1], id);
      if (!state.correctionState.mergeSuggestions.length && state.jobReview?.mergeSuggestions) {
        state.correctionState.mergeSuggestions = asArray(state.jobReview.mergeSuggestions);
      }
      const config = jobConfig(state.selectedJob);
      const baseTracks = buildReviewTracks({ job: state.selectedJob, config, artifacts: state.jobArtifacts, review: state.jobReview });
      state.reviewTracks = applyCorrectionStateToTracks(baseTracks, state.correctionState);
      for (const track of state.reviewTracks) {
        if (!(track.id in state.trackVisibility)) state.trackVisibility[track.id] = true;
      }
      renderJobReview();
    }

    function shouldPollJobs() {
      return Boolean(state.selectedProjectId && (state.jobs.some(isActiveJob) || (selectedJob() && !TERMINAL_JOB_STATUSES.has(String(selectedJob().status || "").toLowerCase()))));
    }

    function stopPolling() {
      if (pollTimer) window.clearInterval(pollTimer);
      pollTimer = null;
      state.polling = false;
    }

    function startPolling() {
      if (pollTimer) return;
      state.polling = true;
      pollTimer = window.setInterval(async () => {
        if (pollInFlight) return;
        pollInFlight = true;
        try {
          await refreshProjectData({ quiet: true });
        } finally {
          pollInFlight = false;
          if (!shouldPollJobs()) stopPolling();
        }
      }, 2200);
    }

    async function refreshProjectData(options = {}) {
      state.errors.videos = "";
      state.errors.jobs = "";
      if (!state.selectedProjectId) {
        state.videos = [];
        state.jobs = [];
        state.selectedJobId = "";
      } else {
        const [videos, jobs, progress] = await Promise.all(
          [
            ["videos", `/api/videos?projectId=${encodeURIComponent(state.selectedProjectId)}`],
            ["jobs", `/api/jobs?projectId=${encodeURIComponent(state.selectedProjectId)}`],
            ["progress", `/api/progress?projectId=${encodeURIComponent(state.selectedProjectId)}`],
          ].map(async ([key, route]) => {
            try {
              return [key, await api(route), null];
            } catch (error) {
              return [key, null, error.message];
            }
          }),
        );

        state.videos = videos[1]?.videos || [];
        state.jobs = mergeProgressJobs(jobs[1]?.jobs || [], progress[1]?.progress || []);
        if (videos[2]) state.errors.videos = videos[2];
        if (jobs[2]) state.errors.jobs = jobs[2];
      }
      ensureSelectedJob();
      renderVideos();
      renderJobs();
      await refreshSelectedJobReview();
      if (!options.quiet && shouldPollJobs()) startPolling();
    }

    async function refreshAll() {
      renderApiStatus("is-neutral", "Checking API");
      await loadRootData();
      renderHealth();
      renderCapabilities();
      renderFirstRunChecklist();
      renderRunDefaults();
      renderProjects();
      renderExportPresetOptions();
      renderMaskProviderOptions();
      renderPresetFields();
      renderApiStatus(state.errors.health ? "is-bad" : "is-ready", state.errors.health ? "API unavailable" : "API ready");
      await refreshProjectData();
      renderConfigPreview();
    }

    async function startJobFromConfig({ forceMock = false } = {}) {
      if (!state.selectedProjectId) {
        $("#runStatus").textContent = "No project";
        $("#runStatus").className = "status-chip is-bad";
        $("#fallbackDiagnostics").innerHTML = `<div class="diagnostic-row is-bad"><strong>project required</strong><span class="row-meta">Create or select a local project before starting a run.</span></div>`;
        return;
      }
      if (!state.selectedVideoId) {
        $("#runStatus").textContent = "No video";
        $("#runStatus").className = "status-chip is-bad";
        $("#fallbackDiagnostics").innerHTML = `<div class="diagnostic-row is-bad"><strong>video required</strong><span class="row-meta">Register and select a local source video before starting a run.</span></div>`;
        return;
      }

      let config;
      try {
        config = buildRunConfig(collectFormState($));
      } catch (error) {
        $("#runStatus").textContent = "Config invalid";
        $("#runStatus").className = "status-chip is-bad";
        $("#fallbackDiagnostics").innerHTML = `<div class="diagnostic-row is-bad"><strong>config</strong><span class="row-meta">${escapeHtml(error.message)}</span></div>`;
        return;
      }

      const requestedProvider = forceMock ? "mock" : config.provider.name;
      const runtimeConfig = forceMock ? { ...config, provider: { ...config.provider, name: "mock" } } : config;
      state.lastRunConfig = runtimeConfig;

      if (!forceMock && !LOCAL_JOB_PROVIDERS.has(requestedProvider)) {
        $("#runStatus").textContent = "Provider gated";
        $("#runStatus").className = "status-chip is-bad";
        $("#fallbackDiagnostics").innerHTML = `
          <div class="diagnostic-row is-bad">
            <strong>${escapeHtml(requestedProvider)}</strong>
            <span class="row-meta">Local job execution currently accepts deterministic providers only: mock, threshold, or external. Use the mock job control for a no-model smoke run, or switch providers before starting.</span>
          </div>
        `;
        return;
      }

      $("#runStatus").textContent = forceMock ? "Starting mock" : "Starting";
      $("#runStatus").className = "status-chip is-neutral";
      try {
        const payload = {
          projectId: state.selectedProjectId,
          videoId: state.selectedVideoId,
          maskProvider: requestedProvider,
          sampleFps: runtimeConfig.sampling?.sample_fps,
          maxFrames: runtimeConfig.sampling?.max_frames,
          rightsContext: runtimeConfig.rights || {},
          runConfig: runtimeConfig,
          run: true,
        };
        const created = await api("/api/jobs", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        const id = jobIdentifier(created.job);
        state.runConfigsByJob[id] = runtimeConfig;
        state.selectedJobId = id;
        state.selectedJob = created.job;
        state.jobs = [created.job, ...state.jobs.filter((job) => jobIdentifier(job) !== id)];
        state.jobEvents = [];
        state.jobArtifacts = [];
        state.correctionState = emptyCorrectionState(id);
        state.reviewTracks = buildReviewTracks({ job: created.job, config: runtimeConfig, artifacts: [] });
        for (const track of state.reviewTracks) state.trackVisibility[track.id] = true;
        renderJobs();
        renderJobReview();
        await refreshSelectedJobReview();
        startPolling();
      } catch (error) {
        $("#runStatus").textContent = "Start failed";
        $("#runStatus").className = "status-chip is-bad";
        $("#fallbackDiagnostics").innerHTML = `
          <div class="diagnostic-row is-bad">
            <strong>job start failed</strong>
            <span class="row-meta">${escapeHtml(error.message)}</span>
          </div>
        `;
      }
    }

    function selectedCorrectionFrameRange() {
      const start = toInteger($("#correctionFrameStart").value, state.video.currentFrame);
      const end = toInteger($("#correctionFrameEnd").value, start);
      return [Math.max(0, Math.min(start, end)), Math.max(0, Math.max(start, end))];
    }

    function correctionPromptsFromCurrentTools() {
      return allPromptsForDisplay().map((prompt) => ({
        kind: prompt.kind,
        frame_index: toInteger(prompt.frame_index, state.video.currentFrame),
        object_id: prompt.object_id,
        label: prompt.label,
        data: { ...prompt.data },
      }));
    }

    function rebuildTracksFromCorrectionState() {
      const baseTracks = buildReviewTracks({
        job: selectedJob(),
        config: jobConfig(selectedJob()),
        artifacts: state.jobArtifacts,
        review: state.jobReview,
      });
      state.reviewTracks = applyCorrectionStateToTracks(baseTracks, state.correctionState);
      for (const track of state.reviewTracks) {
        if (!(track.id in state.trackVisibility)) state.trackVisibility[track.id] = true;
      }
    }

    function markCorrectionFailure(message) {
      state.correctionState.persistenceStatus = "failed";
      state.correctionState.persistenceMessage = `Backend correction API did not save the last edit: ${message}`;
      const last = state.correctionState.history[state.correctionState.history.length - 1];
      if (last) last.persistenceStatus = "failed";
      rebuildTracksFromCorrectionState();
      renderJobReview();
    }

    function appendOptimisticCorrection(action) {
      const entry = normalizeHistoryEntry(
        {
          ...action,
          id: action.id || `local_${Date.now()}_${Math.random().toString(16).slice(2)}`,
          createdAt: new Date().toISOString(),
          persistenceStatus: "saving",
        },
        state.correctionState.history.length,
      );
      const trackEdits = { ...(state.correctionState.trackEdits || {}) };
      applyActionToTrackEdits(trackEdits, entry);
      state.correctionState = {
        ...state.correctionState,
        trackEdits,
        history: [...asArray(state.correctionState.history), entry],
        persistenceStatus: "saving",
        persistenceMessage: "Saving correction edit through the local backend correction API.",
      };
      rebuildTracksFromCorrectionState();
      renderJobReview();
      return entry;
    }

    function applyCorrectionResponse(response, fallbackState) {
      const normalized = normalizeCorrectionState(response, state.selectedJobId);
      if (!normalized.history.length) normalized.history = fallbackState.history;
      if (!Object.keys(normalized.trackEdits || {}).length) normalized.trackEdits = fallbackState.trackEdits;
      if (!normalized.syntheticTracks.length) normalized.syntheticTracks = fallbackState.syntheticTracks;
      const diagnosticMessage = correctionResponseMessage(response);
      normalized.persistenceStatus = "saved";
      normalized.persistenceMessage = diagnosticMessage
        ? `Correction edit saved; ${diagnosticMessage}`
        : "Correction edit saved in the local backend project state.";
      normalized.history = normalized.history.map((entry) => ({ ...entry, persistenceStatus: "saved" }));
      if (response?.review) state.jobReview = response.review;
      state.correctionState = normalized;
      rebuildTracksFromCorrectionState();
      renderJobReview();
    }

    async function postCorrectionAction(jobId, payload) {
      try {
        return await api(trackEditRoute(jobId), {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } catch (error) {
        if (!/route not found|not found|404/i.test(error.message)) throw error;
        return api(correctionRoute(jobId), {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
    }

    async function submitCorrectionAction(action) {
      if (!state.selectedJobId) {
        state.correctionState = {
          ...emptyCorrectionState(),
          persistenceStatus: "failed",
          persistenceMessage: "Select a run before applying track corrections.",
        };
        renderJobReview();
        return;
      }

      appendOptimisticCorrection(action);
      const fallbackState = {
        ...state.correctionState,
        trackEdits: { ...(state.correctionState.trackEdits || {}) },
        history: [...state.correctionState.history],
        syntheticTracks: [...asArray(state.correctionState.syntheticTracks)],
      };
      try {
        const response = await postCorrectionAction(state.selectedJobId, {
          projectId: state.selectedProjectId,
          jobId: state.selectedJobId,
          action,
          correction: action,
          correctionState: {
            format: CORRECTION_STATE_FORMAT,
            jobId: state.selectedJobId,
            trackEdits: state.correctionState.trackEdits,
            syntheticTracks: state.correctionState.syntheticTracks,
            history: state.correctionState.history,
          },
        });
        applyCorrectionResponse(response, fallbackState);
      } catch (error) {
        markCorrectionFailure(error.message);
      }
    }

    function relabelSelectedTrack() {
      const trackId = state.selectedCorrectionTrackId;
      const label = $("#correctionLabelInput").value.trim();
      if (!trackId || !label) {
        markCorrectionFailure("Select a track and enter a non-empty label.");
        return;
      }
      submitCorrectionAction({ type: "relabel_track", trackId, label });
    }

    function mergeSelectedTracks() {
      const trackIds = [...state.mergeSelection].filter(Boolean);
      if (trackIds.length < 2) {
        markCorrectionFailure("Select at least two tracks to merge.");
        return;
      }
      const keepTrackId = trackIds.includes(state.selectedCorrectionTrackId) ? state.selectedCorrectionTrackId : trackIds[0];
      submitCorrectionAction({ type: "merge_tracks", trackIds, keepTrackId });
    }

    function splitSelectedTrack() {
      const trackId = state.selectedCorrectionTrackId;
      if (!trackId) {
        markCorrectionFailure("Select a track before splitting.");
        return;
      }
      const frameRange = selectedCorrectionFrameRange();
      submitCorrectionAction({ type: "split_track", trackId, frameRange });
    }

    function addObjectFromPrompts() {
      const prompts = correctionPromptsFromCurrentTools();
      if (!prompts.length) {
        markCorrectionFailure("Draw a point, box, or brush prompt before adding an object.");
        return;
      }
      const { objectId, label } = currentObjectIdentity();
      const existing = new Set(state.reviewTracks.map((track) => track.id));
      const nextObjectId = existing.has(objectId) ? `${objectId}_added_${state.correctionState.history.length + 1}` : objectId;
      const frameRange = selectedCorrectionFrameRange();
      submitCorrectionAction({
        type: "add_object",
        objectId: nextObjectId,
        label,
        prompts,
        frameRange,
        correctionRequest: buildCorrectionRequestFromPrompts(nextObjectId, prompts, frameRange),
      });
    }

    function repairSelectedTrackFromPrompts() {
      const trackId = state.selectedCorrectionTrackId;
      const prompts = correctionPromptsFromCurrentTools();
      if (!trackId) {
        markCorrectionFailure("Select a track before repairing it.");
        return;
      }
      if (!prompts.length) {
        markCorrectionFailure("Draw a point, box, or brush prompt before repairing a track.");
        return;
      }
      const frameRange = selectedCorrectionFrameRange();
      submitCorrectionAction({
        type: "repair_track",
        trackId,
        prompts,
        frameRange,
        correctionRequest: buildCorrectionRequestFromPrompts(trackId, prompts, frameRange),
      });
    }

    async function validateSelectedExport() {
      if (!state.selectedJobId) return;
      const payload = exportPayloadFromControls();
      state.exportValidation = {
        jobId: state.selectedJobId,
        validation: null,
        message: "Validating export.",
      };
      renderExportPanel();
      try {
        const response = await api(`/api/jobs/${encodeURIComponent(state.selectedJobId)}/validate`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        state.exportValidation = { ...response, jobId: state.selectedJobId };
      } catch (error) {
        state.exportValidation = {
          jobId: state.selectedJobId,
          validation: { ok: false, checked: 0, issueCount: 1, issues: [{ path: "export", message: error.message }] },
        };
      }
      renderExportPanel();
    }

    async function exportSelectedMotionJson() {
      if (!state.selectedJobId) return;
      const payload = exportPayloadFromControls();
      state.exportResult = {
        jobId: state.selectedJobId,
        validation: null,
        assets: [],
      };
      $("#exportStatus").textContent = "Exporting";
      $("#exportStatus").className = "status-chip is-neutral";
      try {
        const response = await api(`/api/jobs/${encodeURIComponent(state.selectedJobId)}/exports`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        state.exportResult = { ...(response.export || {}), jobId: state.selectedJobId };
        state.exportValidation = {
          jobId: state.selectedJobId,
          validation: state.exportResult.validation,
          includedObjectIds: state.exportResult.includedObjectIds,
          excludedObjectIds: state.exportResult.excludedObjectIds,
        };
        if (response.review) state.jobReview = response.review;
        await refreshSelectedJobReview();
      } catch (error) {
        state.exportResult = {
          jobId: state.selectedJobId,
          assets: [],
          validation: { ok: false, checked: 0, issueCount: 1, issues: [{ path: "export", message: error.message }] },
        };
        renderExportPanel();
      }
    }

    async function importExistingMotionJson() {
      if (!state.selectedProjectId) {
        state.importStatus = "Create or select a project before importing a result.";
        $("#importStatus").textContent = "No project";
        return;
      }
      const importPath = $("#motionJsonImportPath").value.trim();
      if (!importPath) return;
      $("#importStatus").textContent = "Importing";
      try {
        const response = await api(`/api/projects/${encodeURIComponent(state.selectedProjectId)}/imports/motionjson`, {
          method: "POST",
          body: JSON.stringify({ path: importPath }),
        });
        const imported = response.import || {};
        state.importStatus = imported.validation?.ok ? "Imported and valid" : "Imported with validation issues";
        $("#importStatus").textContent = imported.validation?.ok ? "Valid import" : "Review import";
        state.selectedJobId = jobIdentifier(imported.job || {});
        await refreshProjectData();
      } catch (error) {
        state.importStatus = error.message;
        $("#importStatus").textContent = "Import failed";
      }
    }

    $("#refreshButton").addEventListener("click", refreshAll);
    $("#startRunButton").addEventListener("click", () => startJobFromConfig({ forceMock: false }));
    $("#startMockRunButton").addEventListener("click", () => startJobFromConfig({ forceMock: true }));
    $("#validateExportButton").addEventListener("click", validateSelectedExport);
    $("#exportMotionJsonButton").addEventListener("click", exportSelectedMotionJson);
    $("#exportPresetSelect").addEventListener("change", applyExportPresetDefaults);

    $("#jobList").addEventListener("click", async (event) => {
      const choice = event.target.closest("[data-job-id]");
      if (!choice) return;
      state.selectedJobId = choice.dataset.jobId;
      renderJobs();
      await refreshSelectedJobReview();
      if (shouldPollJobs()) startPolling();
    });

    $("#trackList").addEventListener("change", (event) => {
      const visibleToggle = event.target.closest("[data-track-visible]");
      if (visibleToggle) {
        const trackId = visibleToggle.dataset.trackVisible;
        state.trackVisibility[trackId] = visibleToggle.checked;
        submitCorrectionAction({ type: "set_track_visibility", trackId, visible: visibleToggle.checked });
        return;
      }

      const exportToggle = event.target.closest("[data-track-export]");
      if (exportToggle) {
        submitCorrectionAction({
          type: "set_export_inclusion",
          trackId: exportToggle.dataset.trackExport,
          included: exportToggle.checked,
        });
        return;
      }

      const mergeToggle = event.target.closest("[data-track-merge]");
      if (mergeToggle) {
        if (mergeToggle.checked) state.mergeSelection.add(mergeToggle.dataset.trackMerge);
        else state.mergeSelection.delete(mergeToggle.dataset.trackMerge);
        renderTrackList();
        renderCorrectionPanel();
      }
    });

    $("#trackList").addEventListener("click", (event) => {
      const editButton = event.target.closest("[data-track-edit]");
      if (editButton) {
        state.selectedCorrectionTrackId = editButton.dataset.trackEdit;
        renderCorrectionPanel();
        return;
      }

      const deleteButton = event.target.closest("[data-track-delete]");
      if (deleteButton) {
        submitCorrectionAction({ type: "delete_track", trackId: deleteButton.dataset.trackDelete });
      }
    });

    $("#correctionTrackSelect").addEventListener("change", (event) => {
      state.selectedCorrectionTrackId = event.target.value;
      renderCorrectionPanel();
    });

    $("#relabelTrackButton").addEventListener("click", relabelSelectedTrack);
    $("#mergeTracksButton").addEventListener("click", mergeSelectedTracks);
    $("#splitTrackButton").addEventListener("click", splitSelectedTrack);
    $("#addObjectButton").addEventListener("click", addObjectFromPrompts);
    $("#repairTrackButton").addEventListener("click", repairSelectedTrackFromPrompts);

    $("#useCurrentFrameRangeButton").addEventListener("click", () => {
      $("#correctionFrameStart").value = String(state.video.currentFrame);
      $("#correctionFrameEnd").value = String(state.video.currentFrame);
      renderCorrectionPanel();
    });

    $("#mergeSuggestionList").addEventListener("click", (event) => {
      const suggestion = event.target.closest("[data-merge-suggestion]");
      if (!suggestion) return;
      state.mergeSelection = new Set(
        suggestion.dataset.mergeSuggestion
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      );
      renderTrackList();
      renderCorrectionPanel();
    });

    document.querySelectorAll(".goal").forEach((button) => {
      button.addEventListener("click", () => applyPreset(button.dataset.preset));
    });

    document.querySelectorAll("[data-tool]").forEach((button) => {
      button.addEventListener("click", () => updateTool(button.dataset.tool));
    });

    document.querySelectorAll("[data-point-kind]").forEach((button) => {
      button.addEventListener("click", () => updatePointKind(button.dataset.pointKind));
    });

    $("#projectForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const created = await api("/api/projects", {
          method: "POST",
          body: JSON.stringify({ name: $("#projectName").value.trim() }),
        });
        state.selectedProjectId = created.project.id;
        await refreshAll();
      } catch (error) {
        state.errors.projects = error.message;
        renderProjects();
      }
    });

    $("#projectSelect").addEventListener("change", async (event) => {
      state.selectedProjectId = event.target.value;
      state.selectedVideoId = "";
      state.selectedJobId = "";
      state.selectedJob = null;
      state.jobEvents = [];
      state.jobArtifacts = [];
      state.reviewTracks = [];
      state.correctionState = emptyCorrectionState();
      await refreshProjectData();
    });

    $("#videoSelect").addEventListener("change", (event) => {
      state.selectedVideoId = event.target.value;
      renderVideos();
    });

    $("#videoList").addEventListener("click", (event) => {
      const choice = event.target.closest("[data-video-id]");
      if (!choice) return;
      state.selectedVideoId = choice.dataset.videoId;
      renderVideos();
    });

    $("#videoForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!state.selectedProjectId) {
        $("#videoList").innerHTML = `<div class="error-state">Create a project before adding a video.</div>`;
        return;
      }
      try {
        await api("/api/videos", {
          method: "POST",
          body: JSON.stringify({ projectId: state.selectedProjectId, path: $("#videoPath").value.trim() }),
        });
        await refreshProjectData();
      } catch (error) {
        $("#videoList").innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
      }
    });

    $("#importMotionJsonForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await importExistingMotionJson();
    });

    $("#videoFileInput").addEventListener("change", () => {
      const file = $("#videoFileInput").files?.[0];
      if (!file) return;
      if (state.previewObjectUrl) URL.revokeObjectURL(state.previewObjectUrl);
      state.previewObjectUrl = URL.createObjectURL(file);
      state.video.loadedName = file.name;
      elements.video.src = state.previewObjectUrl;
      elements.video.load();
    });

    elements.video.addEventListener("loadedmetadata", () => {
      state.video.width = elements.video.videoWidth || 0;
      state.video.height = elements.video.videoHeight || 0;
      state.video.duration = Number.isFinite(elements.video.duration) ? elements.video.duration : 0;
      elements.stage.classList.toggle("has-video", Boolean(state.video.width && state.video.height));
      renderVideoMetrics();
      renderConfigPreview();
    });

    elements.video.addEventListener("timeupdate", () => {
      renderVideoMetrics();
      drawOverlay();
    });

    elements.video.addEventListener("play", () => {
      $("#playPauseButton").textContent = "Pause";
    });

    elements.video.addEventListener("pause", () => {
      $("#playPauseButton").textContent = "Play";
    });

    $("#playPauseButton").addEventListener("click", async () => {
      if (!elements.video.src) return;
      if (elements.video.paused) await elements.video.play();
      else elements.video.pause();
    });

    $("#frameSlider").addEventListener("input", (event) => {
      seekToFrame(event.target.value);
    });

    $("#markKeyframeButton").addEventListener("click", () => markKeyframe());

    elements.stage.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        seekToFrame(state.video.currentFrame - 1);
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        seekToFrame(state.video.currentFrame + 1);
      }
    });

    elements.canvas.addEventListener("pointerdown", onCanvasPointerDown);
    elements.canvas.addEventListener("pointermove", onCanvasPointerMove);
    elements.canvas.addEventListener("pointerup", onCanvasPointerUp);
    elements.canvas.addEventListener("pointercancel", onCanvasPointerUp);
    elements.canvas.addEventListener("pointerleave", () => {
      state.pointer = null;
      $("#coordinateReadout").textContent = "x: -, y: -";
      drawOverlay();
    });

    $("#promptList").addEventListener("click", (event) => {
      const row = event.target.closest("[data-prompt-id]");
      if (!row) return;
      state.selectedPromptId = row.dataset.promptId;
      renderPromptList();
    });

    $("#maskProviderSelect").addEventListener("change", () => {
      $("#maskProviderSelect").dataset.userSelected = "true";
      renderConfigPreview();
    });

    [
      "objectLabel",
      "objectId",
      "deviceSelect",
      "brushSize",
      "sampleFps",
      "maxFrames",
      "minArea",
      "maxAreaRatio",
      "stabilityThreshold",
      "overlapThreshold",
      "boxThreshold",
      "textThreshold",
      "motionSensitivity",
      "maxObjects",
      "modelName",
      "outputMode",
      "textPrompt",
      "classList",
      "externalMaskDir",
      "videoPath",
    ].forEach((id) => {
      $(`#${id}`).addEventListener("input", () => {
        renderVideoMetrics();
        renderConfigPreview();
      });
      $(`#${id}`).addEventListener("change", () => {
        renderVideoMetrics();
        renderConfigPreview();
      });
    });

    $("#saveConfigButton").addEventListener("click", () => {
      const config = buildRunConfig(collectFormState($));
      const blob = new Blob([JSON.stringify(config, null, 2) + "\n"], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "motionjson.run_config.json";
      anchor.click();
      URL.revokeObjectURL(url);
    });

    $("#validateConfigButton").addEventListener("click", validateConfigWithBackend);

    $("#loadConfigInput").addEventListener("change", async () => {
      const file = $("#loadConfigInput").files?.[0];
      if (!file) return;
      try {
        applyLoadedConfig(JSON.parse(await file.text()));
      } catch (error) {
        $("#configStatus").textContent = "Load failed";
        $("#configStatus").className = "status-chip is-bad";
        $("#configPreview").textContent = error.message;
      }
    });

    window.addEventListener("resize", drawOverlay);

    updatePointKind("positive_point");
    updateTool("point");
    renderMaskProviderOptions();
    renderPresetFields();
    renderVideoMetrics();
    renderConfigPreview();
    refreshAll();
  }

  const publicApi = {
    API_ROUTES,
    CORRECTION_STATE_FORMAT,
    PRESETS,
    RUN_CONFIG_SCHEMA,
    applyCorrectionStateToTracks,
    buildCorrectionRequestFromPrompts,
    buildExportPanelSummary,
    buildRunConfig,
    buildReviewTracks,
    containedVideoRect,
    correctionDiagnosticMessages,
    correctionResponseMessage,
    normalizeCorrectionState,
    mapClientPointToVideo,
    normalizePrompt,
    parseCsv,
    parseKeyframes,
    slugObjectId,
    trackFrameForDisplay,
  };

  globalThis.MotionJSONUI = publicApi;

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }

  return publicApi;
})();
