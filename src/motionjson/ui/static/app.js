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
  ];

  const RUN_CONFIG_SCHEMA = "motionjson.extraction_run_config.v0.1";

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

  const defaultState = () => ({
    health: null,
    capabilities: null,
    runDefaults: null,
    projects: [],
    selectedProjectId: "",
    videos: [],
    selectedVideoId: "",
    jobs: [],
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

  function normalizeProgress(job) {
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
              const progress = normalizeProgress(job);
              const status = job.status || "unknown";
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
                <div class="artifact-row">
                  <strong>${escapeHtml(job.type || "job")}</strong>
                  ${statusChip(status, status, /complete|succeeded/.test(String(status).toLowerCase()))}
                  <span class="row-meta">${escapeHtml(job.id || "no id reported")}</span>
                  <div class="job-progress" role="group" aria-label="${escapeAttribute(`${job.type || "job"} progress`)}">
                    <div class="job-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}">
                      <div class="job-progress-bar" style="--progress: ${progress}%"></div>
                    </div>
                    <span class="job-progress-text">${progress}% complete${diagnostics.length ? ` - ${escapeHtml(diagnostics.join(" "))}` : ""}</span>
                  </div>
                </div>
              `;
            })
            .join("")
        : `<div class="empty-state">Jobs will appear here with status, progress, and export diagnostics.</div>`;
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
      const entries = await Promise.all(
        [
          ["health", "/api/health"],
          ["capabilities", "/api/capabilities"],
          ["runDefaults", "/api/run-config/defaults"],
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
        if (key === "projects") state.projects = payload?.projects || [];
      }
    }

    async function refreshProjectData() {
      state.errors.videos = "";
      state.errors.jobs = "";
      if (!state.selectedProjectId) {
        state.videos = [];
        state.jobs = [];
      } else {
        const [videos, jobs] = await Promise.all(
          [
            ["videos", `/api/videos?projectId=${encodeURIComponent(state.selectedProjectId)}`],
            ["jobs", `/api/jobs?projectId=${encodeURIComponent(state.selectedProjectId)}`],
          ].map(async ([key, route]) => {
            try {
              return [key, await api(route), null];
            } catch (error) {
              return [key, null, error.message];
            }
          }),
        );

        state.videos = videos[1]?.videos || [];
        state.jobs = jobs[1]?.jobs || [];
        if (videos[2]) state.errors.videos = videos[2];
        if (jobs[2]) state.errors.jobs = jobs[2];
      }
      renderVideos();
      renderJobs();
    }

    async function refreshAll() {
      renderApiStatus("is-neutral", "Checking API");
      await loadRootData();
      renderHealth();
      renderCapabilities();
      renderRunDefaults();
      renderProjects();
      renderMaskProviderOptions();
      renderPresetFields();
      renderApiStatus(state.errors.health ? "is-bad" : "is-ready", state.errors.health ? "API unavailable" : "API ready");
      await refreshProjectData();
      renderConfigPreview();
    }

    $("#refreshButton").addEventListener("click", refreshAll);

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
    PRESETS,
    RUN_CONFIG_SCHEMA,
    buildRunConfig,
    containedVideoRect,
    mapClientPointToVideo,
    normalizePrompt,
    parseCsv,
    parseKeyframes,
    slugObjectId,
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
