const MotionJSONUI = (() => {
  const API_ROUTES = [
    "/api/health",
    "/api/workspace",
    "/api/preferences",
    "/api/commercial-readiness",
    "/api/capabilities",
    "/api/provider-settings",
    "/api/provider-settings/{providerId}",
    "/api/provider-settings/{providerId}/test",
    "/api/provider-settings/{providerId}/diagnose",
    "/api/provider-settings/{providerId}/smoke-test",
    "/api/provider-settings/{providerId}/advanced-local-paths",
    "/api/provider-settings/{providerId}/setup/start",
    "/api/provider-settings/setup-jobs/{jobId}",
    "/api/provider-settings/setup-jobs/{jobId}/cancel",
    "/api/model-providers",
    "/api/model-providers/{providerId}",
    "/api/model-providers/{providerId}/test",
    "/api/model-providers/{providerId}/estimate",
    "/api/model-runs",
    "/api/model-runs/{runId}",
    "/api/model-runs/{runId}/events",
    "/api/model-runs/{runId}/cancel",
    "/api/model-runs/{runId}/confirm-job",
    "/api/projects",
    "/api/run-config/defaults",
    "/api/run-config/validate",
    "/api/videos",
    "/api/videos/{videoId}/content",
    "/api/videos/{videoId}/prepare-browser-preview",
    "/api/jobs",
    "/api/jobs/{jobId}",
    "/api/jobs/{jobId}/events",
    "/api/jobs/{jobId}/artifacts",
    "/api/jobs/{jobId}/review",
    "/api/jobs/{jobId}/corrections",
    "/api/jobs/{jobId}/track-edits",
    "/api/jobs/{jobId}/track-selected",
    "/api/jobs/{jobId}/cancel",
    "/api/jobs/{jobId}/validate",
    "/api/jobs/{jobId}/exports",
    "/api/jobs/{jobId}/model-plan",
    "/api/progress",
    "/api/artifacts",
    "/api/assets/{assetId}/content",
    "/api/exports/formats",
    "/api/library/assets",
    "/api/library/assets/{libraryAssetId}",
    "/api/library/collections",
    "/api/library/collections/{collectionId}/assets",
    "/api/library/packs",
    "/api/projects/{projectId}/library-assets",
    "/api/projects/{projectId}/imports/motionjson",
  ];

  const RUN_CONFIG_SCHEMA = "motionjson.extraction_run_config.v0.1";
  const CORRECTION_STATE_FORMAT = "motionjson.local_ui_corrections.v0.1";
  const TERMINAL_JOB_STATUSES = new Set(["succeeded", "failed", "canceled", "cancelled"]);
  const STALE_ACTIVE_JOB_MS = 2 * 60 * 1000;
  const LOCAL_JOB_PROVIDERS = new Set(["mock", "threshold", "motion", "external", "sam2-local", "sam2-hf-auto-masks", "sam2-hosted", "sam3-local", "sam3-hosted"]);
  const SHELL_STORAGE_KEYS = {
    sidebarCollapsed: "motionjson.localUi.sidebarCollapsed",
    railCollapsed: "motionjson.localUi.railCollapsed",
    workflowStep: "motionjson.localUi.workflowStep",
    workflowDashboard: "motionjson.localUi.workflowDashboard",
  };
  const SAFE_LOCAL_CONTENT_URL_RE = /^\/api\/(?:videos|artifacts|assets)\/[A-Za-z0-9._~-]+\/content(?:[?#][^\s]*)?$/;
  const TRACK_COLORS = ["#20c4cf", "#45b844", "#2f8dea", "#f9bd0a", "#9b59b6", "#ef5b5b", "#6f7a86"];
  const MODEL_CONNECTOR_PROVIDER_ORDER = ["fake-local-planner", "openai-planner", "openrouter-planner"];
  const BUNDLED_DEMO_VIDEO_PATH = "examples/demo_red_ball.mp4";
  const MODEL_CONNECTIONS = [
    {
      id: "sam2-local",
      providerId: "sam2-local",
      engine: "sam2",
      locality: "local",
      displayLabel: "SAM2 prompt tracking",
      workflow: "Trace one object",
      title: "SAM2 prompt tracking",
      capabilities: ["point", "box", "tracking"],
      recommendation: "Recommended local path for cutting out one prompted object.",
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
      recommendation: "Hosted fallback for promptable SAM2 video tracking when local SAM2 is not ready.",
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
      recommendation: "Recommended local path for finding everything in the scene with SAM3 Tracker masks and video tracking.",
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
  const MODEL_FREE_PRESETS = new Set(["motion_foreground", "external_masks", "review_existing"]);
  const MODEL_CONNECTION_PRIORITY = {
    trace_one_object: ["sam2-local", "sam2-hosted:replicate-sam2-video"],
    trace_all_objects: ["sam3-local", "sam2-hf-auto-masks", "sam3-hosted:custom-sam3-compatible"],
    auto_object_proposals: ["sam2-hf-auto-masks", "sam2-local"],
    text_detector: ["sam3-local", "sam3-hosted:roboflow-sam3-pcs", "sam3-hosted:custom-sam3-compatible", "sam3-hosted:fal-sam3-image"],
  };
  const ADVANCED_MODEL_CONNECTIONS = {
    trace_one_object: ["sam3-local", "sam3-hosted:custom-sam3-compatible"],
  };
  const LIBRARY_SAVEABLE_ARTIFACT_KINDS = new Set([
    "cutout",
    "final_render_mp4",
    "lottie_silhouette",
    "motionjson_export_zip",
    "object_layer_pack",
    "object_manifest",
    "remotion_plan",
    "scene_graph",
    "transparent_webm",
    "validated_motionjson_scene",
    "web_manifest",
    "website_package",
  ]);
  const EXPORT_PRESET_DEFAULTS = {
    compact: { includeMasks: false, includeContours: false, includePreview: true },
    debug: { includeMasks: true, includeContours: true, includePreview: true },
    "vector-heavy": { includeMasks: false, includeContours: true, includePreview: true },
    "raster-fallback": { includeMasks: true, includeContours: false, includePreview: true },
  };
  const EXPORT_HANDOFF_DEFS = [
    {
      id: "website-package",
      title: "Website package",
      kind: "website_package",
      description: "A ZIP with the selected reviewed objects, runtime files, and a ready browser example.",
      readyAction: "Open ZIP",
      pendingAction: "Create package",
    },
    {
      id: "motionjson-scene",
      title: "MotionJSON scene",
      kind: "validated_motionjson_scene",
      description: "A cleaned scene graph with only reviewed export objects and public-safe paths.",
      readyAction: "Open scene",
      pendingAction: "Create scene",
    },
    {
      id: "runtime-snippet",
      title: "Runtime snippet",
      kind: "object_layer_pack",
      snippetKey: "plainJs",
      description: "Copy a plain JavaScript snippet for embedding the reviewed object layer.",
      readyAction: "Copy snippet",
      pendingAction: "Create snippet",
    },
    {
      id: "remotion-plan",
      title: "Remotion plan",
      kind: "remotion_plan",
      snippetKey: "remotion",
      description: "A no-network adapter plan for wiring reviewed objects into an existing Remotion project.",
      readyAction: "Open plan",
      pendingAction: "Create plan",
    },
    {
      id: "developer-handoff",
      title: "Developer handoff",
      kind: "motionjson_export_zip",
      description: "A complete bundle with scene, manifest, validation, quality routing, snippets, and website package.",
      readyAction: "Open bundle",
      pendingAction: "Create bundle",
    },
  ];

  const PRESETS = {
    trace_all_objects: {
      label: "Find everything in scene",
      discoveryMode: "sam3_auto_masks",
      maskProvider: "sam3-local",
      outputMode: "authoring",
    },
    auto_object_proposals: {
      label: "Discover objects",
      discoveryMode: "auto_object_proposals",
      maskProvider: "sam2-local",
      outputMode: "authoring",
    },
    trace_one_object: {
      label: "Cut out one object",
      discoveryMode: "manual_prompt",
      maskProvider: "sam2-local",
      outputMode: "authoring",
    },
    text_detector: {
      label: "Find objects from text",
      discoveryMode: "sam3_concept",
      maskProvider: "sam3-local",
      outputMode: "authoring",
    },
    class_detector: {
      label: "Find known classes",
      discoveryMode: "class_detector",
      maskProvider: "sam2-local",
      outputMode: "authoring",
    },
    sam_auto_masks: {
      label: "Propose visible segments",
      discoveryMode: "sam_auto_masks",
      maskProvider: "sam2-local",
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
      maskProvider: "sam2-local",
      outputMode: "authoring",
    },
  };

  const RUN_PLAN_GOALS = {
    trace_all_objects: {
      title: "Find everything in scene",
      summary: "Sweep the scene for visible object candidates, track accepted objects, then export reviewed tracks.",
    },
    trace_one_object: {
      title: "Cut out one object",
      summary: "Use a point, box, or brush prompt to follow one subject through the video.",
    },
    auto_object_proposals: {
      title: "Discover objects",
      summary: "Propose object candidates first, then keep only the tracks worth exporting.",
    },
    text_detector: {
      title: "Find by description",
      summary: "Use text labels to propose candidates, then review them before tracking.",
    },
    class_detector: {
      title: "Find known classes",
      summary: "Search for configured object classes and review the proposed candidates.",
    },
    sam_auto_masks: {
      title: "Propose all visible segments",
      summary: "Create broad mask proposals for inspection; export stays review-gated.",
    },
    motion_foreground: {
      title: "Find moving things",
      summary: "Use CPU motion cues to find objects that change across frames.",
    },
    external_masks: {
      title: "Import masks",
      summary: "Turn prepared mask frames into object tracks and MotionJSON exports.",
    },
    review_existing: {
      title: "Review previous result",
      summary: "Open an existing result and check tracks before exporting assets.",
    },
  };

  const WORKFLOW_STEPS = [
    {
      id: "choose_goal",
      title: "Choose goal",
      label: "Goal",
      description: "Pick the kind of object tracing workflow before setup details appear.",
      nextHint: "Choose a tracing goal to continue.",
    },
    {
      id: "source_video",
      title: "Add or select video",
      label: "Video",
      description: "Add a local video or open an existing result. Guided mode creates a local workspace automatically.",
      nextHint: "Add a local video or existing result to continue.",
    },
    {
      id: "provider_settings",
      title: "Model setup",
      label: "Model",
      description: "Install, check, or select one compatible SAM engine for the selected workflow.",
      nextHint: "Choose one compatible model connection to continue.",
    },
    {
      id: "prompt_preview",
      title: "Prepare run",
      label: "Prepare",
      description: "Show only the inputs needed for the selected workflow, then run extraction.",
      nextHint: "Add the required prompt or run the prepared workflow.",
    },
    {
      id: "run_monitor",
      title: "Run monitor",
      label: "Run",
      description: "Watch progress, inspect logs, or recover from a failed run before review.",
      nextHint: "Start a run before reviewing tracks and exporting.",
    },
    {
      id: "review_export",
      title: "Review and export",
      label: "Review",
      description: "Inspect the results, correct mistakes, and export reviewed objects.",
      nextHint: "Run extraction before reviewing tracks and exporting.",
    },
  ];

  const WORKFLOW_PANEL_STEP_ALIASES = {
    choose_goal: ["choose_goal"],
    source_video: ["project_video", "source_video"],
    provider_settings: ["provider_settings"],
    prompt_preview: ["prompt_preview", "validate_run"],
    run_monitor: ["run_monitor"],
    review_export: ["review_candidates", "correct_tracks", "export"],
  };

  const WORKFLOW_FRAGMENT_STEP_ALIASES = {
    choose_goal: ["choose_goal"],
    source_video: ["source_video"],
    provider_settings: ["provider_settings"],
    prompt_preview: ["prompt_preview"],
    run_monitor: ["run_monitor"],
    review_export: ["review_candidates", "correct_tracks", "export"],
  };
  const SCREEN_STEPS = [
    { id: "start", label: "Start", workflowSteps: ["choose_goal"] },
    { id: "video", label: "Video", workflowSteps: ["source_video"] },
    { id: "model", label: "Model", workflowSteps: ["provider_settings"] },
    { id: "prepare", label: "Prepare", workflowSteps: ["prompt_preview"] },
    { id: "run", label: "Run", workflowSteps: ["run_monitor"] },
    { id: "review", label: "Review", workflowSteps: ["review_export"] },
  ];

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
    providerSettings: null,
    modelProviders: null,
    workspace: null,
    commercialReadiness: null,
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
    configValidation: null,
    exportValidation: null,
    exportResult: null,
    exportCopyPayloads: {},
    exportCopiedHandoffId: "",
    libraryAssets: [],
    libraryCollections: [],
    libraryPacks: [],
    selectedLibraryAssetId: "",
    selectedLibraryArtifactId: "",
    selectedLibraryCollectionId: "",
    libraryStatus: "Not loaded",
    importStatus: "",
    selectedModelSetupProviderId: "sam2-local",
    modelSetupAlternativesOpen: false,
    providerSetupJobs: {},
    advancedLocalPaths: {},
    copiedAdvancedPathProviderId: "",
    selectedProviderSetupJobId: "",
    modelSetupMessage: "",
    modelSetupTone: "neutral",
    pendingModelSetupConfirmation: null,
    confirmedModelSetupAction: null,
    modelPlanRun: null,
    modelPlanValidation: null,
    modelPlanMessage: "",
    modelPlanTone: "neutral",
    modelPlanConfirmedJobId: "",
    modelPlanConfirming: false,
    selectedCorrectionTrackId: "",
    mergeSelection: new Set(),
    candidateSelection: {},
    candidateSelectionJobId: "",
    candidateTrackingStatus: "",
    runConfigsByJob: {},
    lastRunConfig: null,
    polling: false,
    errors: {},
    railOpenedByUser: false,
    selectedPreset: "trace_one_object",
    activeWorkflowStep: "choose_goal",
    workflowDashboard: false,
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

  const storage = {
    get(key) {
      try {
        return globalThis.localStorage?.getItem(key);
      } catch {
        return null;
      }
    },
    set(key, value) {
      try {
        globalThis.localStorage?.setItem(key, value);
      } catch {
        // Local storage can be unavailable in private or embedded contexts.
      }
    },
  };

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

  function statusCardMarkup(card = {}, options = {}) {
    const className = options.className || "status-summary-card";
    const status = card.status || options.defaultStatus || "needs-action";
    const label = options.includeLabel ? `<span class="section-kicker">${escapeHtml(card.label || "")}</span>` : "";
    return `
      <div class="${escapeAttribute(className)} is-${escapeAttribute(status)}">
        ${label}
        <strong>${escapeHtml(card.value || "")}</strong>
        <span class="row-meta">${escapeHtml(card.detail || "")}</span>
      </div>
    `;
  }

  function safeLocalContentUrl(value) {
    const url = String(value || "").trim();
    return SAFE_LOCAL_CONTENT_URL_RE.test(url) ? url : "";
  }

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

  function normalizeWorkflowStepId(value, fallback = "choose_goal") {
    const id = String(value || "").trim();
    return WORKFLOW_STEPS.some((step) => step.id === id) ? id : fallback;
  }

  function workflowStepIndex(stepId) {
    const normalized = normalizeWorkflowStepId(stepId);
    return Math.max(0, WORKFLOW_STEPS.findIndex((step) => step.id === normalized));
  }

  function workflowNextStepId(stepId, direction = 1) {
    const index = workflowStepIndex(stepId);
    const nextIndex = clamp(index + (direction < 0 ? -1 : 1), 0, WORKFLOW_STEPS.length - 1);
    return WORKFLOW_STEPS[nextIndex].id;
  }

  function workflowScreenForStep(stepId = "choose_goal") {
    const normalized = normalizeWorkflowStepId(stepId);
    return SCREEN_STEPS.find((screen) => screen.workflowSteps.includes(normalized))?.id || "setup";
  }

  function workflowStepForScreen(screenId = "setup") {
    return SCREEN_STEPS.find((screen) => screen.id === screenId)?.workflowSteps[0] || "choose_goal";
  }

  function goalRequiresModel(presetId = "trace_one_object") {
    return !MODEL_FREE_PRESETS.has(String(presetId || ""));
  }

  function goalRequiresReviewExportFlow(presetId = "trace_one_object") {
    return presetId !== "review_existing";
  }

  function workflowRestoredStepFromSnapshot(snapshot = {}, requestedStep = "choose_goal") {
    const selectedPreset = snapshot.selectedPreset || "trace_one_object";
    const hasRunData = Boolean(snapshot.selectedJobId || toInteger(snapshot.candidateCount, 0) || toInteger(snapshot.trackCount, 0));
    if (selectedPreset === "review_existing") {
      return snapshot.selectedJobId ? "review_export" : "choose_goal";
    }
    if (!hasRunData) {
      if (!snapshot.selectedVideoId) return "choose_goal";
    }
    const normalizedStep = normalizeWorkflowStepId(requestedStep);
    const readiness = workflowReadinessFromSnapshot(snapshot);
    const requestedIndex = workflowStepIndex(normalizedStep);
    for (let index = 0; index < requestedIndex; index += 1) {
      const prior = WORKFLOW_STEPS[index];
      if (!readiness[prior.id]?.complete) return prior.id;
    }
    return normalizedStep;
  }

  function workflowReadinessFromSnapshot(snapshot = {}) {
    const selectedPreset = snapshot.selectedPreset || "trace_one_object";
    const promptCount = toInteger(snapshot.promptCount, 0) + toInteger(snapshot.strokeCount, 0);
    const candidateCount = toInteger(snapshot.candidateCount, 0);
    const trackCount = toInteger(snapshot.trackCount, 0);
    const correctionCount = toInteger(snapshot.correctionCount, 0);
    const hasRegisteredVideo = Boolean(snapshot.selectedVideoId);
    const hasImportedResult = selectedPreset === "review_existing" && Boolean(snapshot.selectedJobId);
    const hasPreview = Boolean(snapshot.previewName || snapshot.previewLoaded);
    const previewReady = snapshot.videoPreviewReady === true || snapshot.videoPreviewStatus === "ready";
    const previewBlocked = ["failed", "blocked"].includes(String(snapshot.videoPreviewStatus || ""));
    const providerBlocked = Boolean(snapshot.providerBlocked || snapshot.providerTone === "is-bad");
    const providerWarn = snapshot.providerTone === "is-warn";
    const providerSetupTone = String(snapshot.providerSummaryTone || "");
    const providerConfigured = providerSetupTone === "ready";
    const configBlocked = Boolean(snapshot.configBlocked || snapshot.configTone === "is-bad");
    const configValid = Boolean(snapshot.configValid || snapshot.backendValidated);
    const hasJob = Boolean(snapshot.selectedJobId);
    const hasRunData = hasJob || candidateCount > 0 || trackCount > 0;
    const selectedJobStatus = String(snapshot.selectedJobStatus || "").toLowerCase();
    const jobRunning = isActiveJobStatus(selectedJobStatus);
    const jobFailed = isFailedJobStatus(selectedJobStatus);
    const jobSucceeded = /succeeded|completed|complete/.test(selectedJobStatus);
    const exportOk = Boolean(snapshot.exportOk);
    const requiresModel = goalRequiresModel(selectedPreset);
    const manualPromptRequired = selectedPreset === "trace_one_object";
    const requiresSam3Box = selectedPreset === "trace_one_object" && /sam3/i.test(String(snapshot.providerName || ""));
    const hasBoxPrompt = Boolean(snapshot.hasBoxPrompt);
    const hasPointPrompt = Boolean(snapshot.hasPointPrompt);

    const step = (status, message, options = {}) => ({
      status,
      message,
      tone: options.tone || (status === "done" || status === "ready" ? "is-ready" : status === "blocked" ? "is-bad" : "is-warn"),
      complete: options.complete ?? (status === "done" || status === "ready"),
    });

    return {
      choose_goal: step("done", snapshot.presetLabel ? `Goal selected: ${snapshot.presetLabel}` : "Choose the tracing goal.", { complete: true }),
      source_video: hasImportedResult
        ? step("done", "Existing result loaded for review.")
        : hasRegisteredVideo && previewReady
          ? step("done", "Registered video and browser preview are ready.")
          : hasRegisteredVideo && previewBlocked
            ? step("blocked", snapshot.videoPreviewReason || "Browser preview could not be prepared for this video.", { complete: false })
            : hasRegisteredVideo
              ? step("needs-action", "Preparing a browser-safe preview for this video.", { tone: "is-warn", complete: false })
        : hasPreview
            ? step("needs-action", "Browser preview is loaded; add a local video path before extraction.", { tone: "is-warn", complete: false })
            : step("needs-action", selectedPreset === "review_existing" ? "Open an existing MotionJSON result to continue." : "Add a local video or use the demo video to continue.", { complete: false }),
      provider_settings: !requiresModel
        ? step("done", "No model setup is needed for this workflow.")
        : providerBlocked
        ? step("blocked", "Model setup has a blocker. Open the selected connection and fix it before running.", { complete: false })
        : providerSetupTone === "bad"
          ? step("needs-action", snapshot.providerWarning || "Save one compatible model connection before continuing.", { complete: false })
        : providerWarn || providerSetupTone === "warn"
          ? step("needs-action", "Model setup still needs attention before guided runs continue.", { tone: "is-warn", complete: false })
          : providerConfigured
            ? step("done", "Compatible model connection is ready.")
            : step("needs-action", "Save one compatible model connection before continuing.", { complete: false }),
      prompt_preview:
        manualPromptRequired && requiresSam3Box && !hasBoxPrompt
          ? step("needs-action", "Draw one box around the object for SAM3 tracing.", { complete: false })
          : manualPromptRequired && !requiresSam3Box && !hasBoxPrompt && !hasPointPrompt
            ? step("needs-action", "Add at least one point or box prompt for this goal.", { complete: false })
            : hasJob && !jobFailed
              ? step(configBlocked ? "blocked" : configValid ? "ready" : "done", configBlocked ? "Run validation failed. Fix the generated config before retrying." : "Run started. MotionJSON will switch to review when results are ready.")
              : step("done", promptCount ? `${promptCount} prompt mark${promptCount === 1 ? "" : "s"} ready.` : "This workflow is ready to run without manual prompts."),
      run_monitor: jobFailed
        ? step("blocked", "Run failed or was canceled. Open logs, change setup, run again, or choose a different model.", { complete: false })
        : jobRunning
          ? step("needs-action", "Run is in progress. Watch progress and logs before review.", { tone: "is-neutral", complete: false })
          : jobSucceeded || hasRunData
            ? step("done", "Run finished. Continue to review and export.")
            : step("needs-action", "Start a run before review.", { complete: false }),
      review_export: (jobSucceeded || hasRunData) && !jobFailed
        ? exportOk
          ? step("done", "Reviewed objects exported successfully.")
          : step(correctionCount ? "ready" : "done", trackCount ? `${trackCount} reviewed track${trackCount === 1 ? "" : "s"} ready for export.` : `${candidateCount} candidate${candidateCount === 1 ? "" : "s"} ready to review.`)
        : step("needs-action", selectedPreset === "review_existing" ? "Open an existing result before reviewing and exporting." : "Run extraction before reviewing tracks and exporting.", { complete: false }),
    };
  }

  function workflowSummaryCardsFromSnapshot(snapshot = {}, activeStep = "choose_goal") {
    const activeIndex = workflowStepIndex(activeStep);
    if (activeIndex <= 0) return [];
    const readiness = workflowReadinessFromSnapshot(snapshot);
    const promptCount = toInteger(snapshot.promptCount, 0) + toInteger(snapshot.strokeCount, 0);
    const candidateCount = toInteger(snapshot.candidateCount, 0);
    const trackCount = toInteger(snapshot.trackCount, 0);
    const correctionCount = toInteger(snapshot.correctionCount, 0);
    const providerName = snapshot.providerName || "selected provider";
    const providerDevice = snapshot.providerDevice ? ` on ${snapshot.providerDevice}` : "";
    const values = {
      choose_goal: snapshot.presetLabel || "Goal selected",
      source_video:
        snapshot.selectedPreset === "review_existing"
          ? snapshot.selectedJobId
            ? "Existing result loaded"
            : "No result yet"
          : snapshot.videoName || (snapshot.selectedVideoId ? "Registered video" : snapshot.previewName ? "Preview only" : "No video yet"),
      provider_settings: `${providerName}${providerDevice}`,
      prompt_preview:
        snapshot.selectedJobStatus
          ? humanizeReviewCode(snapshot.selectedJobStatus)
          : promptCount
            ? `${promptCount} prompt mark${promptCount === 1 ? "" : "s"}`
            : "Ready to run",
      run_monitor: snapshot.selectedJobStatus ? humanizeReviewCode(snapshot.selectedJobStatus) : "No run yet",
      review_export: snapshot.exportOk
        ? "Exported"
        : trackCount
          ? `${trackCount} track${trackCount === 1 ? "" : "s"}`
          : `${candidateCount} candidate${candidateCount === 1 ? "" : "s"}`,
    };
    return WORKFLOW_STEPS.slice(0, activeIndex).map((step) => {
      const stepReadiness = readiness[step.id] || {};
      return {
        id: step.id,
        label: step.label,
        value: values[step.id] || step.label,
        detail: stepReadiness.message || step.nextHint || "",
        status: stepReadiness.status || "not-started",
        tone: stepReadiness.tone || "is-muted",
        complete: Boolean(stepReadiness.complete),
      };
    });
  }

  function defaultProjectSummaryText() {
    const project = state.projects.find((item) => item.id === state.selectedProjectId) || null;
    if (project?.name) return `Using ${project.name}. Guided mode creates this local workspace automatically.`;
    return "A local project is created automatically when you add a video or open an existing result.";
  }

  function primaryRunLabelForPreset(presetId = "trace_one_object") {
    const labels = {
      trace_one_object: "Run trace",
      trace_all_objects: "Run scene sweep",
      auto_object_proposals: "Run discovery",
      text_detector: "Run search",
      class_detector: "Run class search",
      sam_auto_masks: "Run segment scan",
      motion_foreground: "Run motion scan",
      external_masks: "Import masks",
      review_existing: "Open result",
    };
    return labels[presetId] || "Run workflow";
  }

  function isActiveJobStatus(status) {
    return /queued|running|pending|started|cancel_requested/.test(String(status || "").toLowerCase());
  }

  function isFailedJobStatus(status) {
    return /failed|error|canceled|cancelled/.test(String(status || "").toLowerCase());
  }

  function workflowStepContractFromSnapshot(snapshot = {}, activeStep = "choose_goal") {
    const readiness = workflowReadinessFromSnapshot(snapshot);
    const activeReadiness = readiness[activeStep] || {};
    const requiresModel = goalRequiresModel(snapshot.selectedPreset || state.selectedPreset);
    const hasVideo = Boolean(snapshot.selectedVideoId);
    const hasResult = Boolean(snapshot.selectedJobId) && (snapshot.selectedPreset || state.selectedPreset) === "review_existing";
    const previewStatus = String(snapshot.videoPreviewStatus || "");
    const previewReason = snapshot.videoPreviewReason || "";
    const videoPathValue = typeof document !== "undefined" ? document.querySelector("#videoPath")?.value.trim() || "" : "";
    const importPathValue = typeof document !== "undefined" ? document.querySelector("#motionJsonImportPath")?.value.trim() || "" : "";
    const hasModelSetupForm = typeof document !== "undefined" ? Boolean(document.querySelector("#modelSetupForm")) : snapshot.providerSummaryTone === "ready" || snapshot.providerSummaryTone === "warn";
    const selectedJobStatus = String(snapshot.selectedJobStatus || selectedJob()?.status || "").toLowerCase();
    const jobRunning = isActiveJobStatus(selectedJobStatus);
    const jobFailed = isFailedJobStatus(selectedJobStatus);
    const exportIncludedIds = state.reviewTracks.filter(isTrackExportIncluded).map(trackObjectId).filter(Boolean);
    const exportStatus = state.exportValidation?.validation || state.exportResult?.validation || null;
    const staticFallbackCount = state.reviewTracks.filter((track) => isTrackExportIncluded(track) && trackUsesStaticKeyframeFallback(track)).length;
    const exportAction = exportActionState({
      job: selectedJob(),
      includedIds: exportIncludedIds,
      status: exportStatus,
      trackCount: state.reviewTracks.length,
      pendingIds: buildExportPanelSummary({
        exportState: state.exportResult || state.exportValidation || {},
        reviewExport: state.jobReview?.export || {},
        reviewTracks: state.reviewTracks,
        reviewObjects: state.jobReview?.objects,
      }).pendingIds,
      staticFallbackCount,
    });
    const reviewFlow = reviewFlowStateFromSnapshot({
      ...snapshot,
      job: selectedJob(),
      trackCount: state.reviewTracks.length,
      exportIncludedCount: exportIncludedIds.length,
      exportValidated: Boolean(exportStatus),
      exportOk: exportStatus?.ok === true,
    });
    const reviewGate = reviewFlow.gate;
    const reviewPrimaryAction = reviewGate.primaryAction;
    const reviewPrimaryLabel = reviewPrimaryAction === "export_reviewed" && !exportAction.disabled ? "Export reviewed objects" : reviewPrimaryAction === "export_reviewed" ? exportAction.label : reviewGate.primaryLabel;
    const reviewPrimaryBlockedReason = reviewPrimaryAction === "export_reviewed" ? exportAction.reason : reviewGate.reason;
    const reviewPrimaryEnabled =
      reviewPrimaryAction === "export_reviewed"
        ? !exportAction.disabled
        : reviewPrimaryAction === "track_selected"
          ? state.candidateTrackingStatus !== "tracking" && reviewFlow.selectedCandidateCount > 0
          : reviewPrimaryAction !== "start_run";
    const reviewStep = {
      id: "review_export",
      primaryLabel: jobRunning ? "Cancel run" : jobFailed ? "Change setup" : reviewPrimaryLabel,
      primaryAction: jobRunning ? "cancel_run" : jobFailed ? "prepare_new_run" : reviewPrimaryAction,
      enabled: jobRunning || jobFailed || reviewPrimaryEnabled,
      blockedReason: jobRunning || jobFailed ? "" : reviewPrimaryBlockedReason,
      successAdvanceTo: "review_export",
      backTarget: "prompt_preview",
    };

    if (activeStep === "choose_goal") {
      return {
        id: activeStep,
        primaryLabel: "Continue to video",
        primaryAction: "continue_to_video",
        enabled: true,
        blockedReason: "",
        successAdvanceTo: "source_video",
        backTarget: "",
      };
    }

    if (activeStep === "source_video") {
      if ((snapshot.selectedPreset || state.selectedPreset) === "review_existing") {
        return {
          id: activeStep,
          primaryLabel: hasResult ? "Continue to review" : "Open result",
          primaryAction: hasResult ? "continue_to_review" : "open_result",
          enabled: hasResult || Boolean(importPathValue),
          blockedReason: hasResult ? "" : "Enter a MotionJSON path to review an existing result.",
          successAdvanceTo: "review_export",
          backTarget: "choose_goal",
        };
      }
      if (hasVideo) {
        if (previewStatus === "failed" || previewStatus === "blocked") {
          return {
            id: activeStep,
            primaryLabel: "Retry preview",
            primaryAction: "retry_preview",
            enabled: true,
            blockedReason: previewReason || "Browser preview could not be prepared.",
            successAdvanceTo: "source_video",
            backTarget: "choose_goal",
          };
        }
        return {
          id: activeStep,
          primaryLabel: requiresModel ? "Continue to model" : "Continue to prepare",
          primaryAction: "continue_after_video",
          enabled: true,
          blockedReason: "",
          successAdvanceTo: requiresModel ? "provider_settings" : "prompt_preview",
          backTarget: "choose_goal",
        };
      }
      return {
        id: activeStep,
        primaryLabel: "Add video",
        primaryAction: "add_video",
        enabled: Boolean(videoPathValue),
        blockedReason: "Enter a local video path or use the demo video to continue.",
        successAdvanceTo: requiresModel ? "provider_settings" : "prompt_preview",
        backTarget: "choose_goal",
      };
    }

    if (activeStep === "provider_settings") {
      const connection = modelConnectionById(state.selectedModelSetupProviderId || recommendedConnectionIdForPreset(snapshot.selectedPreset || state.selectedPreset));
      const provider = providerSettingsById(connection?.providerId || "");
      const setupState = modelSetupStateForConnection(connection, provider, connection ? setupJobForProvider(connection.providerId) : null);
      const setupAction = modelSetupPrimaryActionForState(setupState, connection);
      const ready = setupState.status === "ready";
      return {
        id: activeStep,
        primaryLabel: ready ? "Continue to run" : setupAction.label,
        primaryAction: ready ? "continue_to_prepare" : "run_model_setup_action",
        modelSetupAction: setupAction.id,
        enabled: ready || Boolean(hasModelSetupForm || connection),
        blockedReason: ready ? "" : setupState.message || "Choose one compatible model connection before continuing.",
        successAdvanceTo: "prompt_preview",
        backTarget: "source_video",
      };
    }

    if (activeStep === "prompt_preview") {
      const blocksNewRun = jobRunning;
      return {
        id: activeStep,
        primaryLabel: primaryRunLabelForPreset(snapshot.selectedPreset || state.selectedPreset),
        primaryAction: "run_prepared_workflow",
        enabled: Boolean(activeReadiness.complete) && !blocksNewRun,
        blockedReason: blocksNewRun
          ? "Wait for the current run to finish before starting another guided run."
          : activeReadiness.message || "Finish the required prepare step before running.",
        successAdvanceTo: "run_monitor",
        backTarget: requiresModel ? "provider_settings" : "source_video",
      };
    }

    if (activeStep === "run_monitor") {
      const hasReviewData = Boolean(snapshot.candidateCount || snapshot.trackCount || snapshot.selectedJobId);
      if (jobRunning) {
        return {
          id: activeStep,
          primaryLabel: "Cancel run",
          primaryAction: "cancel_run",
          enabled: true,
          blockedReason: "",
          successAdvanceTo: "run_monitor",
          backTarget: "prompt_preview",
        };
      }
      if (jobFailed) {
        return {
          id: activeStep,
          primaryLabel: "Change setup",
          primaryAction: "prepare_new_run",
          enabled: true,
          blockedReason: "",
          successAdvanceTo: "provider_settings",
          backTarget: "prompt_preview",
        };
      }
      if (hasReviewData) {
        return {
          id: activeStep,
          primaryLabel: "Continue to review",
          primaryAction: "continue_to_review",
          enabled: true,
          blockedReason: "",
          successAdvanceTo: "review_export",
          backTarget: "prompt_preview",
        };
      }
      return {
        id: activeStep,
        primaryLabel: primaryRunLabelForPreset(snapshot.selectedPreset || state.selectedPreset),
        primaryAction: "run_prepared_workflow",
        enabled: Boolean(readiness.prompt_preview?.complete),
        blockedReason: readiness.prompt_preview?.message || "Prepare the run before starting extraction.",
        successAdvanceTo: "run_monitor",
        backTarget: "prompt_preview",
      };
    }

    return reviewStep;
  }

  function screenContractFromSnapshot(snapshot = {}, activeStep = "choose_goal") {
    const screenId = workflowScreenForStep(activeStep);
    const selectedPreset = snapshot.selectedPreset || state.selectedPreset;
    const requiresModel = goalRequiresModel(selectedPreset);
    const previewStatus = String(snapshot.videoPreviewStatus || "");
    const previewReason = snapshot.videoPreviewReason || "";
    const providerReady = snapshot.providerSummaryTone === "ready";
    const hasVideo = Boolean(snapshot.selectedVideoId);
    const hasResult = selectedPreset === "review_existing" && Boolean(snapshot.selectedJobId);
    const selectedJobStatus = String(snapshot.selectedJobStatus || selectedJob()?.status || "").toLowerCase();
    const jobRunning = isActiveJobStatus(selectedJobStatus);
    const jobFailed = isFailedJobStatus(selectedJobStatus);
    if (screenId === "start") {
      return {
        title: "Start",
        description: "Choose the workflow first. The rest of the interface changes to match that goal.",
        statusLabel: "Ready",
        statusTone: "is-ready",
        primaryLabel: "Continue to video",
        enabled: true,
        blockedReason: "",
        primaryAction: "continue_to_video",
        backTarget: "",
      };
    }
    if (screenId === "video") {
      if (selectedPreset === "review_existing" && hasResult) {
        return {
          title: "Video",
          description: "Existing result loaded. Continue to review and export.",
          statusLabel: "Ready",
          statusTone: "is-ready",
          primaryLabel: "Continue to review",
          enabled: true,
          blockedReason: "",
          primaryAction: "continue_to_review",
          backTarget: "choose_goal",
        };
      }
      const videoPathValue = typeof document !== "undefined" ? document.querySelector("#videoPath")?.value.trim() || "" : "";
      if (!hasVideo) {
        return {
          title: "Video",
          description: selectedPreset === "review_existing" ? "Open an existing MotionJSON result for review." : "Import a source video and confirm project settings.",
          statusLabel: videoPathValue ? "Ready to add" : "Needs video",
          statusTone: videoPathValue ? "is-ready" : "is-warn",
          primaryLabel: selectedPreset === "review_existing" ? "Open result" : "Add video",
          enabled: selectedPreset === "review_existing" ? Boolean(typeof document !== "undefined" ? document.querySelector("#motionJsonImportPath")?.value.trim() : false) : Boolean(videoPathValue),
          blockedReason: selectedPreset === "review_existing" ? "Enter a MotionJSON path to open an existing result." : "Enter a local video path or use the demo video.",
          primaryAction: selectedPreset === "review_existing" ? "open_result" : "add_video",
          backTarget: "choose_goal",
        };
      }
      if (previewStatus === "failed" || previewStatus === "blocked") {
        return {
          title: "Video",
          description: "The source video needs a browser-safe preview before you can continue.",
          statusLabel: "Preview failed",
          statusTone: "is-bad",
          primaryLabel: "Retry preview",
          enabled: true,
          blockedReason: previewReason || "Browser preview could not be prepared.",
          primaryAction: "retry_preview",
          backTarget: "choose_goal",
        };
      }
      if (previewStatus && previewStatus !== "ready") {
        return {
          title: "Video",
          description: "The source video needs a browser-safe preview before you can continue.",
          statusLabel: "Preparing preview",
          statusTone: "is-neutral",
          primaryLabel: "Preparing preview",
          enabled: false,
          blockedReason: "Wait for MotionJSON to finish preparing the browser preview.",
          primaryAction: "noop",
          backTarget: "choose_goal",
        };
      }
      return {
        title: "Video",
        description: "The source video and preview are ready for model setup.",
        statusLabel: "Ready",
        statusTone: "is-ready",
        primaryLabel: requiresModel ? "Continue to model setup" : "Continue to prepare",
        enabled: true,
        blockedReason: "",
        primaryAction: "continue_after_video",
        backTarget: "choose_goal",
      };
    }
    if (screenId === "model") {
      return {
        title: "Model setup",
        description: requiresModel ? "Install, check, or choose the model runtime for this workflow." : "This workflow can run without SAM setup.",
        statusLabel: !requiresModel ? "Not needed" : providerReady ? "Ready" : "Needs setup",
        statusTone: !requiresModel || providerReady ? "is-ready" : "is-warn",
        primaryLabel: !requiresModel || providerReady ? "Continue to prepare" : "Save and continue",
        enabled: !requiresModel || Boolean(typeof document !== "undefined" ? document.querySelector("#modelSetupForm") : true),
        blockedReason: requiresModel ? "Choose one compatible model connection." : "",
        primaryAction: !requiresModel || providerReady ? "continue_to_prepare" : "save_model_setup",
        backTarget: "source_video",
      };
    }
    if (screenId === "prepare") {
      const base = workflowStepContractFromSnapshot(snapshot, "prompt_preview");
      return {
        title: "Prepare",
        description: "Configure the scene sweep, prompt, or import settings before starting extraction.",
        statusLabel: base.enabled ? "Ready" : "Needs input",
        statusTone: base.enabled ? "is-ready" : "is-warn",
        primaryLabel: base.primaryLabel,
        enabled: base.enabled,
        blockedReason: base.blockedReason,
        primaryAction: "run_prepared_workflow",
        backTarget: requiresModel ? "provider_settings" : "source_video",
      };
    }
    if (screenId === "run") {
      if (jobRunning) {
        return {
          title: "Run",
          description: "The run is active. Watch progress here, cancel if needed, then review results when the job finishes.",
          statusLabel: "Running",
          statusTone: "is-neutral",
          primaryLabel: "Cancel run",
          enabled: true,
          blockedReason: "",
          primaryAction: "cancel_run",
          backTarget: "prompt_preview",
        };
      }
      if (jobFailed) {
        return {
          title: "Run",
          description: "The selected run failed or was canceled. Open logs, change setup, run again, or choose another model.",
          statusLabel: "Needs attention",
          statusTone: "is-bad",
          primaryLabel: "Change setup",
          enabled: true,
          blockedReason: "",
          primaryAction: "prepare_new_run",
          backTarget: "prompt_preview",
        };
      }
      const hasRunData = Boolean(snapshot.selectedJobId || snapshot.candidateCount || snapshot.trackCount);
      return {
        title: "Run",
        description: hasRunData ? "The run finished. Continue to inspect object tracks before export." : "Start the prepared run and keep logs visible here.",
        statusLabel: hasRunData ? "Ready" : "No run",
        statusTone: hasRunData ? "is-ready" : "is-warn",
        primaryLabel: hasRunData ? "Continue to review" : primaryRunLabelForPreset(selectedPreset),
        enabled: hasRunData || Boolean(workflowReadinessFromSnapshot(snapshot).prompt_preview?.complete),
        blockedReason: hasRunData ? "" : "Prepare the run before starting extraction.",
        primaryAction: hasRunData ? "continue_to_review" : "run_prepared_workflow",
        backTarget: "prompt_preview",
      };
    }
    const reviewContract = workflowStepContractFromSnapshot(snapshot, "review_export");
    const reviewReady = reviewContract.primaryAction === "export_reviewed" && reviewContract.enabled;
    return {
      title: "Review",
      description: reviewContract.blockedReason || "Review candidates, create tracks, correct them if needed, then export.",
      statusLabel: reviewReady ? "Ready" : "Needs review",
      statusTone: reviewReady ? "is-ready" : "is-warn",
      primaryLabel: reviewContract.primaryLabel,
      enabled: reviewContract.enabled,
      blockedReason: reviewContract.blockedReason,
      primaryAction: reviewContract.primaryAction,
      backTarget: selectedPreset === "review_existing" ? "source_video" : "prompt_preview",
    };
  }

  function postRunWorkflowSummaryFromSnapshot(snapshot = {}) {
    return reviewFlowStateFromSnapshot(snapshot).stages;
  }

  function runMonitorStageFromSnapshot(snapshot = {}) {
    const activeJobs = toInteger(snapshot.activeJobs, 0);
    const selectedJobStatus = String(snapshot.selectedJobStatus || "").toLowerCase();
    const hasSelectedJob = Boolean(snapshot.hasSelectedJob || selectedJobStatus);
    const diagnosticCount = toInteger(snapshot.diagnosticCount, 0);
    const attentionDiagnosticCount = toInteger(snapshot.attentionDiagnosticCount, 0);
    const hasFailure = Boolean(snapshot.hasFailure || /failed|error|canceled/.test(selectedJobStatus));
    const hasStaleProgress = Boolean(snapshot.hasStaleProgress);
    const selectedJobComplete = /succeeded|completed|complete/.test(selectedJobStatus);
    const selectedJobRunning = /queued|running|pending|started/.test(selectedJobStatus) || activeJobs > 0;

    const stage = (id, label, value, detail, status = "needs-action") => ({
      id,
      label,
      value,
      detail,
      status,
      tone: status === "done" || status === "ready" ? "is-ready" : status === "running" ? "is-neutral" : status === "blocked" ? "is-bad" : "is-warn",
    });

    if (hasFailure) return stage("run", "Run monitor", selectedJobStatus || "Run issue", "Open diagnostics and logs to inspect the backend failure.", "blocked");
    if (hasStaleProgress) {
      return stage(
        "run",
        "Run monitor",
        `${activeJobs || 1} active`,
        snapshot.staleProgressDetail || "No progress update has arrived recently. Open logs or cancel the run if it is blocked.",
        "warning",
      );
    }
    if (selectedJobComplete) {
      return stage(
        "run",
        "Run monitor",
        selectedJobStatus || "Run complete",
        attentionDiagnosticCount
          ? `${attentionDiagnosticCount} fallback or provider diagnostic${attentionDiagnosticCount === 1 ? "" : "s"} need review.`
          : diagnosticCount
            ? `${diagnosticCount} diagnostic item${diagnosticCount === 1 ? "" : "s"} available.`
            : "Run completed and review data can be checked.",
        attentionDiagnosticCount ? "warning" : "done",
      );
    }
    if (selectedJobRunning) return stage("run", "Run monitor", `${activeJobs || 1} active`, "Wait for the local job to finish or cancel it if needed.", "running");
    if (hasSelectedJob) return stage("run", "Run monitor", selectedJobStatus || "Run selected", "Review the selected run status before continuing.", "ready");
    return stage("run", "Run monitor", "No run selected", "Start or select a run before reviewing candidates.");
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

  function normalizePolygonPoints(polygon) {
    const points = asArray(polygon)
      .map((point) => {
        if (Array.isArray(point)) {
          return { x: toNumber(point[0], Number.NaN), y: toNumber(point[1], Number.NaN) };
        }
        if (point && typeof point === "object") {
          return { x: toNumber(point.x ?? point[0], Number.NaN), y: toNumber(point.y ?? point[1], Number.NaN) };
        }
        return null;
      })
      .filter((point) => point && Number.isFinite(point.x) && Number.isFinite(point.y));
    return points.length >= 3 ? points : null;
  }

  function polygonBounds(points, width, height) {
    const xs = points.map((point) => point.x);
    const ys = points.map((point) => point.y);
    return clampBox(
      {
        x: Math.min(...xs),
        y: Math.min(...ys),
        w: Math.max(...xs) - Math.min(...xs),
        h: Math.max(...ys) - Math.min(...ys),
      },
      width,
      height,
    );
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

  function objectDiscoveryDefaults(qualityPreset) {
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

  function normalizedModelConnection(connection) {
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

  function modelConnectionByConnectionId(connectionId) {
    const normalized = String(connectionId || "").trim();
    return normalizedModelConnection(MODEL_CONNECTIONS.find((connection) => connection.id === normalized) || null);
  }

  function providerIdFromConnectionId(connectionId) {
    const id = String(connectionId || "").trim();
    if (id.startsWith("sam2-hosted:")) return "sam2-hosted";
    if (id.startsWith("sam3-hosted:")) return "sam3-hosted";
    return id;
  }

  function profileIdFromConnectionId(connectionId) {
    const parts = String(connectionId || "").split(":");
    return parts.length > 1 ? parts.slice(1).join(":") : "";
  }

  function engineFromProviderId(providerId) {
    const id = String(providerId || "");
    if (id.includes("sam3")) return "sam3";
    if (id.includes("sam2")) return "sam2";
    if (id.includes("motion")) return "motion";
    if (id.includes("external")) return "external_masks";
    return id ? "no_model" : "";
  }

  function localityFromProviderId(providerId) {
    const id = String(providerId || "");
    if (id.includes("hosted")) return "hosted";
    if (MODEL_FREE_PRESETS.has(id) || ["mock", "threshold", "motion", "external"].includes(id)) return "no_model";
    return id ? "local" : "";
  }

  function providerLabel(providerId, profileId = "") {
    if (providerId === "sam2-local") return "SAM2 local";
    if (providerId === "sam2-hf-auto-masks") return "SAM2 HF automatic masks";
    if (providerId === "sam2-hosted" && profileId === "replicate-sam2-video") return "Replicate SAM2 video";
    if (providerId === "sam2-hosted") return "Hosted SAM2";
    if (providerId === "sam3-local") return "SAM3 local";
    if (providerId === "sam3-hosted" && profileId === "roboflow-sam3-pcs") return "Roboflow SAM3";
    if (providerId === "sam3-hosted" && profileId === "fal-sam3-image") return "Fal SAM3 image";
    if (providerId === "sam3-hosted") return "Custom SAM3 endpoint";
    return {
      mock: "Mock no-model",
      threshold: "Color threshold",
      motion: "Motion foreground",
      external: "Imported masks",
      "motion_foreground": "Motion foreground",
      "external_masks": "Imported masks",
    }[providerId] || providerId || "No model";
  }

  function hostedCallsAllowedForProvider(input, providerId) {
    if (providerId === "sam2-hosted") return Boolean(input.hostedSam2AllowHosted);
    if (providerId === "sam3-hosted") return Boolean(input.hostedSam3AllowHosted);
    return false;
  }

  function selectedConnectionForInput(input = {}) {
    const explicit = modelConnectionByConnectionId(input.modelConnectionId);
    if (explicit) return explicit;
    if (input.maskProvider === "sam2-local") return modelConnectionByConnectionId("sam2-local");
    if (input.maskProvider === "sam2-hf-auto-masks") return modelConnectionByConnectionId("sam2-hf-auto-masks");
    if (input.maskProvider === "sam2-hosted") return modelConnectionByConnectionId("sam2-hosted:replicate-sam2-video");
    if (input.maskProvider === "sam3-local" || input.textDiscoveryProvider === "sam3-local") return modelConnectionByConnectionId("sam3-local");
    if (input.maskProvider === "sam3-hosted" || input.textDiscoveryProvider === "sam3-hosted") {
      return (
        modelConnectionByConnectionId(`sam3-hosted:${input.hostedSam3ProfileId || "roboflow-sam3-pcs"}`) ||
        modelConnectionByConnectionId("sam3-hosted:custom-sam3-compatible")
      );
    }
    if (input.maskProvider || input.textDiscoveryProvider) return null;
    const connectionId = state.selectedModelSetupProviderId || recommendedConnectionIdForPreset(input.preset || state.selectedPreset);
    return modelConnectionByConnectionId(connectionId);
  }

  function providerContractForInput(input = {}) {
    const presetName = input.preset || state.selectedPreset;
    const preset = PRESETS[presetName] || PRESETS.auto_object_proposals;
    const connection = selectedConnectionForInput(input);
    const providerId =
      connection?.providerId ||
      (["sam3-local", "sam3-hosted"].includes(input.textDiscoveryProvider) ? input.textDiscoveryProvider : "") ||
      input.maskProvider ||
      "";
    const profileId = connection?.profileId || (providerId === "sam2-hosted" ? input.hostedSam2ProfileId || "replicate-sam2-video" : providerId === "sam3-hosted" ? input.hostedSam3ProfileId || "roboflow-sam3-pcs" : "");
    const noModelProviderId = input.maskProvider || preset.maskProvider || "threshold";
    if (!goalRequiresModel(presetName)) {
      return {
        connection,
        connectionId: "",
        providerId: noModelProviderId,
        providerName: noModelProviderId,
        profileId: "",
        displayLabel: providerLabel(noModelProviderId),
        engine: engineFromProviderId(noModelProviderId),
        locality: "no_model",
        hostedCallsAllowed: false,
      };
    }
    return {
      connection,
      connectionId: connection?.connectionId || (providerId && profileId && providerId.includes("hosted") ? `${providerId}:${profileId}` : providerId),
      providerId,
      providerName: providerId,
      profileId,
      displayLabel: connection?.displayLabel || providerLabel(providerId, profileId),
      engine: connection?.engine || engineFromProviderId(providerId),
      locality: connection?.locality || localityFromProviderId(providerId),
      hostedCallsAllowed: hostedCallsAllowedForProvider(input, providerId),
    };
  }

  function enginePlanFromContract(contract, input, { providerId, discoveryMode, profileId = "", connection = null } = {}) {
    const selectedProviderId = providerId || contract.providerId || "threshold";
    const selectedProfileId = profileId || contract.profileId || "";
    const selectedConnection = normalizedModelConnection(connection || contract.connection || modelConnectionByConnectionId(
      selectedProviderId.includes("hosted") && selectedProfileId ? `${selectedProviderId}:${selectedProfileId}` : selectedProviderId,
    ));
    return {
      ...contract,
      connection: selectedConnection,
      connectionId: selectedConnection?.connectionId || (selectedProviderId.includes("hosted") && selectedProfileId ? `${selectedProviderId}:${selectedProfileId}` : selectedProviderId),
      providerId: selectedProviderId,
      providerName: selectedProviderId,
      profileId: selectedProfileId,
      displayLabel: selectedConnection?.displayLabel || providerLabel(selectedProviderId, selectedProfileId),
      engine: selectedConnection?.engine || engineFromProviderId(selectedProviderId),
      locality: selectedConnection?.locality || localityFromProviderId(selectedProviderId),
      hostedCallsAllowed: hostedCallsAllowedForProvider(input, selectedProviderId),
      discoveryMode,
    };
  }

  function guidedEnginePlan(input = {}) {
    const presetName = input.preset || state.selectedPreset;
    const preset = PRESETS[presetName] || PRESETS.auto_object_proposals;
    const contract = providerContractForInput(input);
    const connection = contract.connection;
    const requestedDiscoveryMode = input.discoveryMode || preset.discoveryMode || "manual_prompt";
    let providerId = contract.providerId || "";
    const profileId = contract.profileId || "";
    const allowLegacyDetector =
      input.allowLegacyTextDetector === true ||
      (input.debugMockMode === true && (input.maskProvider === "mock" || input.textDiscoveryProvider === "mock" || requestedDiscoveryMode === "text_detector"));
    if (!goalRequiresModel(presetName)) {
      return enginePlanFromContract(contract, input, { providerId: contract.providerId || preset.maskProvider || "threshold", discoveryMode: requestedDiscoveryMode, connection: null });
    }
    if (presetName === "trace_one_object") {
      if (providerId === "sam3-local" || providerId === "sam3-hosted") {
        return enginePlanFromContract(contract, input, { providerId, discoveryMode: requestedDiscoveryMode === "manual_prompt" ? "sam3_exemplar" : requestedDiscoveryMode, profileId, connection });
      }
      providerId = providerId === "sam2-hosted" ? "sam2-hosted" : providerId || "sam2-local";
      return enginePlanFromContract(contract, input, { providerId, discoveryMode: requestedDiscoveryMode === "sam3_exemplar" ? "manual_prompt" : requestedDiscoveryMode, profileId, connection });
    }
    if (presetName === "trace_all_objects") {
      if (providerId === "sam2-hf-auto-masks") {
        return enginePlanFromContract(contract, input, { providerId: "sam2-hf-auto-masks", discoveryMode: "sam2_hf_auto_masks", connection });
      }
      if (providerId === "sam2-local") {
        return enginePlanFromContract(contract, input, { providerId: "sam2-local", discoveryMode: requestedDiscoveryMode === "sam3_auto_masks" ? "auto_object_proposals" : requestedDiscoveryMode, connection });
      }
      providerId = providerId === "sam3-hosted" ? "sam3-hosted" : providerId || "sam3-local";
      return enginePlanFromContract(contract, input, { providerId, discoveryMode: requestedDiscoveryMode === "auto_object_proposals" && providerId?.startsWith("sam3") ? "sam3_auto_masks" : requestedDiscoveryMode, profileId, connection });
    }
    if (presetName === "text_detector") {
      if (allowLegacyDetector) {
        const detectorProvider = input.maskProvider || "threshold";
        return enginePlanFromContract(contract, input, { providerId: detectorProvider, discoveryMode: "text_detector", connection: null, profileId: "" });
      }
      providerId = providerId?.startsWith("sam3") ? providerId : "sam3-local";
      return enginePlanFromContract(contract, input, {
        providerId,
        discoveryMode: requestedDiscoveryMode === "text_detector" ? "sam3_concept" : requestedDiscoveryMode,
        profileId: providerId === "sam3-hosted" ? profileId : "",
        connection: providerId === contract.providerId ? connection : modelConnectionByConnectionId(providerId),
      });
    }
    return enginePlanFromContract(contract, input, {
      providerId: contract.providerId || input.maskProvider || preset.maskProvider || "threshold",
      discoveryMode: requestedDiscoveryMode,
      profileId,
      connection,
    });
  }

  function firstPromptBox(promptsForConfig = []) {
    const prompt = asArray(promptsForConfig).find((item) => item.kind === "box" && item.data);
    if (!prompt?.data) return null;
    return {
      x: toInteger(prompt.data.x, 0),
      y: toInteger(prompt.data.y, 0),
      w: toInteger(prompt.data.w, 0),
      h: toInteger(prompt.data.h, 0),
    };
  }

  function objectDiscoveryConfig(input) {
    const defaultQualityPreset = input.preset === "trace_all_objects" ? "balanced" : "clean";
    const qualityPreset = input.traceEverythingMode ? "trace_everything" : input.qualityPreset || defaultQualityPreset;
    const defaults = objectDiscoveryDefaults(qualityPreset);
    const keyframes = parseKeyframes(input.keyframes);
    return {
      mock: Boolean(input.debugMockMode),
      qualityPreset,
      intent: defaults.intent,
      providerPreference: input.debugMockMode ? "mock" : input.providerName === "sam2-hf-auto-masks" ? "sam2-hf-auto-masks" : input.providerName === "sam2-local" ? "sam2-local" : "auto",
      sam2Checkpoint: input.localSam2CheckpointPath || null,
      sam2ModelConfig: input.localSam2ModelConfigPath || null,
      sam2Device: input.localSam2Device || input.device || "auto",
      keyframePolicy: defaults.keyframePolicy,
      keyframes,
      maxKeyframes: defaults.maxKeyframes,
      frameInterval: defaults.frameInterval,
      maxCandidatesPerKeyframe: defaults.maxCandidatesPerKeyframe,
      maxObjects: qualityPreset === "clean" ? toInteger(input.maxObjects, defaults.maxObjects) : defaults.maxObjects,
      minMaskArea: defaults.minMaskArea,
      maxMaskAreaRatio: defaults.maxMaskAreaRatio,
      dedupeIou: defaults.dedupeIou,
      stabilityThreshold: defaults.stabilityThreshold,
      motionScoreWeight: 0.35,
      rejectWholeFrame: true,
      rejectBackgroundLike: true,
      trackSelectedOnly: defaults.trackSelectedOnly,
      trackTopCandidates: defaults.trackTopCandidates,
      requireReview: true,
      writeRejectedCandidates: true,
      requireExplicitCostWarning: defaults.requireExplicitCostWarning,
      ...(qualityPreset === "trace_everything" ? { costWarningAcknowledged: input.traceEverythingAcknowledged === true } : {}),
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

  function sam3TrackerModelForInput(input = {}) {
    const value = String(input.localSam3TrackerModel || input.sam3TrackerModel || "").trim();
    if (!value || value === "sam3/local-model-path") return "facebook/sam3";
    return value;
  }

  function buildDiscoveryConfig(input, promptsForConfig) {
    const keyframes = parseKeyframes(input.keyframes);
    if (input.discoveryMode === "auto_object_proposals") {
      return objectDiscoveryConfig(input);
    }
    if (input.discoveryMode === "sam2_hf_auto_masks") {
      const defaults = objectDiscoveryDefaults(input.traceEverythingMode ? "trace_everything" : input.qualityPreset || "clean");
      return {
        ...objectDiscoveryConfig({ ...input, providerName: "sam2-hf-auto-masks" }),
        providerPreference: "sam2-hf-auto-masks",
        sam2HfModel: input.localSam2HfModel || input.sam2HfModel || "facebook/sam2.1-hiera-large",
        sam2HfDevice: input.localSam2HfDevice || input.device || "auto",
        maxCandidatesPerKeyframe: defaults.maxCandidatesPerKeyframe,
        maxObjects: defaults.maxObjects,
      };
    }
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
        mock: Boolean(input.debugMockMode),
      };
    }
    if (input.discoveryMode === "sam3_concept") {
      const hosted = input.providerName === "sam3-hosted";
      return {
        concept: input.textPrompt || "",
        text: input.textPrompt || "",
        labels: parseCsv(input.textPrompt),
        providerPreference: hosted ? "sam3-hosted" : "sam3-local",
        hosted,
        hostedProfile: hosted ? input.profileId || input.hostedSam3ProfileId || "roboflow-sam3-pcs" : null,
        model: hosted ? input.hostedSam3Model || null : input.localSam3ModelPath || null,
        sam3ModelPath: input.localSam3ModelPath || null,
        sam3Device: input.localSam3Device || input.device || "cuda",
        keyframes,
        max_candidates: toInteger(input.maxObjects, 12),
        box_threshold: toNumber(input.boxThreshold, 0.35),
        text_threshold: toNumber(input.textThreshold, 0.25),
        deduplicate: true,
        allowNetwork: hosted ? Boolean(input.hostedSam3AllowHosted) : false,
        acknowledgeCostPrivacy: hosted ? Boolean(input.hostedSam3AllowHosted) : false,
        mock: false,
      };
    }
    if (input.discoveryMode === "sam3_exemplar") {
      const hosted = input.providerName === "sam3-hosted";
      const box = firstPromptBox(promptsForConfig);
      return {
        providerPreference: hosted ? "sam3-hosted" : "sam3-local",
        hosted,
        hostedProfile: hosted ? input.profileId || input.hostedSam3ProfileId || "custom-sam3-compatible" : null,
        model: hosted ? input.hostedSam3Model || null : input.localSam3ModelPath || null,
        sam3ModelPath: input.localSam3ModelPath || null,
        sam3Device: input.localSam3Device || input.device || "cuda",
        frameIndex: toInteger(box ? input.currentFrame : keyframes[0], toInteger(input.currentFrame, 0)),
        keyframes,
        box,
        exemplars: box ? null : asArray(input.sam3Exemplars),
        allowNetwork: hosted ? Boolean(input.hostedSam3AllowHosted) : false,
        acknowledgeCostPrivacy: hosted ? Boolean(input.hostedSam3AllowHosted) : false,
        mock: false,
      };
    }
    if (input.discoveryMode === "sam3_auto_masks") {
      const hosted = input.providerName === "sam3-hosted";
      const defaults = objectDiscoveryDefaults(input.traceEverythingMode ? "trace_everything" : input.qualityPreset || "clean");
      const config = {
        sceneSweep: true,
        useTransformersTracker: !hosted && Boolean(input.useTransformersTracker),
        pointsPerBatch: toInteger(input.pointsPerBatch, 64),
        qualityPreset: input.traceEverythingMode ? "trace_everything" : input.qualityPreset || "clean",
        providerPreference: hosted ? "sam3-hosted" : "sam3-local",
        hosted,
        hostedProfile: hosted ? input.profileId || input.hostedSam3ProfileId || "custom-sam3-compatible" : null,
        sam3Device: input.localSam3Device || input.device || "cuda",
        keyframes,
        maxCandidatesPerKeyframe: defaults.maxCandidatesPerKeyframe,
        maxObjects: defaults.maxObjects,
        minMaskArea: defaults.minMaskArea,
        maxMaskAreaRatio: defaults.maxMaskAreaRatio,
        dedupeIou: defaults.dedupeIou,
        stabilityThreshold: defaults.stabilityThreshold,
        requireReview: true,
        allowNetwork: hosted ? Boolean(input.hostedSam3AllowHosted) : false,
        acknowledgeCostPrivacy: hosted ? Boolean(input.hostedSam3AllowHosted) : false,
        mock: false,
      };
      if (hosted) {
        config.model = input.hostedSam3Model || null;
      } else {
        config.sam3TrackerModel = sam3TrackerModelForInput(input);
      }
      return config;
    }
    if (input.discoveryMode === "sam_auto_masks") {
      return {
        keyframes,
        providerPreference: input.debugMockMode ? "mock" : "sam2-local",
        sam2Checkpoint: input.localSam2CheckpointPath || null,
        sam2ModelConfig: input.localSam2ModelConfigPath || null,
        sam2Device: input.localSam2Device || input.device || "auto",
        min_area: toNumber(input.minArea, 100),
        max_area_ratio: toNumber(input.maxAreaRatio, 0.65),
        stability_threshold: toNumber(input.stabilityThreshold, 0.82),
        overlap_threshold: toNumber(input.overlapThreshold, 0.72),
        max_candidates: toInteger(input.maxObjects, 12),
        reject_background: true,
        mock: Boolean(input.debugMockMode),
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
        class_preset: input.classPreset || "common_objects",
        classes: parseCsv(input.classList),
        confidence_threshold: toNumber(input.boxThreshold, 0.35),
        max_candidates: toInteger(input.maxObjects, 12),
        keyframes,
        mock: Boolean(input.debugMockMode),
      };
    }
    return {
      prompts: promptsForConfig,
      keyframes,
    };
  }

  function buildRunConfig(input) {
    const preset = PRESETS[input.preset] || PRESETS.auto_object_proposals;
    const objectId = slugObjectId(input.objectId, "object_0");
    const objectLabel = String(input.objectLabel || objectId || "selected_object").trim() || objectId;
    const enginePlan = guidedEnginePlan(input);
    const discoveryMode = enginePlan.discoveryMode || input.discoveryMode || preset.discoveryMode || "manual_prompt";
    const maskProvider = enginePlan.providerName || input.maskProvider || preset.maskProvider || "threshold";
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
    const hostedSam2ProfileId = input.hostedSam2ProfileId || "replicate-sam2-video";
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
          checkpoint: input.localSam2CheckpointPath || null,
          model_config: input.localSam2ModelConfigPath || null,
          prompt_frame: frameIndex,
          hosted_config: {
            ...(modelName ? { model: modelName } : {}),
            ...(maskProvider === "sam2-hosted" ? { profile: hostedSam2ProfileId, hostedProfile: hostedSam2ProfileId } : {}),
          },
          hosted_allow_network: maskProvider === "sam2-hosted" ? Boolean(input.hostedSam2AllowHosted) : false,
        },
        sam3: {
          model_path: input.localSam3ModelPath || null,
          device: input.localSam3Device || device || null,
          prompt_frame: frameIndex,
          endpoint: null,
          auth_env: "SAM3_HOSTED_API_KEY",
          endpoint_env: "SAM3_HOSTED_URL",
          hosted_config: {
            ...(maskProvider === "sam3-hosted" ? { profile: enginePlan.profileId || input.hostedSam3ProfileId || "custom-sam3-compatible", hostedProfile: enginePlan.profileId || input.hostedSam3ProfileId || "custom-sam3-compatible" } : {}),
            ...(maskProvider === "sam3-hosted" && input.hostedSam3Model ? { model: input.hostedSam3Model } : {}),
          },
          hosted_allow_network: maskProvider === "sam3-hosted" ? Boolean(input.hostedSam3AllowHosted) : false,
        },
        cache: {
          enabled: true,
          directory: ".motionjson-cache/masks",
        },
        fallback_mask_provider:
          maskProvider === "mock" || maskProvider === "threshold" || maskProvider === "sam3-local" || maskProvider === "sam3-hosted"
            ? null
            : "threshold",
      },
      discovery: {
        mode: discoveryMode,
        config: buildDiscoveryConfig(
          {
            ...input,
            providerName: maskProvider,
            profileId: enginePlan.profileId || "",
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

  function presetNameForRunPlan(config, input = {}) {
    if (input.preset && PRESETS[input.preset]) return input.preset;
    const discoveryMode = config?.discovery?.mode;
    const providerName = config?.provider?.name;
    if (discoveryMode === "motion_foreground") return "motion_foreground";
    if (discoveryMode === "sam3_concept") return "text_detector";
    if (discoveryMode === "sam3_exemplar") return "trace_one_object";
    if (discoveryMode === "sam3_auto_masks") return "trace_all_objects";
    if (discoveryMode === "text_detector") return "text_detector";
    if (discoveryMode === "class_detector") return "class_detector";
    if (discoveryMode === "sam_auto_masks") return "sam_auto_masks";
    if (discoveryMode === "external_masks" || providerName === "external") return "external_masks";
    if (discoveryMode === "manual_prompt") return "trace_one_object";
    return "auto_object_proposals";
  }

  function buildRunPlan(config, input = {}, validation = null) {
    const presetName = presetNameForRunPlan(config, input);
    const goal = RUN_PLAN_GOALS[presetName] || RUN_PLAN_GOALS.auto_object_proposals;
    const enginePlan = guidedEnginePlan(input);
    const providerId = enginePlan.providerId || config?.provider?.name || "sam2-local";
    const providerName = enginePlan.displayLabel || providerLabel(providerId, enginePlan.profileId);
    const discoveryMode = config?.discovery?.mode || PRESETS[presetName]?.discoveryMode || "manual_prompt";
    const hostedAllowed = Boolean(config?.provider?.sam2?.hosted_allow_network || config?.provider?.sam3?.hosted_allow_network || config?.discovery?.config?.allowNetwork);
    const localOrMock = LOCAL_JOB_PROVIDERS.has(providerId) || providerId === "threshold";
    const hasRegisteredVideo = Boolean(input.videoId || config?.rights?.source_asset_id);
    const hasBrowserPreview = Boolean(input.previewName);
    const hasPrompts = asArray(config?.prompts).length > 0;
    const errors = asArray(validation?.errors).map((item) => item.message || String(item));
    const warnings = asArray(validation?.warnings).map((item) => item.message || String(item));

    const sourceDetail = hasRegisteredVideo
      ? "The backend can run against the registered local asset."
      : hasBrowserPreview
        ? "The browser preview is ready for drawing. Register a local path before starting a backend job."
        : "Register a local video path for backend jobs, and optionally add a browser preview for drawing.";

    const steps = [
      {
        label: "Goal",
        value: goal.title,
        detail: goal.summary,
        status: "ready",
      },
      {
        label: "Source",
        value: hasRegisteredVideo ? "Registered local video" : hasBrowserPreview ? "Browser preview loaded" : "Video still needed",
        detail: sourceDetail,
        status: hasRegisteredVideo ? "ready" : "needs-action",
      },
      {
        label: "Model mode",
        value: localOrMock ? providerName : `${providerName} needs diagnostics`,
        detail: hostedAllowed
          ? "Hosted calls are allowed for this provider. Confirm privacy and cost before running."
          : "No hosted calls are enabled by this plan; provider diagnostics still decide what can run.",
        status: hostedAllowed || !localOrMock ? "warning" : "ready",
      },
      {
        label: "Review gate",
        value: "Review before export",
        detail: "Candidates and tracks must be reviewed so raster-only or background-like output is explained before export.",
        status: "ready",
      },
    ];

    if (discoveryMode === "manual_prompt" && !hasPrompts) {
      steps.splice(2, 0, {
        label: "Prompt",
        value: "Add a point or box",
        detail: "Place a positive point or draw a box on the preview to tell the extractor which object matters.",
        status: "needs-action",
      });
    }

    const nextSteps = [];
    if (!hasBrowserPreview && !hasRegisteredVideo) nextSteps.push("Choose a video preview or register a local video path.");
    if (!hasRegisteredVideo) nextSteps.push("Register a local video path before starting a backend run.");
    if (discoveryMode === "manual_prompt" && !hasPrompts) nextSteps.push("Add a point, box, or brush prompt for the object.");
    if (warnings.length) nextSteps.push("Review backend warnings before running.");
    if (errors.length) nextSteps.push("Fix validation errors before starting extraction.");
    if (!nextSteps.length) nextSteps.push("Start extraction or validate again before running.");

    return {
      preset: presetName,
      title: goal.title,
      summary: goal.summary,
      privacy: hostedAllowed ? "Hosted calls allowed after confirmation" : "Frames stay local for this plan",
      providerName,
      providerId,
      modelConnectionId: enginePlan.connectionId || "",
      providerEngine: enginePlan.engine || "",
      providerLocality: enginePlan.locality || "",
      discoveryMode,
      errors,
      warnings,
      steps,
      nextSteps,
    };
  }

  function modelPlanGoalForPreset(preset) {
    return (
      {
        trace_one_object: "trace_one_object",
        trace_all_objects: "discover_objects",
        auto_object_proposals: "trace_one_object",
        text_detector: "find_objects_from_text",
        class_detector: "find_objects_from_text",
        sam_auto_masks: "trace_one_object",
        motion_foreground: "find_moving_things",
        external_masks: "import_masks",
        review_existing: "review_existing_result",
      }[preset] || "trace_one_object"
    );
  }

  function modelPlanRequestFromInput(input = {}, providerId = "fake-local-planner") {
    const preset = input.preset || "trace_one_object";
    const prompt = String(input.modelIntent || input.textPrompt || input.objectLabel || RUN_PLAN_GOALS[preset]?.summary || "").trim();
    return {
      providerId: providerId || "fake-local-planner",
      request: {
        goal: modelPlanGoalForPreset(preset),
        prompt,
        projectId: input.projectId || null,
        videoId: input.videoId || null,
        sourcePath: input.sourcePath || input.videoPath || null,
        outputDirectory: input.outputDirectory || null,
        objectLabel: input.objectLabel || "selected_object",
        objectId: input.objectId || "object_0",
        textPrompt: input.textPrompt || prompt,
        maskDir: input.externalMaskDir || "masks/object_0",
        sampleFps: toNumber(input.sampleFps, 12),
        maxFrames: toInteger(input.maxFrames, 48),
        maxObjects: toInteger(input.maxObjects, 12),
        metadata: {
          preset,
          previewName: input.previewName || "",
        },
      },
    };
  }

  function modelPlanValidationMessages(validation = {}) {
    const errors = asArray(validation.errors).map((item) => item.message || String(item));
    const warnings = asArray(validation.warnings).map((item) => item.message || String(item));
    const blockers = asArray(validation.warnings)
      .filter((item) => typeof item === "object" && String(item.severity || "").toLowerCase() === "error")
      .map((item) => item.message || String(item));
    return { errors, warnings, blockers };
  }

  function modelPlanProviderFacts(modelPlan = null, validation = null) {
    const providerPlan = modelPlan?.providerPlan || {};
    const privacy = modelPlan?.privacy || {};
    const estimatedCost = modelPlan?.estimatedCost || {};
    const effectiveValidation = validation || modelPlan?.validation || {};
    const messages = modelPlanValidationMessages(effectiveValidation);
    const valid = effectiveValidation.valid === true && !messages.errors.length && !messages.blockers.length;
    return {
      plannerProvider: modelPlan?.providerId || providerPlan.reasoningProvider || "not generated",
      discoveryProvider: providerPlan.discoveryProvider || modelPlan?.runConfig?.discovery?.mode || "not reported",
      maskProvider: providerPlan.maskProvider || modelPlan?.runConfig?.provider?.name || "not reported",
      trackingMode: providerPlan.trackingMode || "selected_only",
      privacy: privacy.summary || (privacy.hostedCallsRequired ? "Hosted planning required confirmation." : "Frames stay on this machine."),
      cost: estimatedCost.message || estimatedCost.label || estimatedCost.status || "not reported",
      validationLabel: valid ? (messages.warnings.length ? "Valid with warnings" : "Ready to confirm") : "Blocked",
      valid,
      errors: messages.errors,
      warnings: messages.warnings,
      blockers: messages.blockers,
      requiresUserConfirmation: modelPlan?.requiresUserConfirmation !== false,
    };
  }

  function modelPlanConfirmPayload({ projectId = "", videoId = "", run = true } = {}) {
    if (!projectId) throw new Error("Create or select a project before starting extraction from a model plan.");
    if (!videoId) throw new Error("Register or select a video before starting extraction from a model plan.");
    return {
      confirmed: true,
      projectId,
      videoId,
      run: Boolean(run),
    };
  }

  function modelPlanSourceIds(modelPlan = null) {
    const path = String(modelPlan?.runConfig?.input?.path || "");
    const assetMatch = path.match(/^local-ui:\/\/assets\/([^/?#]+)/);
    return {
      projectId: modelPlan?.request?.projectId || "",
      videoId: modelPlan?.runConfig?.rights?.source_asset_id || (assetMatch ? assetMatch[1] : "") || modelPlan?.request?.videoId || "",
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

  function eventLabel(event = {}) {
    return event.event_type || event.eventType || event.type || event.stage || "event";
  }

  function eventTimestamp(event = {}) {
    const metadata = eventMetadata(event);
    return event.created_at || event.createdAt || event.timestamp || metadata.timestamp || "";
  }

  function eventMessage(event = {}) {
    const metadata = eventMetadata(event);
    return event.message || metadata.message || event.stage || "job event";
  }

  function eventSeverity(event = {}) {
    const metadata = eventMetadata(event);
    const text = `${eventLabel(event)} ${event.status || ""} ${metadata.reasonCode || ""} ${eventMessage(event)}`.toLowerCase();
    if (/failed|failure|error|exception|traceback|unavailable|denied|invalid|whole_frame|too_large/.test(text)) return "bad";
    if (/warn|fallback|raster|blocked|cancel|stale|missing|retry|diagnostic/.test(text)) return "warn";
    if (/succeeded|complete|cached|ready|verified|written/.test(text)) return "ready";
    return "neutral";
  }

  function eventProgressText(event = {}) {
    const progress = eventProgress(event);
    const ratio = progress.overallRatio ?? progress.ratio;
    if (typeof ratio === "number") return `${Math.round((ratio <= 1 ? ratio : ratio / 100) * 100)}%`;
    const percent = progress.percent;
    if (typeof percent === "number") return `${Math.round(percent)}%`;
    return "";
  }

  function eventMetadataChips(event = {}) {
    const metadata = eventMetadata(event);
    const progressText = eventProgressText(event);
    return [
      metadata.stage || event.stage || "",
      metadata.provider || event.provider || "",
      metadata.action || event.action || "",
      metadata.reasonCode || metadata.reason_code || "",
      metadata.model || event.model || "",
      progressText,
    ].filter(Boolean);
  }

  function eventSuggestedActions(event = {}) {
    const metadata = eventMetadata(event);
    const explicit = asArray(metadata.suggestedFixes || metadata.suggested_fixes || metadata.nextActions || metadata.next_actions);
    if (explicit.length) return explicit.slice(0, 4).map(String);
    const text = `${eventLabel(event)} ${eventMessage(event)}`.toLowerCase();
    if (/cuda|gpu|torch|sam3|model|checkpoint|cache|hugging face|transformers/.test(text)) {
      return ["Open Model setup, verify runtime/access/cache status, then retry the run."];
    }
    if (/fallback|raster|vector|whole_frame|too_large/.test(text)) {
      return ["Open fallback diagnostics before export and adjust provider/prompt/filter settings."];
    }
    if (/failed|error|exception/.test(text)) {
      return ["Open debug metadata, fix the failing step, then start a new run."];
    }
    return [];
  }

  function eventDebugMetadata(event = {}) {
    const metadata = { ...eventMetadata(event) };
    delete metadata.progress;
    delete metadata.stage;
    delete metadata.provider;
    delete metadata.action;
    delete metadata.message;
    return metadata;
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

  function jobTimestamp(job = {}) {
    const lifecycle = job.lifecycle || {};
    const value =
      lifecycle.updatedAt ||
      lifecycle.createdAt ||
      job.updated_at ||
      job.updatedAt ||
      job.created_at ||
      job.createdAt ||
      job.timestamp ||
      "";
    if (typeof value === "number") return Number.isFinite(value) ? value : 0;
    const time = Date.parse(value);
    return Number.isFinite(time) ? time : 0;
  }

  function parseTimestampMs(value) {
    if (typeof value === "number") return Number.isFinite(value) ? value : 0;
    if (!value) return 0;
    const time = Date.parse(value);
    return Number.isFinite(time) ? time : 0;
  }

  function latestJobActivityTimestamp(job = {}, events = []) {
    const eventList = asArray(events);
    for (let index = eventList.length - 1; index >= 0; index -= 1) {
      const event = eventList[index] || {};
      const time = parseTimestampMs(event.created_at || event.createdAt || event.timestamp);
      if (time) return time;
    }
    const lifecycle = job.lifecycle || {};
    const latestEvent = lifecycle.latestEvent || job.latestEvent || {};
    for (const value of [
      job.lastEventAt,
      job.last_event_at,
      latestEvent.createdAt,
      latestEvent.created_at,
      latestEvent.timestamp,
      lifecycle.updatedAt,
      lifecycle.updated_at,
    ]) {
      const time = parseTimestampMs(value);
      if (time) return time;
    }
    return jobTimestamp(job);
  }

  function formatJobAge(ms) {
    const seconds = Math.max(1, Math.floor(ms / 1000));
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const remaining = minutes % 60;
    return remaining ? `${hours}h ${remaining}m` : `${hours}h`;
  }

  function jobStaleNotice(job = {}, options = {}) {
    const status = String(options.status || job.lifecycle?.status || job.status || "").toLowerCase();
    const rawStatus = String(options.rawStatus || job.lifecycle?.rawStatus || job.status || status).toLowerCase();
    const terminal = options.terminal ?? (TERMINAL_JOB_STATUSES.has(status) || TERMINAL_JOB_STATUSES.has(rawStatus));
    const active =
      options.active ??
      (/queued|pending|running|working|started|cancel_requested/.test(status) ||
        /queued|pending|running|working|started|cancel_requested/.test(rawStatus));
    const thresholdMs = Math.max(30 * 1000, Number(options.thresholdMs || STALE_ACTIVE_JOB_MS));
    const now = Number.isFinite(Number(options.now)) ? Number(options.now) : Date.now();
    const activityAt = latestJobActivityTimestamp(job, options.events || job.events || []);
    if (!active || terminal || !activityAt || now <= activityAt || now - activityAt < thresholdMs) {
      return { stale: false, ageMs: activityAt ? Math.max(0, now - activityAt) : 0, activityAt, label: "", detail: "" };
    }
    const ageMs = now - activityAt;
    const phase = job.lifecycle?.phase || job.phase || latestStageLabel(job);
    const label = `No progress update for ${formatJobAge(ageMs)}`;
    return {
      stale: true,
      ageMs,
      activityAt,
      label,
      detail: `${label}. Last reported phase: ${phase || status || "running"}. The model may still be loading or blocked; open logs or cancel the run.`,
    };
  }

  function normalizeJobLifecycle(job = {}, options = {}) {
    const lifecycle = job.lifecycle || {};
    const events = asArray(options.events || job.events);
    const status = String(lifecycle.status || job.status || "queued").toLowerCase();
    const rawStatus = String(lifecycle.rawStatus || job.status || status).toLowerCase();
    const progress = lifecycle.progress || job.progress || {};
    const directPercent = Number(progress.percent);
    const percent = Number.isFinite(directPercent) ? clamp(Math.round(directPercent), 0, 100) : normalizeProgress({ ...job, events });
    const progressKnown =
      typeof progress.known === "boolean"
        ? progress.known
        : Boolean(latestProgressEvent({ ...job, events }) || typeof job.progress === "number" || typeof job.percent === "number");
    const latestEvent = lifecycle.latestEvent || job.latestEvent || {};
    const configProvider = job.payload?.run_config?.provider?.name || job.runConfig?.provider?.name || job.config?.provider?.name || "";
    const failure =
      lifecycle.failure ||
      (/failed|canceled|cancelled/.test(status)
        ? {
            headline: /canceled|cancelled/.test(status) ? "Job canceled" : "Job failed",
            reasonCode: /canceled|cancelled/.test(status) ? "user_canceled" : "job_failed",
            message: job.error || job.reason || job.message || (/canceled|cancelled/.test(status) ? "The job was canceled." : "The job failed."),
            suggestedAction: /canceled|cancelled/.test(status) ? "Start a new run when ready." : "Change setup, run again, or open logs before retrying.",
          }
        : null);
    const provider = lifecycle.provider || job.provider || {};
    const terminal = TERMINAL_JOB_STATUSES.has(status) || TERMINAL_JOB_STATUSES.has(rawStatus);
    const active = /queued|pending|running|working|started|cancel_requested/.test(status) || /queued|pending|running|working|started|cancel_requested/.test(rawStatus);
    const actions = lifecycle.actions || job.actions || {};
    const review = lifecycle.review || job.review || {};
    const stale = jobStaleNotice(
      {
        ...job,
        lifecycle: {
          ...lifecycle,
          status,
          rawStatus,
          phase: lifecycle.phase || latestStageLabel({ ...job, events }),
          latestEvent,
        },
      },
      { events, status, rawStatus, active, terminal, now: options.now, thresholdMs: options.staleMs },
    );
    return {
      format: "motionjson.local_ui_job_lifecycle_view.v0.1",
      id: lifecycle.jobId || jobIdentifier(job),
      projectId: lifecycle.projectId || job.project_id || job.projectId || "",
      type: lifecycle.type || job.type || "job",
      workflow: lifecycle.workflow || job.workflow || "",
      status,
      rawStatus,
      phase: lifecycle.phase || latestStageLabel({ ...job, events }),
      progress: {
        known: progressKnown,
        percent,
        label: progress.label || `${percent}% complete`,
      },
      latestEvent: {
        type: latestEvent.type || "",
        message: latestEvent.message || latestStageLabel({ ...job, events }),
        createdAt: latestEvent.createdAt || latestEvent.created_at || "",
      },
      failure,
      review,
      provider: {
        connectionId: provider.connectionId || provider.connection_id || provider.id || "",
        providerId: provider.providerId || provider.provider_id || provider.id || job.payload?.mask_provider || configProvider || "",
        displayLabel: provider.displayLabel || provider.display_label || provider.label || provider.name || job.payload?.mask_provider || configProvider || "not reported",
        engine: provider.engine || "",
        locality: provider.locality || "",
        hostedCallsAllowed: Boolean(provider.hostedCallsAllowed || provider.hosted_calls_allowed),
      },
      actions: {
        ...actions,
        canCancel: actions.canCancel ?? actions.cancel ?? (active && !terminal),
        canRetry: actions.canRetry ?? false,
      },
      active,
      terminal,
      stale,
      timestamp: jobTimestamp(job),
      rawJob: job,
    };
  }

  function jobProgressText(job = {}) {
    const status = String(job.status || job.rawStatus || "").toLowerCase();
    const progress = job.progress || {};
    const label = String(progress.label || "").trim();
    if (/failed/.test(status)) return label && !/complete/i.test(label) ? label : "Failed";
    if (/canceled|cancelled/.test(status)) return label && !/complete/i.test(label) ? label : "Canceled";
    const percent = Number.isFinite(Number(progress.percent)) ? clamp(Math.round(Number(progress.percent)), 0, 100) : 0;
    return `${percent}% ${progress.known ? "complete" : "estimated"}`;
  }

  function jobCenterStateFromSnapshot(snapshot = {}) {
    const jobs = asArray(snapshot.jobs).map((job) => normalizeJobLifecycle(job));
    const recentJobs = jobs.slice().sort((a, b) => b.timestamp - a.timestamp || String(b.id).localeCompare(String(a.id)));
    const activeJobs = recentJobs.filter((job) => job.active);
    const requestedId = String(snapshot.selectedJobId || "").trim();
    const selectedJob =
      recentJobs.find((job) => job.id === requestedId) ||
      activeJobs[0] ||
      recentJobs[0] ||
      null;
    return {
      format: "motionjson.local_ui_job_center_view.v0.1",
      activeJobsCount: activeJobs.length,
      selectedJobId: selectedJob?.id || "",
      activeJobs,
      recentJobs,
      selectedJob,
    };
  }

  function reviewGateFromSnapshot(snapshot = {}) {
    const job = snapshot.job ? normalizeJobLifecycle(snapshot.job) : null;
    const review = job?.review || {};
    const candidateCount = toInteger(snapshot.candidateCount ?? review.candidateCount, 0);
    const selectedCandidateCount = toInteger(snapshot.selectedCandidateCount ?? review.selectedCandidateCount, 0);
    const trackCount = toInteger(snapshot.trackCount ?? review.trackCount, 0);
    const exportIncludedCount = toInteger(snapshot.exportIncludedCount ?? snapshot.exportableTrackCount ?? review.exportIncludedCount ?? review.exportableTrackCount, 0);
    const diagnosticCount = toInteger(snapshot.diagnosticCount ?? review.diagnosticCount, 0);
    const rasterReason = snapshot.vectorUnavailableReason || snapshot.rasterFallbackReason || review.vectorUnavailableReason || "";
    if (!job) return { status: "blocked", primaryAction: "start_run", primaryLabel: "Start a run", reason: "Run extraction before reviewing results." };
    if (job.status === "failed" || job.status === "canceled") {
      return { status: "blocked", primaryAction: "prepare_new_run", primaryLabel: "Change setup", reason: job.failure?.message || "The selected run did not produce reviewable output." };
    }
    if (job.active) return { status: "running", primaryAction: "watch_job", primaryLabel: "Watch job", reason: "Wait for the selected run to finish." };
    if (candidateCount > 0 && trackCount === 0) {
      const readyCandidateCount = selectedCandidateCount || candidateCount;
      return selectedCandidateCount > 0 || job.actions?.canTrackSelected
        ? { status: "needs-action", primaryAction: "track_selected", primaryLabel: "Track selected", reason: `${readyCandidateCount} candidate${readyCandidateCount === 1 ? "" : "s"} ready to track.` }
        : { status: "needs-action", primaryAction: "select_candidates", primaryLabel: "Keep candidates", reason: "Keep at least one candidate before tracking." };
    }
    if (trackCount > 0 && exportIncludedCount === 0) {
      return { status: "needs-action", primaryAction: "mark_reviewed", primaryLabel: "Mark reviewed", reason: "Mark at least one track for export." };
    }
    if (exportIncludedCount > 0 || job.actions?.canExport) {
      return { status: "ready", primaryAction: "export_reviewed", primaryLabel: "Export reviewed objects", reason: "" };
    }
    if (diagnosticCount > 0 || review.hasRasterFallback || rasterReason) {
      return { status: "needs-action", primaryAction: "inspect_diagnostics", primaryLabel: "Open diagnostics", reason: rasterReason || "The completed run produced diagnostics before exportable tracks." };
    }
    return { status: "needs-action", primaryAction: "inspect_diagnostics", primaryLabel: "Open diagnostics", reason: "No candidates or tracks were reported for this completed run." };
  }

  function reviewCountsFromSnapshot(snapshot = {}) {
    const job = snapshot.job ? normalizeJobLifecycle(snapshot.job) : null;
    const review = job?.review || {};
    return {
      job,
      candidateCount: toInteger(snapshot.candidateCount ?? review.candidateCount, 0),
      selectedCandidateCount: toInteger(snapshot.selectedCandidateCount ?? review.selectedCandidateCount, 0),
      trackCount: toInteger(snapshot.trackCount ?? review.trackCount, 0),
      exportIncludedCount: toInteger(snapshot.exportIncludedCount ?? snapshot.exportableTrackCount ?? review.exportIncludedCount ?? review.exportableTrackCount, 0),
      correctionCount: toInteger(snapshot.correctionCount, 0),
      exportValidated: Boolean(snapshot.exportValidated),
      exportOk: Boolean(snapshot.exportOk),
      diagnosticCount: toInteger(snapshot.diagnosticCount ?? review.diagnosticCount, 0),
      attentionDiagnosticCount: toInteger(snapshot.attentionDiagnosticCount, 0),
      hasFailure: Boolean(snapshot.hasFailure || job?.failure || /failed|error|canceled/.test(String(job?.status || snapshot.selectedJobStatus || "").toLowerCase())),
    };
  }

  function reviewFlowStateFromSnapshot(snapshot = {}) {
    const counts = reviewCountsFromSnapshot(snapshot);
    const gate = reviewGateFromSnapshot({ ...snapshot, job: counts.job });
    const hasJob = Boolean(counts.job || snapshot.hasSelectedJob || snapshot.selectedJobStatus);
    const failed = gate.primaryAction === "open_logs";
    const running = gate.primaryAction === "watch_job";
    const stage = (id, label, value, detail, status = "needs-action") => ({
      id,
      label,
      value,
      detail,
      status,
      tone: status === "done" || status === "ready" ? "is-ready" : status === "running" ? "is-neutral" : status === "blocked" ? "is-bad" : "is-warn",
    });
    const candidatesStage = failed
      ? stage("candidates", "Candidates", "Blocked", "Open diagnostics before reviewing candidates.", "blocked")
      : counts.candidateCount
        ? stage("candidates", "Candidates", `${counts.selectedCandidateCount}/${counts.candidateCount} kept`, counts.selectedCandidateCount ? "Kept candidates are ready for tracking." : "Keep at least one candidate before tracking.", counts.selectedCandidateCount ? "done" : "needs-action")
        : hasJob
          ? stage("candidates", "Candidates", "None reported", "Open diagnostics or retry with clearer prompts.", counts.diagnosticCount || counts.hasFailure ? "blocked" : "needs-action")
          : stage("candidates", "Candidates", "Not loaded", "Run extraction before reviewing candidates.", "needs-action");
    const trackSelectedStage = failed
      ? stage("track_selected", "Track selected", "Blocked", "The run did not produce reviewable candidates.", "blocked")
      : counts.trackCount
        ? stage("track_selected", "Track selected", "Done", "Selected candidates were turned into tracks.", "done")
        : counts.selectedCandidateCount
          ? stage("track_selected", "Track selected", `${counts.selectedCandidateCount} ready`, "Track selected candidates to create object tracks.", "needs-action")
          : counts.candidateCount
            ? stage("track_selected", "Track selected", "Needs kept candidates", "Keep at least one candidate before tracking.", "needs-action")
            : stage("track_selected", "Track selected", "Waiting", "Candidates must exist before tracking.", running ? "running" : "needs-action");
    const tracksStage = failed
      ? stage("tracks", "Tracks", "Unavailable", "No vector/object tracks were produced.", "blocked")
      : counts.trackCount
        ? stage("tracks", "Tracks", `${counts.trackCount} track${counts.trackCount === 1 ? "" : "s"}`, `${counts.exportIncludedCount} marked for export.`, counts.exportIncludedCount ? "done" : "needs-action")
        : counts.candidateCount
          ? stage("tracks", "Tracks", "Not created", "Track selected candidates before correcting or exporting.", "needs-action")
          : stage("tracks", "Tracks", "None", "Tracks appear after candidate tracking.", running ? "running" : "needs-action");
    const correctionsStage = counts.correctionCount
      ? stage("corrections", "Corrections", `${counts.correctionCount} edit${counts.correctionCount === 1 ? "" : "s"}`, "Correction edits are saved locally before export.", "done")
      : counts.trackCount
        ? stage("corrections", "Corrections", "Optional", "Repair, relabel, merge, split, or continue to export.", "ready")
        : stage("corrections", "Corrections", "No tracks", "Correction tools become useful after tracks exist.", failed ? "blocked" : "needs-action");
    const exportStage = failed
      ? stage("export", "Export", "Blocked", "Resolve the failed run before exporting.", "blocked")
      : counts.exportOk
        ? stage("export", "Export", "Validated", "Reviewed object export passed validation.", "done")
        : counts.exportValidated
          ? stage("export", "Export", "Needs fixes", "Resolve validation issues before writing MotionJSON.", "blocked")
          : counts.exportIncludedCount
            ? stage("export", "Export", `${counts.exportIncludedCount} included`, "Validate export settings before writing artifacts.", "needs-action")
            : counts.trackCount
              ? stage("export", "Export", "Needs reviewed track", "Mark at least one track for export.", "needs-action")
              : stage("export", "Export", "Not ready", "Create tracks before exporting.", running ? "running" : "needs-action");
    return {
      format: "motionjson.local_ui_review_flow_view.v0.1",
      gate,
      ...counts,
      stages: [candidatesStage, trackSelectedStage, tracksStage, correctionsStage, exportStage],
    };
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

  function providerSmokeTestEndpoint(providerId) {
    return `/api/provider-settings/${encodeURIComponent(providerId)}/smoke-test`;
  }

  function selectedVideo() {
    return state.videos.find((video) => video.id === state.selectedVideoId) || null;
  }

  function selectedVideoBrowserPreview(video = selectedVideo()) {
    return video?.browserPreview && typeof video.browserPreview === "object" ? video.browserPreview : null;
  }

  function browserPreviewReady(video = selectedVideo()) {
    return selectedVideoBrowserPreview(video)?.status === "ready";
  }

  function selectedVideoPosterUrl(video = selectedVideo()) {
    return safeLocalContentUrl(selectedVideoBrowserPreview(video)?.posterUrl || "");
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
    const preset = PRESETS[state.selectedPreset] || PRESETS.auto_object_proposals;
    const frameIndex = state.video.currentFrame || toInteger($("#frameSlider").value, 0);
    const hostedSam2Provider = providerSettingsById("sam2-hosted");
    const hostedSam3Provider = providerSettingsById("sam3-hosted");
    const localSam2Provider = providerSettingsById("sam2-local");
    const localSam2HfProvider = providerSettingsById("sam2-hf-auto-masks");
    const localSam3Provider = providerSettingsById("sam3-local");
    const hostedSam2Settings = hostedSam2Provider?.settings || {};
    const hostedSam3Settings = hostedSam3Provider?.settings || {};
    const localSam2Settings = localSam2Provider?.settings || {};
    const localSam2HfSettings = localSam2HfProvider?.settings || {};
    const localSam3Settings = localSam3Provider?.settings || {};
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
      modelConnectionId: state.selectedModelSetupProviderId,
      maskProvider: $("#maskProviderSelect").value || preset.maskProvider || state.runDefaults?.defaults?.maskProvider || "threshold",
      textDiscoveryProvider: $("#textDiscoveryProviderSelect")?.value || "sam3-hosted",
      allowLegacyTextDetector: state.workflowDashboard === true,
      debugMockMode: Boolean(state.health?.mockMode),
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
      qualityPreset: $("#discoveryQualityPreset").value,
      traceEverythingMode: $("#traceEverythingMode").checked,
      traceEverythingAcknowledged: $("#traceEverythingAck").checked,
      textPrompt: $("#textPrompt").value.trim(),
      classPreset: $("#classPreset").value,
      classList: $("#classList").value.trim(),
      externalMaskDir: $("#externalMaskDir").value.trim(),
      hostedSam2ProfileId: hostedSam2Settings.hostedProfileId || "replicate-sam2-video",
      hostedSam2AllowHosted: Boolean(hostedSam2Settings.allowHosted),
      hostedSam2Model: providerEffectiveModel(hostedSam2Provider),
      hostedSam3ProfileId: hostedSam3Settings.hostedProfileId || "roboflow-sam3-pcs",
      hostedSam3AllowHosted: Boolean(hostedSam3Settings.allowHosted),
      hostedSam3Model: providerEffectiveModel(hostedSam3Provider),
      localSam2CheckpointPath: localSam2Settings.sam2CheckpointPath || "",
      localSam2ModelConfigPath: localSam2Settings.sam2ModelConfigPath || "",
      localSam2Device: localSam2Settings.sam2Device || "",
      localSam2HfModel: providerEffectiveModel(localSam2HfProvider) || "facebook/sam2.1-hiera-large",
      localSam2HfDevice: localSam2HfSettings.sam2HfDevice || "",
      localSam3TrackerModel: providerEffectiveModel(localSam3Provider) || "facebook/sam3",
      localSam3ModelPath: localSam3Settings.sam3ModelPath || "",
      localSam3Device: localSam3Settings.sam3Device || "",
    };
  }

  function providerByName(name, kind = null) {
    return asArray(state.capabilities?.providers).find((provider) => provider.name === name && (!kind || provider.kind === kind));
  }

  function providerSettingsById(providerId) {
    return asArray(state.providerSettings?.providers).find(
      (provider) => provider.id === providerId || provider.capabilityName === providerId,
    );
  }

  function providerEffectiveModel(provider) {
    if (!provider) return "";
    return provider.effectiveModel || provider.settings?.customModelId || provider.settings?.selectedModel || provider.defaultModel || "";
  }

  function cleanPublicModelValue(value) {
    const text = String(value || "").trim();
    return text === "[LOCAL_PATH_REDACTED]" ? "" : text;
  }

  function connectionCapabilityMeta(connection) {
    const provider = providerSettingsById(connection.providerId);
    if (!provider) return null;
    if (!connection.profileId) return provider;
    return asArray(provider.hostedProfiles).find((profile) => profile.id === connection.profileId) || provider;
  }

  function connectionSupportsGoal(connection, presetId = state.selectedPreset) {
    if (!connection || !goalRequiresModel(presetId)) return false;
    const meta = connectionCapabilityMeta(connection);
    const capabilities = new Set(asArray(connection.capabilities));
    const supportedGoals = asArray(meta?.supportedGoals).map(String);
    if (supportedGoals.length && !supportedGoals.includes(presetId)) return false;
    if (presetId === "trace_one_object") {
      const promptTypes = asArray(meta?.supportedPromptTypes);
      return (promptTypes.includes("box") || capabilities.has("box")) && meta?.supportsTracking !== false;
    }
    if (presetId === "trace_all_objects") {
      return meta?.supportsAutoMasks === true || capabilities.has("auto_masks");
    }
    if (presetId === "auto_object_proposals") {
      return meta?.supportsAutoMasks === true || capabilities.has("auto_masks") || capabilities.has("scene_sweep");
    }
    if (presetId === "text_detector") {
      return meta?.supportsConcept === true || capabilities.has("concept");
    }
    return true;
  }

  function compatibleModelConnectionsForPreset(presetId = state.selectedPreset, options = {}) {
    if (!goalRequiresModel(presetId)) return [];
    const priority = MODEL_CONNECTION_PRIORITY[presetId] || [];
    const advancedPriority = ADVANCED_MODEL_CONNECTIONS[presetId] || [];
    const visibleIds = options.includeAdvanced ? [...priority, ...advancedPriority] : priority;
    return MODEL_CONNECTIONS
      .filter((connection) => connectionSupportsGoal(connection, presetId))
      .filter((connection) => !visibleIds.length || visibleIds.includes(connection.id))
      .sort((a, b) => {
        const aIndex = visibleIds.includes(a.id) ? visibleIds.indexOf(a.id) : visibleIds.length;
        const bIndex = visibleIds.includes(b.id) ? visibleIds.indexOf(b.id) : visibleIds.length;
        return aIndex - bIndex || MODEL_CONNECTIONS.indexOf(a) - MODEL_CONNECTIONS.indexOf(b);
      });
  }

  function modelConnectionById(id) {
    return modelConnectionByConnectionId(id) || normalizedModelConnection(MODEL_CONNECTIONS[0]);
  }

  function capabilityForConnection(connection) {
    if (connection?.providerId === "sam3-local" && state.selectedPreset === "trace_all_objects") {
      return providerByName("sam3-auto-masks", "discovery_provider") || providerByName("sam3-auto-masks");
    }
    const provider = providerSettingsById(connection.providerId);
    const capabilityName = provider?.capabilityName || connection.providerId;
    return providerByName(capabilityName, provider?.kind || null) || providerByName(capabilityName);
  }

  function connectionReadiness(connection) {
    const provider = providerSettingsById(connection.providerId);
    const capability = capabilityForConnection(connection);
    const readiness = provider?.readiness || {};
    const hosted = connection.locality === "hosted" || provider?.locality === "hosted";
    const profileOk = !connection.profileId || provider?.settings?.hostedProfileId === connection.profileId || provider?.defaultHostedProfile === connection.profileId;
    const runnable = capability?.runnable === true || (readiness.configured && !hosted);
    const configured = readiness.configured === true || capability?.configured === true;
    const hostedAllowed = !hosted || provider?.settings?.allowHosted === true;
    if (runnable && hostedAllowed && profileOk) {
      return { tone: "ready", status: "ready", label: "Ready", message: "Ready for this workflow." };
    }
    if (configured && hosted && !hostedAllowed) {
      return { tone: "warn", status: "needs_opt_in", label: "Needs hosted confirmation", message: "Key is saved; hosted calls need cost/privacy opt-in." };
    }
    if (configured || capability?.installed) {
      const needsPath = connection.locality === "local" && /model|checkpoint|path|config/i.test(String(readiness.message || capability?.reasons?.join(" ") || ""));
      return { tone: "warn", status: needsPath ? "needs_path" : "installed_not_runnable", label: needsPath ? "Needs path" : "Installed but not runnable", message: readiness.message || capability?.reasons?.[0] || "Review diagnostics before running." };
    }
    const needsKey = hosted && /key|token|credential/i.test(String(readiness.message || capability?.reasons?.join(" ") || ""));
    return { tone: "bad", status: needsKey ? "needs_key" : "unavailable", label: needsKey ? "Needs key" : "Unavailable", message: readiness.message || capability?.reasons?.[0] || connection.recommendation };
  }

  function setupJobForProvider(providerId) {
    return Object.values(state.providerSetupJobs || {})
      .filter((job) => job?.providerId === providerId)
      .sort((a, b) => String(b.updatedAt || b.createdAt || "").localeCompare(String(a.updatedAt || a.createdAt || "")))[0] || null;
  }

  function setupJobStatusSummary(job) {
    if (!job) return { tone: "neutral", label: "No setup job", message: "No setup action has run in this session." };
    const status = String(job.status || "queued");
    const tone = status === "succeeded" ? "ready" : status === "failed" || status === "blocked" || status === "canceled" ? "bad" : "neutral";
    const result = job.result || {};
    const progress = setupJobProgressSummary(job);
    return {
      tone,
      label: status === "succeeded" ? "Setup complete" : status === "running" || status === "queued" ? "Setup running" : humanizeReviewCode(status),
      message: result.message || job.error || `Setup ${status}.`,
      progress,
    };
  }

  function setupJobProgressSummary(job) {
    const normalize = (progress) => {
      if (!progress || typeof progress !== "object") return null;
      const rawPercent = Number(progress.percent);
      const percent = Number.isFinite(rawPercent) ? Math.min(Math.max(rawPercent, 0), 100) : 0;
      const label = String(progress.label || "").trim() || "Setup in progress";
      return { known: progress.known === true, percent, label };
    };
    const eventProgress = asArray(job?.events)
      .slice()
      .reverse()
      .map((event) => normalize(event?.metadata?.progress))
      .find(Boolean);
    return normalize(job?.progress) || normalize(job?.result?.progress) || eventProgress;
  }

  function setupJobStaleNotice(job = {}) {
    const action = String(job.action || "");
    if (!["prepare_model", "smoke", "cache_model", "install"].includes(action)) {
      return { stale: false, detail: "" };
    }
    return jobStaleNotice(job, {
      status: job.status,
      rawStatus: job.status,
      terminal: job.terminal === true,
      active: ["queued", "running"].includes(String(job.status || "")),
      thresholdMs: action === "prepare_model" || action === "smoke" ? 60 * 1000 : 3 * 60 * 1000,
      events: job.events || [],
    });
  }

  function setupJobProgressCard(job, summary = setupJobStatusSummary(job)) {
    if (!job) return "";
    const action = String(job.action || "");
    if (!["install", "check_access", "cache_model", "prepare_model", "smoke", "test", "diagnose"].includes(action)) return "";
    const progress = summary.progress || setupJobProgressSummary(job);
    if (!progress && !["queued", "running"].includes(String(job.status || ""))) return "";
    const normalizedProgress = progress || { known: false, percent: 0, label: summary.message || "Setup in progress" };
    const status = String(job.status || "queued");
    const active = status === "queued" || status === "running";
    const staleNotice = setupJobStaleNotice(job);
    const tone = staleNotice.stale
      ? "warn"
      : summary.tone || (status === "succeeded" ? "ready" : status === "failed" || status === "blocked" || status === "canceled" ? "bad" : "neutral");
    const percent = Math.min(Math.max(Number(normalizedProgress.percent) || 0, 0), 100);
    const displayPercent = normalizedProgress.known || active ? percent : 100;
    const barClass = normalizedProgress.known ? "" : active ? "is-indeterminate" : "is-static";
    const meterText = normalizedProgress.known ? `${Math.round(percent)}%` : active ? "In progress" : "Needs attention";
    const label = staleNotice.stale
      ? `${normalizedProgress.label || summary.message || "Setup in progress"} - ${staleNotice.label}`
      : normalizedProgress.label || summary.message || "Setup in progress";
    const progressAttrs = normalizedProgress.known
      ? `aria-valuenow="${escapeAttribute(String(Math.round(percent)))}"`
      : "";
    return `
      <div class="model-setup-progress-card is-${escapeAttribute(tone)}" role="status" aria-live="polite">
        <div class="model-setup-progress-copy">
          <strong>${escapeHtml(summary.label || humanizeReviewCode(status))}</strong>
          <span class="row-meta">${escapeHtml(label)}</span>
          ${
            staleNotice.stale
              ? `<span class="row-meta model-setup-stall-notice">${escapeHtml(staleNotice.detail || "No backend progress update has arrived. Open logs or cancel setup before retrying.")}</span>`
              : ""
          }
        </div>
        <div class="model-setup-progress-meter">
          <div
            class="model-setup-progress-track"
            role="progressbar"
            aria-label="${escapeAttribute(summary.label || "Setup progress")}"
            aria-valuemin="0"
            aria-valuemax="100"
            ${progressAttrs}
          >
            <span class="model-setup-progress-bar ${barClass}" style="--model-setup-progress: ${escapeAttribute(String(displayPercent))}%;"></span>
          </div>
          <span class="row-meta">${escapeHtml(meterText)}</span>
        </div>
      </div>
    `;
  }

  function environmentRecommendationSummary(capabilities = state.capabilities) {
    const profile = capabilities?.environment?.profile || {};
    const recommendation = capabilities?.summary?.gpuModelRecommendation || {};
    const accelerator = recommendation.accelerator || profile.accelerator || "cpu";
    const tone = accelerator === "cuda" ? "ready" : accelerator === "mps" ? "warn" : "neutral";
    return {
      tone,
      environmentLabel: profile.label || "Local environment",
      environmentType: profile.type || "local_unknown",
      summary: profile.summary || "Environment diagnostics are not loaded yet.",
      accelerator,
      modelLabel: recommendation.label || "No GPU model recommendation loaded",
      model: recommendation.model || "",
      providerId: recommendation.recommendedProviderId || "",
      connectionId: recommendation.connectionId || "",
      reason: recommendation.reason || "",
      status: recommendation.status || "unknown",
      runnable: recommendation.runnable === true,
      missing: asArray(recommendation.missing),
      nextActions: asArray(recommendation.nextActions),
    };
  }

  function environmentRecommendationCard(connection = null) {
    const summary = environmentRecommendationSummary();
    const matchesSelection = summary.providerId && connection?.providerId === summary.providerId;
    const status = summary.runnable ? "ready" : summary.status || "setup";
    const details = [
      summary.accelerator ? `${summary.accelerator.toUpperCase()} detected` : "",
      summary.model || "",
      matchesSelection ? "selected path" : summary.providerId ? `recommended: ${summary.providerId}` : "",
    ].filter(Boolean);
    const actionItems = summary.nextActions.slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    const missing = summary.missing.length
      ? `<span class="row-meta">${escapeHtml(summary.missing.slice(0, 2).join(" "))}</span>`
      : "";
    return `
      <div class="environment-recommendation-card is-${escapeAttribute(summary.tone)}">
        <div>
          <strong>${escapeHtml(summary.environmentLabel)}</strong>
          <p>${escapeHtml(summary.reason || summary.summary)}</p>
          <div class="provider-detail">
            ${details.map((detail) => detailChip(detail)).join("")}
            ${statusChip(summary.modelLabel, status, summary.runnable)}
          </div>
          ${missing}
        </div>
        ${actionItems ? `<ol class="setup-playbook-actions">${actionItems}</ol>` : ""}
      </div>
    `;
  }

  function modelCacheStatusSummary(provider = null, setupJob = null) {
    const cache = setupJob?.result?.modelCache || provider?.modelCache || {};
    if (!cache.required) {
      return {
        required: false,
        status: "not_required",
        label: "No model cache required",
        message: "This connection does not need a local Hugging Face model cache.",
      };
    }
    const cached = cache.cached === true;
    const recorded = cache.serverPathRecorded === true || setupJob?.result?.localPathRecorded === true;
    const pathKnown = cache.localPathKnown === true || recorded;
    return {
      required: true,
      cached,
      recorded,
      pathKnown,
      status: cache.status || (cached ? "cached" : "not_cached"),
      label: cached ? (recorded ? "Cached path recorded" : "Cached locally") : "Cache needed",
      message: cache.pathSummary || cache.message || (cached ? "Model cache is available." : "Cache the model before running."),
      model: cache.model || providerEffectiveModel(provider),
      updatedAt: cache.recordedAt || provider?.settings?.updatedAt || "",
    };
  }

  function modelSetupPlaybookSteps(connection = {}, provider = null, setupState = {}, setupJob = null) {
    const providerId = connection.providerId || provider?.id || "";
    const readiness = provider?.readiness || {};
    const credentials = asArray(provider?.credentials);
    const hfCredential = credentials.find((credential) => credential.name === "hf_token");
    const cache = modelCacheStatusSummary(provider, setupJob);
    const status = String(setupState.status || readiness.status || "");
    const runtimeReady = readiness.configured === true || readiness.status === "ready" || readiness.status === "configured";
    const setupRunning = setupJob && !setupJob.terminal;
    const localCacheProvider = providerId === "sam3-local" || providerId === "sam2-hf-auto-masks";
    const runtimeVerification = provider?.runtimeVerification || setupJob?.result?.diagnosis?.runtimeVerification || {};
    const setupEvents = asArray(setupJob?.events);
    const hasSetupEvent = (...names) => setupEvents.some((event) => names.includes(String(event.eventType || event.type || "")));
    const verificationReady = runtimeVerification.verified === true || (!localCacheProvider && setupState.status === "ready") || setupJob?.result?.ready === true;
    const loadedOnCuda = runtimeVerification.loadedOnCuda === true || setupJob?.result?.smokeTest?.loadedOnCuda === true;
    const deviceActual = runtimeVerification.deviceActual || setupJob?.result?.smokeTest?.deviceActual || provider?.settings?.sam3Device || "cuda";
    const loadRunning =
      setupRunning &&
      ["smoke", "prepare_model"].includes(setupJob.action) &&
      hasSetupEvent(
        "loading_transformers_pipeline",
        "sam3_smoke_subprocess_started",
        "loading_sam3_tracker_processor",
        "loading_sam3_tracker_model_weights",
        "sam3_tracker_model_load_attempt",
        "sam3_tracker_model_load_retry",
        "moving_model_to_device",
        "model_loaded_on_device",
        "model_loaded",
        "model_device_verified"
      );
    const warmupRunning = setupRunning && ["smoke", "prepare_model"].includes(setupJob.action) && hasSetupEvent("warmup_started", "warmup_succeeded");
    const steps = [
      {
        id: "environment",
        label: "Environment",
        status: runtimeReady ? "done" : setupRunning && ["install", "prepare_model", "diagnose"].includes(setupJob.action) ? "running" : "pending",
        detail: runtimeReady ? readiness.message || "Runtime diagnostics are ready." : readiness.message || environmentRecommendationSummary().summary,
      },
    ];
    if (localCacheProvider) {
      steps.push({
        id: "download",
        label: "Download",
        status: cache.cached ? "done" : setupRunning && ["cache_model", "prepare_model"].includes(setupJob.action) ? "running" : status === "needs_download_confirmation" ? "active" : "pending",
        detail: cache.cached
          ? cache.recorded
            ? "Model is cached and the runtime directory is recorded server-side."
            : cache.message
          : providerId === "sam3-local" && !hfCredential?.configured
            ? "Paste a Hugging Face token if facebook/sam3 is gated, then prepare the model."
            : cache.message,
      });
    }
    steps.push({
      id: "load_gpu",
      label: providerId === "sam3-local" ? "Load on GPU" : "Load model",
      status: loadedOnCuda || (verificationReady && providerId !== "sam3-local") ? "done" : loadRunning ? "running" : status === "needs_smoke" ? "active" : "pending",
      detail: loadedOnCuda
        ? `Model loaded on ${deviceActual || "CUDA"}.`
        : providerId === "sam3-local"
          ? "Smoke test must prove the SAM3 Tracker model loads on CUDA."
          : "Smoke test loads the cached model before extraction.",
    });
    steps.push({
      id: "warmup",
      label: "Warm up",
      status: verificationReady ? "done" : warmupRunning ? "running" : status === "needs_smoke" ? "active" : "pending",
      detail: verificationReady ? runtimeVerification.message || "Bounded smoke inference succeeded." : "Run a bounded inference before unlocking extraction.",
    });
    steps.push({
      id: "ready",
      label: "Ready to run",
      status: setupState.status === "ready" ? "done" : "pending",
      detail: setupState.status === "ready" ? setupState.message || "Setup is ready." : "Continue unlocks only after cache, load, and warmup succeed.",
    });
    return steps;
  }

  function modelSetupPlaybookMarkup(connection, provider, setupState, setupJob) {
    const steps = modelSetupPlaybookSteps(connection, provider, setupState, setupJob);
    return `
      <div class="model-setup-playbook" aria-label="Model setup playbook">
        ${steps
          .map(
            (step, index) => `
              <div class="setup-playbook-step is-${escapeAttribute(step.status)}">
                <span class="setup-playbook-index">${index + 1}</span>
                <div>
                  <strong>${escapeHtml(step.label)}</strong>
                  <span class="row-meta">${escapeHtml(step.detail || "")}</span>
                </div>
              </div>
            `,
          )
          .join("")}
      </div>
    `;
  }

  function modelSetupDecisionForConnection(connection, provider = null, latestJob = null) {
    const readiness = provider?.readiness || {};
    const backendState = latestJob?.setupState || provider?.setupState || {};
    const jobStatus = String(latestJob?.status || "").toLowerCase();
    if (latestJob && !latestJob.terminal) {
      const statusByAction = {
        cache_model: "caching_model",
        install: "installing_runtime",
        prepare_model: "preparing_model",
        smoke: "smoke_testing",
        check_access: "checking_environment",
        diagnose: "checking_environment",
        test: "checking_environment",
      };
      const activeStatus = statusByAction[latestJob.action] || backendState.status || "checking_environment";
      return {
        status: activeStatus,
        label: backendState.label || setupJobStatusSummary(latestJob).label,
        message: backendState.message || setupJobStatusSummary(latestJob).message,
        nextAction: "cancel_setup_job",
      };
    }
    if (latestJob && ["failed", "blocked", "canceled", "cancelled"].includes(jobStatus)) {
      const failedAction = String(latestJob.action || "");
      const failedMessage = String(latestJob.result?.message || latestJob.error || "");
      if (failedAction === "check_access" && !/huggingface_hub is not installed/i.test(failedMessage)) {
        return {
          status: "needs_access",
          label: connection?.providerId === "sam3-local" ? "Needs Hugging Face access" : "Needs access",
          message: failedMessage || "Check access again after updating credentials.",
        };
      }
      if (failedAction === "cache_model" && /access|token|credential|hugging face|hf_|gated|401|403/i.test(failedMessage)) {
        return {
          status: "needs_access",
          label: connection?.providerId === "sam3-local" ? "Needs Hugging Face access" : "Needs access",
          message: failedMessage || "Confirm provider access before caching the model.",
        };
      }
      if (failedAction === "cache_model") {
        return {
          status: "needs_download_confirmation",
          label: "Cache model",
          message: failedMessage || "Cache the selected model again after resolving the local setup issue.",
          nextAction: "cache_model",
        };
      }
      if (failedAction === "prepare_model") {
        const nextAction = String(latestJob.result?.nextAction || "");
        if (nextAction === "check_access") {
          return {
            status: "needs_access",
            label: "Needs Hugging Face access",
            message: failedMessage || "Check access before caching the model.",
            nextAction,
          };
        }
        if (nextAction === "cache_model") {
          return {
            status: "needs_download_confirmation",
            label: "Cache model",
            message: failedMessage || "Confirm model caching before continuing.",
            nextAction,
          };
        }
        if (nextAction === "smoke") {
          return {
            status: "needs_smoke",
            label: "Ready to verify",
            message: failedMessage || "Run a bounded smoke test before extraction.",
            nextAction,
          };
        }
        return {
          status: "not_configured",
          label: "Needs setup",
          message: failedMessage || "Install the runtime before preparing this model.",
          nextAction: nextAction || "install",
        };
      }
      if (backendState.status && backendState.status !== "ready" && failedAction !== "smoke") {
        return backendState;
      }
      return {
        status: "failed_recoverable",
        label: "Needs recovery",
        message: latestJob.result?.message || latestJob.error || "Setup did not finish. Retry or choose a different model.",
      };
    }
    const providerSetupStatus = String(provider?.setupState?.status || "");
    if (["needs_access", "needs_download_confirmation", "needs_path", "needs_smoke", "failed_recoverable"].includes(providerSetupStatus)) {
      return provider.setupState;
    }
    const cacheSummary = modelCacheStatusSummary(provider, latestJob);
    const localCacheProvider = connection?.providerId === "sam3-local" || connection?.providerId === "sam2-hf-auto-masks";
    const smokeReady =
      latestJob?.status === "succeeded" &&
      ["smoke", "prepare_model"].includes(String(latestJob?.action || "")) &&
      latestJob?.result?.ready === true;
    if (
      providerSetupStatus === "ready" &&
      localCacheProvider &&
      cacheSummary.cached &&
      !smokeReady
    ) {
      return {
        status: "needs_smoke",
        label: "Ready to verify",
        message: "The model path is recorded server-side. Run a bounded smoke test before extraction.",
        nextAction: "smoke",
      };
    }
    if (providerSetupStatus === "ready" && (readiness.configured === true || readiness.status === "ready" || readiness.status === "configured")) {
      return provider.setupState;
    }
    const cached = cacheSummary.cached || (latestJob?.action === "cache_model" && latestJob.status === "succeeded");
    const runtimeReady = readiness.configured === true || readiness.status === "ready" || readiness.status === "configured";
    const hfCredential = asArray(provider?.credentials).find((credential) => credential?.name === "hf_token");
    const hfTokenConfigured = hfCredential?.configured === true;
    if (latestJob?.status === "succeeded" && latestJob?.result?.ready === true && (runtimeReady || state.health?.mockMode)) {
      return { status: "ready", label: "Ready", message: latestJob.result.message || readiness.message || "Model setup is ready for this workflow." };
    }
    const needsAccess = /access|token|credential|key|hugging face|hf_/i.test(`${readiness.status || ""} ${readiness.message || ""} ${asArray(readiness.missing).join(" ")}`);
    const needsRuntime = /not_configured|missing|unavailable/i.test(String(readiness.status || "")) || readiness.configured === false;
    if (smokeReady || (runtimeReady && connection?.locality !== "local")) {
      return { status: "ready", label: "Ready", message: readiness.message || "Model setup is ready for this workflow." };
    }
    if (runtimeReady && connection?.providerId === "sam3-local" && state.selectedPreset === "trace_all_objects" && !cached && !hfTokenConfigured) {
      return { status: "needs_access", label: "Needs Hugging Face access", message: "Paste a Hugging Face token for facebook/sam3, then check access before caching the model." };
    }
    if (runtimeReady && connection?.providerId === "sam3-local" && state.selectedPreset === "trace_all_objects" && !cached) {
      return { status: "needs_download_confirmation", label: "Confirm model cache", message: "Cache facebook/sam3 before the first scene sweep so extraction does not download unexpectedly." };
    }
    if (runtimeReady && connection?.providerId === "sam2-hf-auto-masks" && !cached) {
      return { status: "needs_download_confirmation", label: "Confirm model cache", message: "Cache facebook/sam2.1-hiera-large before using the SAM2 HF fallback." };
    }
    if (runtimeReady) {
      return { status: "ready", label: "Ready", message: readiness.message || "Model setup is ready for this workflow." };
    }
    if (needsAccess) {
      return { status: "needs_access", label: "Needs access", message: readiness.message || "Sign in or confirm model/provider access before continuing." };
    }
    if (needsRuntime) {
      return { status: "not_configured", label: "Needs setup", message: readiness.message || connection?.nextAction || "Install the required runtime from this setup step." };
    }
    return {
      status: backendState.status || "not_configured",
      label: backendState.label || "Needs setup",
      message: backendState.message || readiness.message || "Complete setup before running.",
    };
  }

  function modelSetupStateForConnection(connection, provider = null, latestJob = null) {
    return modelSetupDecisionForConnection(connection, provider, latestJob);
  }

  function modelSetupPrimaryActionForState(stateInfo = {}, connection = null) {
    const status = String(stateInfo.status || "not_configured");
    const nextAction = String(stateInfo.nextAction || "");
    const providerId = connection?.providerId || "";
    const localSetupProvider = connection?.locality === "local" || ["sam3-local", "sam2-hf-auto-masks", "sam2-local"].includes(providerId);
    if (["checking_environment", "caching_model", "installing_runtime", "preparing_model", "smoke_testing"].includes(status)) {
      return { id: "cancel-setup-job", label: "Cancel setup", primary: false };
    }
    if (status === "needs_smoke") {
      return { id: "smoke", label: "Run smoke test", primary: true };
    }
    if (localSetupProvider && nextAction === "install") {
      return {
        id: "install",
        label: providerId === "sam3-local" ? "Install scene sweep" : providerId === "sam2-hf-auto-masks" ? "Install SAM2 HF fallback" : "Install runtime",
        primary: true,
      };
    }
    if (localSetupProvider && nextAction === "choose_model") {
      return { id: "save", label: "Save setup", primary: true };
    }
    if (localSetupProvider && ["needs_access", "needs_download_confirmation", "needs_path", "not_configured"].includes(status)) {
      return { id: "prepare-model", label: "Prepare local model", primary: true };
    }
    if (status === "needs_access") {
      return { id: providerId.includes("hosted") ? "test" : "check-access", label: providerId.includes("hosted") ? "Check access" : "Check Hugging Face access", primary: true };
    }
    if (status === "needs_download_confirmation") {
      return { id: "cache-model", label: "Cache model", primary: true };
    }
    if (status === "needs_path") {
      return { id: nextAction === "cache_model" ? "cache-model" : "diagnose", label: nextAction === "cache_model" ? "Cache model" : "Diagnose", primary: true };
    }
    if (status === "ready") {
      return { id: "continue-to-run", label: "Continue to run", primary: true };
    }
    if (status === "failed_recoverable") {
      if (nextAction === "check_access") return { id: "check-access", label: "Check Hugging Face access", primary: true };
      if (nextAction === "cache_model") return { id: "cache-model", label: "Cache model", primary: true };
      return { id: providerId === "sam3-local" || providerId === "sam2-hf-auto-masks" || providerId === "sam2-local" ? "install" : "diagnose", label: "Retry setup", primary: true };
    }
    if (nextAction === "cache_model") return { id: "cache-model", label: "Cache model", primary: true };
    return { id: "install", label: providerId === "sam3-local" ? "Install scene sweep" : providerId === "sam2-hf-auto-masks" ? "Install SAM2 HF fallback" : "Install runtime", primary: true };
  }

  function modelSetupConfirmationForAction(action, providerId, options = {}) {
    const normalized = String(action || "");
    const provider = providerSettingsById(providerId) || {};
    const hosted = options.hosted ?? provider.locality === "hosted";
    const model = options.model || providerEffectiveModel(provider) || provider.defaultModel || "";
    const labels = {
      "check-access": "Check Hugging Face access",
      test: "Check access",
      "prepare-model": "Prepare local model",
      install: providerId === "sam3-local" ? "Install scene sweep" : providerId === "sam2-hf-auto-masks" ? "Install SAM2 HF fallback" : "Install runtime",
      "cache-model": "Cache model",
      smoke: hosted ? "Run hosted smoke test" : "Run local smoke test",
    };
    const flags = [];
    if (["check-access", "cache-model", "prepare-model", "install"].includes(normalized) || hosted) flags.push("network");
    if (normalized === "cache-model" || normalized === "prepare-model") flags.push("disk");
    if (normalized === "install" || normalized === "prepare-model" || (normalized === "smoke" && !hosted)) flags.push("heavy local runtime");
    if (hosted && normalized === "smoke") flags.push("hosted cost/privacy");
    const copy = {
      "check-access": "This checks Hugging Face access for the selected local model after your confirmation.",
      test: "This checks saved hosted setup fields without sending frames.",
      "prepare-model": "This runs the guided local setup: checks runtime, caches the model when needed, records the path server-side, and runs a bounded smoke test.",
      install: "This runs the allowlisted optional dependency install for the selected local provider.",
      "cache-model": "This resolves or downloads the selected model into the local Hugging Face cache or validates a local model directory.",
      smoke: hosted
        ? "This can contact the hosted provider and may incur cost after your confirmation."
        : "This imports local model runtimes and checks the selected local setup.",
    };
    return {
      action: normalized,
      providerId,
      providerLabel: provider.name || providerId,
      label: labels[normalized] || humanizeReviewCode(normalized),
      message: copy[normalized] || "Confirm this setup action before continuing.",
      model,
      flags,
      settingsPayload: options.settingsPayload && typeof options.settingsPayload === "object" ? { ...options.settingsPayload } : {},
      endpoint: normalized === "smoke" ? providerSmokeTestEndpoint(providerId) : "",
      requiresConfirmation: ["check-access", "test", "install", "prepare-model", "cache-model", "smoke"].includes(normalized),
      hosted: Boolean(hosted),
    };
  }

  function eventRowsMarkup(events, options = {}) {
    return asArray(events)
      .slice()
      .reverse()
      .map((event) => {
        const progress = eventProgress(event);
        const progressText = eventProgressText(event);
        const label = eventLabel(event);
        const timestamp = eventTimestamp(event);
        const message = eventMessage(event);
        const severity = eventSeverity(event);
        const metadataChips = eventMetadataChips(event);
        const suggestedActions = eventSuggestedActions(event);
        const debugMetadata = eventDebugMetadata(event);
        const debugKeys = Object.keys(debugMetadata);
        const progressBar =
          progressText && (typeof progress.overallRatio === "number" || typeof progress.ratio === "number" || typeof progress.percent === "number")
            ? `<div class="event-progress-track" role="progressbar" aria-label="${escapeAttribute(`${label} progress`)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${escapeAttribute(progressText.replace("%", ""))}">
                <span style="--event-progress: ${escapeAttribute(progressText)};"></span>
              </div>`
            : "";
        return `
          <div class="event-row is-${escapeAttribute(severity)} ${options.source === "setup" ? "is-setup-event" : ""}">
            <div class="event-row-main">
              <strong>${escapeHtml(label)}</strong>
              <span class="event-time">${escapeHtml(timestamp)}</span>
              <span class="row-meta">${escapeHtml(message)}</span>
            </div>
            ${metadataChips.length ? `<div class="event-chips">${metadataChips.map((chip) => detailChip(chip)).join("")}</div>` : ""}
            ${progressBar}
            ${suggestedActions.length ? `<ul class="event-actions">${suggestedActions.map((action) => `<li>${escapeHtml(action)}</li>`).join("")}</ul>` : ""}
            ${
              debugKeys.length
                ? `<details class="event-debug">
                    <summary>Debug metadata</summary>
                    <pre>${escapeHtml(JSON.stringify(debugMetadata, null, 2))}</pre>
                  </details>`
                : ""
            }
          </div>
        `;
      })
      .join("");
  }

  function eventLogOverviewMarkup(job, events, errorMessage = "") {
    if (errorMessage) return "";
    const lifecycle = job ? normalizeJobLifecycle({ ...job, events }) : null;
    const latest = asArray(events).slice(-1)[0] || null;
    const severity = latest ? eventSeverity(latest) : lifecycle?.failure ? "bad" : "neutral";
    const progress = lifecycle?.progress || { known: false, percent: 0, label: "No progress reported" };
    const stale = lifecycle?.stale?.stale;
    const action = lifecycle?.failure?.suggestedAction || (stale ? lifecycle.stale.detail : latest ? eventSuggestedActions(latest)[0] : "");
    const provider = lifecycle?.provider?.displayLabel || "";
    return `
      <div class="event-log-overview is-${escapeAttribute(severity)}">
        <div>
          <strong>${escapeHtml(lifecycle ? lifecycle.phase || lifecycle.status : "No run selected")}</strong>
          <span class="row-meta">${escapeHtml(latest ? eventMessage(latest) : "Select or start a run to inspect backend events.")}</span>
        </div>
        <div class="provider-detail">
          ${provider ? detailChip(provider) : ""}
          ${detailChip(progress.known ? `${progress.percent}% complete` : `${progress.percent}% estimated`)}
          ${stale ? detailChip("stale progress") : ""}
        </div>
        ${action ? `<p>${escapeHtml(action)}</p>` : ""}
      </div>
    `;
  }

  function setupJobEventsMarkup(job) {
    const events = asArray(job?.events);
    if (!events.length) return `<div class="empty-state">Setup logs appear here after you run an install, access check, or smoke test.</div>`;
    return eventRowsMarkup(events, { source: "setup" });
  }

  function recommendedConnectionIdForPreset(presetId = state.selectedPreset) {
    if (!goalRequiresModel(presetId)) return "";
    const priority = MODEL_CONNECTION_PRIORITY[presetId] || MODEL_CONNECTION_PRIORITY.trace_one_object;
    const compatible = compatibleModelConnectionsForPreset(presetId);
    const ordered = compatible
      .slice()
      .sort((a, b) => (priority.indexOf(a.id) === -1 ? 99 : priority.indexOf(a.id)) - (priority.indexOf(b.id) === -1 ? 99 : priority.indexOf(b.id)));
    const ready = ordered.find((connection) => connectionReadiness(connection).tone === "ready");
    if (ready) return ready.id;
    const setup = ordered.find((connection) => connectionReadiness(connection).tone !== "bad");
    return (setup || ordered[0] || modelConnectionById("sam2-local")).id;
  }

  function modelConnectorsForSetup(payload = state.modelProviders) {
    const providers = asArray(payload?.providers);
    const order = new Map(MODEL_CONNECTOR_PROVIDER_ORDER.map((id, index) => [id, index]));
    return providers
      .filter((provider) => MODEL_CONNECTOR_PROVIDER_ORDER.includes(provider.id))
      .sort(
        (a, b) =>
          (order.get(a.id) ?? 99) - (order.get(b.id) ?? 99) ||
          String(a.label || a.name || a.id).localeCompare(String(b.label || b.name || b.id)),
      );
  }

  function modelConnectorById(providerId) {
    return modelConnectorsForSetup().find((provider) => provider.id === providerId) || null;
  }

  function modelSetupProviderSummary(provider, settingsProvider = null) {
    if (!provider) {
      return {
        label: "Unavailable",
        status: "unavailable",
        tone: "bad",
        message: "Model provider information has not loaded yet.",
        cost: "not reported",
        privacy: "not reported",
        action: "Refresh",
      };
    }
    const readiness = provider.readiness || {};
    const settingsReadiness = settingsProvider?.readiness || readiness.settingsProvider?.readiness || {};
    const hosted = Boolean(provider.hostedCallsRequired || readiness.hostedCallsRequired || settingsProvider?.locality === "hosted");
    const planned = Boolean(readiness.plannedConnector || provider.implemented === false);
    const configured = Boolean(readiness.configured || settingsReadiness.configured);
    const runnable = readiness.runnable === true;
    const status = readiness.status || settingsReadiness.status || (hosted ? "not_configured" : "ready");
    const cost = provider.estimatedCost?.label || settingsProvider?.cost?.label || (hosted ? "Provider billed" : "Free local");
    const privacy =
      provider.privacy?.summary ||
      settingsProvider?.privacy ||
      (hosted ? "Hosted provider can receive redacted planning context only after confirmation." : "Frames and prompts stay on this machine.");

    if (!hosted) {
      return {
        label: "Mock/local",
        status: "ready",
        tone: "ready",
        message: "Ready now. No API key, hosted call, or model install is required for planning checks.",
        cost,
        privacy,
        action: "Use safely",
      };
    }
    if (/missing|not_configured/.test(String(status))) {
      return {
        label: "Needs setup",
        status,
        tone: "bad",
        message: readiness.message || settingsReadiness.message || "Paste a server-side API key before this hosted planner can be used.",
        cost,
        privacy,
        action: "Add key",
      };
    }
    if (/invalid/.test(String(status))) {
      return {
        label: "Invalid setup",
        status,
        tone: "bad",
        message: readiness.message || settingsReadiness.message || "The saved credential format is invalid. Replace it with a valid key.",
        cost,
        privacy,
        action: "Fix key",
      };
    }
    if (/hosted|confirmation/.test(String(status)) && !readiness.hostedCallsAllowed) {
      return {
        label: "Confirm hosted use",
        status,
        tone: "warn",
        message: readiness.message || settingsReadiness.message || "Hosted calls remain disabled until cost and privacy are confirmed.",
        cost,
        privacy,
        action: "Confirm",
      };
    }
    if (planned || /settings_only|planned/.test(String(status))) {
      return {
        label: "Settings saved",
        status,
        tone: "warn",
        message:
          readiness.message ||
          "Settings are saved, but this hosted planning connector is not enabled for model runs yet. No hosted network call will be made.",
        cost,
        privacy,
        action: "Settings only",
      };
    }
    if (configured && runnable) {
      return {
        label: "Ready",
        status: status || "ready",
        tone: "ready",
        message: readiness.message || "Configured and ready. A hosted run still requires per-run confirmation before network access.",
        cost,
        privacy,
        action: "Test setup",
      };
    }
    return {
      label: "Check setup",
      status,
      tone: "warn",
      message: readiness.message || settingsReadiness.message || "Review settings before using this hosted planner.",
      cost,
      privacy,
      action: "Review",
    };
  }

    function modelSetupPayloadFromValues(providerId, values = {}) {
      const payload = {
        providerId,
        hostedProfileId: String(values.hostedProfileId || "").trim(),
        selectedModel: cleanPublicModelValue(values.selectedModel),
        customModelId: cleanPublicModelValue(values.customModelId),
        baseUrl: String(values.baseUrl || "").trim(),
        endpoint: String(values.endpoint || "").trim(),
        allowHosted: Boolean(values.allowHosted),
        sam2CheckpointPath: String(values.sam2CheckpointPath || "").trim(),
        sam2ModelConfigPath: String(values.sam2ModelConfigPath || "").trim(),
        sam2Device: String(values.sam2Device || "").trim(),
        sam2HfDevice: String(values.sam2HfDevice || "").trim(),
        sam3ModelPath: String(values.sam3ModelPath || "").trim(),
        sam3Device: String(values.sam3Device || "").trim(),
      };
    const apiKey = String(values.apiKey || "").trim();
    if (apiKey) payload.apiKey = apiKey;
    const hfToken = String(values.hfToken || "").trim();
    if (hfToken) payload.hfToken = hfToken;
    for (const optional of ["hostedProfileId", "customModelId", "sam2CheckpointPath", "sam2ModelConfigPath", "sam2Device", "sam2HfDevice", "sam3ModelPath", "sam3Device"]) {
      if (!payload[optional] || payload[optional] === "[LOCAL_PATH_REDACTED]") delete payload[optional];
    }
    if (payload.selectedModel === "[LOCAL_PATH_REDACTED]") delete payload.selectedModel;
    return payload;
  }

  function capabilityWarningLookupsForConfig(config) {
    const preference = config.discovery.config?.providerPreference;
    const discoveryName =
      config.discovery.mode === "sam3_auto_masks"
        ? "sam3-auto-masks"
        : preference === "sam3-hosted" || preference === "sam3-local"
          ? preference
          : config.discovery.mode;
    const lookups = [];
    if (discoveryName) {
      lookups.push({
        name: discoveryName,
        kind: "discovery_provider",
        aliases: [String(config.discovery.mode || "").replaceAll("_", "-")],
      });
    }
    if (config.provider.name && !(config.provider.name === "sam3-local" && config.discovery.mode === "sam3_auto_masks")) {
      const kind = config.provider.name.startsWith("sam3-") ? "discovery_provider" : "mask_provider";
      lookups.push({
        name: config.provider.name,
        kind,
        aliases: kind === "mask_provider" ? [{ name: config.provider.name, kind: "discovery_provider" }] : [],
      });
    }
    return lookups.filter((lookup, index, entries) =>
      entries.findIndex((entry) => entry.name === lookup.name && entry.kind === lookup.kind) === index,
    );
  }

  function capabilityWarningNamesForConfig(config) {
    return capabilityWarningLookupsForConfig(config).map((lookup) => lookup.name);
  }

  function providerForCapabilityWarningLookup(lookup) {
    const provider = providerByName(lookup.name, lookup.kind) || providerByName(lookup.name);
    if (provider) return provider;
    for (const alias of asArray(lookup.aliases)) {
      const aliasName = typeof alias === "string" ? alias : alias?.name;
      const aliasKind = typeof alias === "string" ? lookup.kind : alias?.kind || lookup.kind;
      const matched = providerByName(aliasName, aliasKind) || providerByName(aliasName);
      if (matched) return matched;
    }
    return null;
  }

  function selectedCapabilityWarnings(config, $) {
    const warnings = [];
    const providersForWarnings = capabilityWarningLookupsForConfig(config)
      .map(providerForCapabilityWarningLookup)
      .filter(Boolean)
      .filter((provider, index, providers) => providers.findIndex((item) => item?.name === provider?.name) === index);
    const device = $("#deviceSelect").value;
    const hasPointOrBox = config.prompts.some((prompt) => ["point", "positive_point", "box"].includes(prompt.kind));
    const hasBox = config.prompts.some((prompt) => prompt.kind === "box");

    for (const provider of providersForWarnings) {
      if (!provider.available || provider.runnable === false) {
        const reasons = asArray(provider.reasons).join(" ");
        const setup = provider.available && provider.runnable === false ? "configured but not runnable yet" : provider.status || "unavailable";
        warnings.push(
          `${provider.name}: ${setup}${reasons ? ` - ${reasons}` : ""}`,
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

    if (["sam3-local", "sam3-hosted"].includes(config.provider.name) && config.discovery.mode === "sam3_exemplar" && !hasBox) {
      warnings.push(`${config.provider.name} single-object runs require one box prompt.`);
    }

    if (config.provider.name === "sam2-hosted" && !config.provider.sam2?.hosted_allow_network) {
      warnings.push("sam2-hosted needs hosted cost/privacy confirmation before extraction can send video frames.");
    }

    if (config.provider.name === "sam3-hosted" && !config.provider.sam3?.hosted_allow_network) {
      warnings.push("sam3-hosted needs hosted cost/privacy confirmation before discovery can send sampled frames.");
    }

    if (config.provider.name === "sam3-hosted" && config.discovery.mode === "sam3_auto_masks") {
      const hostedProfile = config.provider.sam3?.hosted_config?.profile || config.discovery.config?.hostedProfile || "";
      if (hostedProfile !== "custom-sam3-compatible") {
        warnings.push("Hosted SAM3 scene sweep requires a custom endpoint that explicitly supports automatic mask generation; Roboflow SAM3 is concept-only.");
      }
    }

    if (state.selectedPreset === "text_detector" && !String(config.discovery.config.text || "").trim()) {
      warnings.push(`${config.discovery.mode === "sam3_concept" ? "sam3-hosted" : "text_detector"} needs at least one text label.`);
    }

    if (
      state.selectedPreset === "class_detector" &&
      config.discovery.config.class_preset === "custom" &&
      !asArray(config.discovery.config.classes).length
    ) {
      warnings.push("class_detector custom mode needs at least one class label.");
    }

    if (config.discovery.mode === "auto_object_proposals" && config.discovery.config.qualityPreset === "trace_everything") {
      if (!config.discovery.config.costWarningAcknowledged) {
        warnings.push("Trace Everything requires explicit cost and noise acknowledgement.");
      } else {
        warnings.push("Trace Everything is expert mode; expect slower, noisier output that is blocked from export until reviewed.");
      }
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
      exportIncluded: track.exportIncluded ?? track.export_included,
      exportable: track.exportable !== false,
      demoMode: track.demoMode === true || track.demo_mode === true,
      providerName: track.providerName || track.provider_name || null,
      trackingProvider: track.trackingProvider || track.tracking_provider || track.discovery?.trackingProvider || track.discovery?.tracking_provider || track.metadata?.trackingProvider || null,
      discovery: track.discovery && typeof track.discovery === "object" ? { ...track.discovery } : {},
      metadata: track.metadata && typeof track.metadata === "object" ? { ...track.metadata } : {},
      rightsSummary: track.rightsSummary || track.rights_summary || null,
      color: track.color || track.colorHex || track.color_hex || TRACK_COLORS[index % TRACK_COLORS.length],
      frames: frames.map((frame) => {
        const polygon = normalizePolygonPoints(frame.polygon || frame.contour || frame.points);
        const width = state.video.width || 1920;
        const height = state.video.height || 1080;
        const rawBox = frame.bbox || frame.box || null;
        const bbox = Array.isArray(rawBox)
          ? { x: rawBox[0], y: rawBox[1], w: rawBox[2], h: rawBox[3] }
          : rawBox && typeof rawBox === "object"
            ? rawBox
            : null;
        return {
          frame: toInteger(frame.frame ?? frame.frameIndex ?? frame.out_index, 0),
          bbox: bbox ? clampBox(bbox, width, height) : polygon ? polygonBounds(polygon, width, height) : null,
          polygon,
          visible: frame.visible !== false,
        };
      }),
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
        source: "demo-only",
        confidence: providerName === "mock" ? 0.92 : 0.72,
        frameCount,
        visibleFrameCount: frameCount,
        frameStart: 0,
        frameEnd: frameCount - 1,
        warnings,
        exportStatus: "review_pending",
        exportable: false,
        demoMode: true,
        providerName,
        color: TRACK_COLORS[index % TRACK_COLORS.length],
        frames,
        reviewSource: "demo-only",
      };
    });
  }

  function buildReviewTracks({ job, config, artifacts, review }) {
    const reviewTracks = asArray(review?.tracks);
    if (reviewTracks.length) {
      const objectsById = new Map(
        asArray(review?.objects)
          .map((object) => [String(object?.objectId || object?.id || ""), object])
          .filter(([id]) => id),
      );
      return reviewTracks.map((track, index) => {
        const normalized = normalizeApiTrack(track, index);
        const object = objectsById.get(normalized.objectId) || {};
        return { ...normalized, rightsSummary: normalized.rightsSummary || object.rightsSummary || null };
      });
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
            source: "demo-only",
            confidence: 0.7,
            frameCount: toInteger(result.scene?.frames ?? result.frames, 1),
            visibleFrameCount: toInteger(result.scene?.frames ?? result.frames, 1),
            frames: [{ frame: 0, bbox: [80 + index * 24, 60 + index * 18, 120, 90], visible: true }],
            warnings: ["result_has_counts_only"],
            exportStatus: "review_pending",
            exportable: false,
            demoMode: true,
          },
          index,
        ),
      );
    }

    return canUseSyntheticTracks ? configReviewTracks(config, job, artifacts) : [];
  }

  function trackFrameForDisplay(track, frameIndex) {
    const frames = asArray(track.frames).filter((frame) => frame.visible !== false && (frame.bbox || asArray(frame.polygon).length >= 3));
    if (!frames.length) return null;
    const sorted = frames.slice().sort((a, b) => toInteger(a.frame, 0) - toInteger(b.frame, 0));
    const first = toInteger(sorted[0].frame, 0);
    const last = toInteger(sorted[sorted.length - 1].frame, first);
    const requested = toInteger(frameIndex, 0);
    if (requested < first || requested > last) return null;
    return sorted.find((frame) => toInteger(frame.frame, 0) === requested) || sorted.reduce((nearest, frame) => {
      if (!nearest) return frame;
      return Math.abs(toInteger(frame.frame, 0) - requested) < Math.abs(toInteger(nearest.frame, 0) - requested) ? frame : nearest;
    }, null);
  }

  function trackCoverageLabel(track) {
    const count = Math.max(1, toInteger(track.frameCount, asArray(track.frames).length || 1));
    const visible = clamp(toInteger(track.visibleFrameCount, count), 0, count);
    return `${track.frameStart ?? 0}-${track.frameEnd ?? Math.max(0, count - 1)} (${Math.round((visible / count) * 100)}%)`;
  }

  function reviewTimelinePayload(review) {
    const timeline = review?.timeline;
    if (!timeline || typeof timeline !== "object") return null;
    return String(timeline.format || "") === "motionjson.review_timeline.v0.1" ? timeline : null;
  }

  function markerFrame(marker) {
    return Math.max(0, toInteger(marker?.frameIndex ?? marker?.frame_index, 0));
  }

  function timelineFrameCount(review, tracks = []) {
    const timeline = reviewTimelinePayload(review);
    const source = review?.source || {};
    const explicit = toInteger(timeline?.frameCount ?? source.frameCount ?? source.frame_count, 0);
    const markerMax = asArray(timeline?.markers).reduce((max, marker) => Math.max(max, markerFrame(marker)), -1);
    const trackMax = asArray(tracks).reduce((max, track) => Math.max(max, toInteger(track.frameEnd, -1)), -1);
    return Math.max(1, explicit || 0, markerMax + 1, trackMax + 1);
  }

  function timelineMarkersForDisplay(review, tracks = [], keyframes = new Set()) {
    const timeline = reviewTimelinePayload(review);
    const parsedKeyframes = parseKeyframes(keyframes);
    const keyframeMax = parsedKeyframes.reduce((max, frameIndex) => Math.max(max, frameIndex), -1);
    const frameCount = Math.max(timelineFrameCount(review, tracks), keyframeMax + 1);
    const apiMarkers = asArray(timeline?.markers).map((marker, index) => ({
      id: String(marker.id || `api-marker-${index}`),
      kind: String(marker.kind || "marker"),
      frameIndex: markerFrame(marker),
      label: String(marker.label || marker.objectId || marker.candidateId || marker.kind || "marker"),
      objectId: marker.objectId || null,
      candidateId: marker.candidateId || null,
      source: marker.source || "api",
      status: marker.status || "",
      apiOwned: true,
    }));
    const localKeyframes = parsedKeyframes.map((frameIndex) => ({
      id: `keyframe:${frameIndex}`,
      kind: "configured_keyframe",
      frameIndex: clamp(frameIndex, 0, Math.max(0, frameCount - 1)),
      label: `keyframe ${frameIndex}`,
      source: "local_config",
      status: "selected",
      apiOwned: false,
    }));
    const markers = [...apiMarkers, ...localKeyframes].sort((a, b) => a.frameIndex - b.frameIndex || a.kind.localeCompare(b.kind));
    const suggestedKeyframes = asArray(timeline?.suggestedKeyframes).map((item) => ({
      frameIndex: clamp(markerFrame(item), 0, Math.max(0, frameCount - 1)),
      reason: String(item.reason || "review_marker"),
      source: String(item.source || "review.timeline"),
    }));
    return {
      frameCount,
      markers,
      suggestedKeyframes,
      markerCountsByKind: timeline?.markerCountsByKind || {},
      hasApiTimeline: Boolean(timeline),
    };
  }

  function correctionRoute(jobId) {
    return `/api/jobs/${encodeURIComponent(jobId)}/corrections`;
  }

  function trackEditRoute(jobId) {
    return `/api/jobs/${encodeURIComponent(jobId)}/track-edits`;
  }

  function trackSelectedRoute(jobId) {
    return `/api/jobs/${encodeURIComponent(jobId)}/track-selected`;
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
      const hasExportEdit = edit.exportIncluded != null;
      if (edit.label) next.label = edit.label;
      if (edit.visible != null) next.visible = edit.visible !== false;
      if (hasExportEdit) next.exportIncluded = edit.exportIncluded !== false;
      if (edit.deleted) next.deleted = true;
      if (edit.mergedInto) next.mergedInto = edit.mergedInto;
      next.warnings = [...asArray(track.warnings)];
      if (next.visible === false && !next.warnings.includes("hidden_by_user")) next.warnings.push("hidden_by_user");
      if (
        next.exportIncluded === false &&
        (hasExportEdit || /deleted|excluded|rejected|failed|fallback_raster/.test(String(next.exportStatus || ""))) &&
        !next.warnings.includes("excluded_from_export")
      ) {
        next.warnings.push("excluded_from_export");
      }
      if (next.deleted && !next.warnings.includes("deleted_by_user")) next.warnings.push("deleted_by_user");
      if (next.mergedInto && !next.warnings.includes(`merged_into_${next.mergedInto}`)) next.warnings.push(`merged_into_${next.mergedInto}`);
      if (edit.repairRequested && !next.warnings.includes("repair_requested")) next.warnings.push("repair_requested");
      if (next.deleted) next.exportStatus = "deleted";
      else if (next.exportIncluded === false && hasExportEdit) next.exportStatus = "excluded";
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
    if (track.exportable === false || track.demoMode === true) return false;
    if (track.deleted || track.exportIncluded === false) return false;
    if (track.exportIncluded === true) return true;
    return !/deleted|excluded|rejected|failed|fallback_raster|review_pending/.test(String(track.exportStatus || ""));
  }

  function trackObjectId(track) {
    return String(track?.objectId || track?.id || "").trim();
  }

  function trackSourceText(track) {
    const values = [
      track?.source,
      track?.providerName,
      track?.trackingProvider,
      track?.reviewSource,
      track?.exportStatus,
      ...asArray(track?.warnings),
      ...asArray(track?.metadata?.warnings),
      track?.discovery?.trackingProvider,
      track?.discovery?.tracking_provider,
      track?.discovery?.reason,
      track?.discovery?.exportStatus,
    ];
    return values.filter(Boolean).join(" ").toLowerCase();
  }

  function trackUsesStaticKeyframeFallback(track) {
    return /keyframe_seed_sequence|static_keyframe|keyframe proposal mask sequence/.test(trackSourceText(track));
  }

  function trackMotionMetrics(track, dimensions = {}) {
    const width = toNumber(dimensions.width, state.video.width || 1920);
    const height = toNumber(dimensions.height, state.video.height || 1080);
    const centers = asArray(track?.frames)
      .filter((frame) => frame?.visible !== false)
      .map((frame) => {
        const polygon = normalizePolygonPoints(frame?.polygon);
        const box = frame?.bbox || (polygon ? polygonBounds(polygon, width, height) : null);
        if (!box) return null;
        return {
          frame: toInteger(frame.frame ?? frame.frameIndex ?? frame.out_index, 0),
          x: toNumber(box.x, 0) + toNumber(box.w, 0) / 2,
          y: toNumber(box.y, 0) + toNumber(box.h, 0) / 2,
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.frame - b.frame);
    let maxCenterShiftPx = 0;
    let pathLengthPx = 0;
    for (let index = 1; index < centers.length; index += 1) {
      const previous = centers[index - 1];
      const current = centers[index];
      const step = Math.hypot(current.x - previous.x, current.y - previous.y);
      pathLengthPx += step;
      const fromStart = Math.hypot(current.x - centers[0].x, current.y - centers[0].y);
      maxCenterShiftPx = Math.max(maxCenterShiftPx, fromStart);
    }
    const thresholdPx = Math.max(2, Math.min(width, height) * 0.004);
    const frameSpan = centers.length ? centers[centers.length - 1].frame - centers[0].frame : 0;
    const moving = centers.length >= 2 && maxCenterShiftPx >= thresholdPx && pathLengthPx >= thresholdPx;
    return {
      moving,
      visibleFrameCount: centers.length,
      maxCenterShiftPx,
      pathLengthPx,
      frameSpan,
      thresholdPx,
    };
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

  function candidateId(candidate) {
    return String(candidate?.candidateId || candidate?.candidate_id || candidate?.id || "").trim();
  }

  function reviewCandidates(review = state.jobReview) {
    return asArray(review?.candidates);
  }

  function candidateRejected(candidate) {
    const status = String(candidate?.reviewStatus || "").toLowerCase();
    return Boolean(candidate?.rejectionReason) || /rejected|ignored|excluded/.test(status);
  }

  function candidateReasonText(candidate) {
    return [candidate?.rejectionReason, candidate?.reviewStatus, ...asArray(candidate?.warnings)]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  }

  function candidateSelectable(candidate) {
    return Boolean(candidateId(candidate)) && !candidateRejected(candidate);
  }

  function candidateDefaultSelected(candidate) {
    return candidateSelectable(candidate) && candidate.defaultSelected !== false;
  }

  function humanizeReviewCode(value) {
    return (
      String(value || "")
        .replace(/[_-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim() || "review"
    );
  }

  function candidateConfidenceScore(candidate) {
    for (const key of ["confidence", "score", "confidenceScore"]) {
      const value = toNumber(candidate?.[key], Number.NaN);
      if (Number.isFinite(value)) return value;
    }
    return null;
  }

  function candidateStatusItems(candidate, { selected = false, exportReady = false } = {}) {
    const reason = candidateReasonText(candidate);
    const rawStatus = String(candidate?.reviewStatus || "").toLowerCase();
    const rejected = candidateRejected(candidate);
    const confidence = candidateConfidenceScore(candidate);
    const statuses = [];
    const add = (key, label, tone) => {
      if (!statuses.some((item) => item.key === key)) statuses.push({ key, label, tone });
    };

    if (selected) add("selected", "Selected", "ready");
    if (rejected) add("rejected", "Rejected", "bad");
    if (/background|whole_frame|wall|floor|too_large/.test(reason)) add("background_like", "Background-like", "warn");
    if (/duplicate|overlap|same object/.test(reason)) add("duplicate", "Duplicate", "warn");
    if ((confidence != null && confidence < 0.45) || /low_confidence|low confidence|uncertain/.test(reason)) {
      add("low_confidence", "Low confidence", "warn");
    }
    if (!rejected && (/needs_review|review_pending|pending/.test(rawStatus) || (!selected && !exportReady))) {
      add("needs_review", "Needs review", "warn");
    }
    if (!rejected && (exportReady || (selected && /reviewed|approved|accepted/.test(rawStatus)))) {
      add("reviewed_for_export", "Reviewed for export", "ready");
    }
    if (!statuses.length) add("candidate", humanizeReviewCode(candidate?.reviewStatus || "candidate"), "neutral");
    return statuses;
  }

  function candidateStatusChip(status) {
    const tone = ["ready", "warn", "bad", "neutral", "muted", "violet"].includes(status?.tone) ? status.tone : "neutral";
    return `<span class="status-chip is-${tone} candidate-status-chip">${escapeHtml(status?.label || "candidate")}</span>`;
  }

  function candidateStatusCounts(candidates, selection = {}) {
    const counts = { selected: 0, rejected: 0, backgroundLike: 0, duplicate: 0, lowConfidence: 0, needsReview: 0, reviewedForExport: 0 };
    for (const candidate of asArray(candidates)) {
      const selected = selection[candidateId(candidate)] === true;
      for (const status of candidateStatusItems(candidate, { selected })) {
        if (status.key === "selected") counts.selected += 1;
        else if (status.key === "rejected") counts.rejected += 1;
        else if (status.key === "background_like") counts.backgroundLike += 1;
        else if (status.key === "duplicate") counts.duplicate += 1;
        else if (status.key === "low_confidence") counts.lowConfidence += 1;
        else if (status.key === "needs_review") counts.needsReview += 1;
        else if (status.key === "reviewed_for_export") counts.reviewedForExport += 1;
      }
    }
    return counts;
  }

  function candidateRetrySuggestions({ candidates = [], visibleCandidates = candidates, summary = {}, filters = {} } = {}) {
    const suggestions = [];
    const add = (key, title, detail, tone = "warn") => {
      if (!suggestions.some((item) => item.key === key)) suggestions.push({ key, title, detail, tone });
    };
    const allCandidates = asArray(candidates);
    const visible = asArray(visibleCandidates);
    const candidateCount = summary?.candidateCount ?? allCandidates.length;
    const reasons = allCandidates.map(candidateReasonText).join(" ");
    const lowConfidence = allCandidates.some((candidate) => {
      const confidence = candidateConfidenceScore(candidate);
      return confidence != null && confidence < 0.45;
    });

    if (!candidateCount) {
      add("maximum_recall", "Try Maximum Recall", "Ask discovery for broader proposals before filtering anything out.");
      add("add_prompt", "Add a prompt", "Place a point or box on the object so the tracker has a stronger starting cue.");
      add("import_masks", "Import masks", "Use prepared masks when automatic discovery cannot see the object.");
    }
    if (visible.length === 0 && allCandidates.length > 0) {
      add("maximum_recall", "Try Maximum Recall", "Relax review filters or rerun with a broader recall preset.");
    }
    if (/background|whole_frame|wall|floor|too_large/.test(reasons)) {
      add("smaller_max_area", "Reduce max area", "Background-like candidates usually mean the largest allowed mask is too broad.");
    }
    if (/duplicate|overlap|same object/.test(reasons)) {
      add("smaller_max_area", "Reduce max area", "Tighter masks and overlap filtering can reduce duplicate candidates.");
    }
    if (lowConfidence || /low_confidence|low confidence|uncertain/.test(reasons)) {
      add("add_prompt", "Add a prompt", "A point, box, or brush prompt can turn a weak candidate into a repairable track.");
    }
    if (filters.movingOnly && visible.length === 0) {
      add("moving_workflow", "Choose moving-object workflow", "CPU motion discovery is better when the thing changes between frames.");
    }
    if (candidateCount > 0 && allCandidates.every(candidateRejected)) {
      add("import_masks", "Import masks", "Prepared masks are safest when every automatic candidate is rejected.");
    }
    return suggestions.slice(0, 4);
  }

  function syncCandidateSelection(candidates) {
    const jobId = state.selectedJobId || "";
    if (state.candidateSelectionJobId !== jobId) {
      state.candidateSelection = {};
      state.candidateSelectionJobId = jobId;
    }
    const ids = new Set(candidates.map(candidateId).filter(Boolean));
    for (const id of Object.keys(state.candidateSelection)) {
      if (!ids.has(id)) delete state.candidateSelection[id];
    }
    for (const candidate of candidates) {
      const id = candidateId(candidate);
      if (id && state.candidateSelection[id] == null) {
        state.candidateSelection[id] = candidateDefaultSelected(candidate);
      }
    }
  }

  function readCandidateFilters() {
    const field = (id) => (typeof document === "undefined" ? null : document.querySelector(`#${id}`));
    return {
      selectedOnly: Boolean(field("candidateFilterSelected")?.checked),
      stableOnly: Boolean(field("candidateFilterStable")?.checked),
      movingOnly: Boolean(field("candidateFilterMoving")?.checked),
      notBackground: field("candidateFilterNotBackground")?.checked !== false,
      notDuplicate: field("candidateFilterNotDuplicate")?.checked !== false,
      minCoverage: toNumber(field("candidateMinCoverage")?.value, 0),
    };
  }

  function filterReviewCandidates(candidates, selection = {}, filters = {}) {
    return asArray(candidates).filter((candidate) => {
      const id = candidateId(candidate);
      const selected = selection[id] === true;
      const reason = candidateReasonText(candidate);
      if (filters.selectedOnly && !selected) return false;
      if (filters.stableOnly && toNumber(candidate.stabilityScore, 0) < 0.8) return false;
      if (filters.movingOnly && toNumber(candidate.motionScore, 0) <= 0.05) return false;
      if (filters.notBackground && /background|whole_frame|wall|floor/.test(reason)) return false;
      if (filters.notDuplicate && /duplicate/.test(reason)) return false;
      if (toNumber(candidate.frameCoverageEstimate, 0) < toNumber(filters.minCoverage, 0)) return false;
      return true;
    });
  }

  function selectedCandidateIds(candidates = reviewCandidates()) {
    syncCandidateSelection(candidates);
    return candidates.filter((candidate) => state.candidateSelection[candidateId(candidate)] === true && candidateSelectable(candidate)).map(candidateId);
  }

  function trackSelectedPayload(candidateIds, { exportReviewRequired = true } = {}) {
    return {
      candidateIds: uniqueIds(candidateIds),
      trackMode: "selected_only",
      exportReviewRequired,
    };
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

  function exportGateSummary({ includedIds = [], excludedIds = [], pendingIds = [], status = null } = {}) {
    const includedCount = asArray(includedIds).length;
    const excludedCount = asArray(excludedIds).length;
    const pendingCount = asArray(pendingIds).length;
    const rows = [
      {
        key: "reviewed_selected_only",
        tone: includedCount ? "ready" : "warn",
        title: includedCount ? `${includedCount} reviewed for export` : "No reviewed exports",
        detail: "Only tracks kept in Review and marked export are included by default.",
      },
    ];
    if (excludedCount) {
      rows.push({
        key: "excluded",
        tone: "warn",
        title: `${excludedCount} not exported`,
        detail: "Rejected, hidden, pending, or unmaterialized tracks stay out of the MotionJSON package.",
      });
    }
    if (pendingCount) {
      rows.push({
        key: "pending_corrections",
        tone: "warn",
        title: "Pending corrections",
        detail: `${pendingCount} track${pendingCount === 1 ? "" : "s"} need materialized assets before export.`,
      });
    }
    if (status) {
      rows.push({
        key: "validation",
        tone: status.ok === true ? "ready" : "bad",
        title: "Validation",
        detail: `${status.issueCount || 0} issue${status.issueCount === 1 ? "" : "s"} across ${status.checked || 0} document${status.checked === 1 ? "" : "s"}.`,
      });
    }
    return rows;
  }

  function exportReadinessSummary({ job = null, includedIds = [], pendingIds = [], reviewTracks = [], status = null } = {}) {
    const lifecycle = job ? normalizeJobLifecycle(job) : null;
    const includedSet = new Set(asArray(includedIds).map(String));
    const reviewedTracks = asArray(reviewTracks).filter((track) => isTrackExportIncluded(track));
    const materializedReviewedTracks = reviewedTracks.filter((track) => {
      const objectId = trackObjectId(track);
      return !includedSet.size || includedSet.has(objectId);
    });
    const staticFallbackTracks = reviewedTracks.filter(trackUsesStaticKeyframeFallback);
    const movingTracks = materializedReviewedTracks.filter((track) => !trackUsesStaticKeyframeFallback(track) && trackMotionMetrics(track).moving);
    const includedCount = asArray(includedIds).length;
    const pendingCount = asArray(pendingIds).length;
    const rows = [];

    if (!lifecycle) {
      rows.push({
        key: "selected_run",
        status: "needs-action",
        title: "Select a completed run",
        detail: "Review and export unlock after extraction produces object tracks.",
      });
      return rows;
    }

    rows.push({
      key: "moving_track_verified",
      status: staticFallbackTracks.length ? "blocked" : movingTracks.length ? "ready" : "needs-action",
      title: movingTracks.length ? "Moving track verified" : staticFallbackTracks.length ? "Static fallback blocked" : "Moving track not verified",
      detail: movingTracks.length
        ? `${movingTracks.length} reviewed track${movingTracks.length === 1 ? "" : "s"} use per-frame motion shown in preview.`
        : staticFallbackTracks.length
          ? "Static keyframe mask sequences stay blocked until tracking is repaired or rerun."
          : "Use Review to confirm the selected object follows frame-by-frame motion.",
    });
    rows.push({
      key: "reviewed_for_export",
      status: includedCount && !pendingCount ? "ready" : includedCount ? "needs-action" : "needs-action",
      title: includedCount ? "Reviewed for export" : "No reviewed export yet",
      detail: includedCount
        ? `${includedCount} materialized track${includedCount === 1 ? "" : "s"} selected for MotionJSON.`
        : "Mark at least one reviewed moving track for export.",
    });
    rows.push({
      key: "motionjson_validation",
      status: status ? (status.ok === true ? "ready" : "blocked") : "needs-action",
      title: status ? (status.ok === true ? "MotionJSON validation passed" : "MotionJSON validation blocked") : "MotionJSON validation needed",
      detail: status
        ? `${status.issueCount || 0} issue${status.issueCount === 1 ? "" : "s"} across ${status.checked || 0} checked document${status.checked === 1 ? "" : "s"}.`
        : "Validate again before writing the MotionJSON package.",
    });
    rows.push({
      key: "static_keyframe_fallback",
      status: staticFallbackTracks.length ? "blocked" : "ready",
      title: staticFallbackTracks.length ? "Static keyframe fallback not exportable" : "Static keyframe fallback not used",
      detail: staticFallbackTracks.length
        ? "The selected export contains a static keyframe sequence; repair tracking before export."
        : "Export will use moving object tracks, not a frozen keyframe mask.",
    });
    return rows;
  }

  function exportReadinessSummaryCards(options = {}) {
    return exportReadinessSummary(options)
      .map((row) =>
        statusCardMarkup(
          {
            status: row.status,
            value: row.title,
            detail: row.detail,
          },
          { className: "status-summary-card export-readiness-card" },
        ),
      )
      .join("");
  }

  function exportActionState({ job = null, includedIds = [], pendingIds = [], trackCount = 0, status = null, staticFallbackCount = 0 } = {}) {
    const lifecycle = job ? normalizeJobLifecycle(job) : null;
    const includedCount = asArray(includedIds).length;
    const pendingCount = asArray(pendingIds).length;
    if (!lifecycle) return { disabled: true, label: "Export MotionJSON", reason: "No completed run is selected." };
    if (lifecycle.active) return { disabled: true, label: "Export MotionJSON", reason: "The selected run is still running." };
    if (lifecycle.status === "failed" || lifecycle.status === "canceled") return { disabled: true, label: "Export MotionJSON", reason: "The selected run failed or was canceled; open logs before export." };
    if (toInteger(trackCount, 0) === 0) return { disabled: true, label: "Export MotionJSON", reason: "Track selected candidates before exporting." };
    if (pendingCount) return { disabled: true, label: "Export MotionJSON", reason: `${pendingCount} reviewed track${pendingCount === 1 ? "" : "s"} need materialized assets before export.` };
    if (!includedCount) return { disabled: true, label: "Export MotionJSON", reason: "Mark at least one reviewed track for export." };
    if (toInteger(staticFallbackCount, 0) > 0) return { disabled: true, label: "Repair tracking first", reason: "Static keyframe fallback tracks cannot be exported as MotionJSON motion." };
    if (status && status.ok !== true) {
      return { disabled: true, label: "Resolve validation first", reason: "Resolve export validation issues before writing MotionJSON." };
    }
    return { disabled: false, label: "Export MotionJSON", reason: "" };
  }

  function assetByKind(assets, kind) {
    return asArray(assets).find((asset) => String(asset?.kind || "") === kind) || null;
  }

  function exportHandoffCards({ job = null, includedIds = [], pendingIds = [], trackCount = 0, assets = [], objectLayerPack = null, status = null, copiedId = "" } = {}) {
    const exportAction = exportActionState({ job, includedIds, pendingIds, trackCount, status });
    const snippets = objectLayerPack?.snippets || {};
    return EXPORT_HANDOFF_DEFS.map((definition) => {
      const asset = assetByKind(assets, definition.kind);
      const url = safeLocalContentUrl(asset?.contentUrl);
      const snippet = definition.snippetKey ? String(snippets[definition.snippetKey] || "") : "";
      const ready = Boolean(url || snippet);
      const action = ready ? (definition.id === "runtime-snippet" || (!url && snippet) ? "copy" : "open") : "export";
      const disabled = ready ? false : exportAction.disabled;
      const copied = action === "copy" && copiedId === definition.id;
      return {
        ...definition,
        ready,
        action,
        disabled,
        copied,
        url,
        copyText: snippet,
        status: copied ? "Copied" : ready ? "Ready" : exportAction.disabled ? "Needs review" : "Ready to create",
        tone: ready ? "ready" : exportAction.disabled ? "warn" : "neutral",
        actionLabel: copied ? "Copied" : ready ? definition.readyAction : definition.pendingAction,
        detail: ready
          ? asset?.metadata?.rel_path || asset?.path || "handoff ready"
          : exportAction.reason || "Creates the reviewed MotionJSON handoff bundle.",
      };
    });
  }

  function exportNextStepText({ exportState = {}, assets = [], objectLayerPack = null } = {}) {
    const includedIds = uniqueIds(exportState.includedObjectIds || objectLayerPack?.selectedObjectIds);
    const scene = assetByKind(assets, "validated_motionjson_scene");
    const website = assetByKind(assets, "website_package");
    const handoff = assetByKind(assets, "motionjson_export_zip");
    const remotion = assetByKind(assets, "remotion_plan");
    const plainJs = objectLayerPack?.snippets?.plainJs || "";
    const lines = [
      `Reviewed objects: ${includedIds.length ? includedIds.join(", ") : "none reported"}`,
      plainJs ? `Runtime snippet:\n${plainJs}` : "",
      website ? "Website package: open website_package.zip and deploy its contents with your site." : "",
      scene ? "MotionJSON scene: use scene_graph.json as the reviewed animation source." : "",
      handoff ? "Developer handoff: share motionjson_export.zip with the scene, manifests, validation, and package artifacts." : "",
      remotion ? "Remotion plan: open remotion_export_plan.json and wire it into your application-owned Remotion project." : "",
    ].filter(Boolean);
    return lines.join("\n\n");
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

  function correctionGuidanceForTrack(track, { promptCount = 0, mergeSelectionSize = 0, status = "" } = {}) {
    if (!track) {
      return {
        title: "Choose a track to correct",
        tone: "muted",
        items: [
          "Open Review, choose a track, then relabel, merge, split, add from prompts, or repair it.",
          "Exports stay disabled until there is a reviewed object track.",
        ],
      };
    }
    const exportIncluded = isTrackExportIncluded(track);
    const items = [];
    if (track.deleted) {
      items.push("This track is deleted and will not export unless you undo or recreate it.");
    } else if (exportIncluded) {
      items.push("This track is currently included in reviewed export output.");
    } else {
      items.push("This track is excluded or still review-gated, so it will not export by default.");
    }
    if (mergeSelectionSize < 2) {
      items.push("To merge duplicates, tick merge on at least two tracks in Review.");
    } else {
      items.push(`${mergeSelectionSize} tracks are selected for merge; the chosen correction target is kept.`);
    }
    if (promptCount === 0) {
      items.push("Draw a point, box, or brush prompt before Add from prompts or Repair with prompts.");
    } else {
      items.push(`${promptCount} prompt${promptCount === 1 ? "" : "s"} ready for add-object or repair actions.`);
    }
    if (/failed|unavailable|route unavailable/i.test(status)) {
      items.push("The correction save route needs attention before edits are durable.");
    }
    return {
      title: track.label || track.objectId || track.id || "Selected track",
      tone: track.deleted ? "bad" : exportIncluded ? "ready" : "warn",
      items,
    };
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
    const lifecycle = job ? normalizeJobLifecycle({ ...job, events }) : null;
    if (lifecycle?.stale?.stale) push("stale_progress", lifecycle.stale.detail, "warn");
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
      if (artifact.kind === "review_state_manifest") {
        push("review_state_manifest", "Saved correction and export decisions are recorded in review_state_manifest.json.", "ready");
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

  function diagnosticNeedsImmediateAttention(diagnostic) {
    const severity = String(diagnostic?.severity || "").toLowerCase();
    if (severity === "bad") return true;
    if (severity !== "warn") return false;
    const text = `${diagnostic?.kind || ""} ${diagnostic?.message || ""}`.toLowerCase();
    return /fallback|raster|vector|unavailable|whole_frame|too_large|failure_diagnostics/.test(text);
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
    let overlayFrame = 0;
    const shell = $(".app-shell");
    const sidebarToggle = $("#sidebarToggle");
    const detailsToggle = $("#detailsToggle");
    const railCloseButton = $("#railCloseButton");
    const workflowRailSteps = new Set(["review_export"]);

    function boolFromStorage(key, fallback) {
      const value = storage.get(key);
      if (value == null) return fallback;
      return value === "true";
    }

    function workflowStepButton(stepId = state.activeWorkflowStep) {
      const normalized = normalizeWorkflowStepId(stepId);
      return (
        [...document.querySelectorAll("[data-workflow-step]")]
          .filter((button) => button.dataset.workflowStep === normalized)
          .sort((a, b) => Number(a.closest("#studioProgressStepper") ? -1 : 1) - Number(b.closest("#studioProgressStepper") ? -1 : 1))[0] || null
      );
    }

    function workflowPanels() {
      return [...document.querySelectorAll("[data-workflow-panel]")];
    }

    function workflowFragments() {
      return [...document.querySelectorAll("[data-workflow-fragment]")];
    }

    function workflowSnapshot() {
      const providerWarning = $("#providerWarning");
      const configStatus = $("#configStatus");
      const project = state.projects.find((item) => item.id === state.selectedProjectId) || null;
      const video = selectedVideo();
      const browserPreview = selectedVideoBrowserPreview(video);
      const enginePlan = guidedEnginePlan(collectFormState($));
      const connection = selectedConnectionForInput({ modelConnectionId: state.selectedModelSetupProviderId, preset: state.selectedPreset });
      const connectionSummary = connection ? connectionReadiness(connection) : { tone: "bad", status: "needs_setup", label: "Setup needed", message: "" };
      const candidates = reviewCandidates();
      const selectedLifecycle = selectedJob() ? normalizeJobLifecycle(selectedJob()) : null;
      const selectedCount = candidates.filter((candidate) => {
        const id = candidateId(candidate);
        return id && state.candidateSelection[id] === true;
      }).length;
      const exportValidation = state.exportValidation?.validation || state.exportResult?.validation || null;
      const exportIncludedCount = state.reviewTracks.filter(isTrackExportIncluded).length;
      return {
        selectedPreset: state.selectedPreset,
        presetLabel: currentPresetLabel(),
        selectedProjectId: state.selectedProjectId,
        projectName: project?.name || "",
        selectedVideoId: state.selectedVideoId,
        videoName: video?.metadata?.filename || video?.filename || video?.path || video?.id || "",
        videoPreviewStatus: browserPreview?.status || "",
        videoPreviewReady: browserPreview?.status === "ready",
        videoPreviewReason: browserPreview?.reason || browserPreview?.errorMessage || "",
        videoPreviewKind: browserPreview?.kind || "",
        previewName: state.video.loadedName,
        providerName: enginePlan.displayLabel || connection?.displayLabel || enginePlan.providerName || "",
        providerDevice: enginePlan.providerId?.startsWith("sam3") ? (state.providerSettings?.providers || []).find((provider) => provider.id === enginePlan.providerId)?.settings?.sam3Device || "" : $("#deviceSelect")?.value || "",
        providerId: enginePlan.providerId || "",
        providerConnectionId: enginePlan.connectionId || "",
        providerEngine: enginePlan.engine || "",
        providerLocality: enginePlan.locality || "",
        providerStatus: connectionSummary.status || "",
        providerSummaryTone: connectionSummary.tone || "",
        providerSummaryLabel: connectionSummary.label || "",
        providerWarning: providerWarning?.textContent?.trim() || "",
        providerTone: providerWarning?.classList.contains("is-bad")
          ? "is-bad"
          : providerWarning?.classList.contains("is-warn")
            ? "is-warn"
            : "",
        providerBlocked: providerWarning?.classList.contains("is-bad") || false,
        configTone: configStatus?.classList.contains("is-bad") ? "is-bad" : configStatus?.classList.contains("is-ready") ? "is-ready" : "",
        configBlocked: configStatus?.classList.contains("is-bad") || false,
        configValid: configStatus?.classList.contains("is-ready") || false,
        backendValidated: state.configValidation?.valid === true,
        selectedJobId: state.selectedJobId,
        selectedJobStatus: selectedLifecycle?.status || selectedJob()?.status || "",
        candidateCount: candidates.length,
        selectedCandidateCount: selectedCount,
        trackCount: state.reviewTracks.length,
        exportIncludedCount,
        correctionCount: asArray(state.correctionState?.history).length,
        exportValidated: Boolean(exportValidation),
        exportOk: exportValidation?.ok === true,
        promptCount: state.prompts.length,
        strokeCount: state.strokes.length,
        hasBoxPrompt: state.prompts.some((prompt) => prompt.kind === "box"),
        hasPointPrompt: state.prompts.some((prompt) => ["point", "positive_point"].includes(prompt.kind)),
      };
    }

    function renderWorkflowStepSummary(snapshot, activeStep) {
      const container = $("#workflowStepSummary");
      if (!container) return;
      const cards = workflowSummaryCardsFromSnapshot(snapshot, activeStep);
      container.innerHTML = cards.length
        ? cards.map((card) => statusCardMarkup(card, { className: "step-summary-card", includeLabel: true, defaultStatus: "not-started" })).join("")
        : "";
    }

    function renderWorkflowContextCopy(activeStep) {
      const screenId = workflowScreenForStep(activeStep);
      const setupCopy = {
        title:
          activeStep === "choose_goal"
            ? "Choose your goal"
            : state.selectedPreset === "review_existing"
              ? "Open an existing result"
              : "Import video and project settings",
        note:
          activeStep === "choose_goal"
            ? "Pick a goal-first workflow. Continue changes this workspace to the next step."
            : state.selectedPreset === "review_existing"
            ? "Open a local MotionJSON result for review. Guided mode creates the local workspace automatically."
            : "Register the local video path. MotionJSON prepares a browser-safe preview automatically before you continue.",
      };
      const enginePlan = guidedEnginePlan(collectFormState($));
      const wizardCopy =
        screenId === "prepare"
          ? state.selectedPreset === "trace_one_object"
            ? {
                title: /^sam3-/.test(String(enginePlan.providerName || "")) ? "Trace the object" : "Trace the object",
                note: /^sam3-/.test(String(enginePlan.providerName || ""))
                  ? "SAM3 single-object tracing uses one box prompt in the viewer before the run starts."
                  : "Name the object, then draw a point or box prompt in the viewer.",
              }
            : state.selectedPreset === "trace_all_objects"
              ? {
                  title: "Prepare object discovery",
                  note: "Choose the discovery quality and review plan before running mask proposals.",
                }
              : state.selectedPreset === "text_detector"
                ? {
                    title: "Describe what to find",
                    note: "Use one short text prompt. The model will propose matching objects before review.",
                  }
                : {
                    title: "Prepare the run",
                    note: "Only the controls that matter for this workflow stay visible here.",
                  }
          : screenId === "run"
            ? {
                title: "Run monitor",
                note: "Watch progress and logs here. Failed runs keep recovery actions visible.",
              }
          : {
              title: goalRequiresModel(state.selectedPreset) ? "Choose and install models" : "No model is needed",
              note: goalRequiresModel(state.selectedPreset)
                ? "Choose one compatible SAM engine for this workflow. Install, access checks, smoke tests, API keys, and local paths stay inside this flow."
                : "This workflow runs without SAM model setup.",
            };
      const configCopy = {
        title: "Advanced run plan",
        note: "Raw config, validation, and save/load controls stay available in Advanced when you need the full technical view.",
      };
      const copyTargets = [
        ["#setupPanelTitle", setupCopy.title],
        ["#setupPanelNote", setupCopy.note],
        ["#wizardPanelTitle", wizardCopy.title],
        ["#wizardPanelNote", wizardCopy.note],
        ["#configPanelTitle", configCopy.title],
        ["#configPanelNote", configCopy.note],
      ];
      for (const [selector, text] of copyTargets) {
        const element = $(selector);
        if (element) element.textContent = text;
      }
      const debugButton = $("#startMockRunButton");
      if (debugButton) debugButton.hidden = !state.health?.mockMode;
    }

    function postRunSnapshot() {
      const candidates = reviewCandidates();
      const selectedLifecycle = selectedJob() ? normalizeJobLifecycle(selectedJob()) : null;
      const selectedCandidateCount = candidates.filter((candidate) => {
        const id = candidateId(candidate);
        return id && state.candidateSelection[id] === true;
      }).length;
      const exportValidation = state.exportValidation?.validation || state.exportResult?.validation || null;
      const diagnostics = collectDiagnostics(selectedJob(), state.jobEvents, state.jobArtifacts, state.reviewTracks, state.jobReview).filter(
        (item) => item.severity !== "ready",
      );
      const attentionDiagnostics = diagnostics.filter(diagnosticNeedsImmediateAttention);
      return {
        activeJobs: state.jobs.filter(isActiveJob).length,
        hasSelectedJob: Boolean(state.selectedJobId),
        selectedJobStatus: selectedLifecycle?.status || selectedJob()?.status || "",
        hasStaleProgress: Boolean(selectedLifecycle?.stale?.stale),
        staleProgressDetail: selectedLifecycle?.stale?.detail || "",
        candidateCount: candidates.length,
        selectedCandidateCount,
        trackCount: state.reviewTracks.length,
        exportIncludedCount: state.reviewTracks.filter(isTrackExportIncluded).length,
        correctionCount: asArray(state.correctionState?.history).length,
        exportValidated: Boolean(exportValidation),
        exportOk: exportValidation?.ok === true,
        diagnosticCount: diagnostics.length,
        attentionDiagnosticCount: attentionDiagnostics.length,
        hasAttentionDiagnostics: Boolean(attentionDiagnostics.length),
        hasFailure: diagnostics.some((item) => item.severity === "bad"),
      };
    }

    function postRunStageCards(stages) {
      return stages.map((stage) => statusCardMarkup(stage, { className: "post-run-stage", includeLabel: true })).join("");
    }

    function summaryCards(stages) {
      return stages.map((stage) => statusCardMarkup(stage)).join("");
    }

    function renderPostRunFlow() {
      const snapshot = postRunSnapshot();
      const reviewFlow = reviewFlowStateFromSnapshot({ ...snapshot, job: selectedJob() });
      const stages = reviewFlow.stages;
      const blocking = stages.find((stage) => stage.status === "blocked");
      const next = blocking || stages.find((stage) => stage.status === "needs-action") || stages.find((stage) => stage.status === "running") || stages[stages.length - 1];
      const runStage = runMonitorStageFromSnapshot(snapshot);
      const candidateStage = stages.find((stage) => stage.id === "candidates");
      const trackSelectedStage = stages.find((stage) => stage.id === "track_selected");
      const trackStage = stages.find((stage) => stage.id === "tracks");
      const correctionStage = stages.find((stage) => stage.id === "corrections");
      const exportStage = stages.find((stage) => stage.id === "export");

      if ($("#postRunGuideList")) $("#postRunGuideList").innerHTML = postRunStageCards(stages);
      if ($("#postRunGuideStatus")) {
        $("#postRunGuideStatus").textContent = reviewFlow.gate.primaryLabel || (next?.status === "done" ? "Ready" : next?.value || "Needs review");
        $("#postRunGuideStatus").className = `status-chip ${next?.tone || "is-muted"}`;
      }
      if ($("#postRunGuideNote")) $("#postRunGuideNote").textContent = reviewFlow.gate.reason || next?.detail || "Review, correct, and export reviewed object tracks.";
      const runSummaryMarkup = summaryCards([runStage].filter(Boolean));
      if ($("#runMonitorSummary")) $("#runMonitorSummary").innerHTML = runSummaryMarkup;
      if ($("#mainRunMonitorSummary")) $("#mainRunMonitorSummary").innerHTML = runSummaryMarkup;
      if ($("#runMonitorStatus") && runStage) {
        $("#runMonitorStatus").textContent = runStage.value;
        $("#runMonitorStatus").className = `status-chip ${runStage.tone}`;
      }
      if ($("#mainRunStatus") && runStage && !selectedJob()) {
        $("#mainRunStatus").textContent = runStage.value;
        $("#mainRunStatus").className = `status-chip ${runStage.tone}`;
      }
      if ($("#reviewStatusSummary")) $("#reviewStatusSummary").innerHTML = summaryCards([candidateStage, trackSelectedStage, trackStage].filter(Boolean));
      if ($("#reviewFlowStatus") && trackStage) {
        $("#reviewFlowStatus").textContent = trackStage.value;
        $("#reviewFlowStatus").className = `status-chip ${trackStage.tone}`;
      }
      if ($("#correctionStatusSummary")) $("#correctionStatusSummary").innerHTML = summaryCards([correctionStage].filter(Boolean));
      if ($("#exportStatusSummary")) {
        const job = selectedJob();
        const exported = state.exportResult?.jobId === state.selectedJobId ? state.exportResult : null;
        const validation = state.exportValidation?.jobId === state.selectedJobId ? state.exportValidation : null;
        const exportState = exported || validation || {};
        const status = exported?.validation || validation?.validation || null;
        const { includedIds, pendingIds } = buildExportPanelSummary({
          exportState,
          reviewExport: state.jobReview?.export,
          reviewTracks: state.reviewTracks,
          reviewObjects: state.jobReview?.objects,
        });
        $("#exportStatusSummary").innerHTML = exportReadinessSummaryCards({
          job,
          includedIds,
          pendingIds,
          reviewTracks: state.reviewTracks,
          status,
        }) || summaryCards([exportStage].filter(Boolean));
      }
      if (snapshot.hasFailure && $("#runLogsDisclosure")) $("#runLogsDisclosure").open = true;
      if (snapshot.hasAttentionDiagnostics && $("#fallbackDiagnosticsDisclosure")) $("#fallbackDiagnosticsDisclosure").open = true;
    }

    function setRunAlert(message, className = "warning-box", { html = false } = {}) {
      for (const selector of ["#providerWarning", "#runPlanAlert"]) {
        const element = $(selector);
        if (!element) continue;
        element.hidden = !message;
        if (html) element.innerHTML = message || "";
        else element.textContent = message || "";
        element.className = className;
      }
      renderShellIndicators();
      renderWorkflowStepper();
    }

    function setElementWorkflowHidden(element, hidden) {
      element.classList.toggle("is-workflow-hidden", hidden);
      element.hidden = hidden;
      element.setAttribute("aria-hidden", String(hidden));
      if ("inert" in element) element.inert = hidden;
      if (hidden && element.contains(document.activeElement)) {
        workflowStepButton()?.focus();
      }
    }

    function panelMatchesWorkflowStep(element, stepId) {
      const steps = String(element.dataset.workflowPanel || "")
        .split(/\s+/)
        .filter(Boolean);
      const aliases = WORKFLOW_PANEL_STEP_ALIASES[stepId] || [stepId];
      return aliases.some((alias) => steps.includes(alias));
    }

    function fragmentMatchesWorkflowStep(element, stepId) {
      const steps = String(element.dataset.workflowFragment || "")
        .split(/\s+/)
        .filter(Boolean);
      const aliases = WORKFLOW_FRAGMENT_STEP_ALIASES[stepId] || [stepId];
      return aliases.some((alias) => steps.includes(alias));
    }

    function syncWorkflowPanels() {
      const activeStep = normalizeWorkflowStepId(state.activeWorkflowStep);
      const showAll = Boolean(state.workflowDashboard);
      const visibleStepIds = [activeStep];
      const postRun = postRunSnapshot();
      const showFailureDetails = !showAll && activeStep === "review_export" && (postRun.hasFailure || postRun.hasAttentionDiagnostics);
      const showReviewDetails = !showAll && activeStep === "review_export" && (showFailureDetails || (postRun.candidateCount > 0 && postRun.trackCount === 0));
      shell?.classList.toggle("is-workflow-dashboard", showAll);
      if (shell) {
        for (const className of Array.from(shell.classList)) {
          if (className.startsWith("is-workflow-step-")) shell.classList.remove(className);
        }
        shell.classList.add(`is-workflow-step-${activeStep.replace(/_/g, "-")}`);
      }
      for (const panel of workflowPanels()) {
        const railDetail = panel.matches("details.rail-section");
        const matchesVisibleStep = visibleStepIds.some((stepId) => panelMatchesWorkflowStep(panel, stepId));
        const hiddenInSimpleMode =
          !showAll &&
          (
            ["studioBottomCta", "runPlanAlert", "modelPlanPanel"].includes(panel.id) ||
            (panel.id === "mainJobCenter" && activeStep !== "run_monitor" && !state.selectedJobId) ||
            (panel.id === "modelSetupPanel" && !goalRequiresModel(state.selectedPreset))
          );
        const visible = !hiddenInSimpleMode && (showAll || ((!railDetail || showReviewDetails) && matchesVisibleStep));
        setElementWorkflowHidden(panel, !visible);
        if (visible && panel.matches("details.rail-section") && !showAll) {
          panel.open = true;
        }
      }
      for (const fragment of workflowFragments()) {
        setElementWorkflowHidden(fragment, !(showAll || visibleStepIds.some((stepId) => fragmentMatchesWorkflowStep(fragment, stepId))));
      }
      if (showAll) {
        setRailCollapsed(false, { persist: false });
      } else if (showReviewDetails) {
        setRailCollapsed(false, { persist: false });
      } else if (!shell?.classList.contains("is-rail-collapsed")) {
        setRailCollapsed(true, { persist: false });
      }
      scheduleDrawOverlay();
    }

    function renderWorkflowStepper() {
      const activeStep = normalizeWorkflowStepId(state.activeWorkflowStep);
      const snapshot = workflowSnapshot();
      const readiness = workflowReadinessFromSnapshot(snapshot);
      const screenId = workflowScreenForStep(activeStep);
      const activeStepIndex = workflowStepIndex(activeStep);
      const screenContract = screenContractFromSnapshot(snapshot, activeStep);
      const stepContract = workflowStepContractFromSnapshot(snapshot, activeStep);
      const activeStepDef = WORKFLOW_STEPS.find((step) => step.id === activeStep) || WORKFLOW_STEPS[0];
      const activeStepReadiness = readiness[activeStep] || {};
      const contract = {
        title: activeStepDef.title,
        description: activeStepDef.description,
        statusLabel: activeStepReadiness.complete ? "Ready" : screenContract.statusLabel,
        statusTone: activeStepReadiness.complete ? "is-ready" : screenContract.statusTone,
        primaryLabel: stepContract.primaryLabel,
        primaryAction: stepContract.primaryAction,
        enabled: stepContract.enabled,
        blockedReason: stepContract.blockedReason,
        backTarget: stepContract.backTarget,
      };
      const title = $("#workflowTitle");
      const description = $("#workflowDescription");
      const status = $("#workflowStatus");
      const footerHint = $("#workflowFooterHint");
      const footerReason = $("#workflowFooterReason");
      const backButton = $("#workflowBackButton");
      const primaryButton = $("#workflowPrimaryButton");
      const dashboardToggle = $("#workflowDashboardToggle");
      const setupComplete = Boolean(readiness.source_video?.complete) && (!goalRequiresModel(snapshot.selectedPreset || state.selectedPreset) || Boolean(readiness.provider_settings?.complete));
      const prepareComplete = screenId === "review" || Boolean(snapshot.selectedJobId || snapshot.candidateCount || snapshot.trackCount);
      const reviewComplete = Boolean(snapshot.exportOk);

      if (title) title.textContent = contract.title;
      if (description) description.textContent = contract.description;
      if (status) {
        status.textContent = contract.statusLabel;
        status.className = `status-chip ${contract.statusTone || "is-muted"}`;
      }
      if (footerHint) footerHint.textContent = contract.blockedReason || contract.description;
      if (footerReason) {
        footerReason.hidden = contract.enabled;
        footerReason.textContent = contract.enabled ? "" : contract.blockedReason || "";
      }
      if (backButton) backButton.disabled = !contract.backTarget;
      if (primaryButton) {
        primaryButton.disabled = !contract.enabled;
        primaryButton.textContent = contract.primaryLabel;
      }
      if (dashboardToggle) {
        dashboardToggle.textContent = state.workflowDashboard ? "Hide all panels" : "Show all panels";
        dashboardToggle.setAttribute("aria-pressed", String(Boolean(state.workflowDashboard)));
      }

      document.querySelectorAll("#workflowStepper [data-workflow-step]").forEach((button) => {
        const stepId = normalizeWorkflowStepId(button.dataset.workflowStep);
        const stepReadiness = readiness[stepId] || {};
        const active = stepId === activeStep;
        const stepComplete = Boolean(stepReadiness.complete) && workflowStepIndex(stepId) < activeStepIndex;
        button.classList.toggle("is-active", active);
        button.classList.toggle("is-complete", stepComplete);
        button.classList.toggle("is-blocked", stepReadiness.status === "blocked");
        button.classList.toggle("is-pending", !stepComplete && !active);
        button.setAttribute("aria-pressed", String(active));
        if (active) button.setAttribute("aria-current", "step");
        else button.removeAttribute("aria-current");
        if ("disabled" in button) button.disabled = false;
        button.setAttribute("title", stepReadiness.message || "");
        button.dataset.workflowStatus = stepReadiness.status || "";
      });

      document.querySelectorAll("#studioProgressStepper [data-workflow-screen]").forEach((button) => {
        const item = button.closest("[data-studio-step]");
        const targetScreen = button.dataset.workflowScreen || "setup";
        const active = targetScreen === screenId;
        const complete = targetScreen === "setup" ? setupComplete && !active : targetScreen === "prepare" ? prepareComplete && !active : reviewComplete && !active;
        const allowed =
          targetScreen === "setup" ||
          (targetScreen === "prepare" && (setupComplete || screenId !== "setup")) ||
          (targetScreen === "review" && (prepareComplete || screenId === "review"));
        button.disabled = !allowed;
        button.setAttribute("aria-pressed", String(active));
        if (active) button.setAttribute("aria-current", "step");
        else button.removeAttribute("aria-current");
        if (item) {
          item.classList.toggle("is-active", active);
          item.classList.toggle("is-complete", complete);
          item.classList.toggle("is-pending", !active && !complete);
        }
      });

      renderWorkflowContextCopy(activeStep);
      renderWorkflowStepSummary(snapshot, activeStep);
      renderPostRunFlow();
      syncWorkflowPanels();
      renderStudioShell(activeStep);
    }

    function reconcileWorkflowProgress({ persist = true } = {}) {
      const snapshot = workflowSnapshot();
      const restoredStep = workflowRestoredStepFromSnapshot(snapshot, state.activeWorkflowStep);
      const hasWorkspaceState = Boolean(snapshot.selectedProjectId || snapshot.selectedVideoId || snapshot.selectedJobId);
      let changed = false;
      if (restoredStep !== state.activeWorkflowStep) {
        state.activeWorkflowStep = restoredStep;
        changed = true;
      }
      if (!hasWorkspaceState && state.workflowDashboard) {
        state.workflowDashboard = false;
        changed = true;
      }
      if (changed && persist) {
        storage.set(SHELL_STORAGE_KEYS.workflowStep, state.activeWorkflowStep);
        storage.set(SHELL_STORAGE_KEYS.workflowDashboard, String(state.workflowDashboard));
      }
      return changed;
    }

    function setWorkflowStep(stepId, { persist = true, focusStep = false } = {}) {
      const nextStep = normalizeWorkflowStepId(stepId, state.activeWorkflowStep);
      if (nextStep !== state.activeWorkflowStep) state.railOpenedByUser = false;
      state.activeWorkflowStep = nextStep;
      if (persist) storage.set(SHELL_STORAGE_KEYS.workflowStep, state.activeWorkflowStep);
      renderWorkflowStepper();
      if (focusStep) {
        const focusActiveStep = () => workflowStepButton(state.activeWorkflowStep)?.focus();
        focusActiveStep();
        window.requestAnimationFrame(focusActiveStep);
        window.setTimeout(focusActiveStep, 0);
        window.setTimeout(focusActiveStep, 50);
        window.setTimeout(focusActiveStep, 150);
      }
    }

    function setWorkflowDashboard(enabled, { persist = true } = {}) {
      state.workflowDashboard = Boolean(enabled);
      if (persist) storage.set(SHELL_STORAGE_KEYS.workflowDashboard, String(state.workflowDashboard));
      renderWorkflowStepper();
    }

    function nextGuidedStepAfterVideo() {
      return goalRequiresModel(state.selectedPreset) ? "provider_settings" : "prompt_preview";
    }

    function maybeAdvanceWorkflowAfterResultLoad() {
      if (state.workflowDashboard) return;
      const status = String(selectedJob()?.status || "").toLowerCase();
      if (state.selectedPreset === "review_existing" && state.selectedJobId) {
        if (state.activeWorkflowStep === "source_video") setWorkflowStep("review_export", { focusStep: true });
        return;
      }
      if (state.activeWorkflowStep === "prompt_preview" && (status || state.selectedJobId)) {
        setWorkflowStep("run_monitor", { focusStep: true });
      }
    }

    async function saveSelectedModelSetupAndContinue() {
      const connection = modelConnectionById(state.selectedModelSetupProviderId);
      const form = $("#modelSetupForm");
      if (!connection || !form) throw new Error("Choose a compatible model connection before continuing.");
      const providerId = form.dataset.providerSettingsId || connection.providerId;
      const payload = modelSetupPayloadFromForm(form);
      const response = await api("/api/provider-settings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.providerSettings = response;
      form.querySelectorAll("[data-model-setup-field='apiKey']").forEach((input) => {
        input.value = "";
      });
      const diagnosis = await api(`/api/provider-settings/${encodeURIComponent(providerId)}/diagnose`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const ready = diagnosis.ready === true || diagnosis.status === "ready" || diagnosis.status === "configured";
      const missing = asArray(diagnosis.checklist).filter((item) => !item.ok).map((item) => item.label).join(", ");
      const message = diagnosis.message || (ready ? "Model connection is ready." : `Needs setup: ${missing || "review the connection form"}`);
      setModelSetupMessage(message, ready ? "ready" : "warn");
      await refreshAll();
      setModelSetupMessage(message, ready ? "ready" : "warn");
      if (ready) setWorkflowStep("prompt_preview", { focusStep: true });
      return ready;
    }

    async function validateAndStartGuidedRun() {
      const formState = collectFormState($);
      let config;
      try {
        config = buildRunConfig(formState);
      } catch (error) {
        $("#configStatus").textContent = "Invalid";
        $("#configStatus").className = "status-chip is-bad";
        $("#configPreview").textContent = error.message;
        renderRunPlanError(error.message);
        setRunAlert(error.message, "warning-box is-bad");
        renderWorkflowStepper();
        return false;
      }

      $("#configStatus").textContent = "Validating";
      $("#configStatus").className = "status-chip is-neutral";
      renderWorkflowStepper();
      let validation;
      try {
        validation = await api("/api/run-config/validate", {
          method: "POST",
          body: JSON.stringify({ runConfig: config }),
        });
        renderBackendValidation(validation);
      } catch (error) {
        $("#configStatus").textContent = "Validation failed";
        $("#configStatus").className = "status-chip is-bad";
        setRunAlert(error.message, "warning-box is-bad");
        renderWorkflowStepper();
        return false;
      }

      if (validation?.valid !== true) {
        setRunAlert("Fix the guided run setup before starting extraction.", "warning-box is-bad");
        renderWorkflowStepper();
        return false;
      }

      await startRunFromConfig({ forceMock: false });
      setWorkflowStep("run_monitor", { focusStep: true });
      renderWorkflowStepper();
      return true;
    }

    async function exportReviewedObjectsFromGuidedFlow() {
      await exportSelectedMotionJson();
      renderWorkflowStepper();
    }

    function focusReviewDetail(target = "candidates") {
      setRailCollapsed(false, { persist: false });
      const reviewDetails = [...document.querySelectorAll("details.rail-section")].find((details) =>
        /review candidates and tracks/i.test(details.querySelector("summary")?.textContent || ""),
      );
      if (reviewDetails) reviewDetails.open = true;
      const selector = target === "tracks" ? "#trackList" : target === "diagnostics" ? "#fallbackDiagnosticsDisclosure" : "#candidateSummaryList";
      const element = $(selector);
      if (element?.tagName === "DETAILS") element.open = true;
      (element?.querySelector?.("button, input, [tabindex]") || element)?.focus?.({ preventScroll: false });
    }

    async function openRunLogsAndDiagnostics() {
      setRailCollapsed(false, { persist: false });
      const logs = $("#runLogsDisclosure");
      if (logs) logs.open = true;
      const mainLogs = $("#mainRunLogsDisclosure");
      if (mainLogs) mainLogs.open = true;
      const diagnostics = $("#fallbackDiagnosticsDisclosure");
      if (diagnostics) diagnostics.open = true;
      if (state.selectedJobId) {
        try {
          await refreshSelectedJobReview();
        } catch (error) {
          state.errors.selectedJob = error.message;
          renderEventLog();
        }
      } else {
        renderEventLog();
      }
      if (logs) logs.open = true;
      if (mainLogs) mainLogs.open = true;
      if (diagnostics) diagnostics.open = true;
      mainLogs?.scrollIntoView?.({ behavior: "smooth", block: "start" });
      (mainLogs?.querySelector?.("summary") || logs?.querySelector?.("summary") || diagnostics?.querySelector?.("summary"))?.focus?.({ preventScroll: false });
    }

    function clearSelectedTerminalJobForRetry() {
      const current = selectedJob();
      const status = current?.status || "";
      if (!current || isActiveJobStatus(status)) return false;
      state.selectedJobId = "";
      state.selectedJob = null;
      state.jobReview = null;
      state.jobEvents = [];
      state.jobArtifacts = [];
      state.reviewTracks = [];
      state.candidateTrackingStatus = "";
      state.exportValidation = null;
      state.exportResult = null;
      state.correctionState = emptyCorrectionState();
      renderJobs();
      renderJobReview();
      return true;
    }

    function prepareNewGuidedRun(targetStep = "prompt_preview") {
      clearSelectedTerminalJobForRetry();
      setWorkflowStep(targetStep, { focusStep: true });
      renderWorkflowStepper();
    }

    async function runAgainFromTerminalJob() {
      clearSelectedTerminalJobForRetry();
      setWorkflowStep("prompt_preview", { focusStep: true });
      await validateAndStartGuidedRun();
    }

    async function performWorkflowPrimaryAction() {
      const snapshot = workflowSnapshot();
      const contract = workflowStepContractFromSnapshot(snapshot, state.activeWorkflowStep);
      if (!contract.enabled) return;
      try {
        if (contract.primaryAction === "continue_to_video") {
          setWorkflowStep("source_video", { focusStep: true });
        } else if (contract.primaryAction === "add_video") {
          $("#videoForm")?.requestSubmit();
        } else if (contract.primaryAction === "retry_preview") {
          await retrySelectedVideoPreview();
        } else if (contract.primaryAction === "continue_after_video") {
          setWorkflowStep(contract.successAdvanceTo, { focusStep: true });
        } else if (contract.primaryAction === "continue_to_prepare") {
          setWorkflowStep("prompt_preview", { focusStep: true });
        } else if (contract.primaryAction === "open_result") {
          $("#importMotionJsonForm")?.requestSubmit();
        } else if (contract.primaryAction === "continue_to_review") {
          setWorkflowStep("review_export", { focusStep: true });
        } else if (contract.primaryAction === "save_model_setup") {
          await saveSelectedModelSetupAndContinue();
        } else if (contract.primaryAction === "run_model_setup_action") {
          const action = contract.modelSetupAction || "diagnose";
          const setupButton = [...document.querySelectorAll("#modelSetupPanel [data-model-setup-action]")]
            .find((item) => item.dataset.modelSetupAction === action);
          if (!setupButton) throw new Error("Model setup action is not available for the selected provider.");
          setupButton.click();
        } else if (contract.primaryAction === "run_prepared_workflow") {
          await validateAndStartGuidedRun();
        } else if (contract.primaryAction === "cancel_run") {
          await cancelSelectedJob();
        } else if (contract.primaryAction === "open_logs") {
          openRunLogsAndDiagnostics();
        } else if (contract.primaryAction === "prepare_new_run") {
          prepareNewGuidedRun("prompt_preview");
        } else if (contract.primaryAction === "select_candidates") {
          focusReviewDetail("candidates");
        } else if (contract.primaryAction === "track_selected") {
          await trackSelectedCandidatesWithApi();
        } else if (contract.primaryAction === "mark_reviewed") {
          await markReviewedTracksForExport();
        } else if (contract.primaryAction === "inspect_diagnostics") {
          focusReviewDetail("diagnostics");
        } else if (contract.primaryAction === "export_reviewed") {
          await exportReviewedObjectsFromGuidedFlow();
        }
      } catch (error) {
        setRunAlert(error.message, "warning-box is-bad");
        renderWorkflowStepper();
      }
    }

    function initWorkflowController() {
      state.activeWorkflowStep = normalizeWorkflowStepId(storage.get(SHELL_STORAGE_KEYS.workflowStep), "choose_goal");
      state.workflowDashboard = boolFromStorage(SHELL_STORAGE_KEYS.workflowDashboard, false);
      reconcileWorkflowProgress({ persist: false });
      const workflowKeyboardKeys = new Set(["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"]);
      let pendingWorkflowKeyboardFocus = "";
      const focusWorkflowKeyboardStep = () => {
        if (!pendingWorkflowKeyboardFocus) return;
        workflowStepButton(pendingWorkflowKeyboardFocus)?.focus();
      };
      document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-workflow-step]");
        if (!button) return;
        if (button.disabled) return;
        setWorkflowStep(button.dataset.workflowStep, { focusStep: true });
      });
      document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-workflow-screen]");
        if (!button) return;
        if (button.disabled) return;
        const screenId = button.dataset.workflowScreen || "setup";
        setWorkflowStep(workflowStepForScreen(screenId), { focusStep: true });
      });
      document.addEventListener("keydown", (event) => {
        const button = event.target.closest("[data-workflow-step]");
        if (!button) return;
        const buttons = [...document.querySelectorAll("#studioProgressStepper [data-workflow-step]")];
        const index = buttons.indexOf(button);
        const keyTargets = {
          ArrowRight: index + 1,
          ArrowDown: index + 1,
          ArrowLeft: index - 1,
          ArrowUp: index - 1,
          Home: 0,
          End: buttons.length - 1,
        };
        if (!(event.key in keyTargets)) return;
        event.preventDefault();
        const nextButton = buttons[clamp(keyTargets[event.key], 0, buttons.length - 1)];
        if (nextButton) {
          pendingWorkflowKeyboardFocus = nextButton.dataset.workflowStep || "";
          setWorkflowStep(pendingWorkflowKeyboardFocus, { focusStep: false });
          window.requestAnimationFrame(() => focusWorkflowKeyboardStep());
          window.setTimeout(() => focusWorkflowKeyboardStep(), 80);
          window.setTimeout(() => focusWorkflowKeyboardStep(), 300);
        }
      });
      document.addEventListener("keyup", (event) => {
        if (!workflowKeyboardKeys.has(event.key)) return;
        window.requestAnimationFrame(() => focusWorkflowKeyboardStep());
      });
      $("#workflowBackButton")?.addEventListener("click", () => {
        const contract = workflowStepContractFromSnapshot(workflowSnapshot(), state.activeWorkflowStep);
        if (contract.backTarget) setWorkflowStep(contract.backTarget, { focusStep: true });
      });
      $("#workflowPrimaryButton")?.addEventListener("click", () => performWorkflowPrimaryAction());
      $("#workflowDashboardToggle")?.addEventListener("click", () => {
        setWorkflowDashboard(!state.workflowDashboard);
      });
      renderWorkflowStepper();
    }

    function currentPresetLabel() {
      return PRESETS[state.selectedPreset]?.label || RUN_PLAN_GOALS[state.selectedPreset]?.title || "Choose goal";
    }

    function setSidebarCollapsed(collapsed, { persist = true, focusToggle = false } = {}) {
      shell?.classList.toggle("is-sidebar-collapsed", collapsed);
      const content = $("#sidebarNavigationContent");
      if (content) {
        content.setAttribute("aria-hidden", String(collapsed));
        content.inert = collapsed;
      }
      if (sidebarToggle) {
        sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
        sidebarToggle.textContent = collapsed ? "Menu" : "Collapse menu";
        sidebarToggle.setAttribute("aria-label", collapsed ? "Expand workspace navigation" : "Collapse workspace navigation");
      }
      if (collapsed && content?.contains(document.activeElement)) {
        sidebarToggle?.focus();
      } else if (focusToggle) {
        sidebarToggle?.focus();
      }
      if (persist) storage.set(SHELL_STORAGE_KEYS.sidebarCollapsed, String(collapsed));
      renderShellIndicators();
    }

    function setRailCollapsed(collapsed, { persist = true, focusToggle = false } = {}) {
      shell?.classList.toggle("is-rail-collapsed", collapsed);
      const rail = $("#diagnosticsRail");
      if (rail) {
        rail.setAttribute("aria-hidden", String(collapsed));
        rail.inert = collapsed;
      }
      if (detailsToggle) detailsToggle.setAttribute("aria-expanded", String(!collapsed));
      if (railCloseButton) {
        railCloseButton.setAttribute("aria-expanded", String(!collapsed));
      }
      if (collapsed && rail?.contains(document.activeElement)) {
        detailsToggle?.focus();
      } else if (focusToggle) {
        (collapsed ? detailsToggle : railCloseButton || detailsToggle)?.focus();
      }
      if (persist) storage.set(SHELL_STORAGE_KEYS.railCollapsed, String(collapsed));
      renderShellIndicators();
    }

    function shellDiagnosticSummary() {
      const providerWarning = $("#providerWarning");
      const providerText = providerWarning?.textContent?.trim() || "";
      const providerBad = providerWarning?.classList.contains("is-bad");
      const providerWarn = providerWarning?.classList.contains("is-warn") || (providerText && !providerWarning?.classList.contains("is-ready"));
      const rootErrors = Object.values(state.errors || {}).filter(Boolean);
      const diagnostics = collectDiagnostics(selectedJob(), state.jobEvents, state.jobArtifacts, state.reviewTracks, state.jobReview).filter(
        (item) => item.severity !== "ready",
      );
      const activeCount = state.jobs.filter(isActiveJob).length;
      if (rootErrors.length) return { label: `${rootErrors.length} setup issue${rootErrors.length === 1 ? "" : "s"}`, tone: "is-bad" };
      if (providerBad) return { label: "Provider blocked", tone: "is-bad" };
      if (diagnostics.some((item) => item.severity === "bad")) return { label: "Run failure details", tone: "is-bad" };
      if (providerWarn) return { label: "Provider warning", tone: "is-warn" };
      if (diagnostics.length) return { label: `${diagnostics.length} diagnostic${diagnostics.length === 1 ? "" : "s"}`, tone: "is-warn" };
      if (activeCount) return { label: `${activeCount} active run${activeCount === 1 ? "" : "s"}`, tone: "is-neutral" };
      return { label: shell?.classList.contains("is-rail-collapsed") ? "Details hidden" : "Details open", tone: "is-muted" };
    }

    function renderShellIndicators() {
      $("#collapsedGoalLabel").textContent = currentPresetLabel();
      const summary = $("#diagnosticsSummary");
      if (summary) {
        const diagnostic = shellDiagnosticSummary();
        summary.textContent = diagnostic.label;
        summary.className = `status-chip ${diagnostic.tone}`;
      }
      if (detailsToggle) {
        detailsToggle.textContent = state.workflowDashboard ? "Simple" : "Advanced";
        detailsToggle.setAttribute("aria-expanded", String(Boolean(state.workflowDashboard)));
      }
    }

    function initShellNavigation() {
      setSidebarCollapsed(boolFromStorage(SHELL_STORAGE_KEYS.sidebarCollapsed, false), { persist: false });
      setRailCollapsed(true, { persist: false });
      sidebarToggle?.addEventListener("click", () => {
        setSidebarCollapsed(!shell?.classList.contains("is-sidebar-collapsed"), { focusToggle: true });
      });
      detailsToggle?.addEventListener("click", () => {
        setWorkflowDashboard(!state.workflowDashboard);
      });
      railCloseButton?.addEventListener("click", () => {
        state.railOpenedByUser = false;
        setWorkflowDashboard(false);
      });
      renderShellIndicators();
    }

    function renderApiStatus(kind, label) {
      const chip = $("#apiStatus");
      chip.className = `status-chip ${kind}`;
      chip.textContent = label === "API ready" ? "Local API ready" : label === "API unavailable" ? "Local API unavailable" : label;
      renderShellIndicators();
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
          debugMock: state.health.mockMode ? "on" : "off",
        });
      }

      $("#routeList").innerHTML = (routes.length ? routes : API_ROUTES)
        .map((route) => {
          const routeState = routes.length ? "reported by local API" : "expected local API route";
          return `<div class="route-row"><strong>${escapeHtml(route)}</strong><span class="row-meta">${routeState}</span></div>`;
        })
        .join("");
    }

    function renderWorkspace() {
      const summary = $("#workspaceSummary");
      const recent = $("#workspaceRecent");
      const projectRailTitle = $("#projectRailTitle");
      const projectRailMeta = $("#projectRailMeta");
      if (!state.workspace) {
        setFacts(summary, {
          status: state.errors.workspace || "not loaded",
          projects: "not reported",
          providers: "not reported",
        });
        if (projectRailTitle) projectRailTitle.textContent = "Local project";
        if (projectRailMeta) projectRailMeta.textContent = state.errors.workspace || "Choose a goal, then add a video.";
        recent.innerHTML = `<div class="${state.errors.workspace ? "error-state" : "empty-state"}">${escapeHtml(state.errors.workspace || "Workspace summary has not loaded yet.")}</div>`;
        return;
      }
      const preferences = state.workspace.preferences?.preferences || {};
      const providerSummary = state.workspace.providerSettingsSummary || {};
      setFacts(summary, {
        projects: asArray(state.workspace.projects).length,
        recent: `${asArray(state.workspace.recentVideos).length} videos, ${asArray(state.workspace.recentJobs).length} jobs`,
        providers: `${providerSummary.configuredCount || 0} configured`,
        "default path": "SAM provider setup",
      });
      $("#preferenceDefaultGoal").value = preferences.defaultGoal || "auto_object_proposals";
      $("#preferenceExportPreset").value = preferences.defaultExportPreset || "compact";
      const tasks = asArray(state.workspace.guidedTasks).slice(0, 4);
      const videos = asArray(state.workspace.recentVideos).slice(0, 3);
      const jobs = asArray(state.workspace.recentJobs).slice(0, 3);
      const selectedProject = state.projects.find((item) => item.id === state.selectedProjectId) || state.projects[0] || null;
      if (projectRailTitle) projectRailTitle.textContent = selectedProject?.name || "Local project";
      if (projectRailMeta) projectRailMeta.textContent = state.selectedVideoId ? "Video selected" : "Add a video in step 2.";
      recent.innerHTML = `
        <div class="workspace-block">
          <strong>Guided tasks</strong>
          ${tasks.map((task) => `<button class="workspace-task" type="button" data-preset="${escapeAttribute(task.id)}">${escapeHtml(task.label)}</button>`).join("") || `<span class="row-meta">No tasks reported.</span>`}
        </div>
        <div class="workspace-block">
          <strong>Recent videos</strong>
          ${videos.map((video) => `<span class="row-meta">${escapeHtml(video.filename || video.id)}</span>`).join("") || `<span class="row-meta">Add a video to start.</span>`}
        </div>
        <div class="workspace-block">
          <strong>Recent jobs</strong>
          ${jobs.map((job) => `<span class="row-meta">${escapeHtml(job.status)} - ${escapeHtml(job.provider || job.type || job.id)}</span>`).join("") || `<span class="row-meta">No extraction jobs yet.</span>`}
        </div>
      `;
    }

    function providerDetails(provider) {
      const details = [];
      if (provider.kind) details.push(provider.kind);
      if (provider.device) details.push(`device: ${provider.device}`);
      if (provider.optionalExtra) details.push(`extra: ${provider.optionalExtra}`);
      if (provider.noModelSafe === true) details.push("no-model safe");
      if (provider.estimatedCost?.status?.startsWith("zero_local") && !provider.networkRequired) details.push("local/free");
      if (provider.networkRequired === true) details.push("network");
      if (provider.needsCredentials === true) details.push("credentials");
      if (provider.needsGpu === true) details.push("GPU required");
      if (provider.needsModelPath === true) details.push("model path");
      if (provider.runnable === true) details.push("runnable");
      if (provider.configured === true && provider.runnable === false) details.push("configured, not runnable");
      if (state.health?.mockMode && provider.mockAvailable === true) details.push("debug mock available");
      return details;
    }

    function renderCapabilities() {
      const list = $("#capabilityList");
      if (!state.capabilities) {
        list.innerHTML = `<div class="error-state">${escapeHtml(state.errors.capabilities || "No capability data available.")}</div>`;
        return;
      }

      const priority = new Set(["mock", "threshold", "motion", "external", "sam2-local", "sam2-hosted", "sam3-local", "sam3-hosted", "sam3-concept", "sam3-exemplar", "sam3-auto-masks", "openai", "openrouter", "text_detector", "class_detector", "sam_auto_masks", "motion_foreground"]);
      const providers = asArray(state.capabilities.providers)
        .filter((provider) => priority.has(provider.name))
        .filter((provider) => state.health?.mockMode || provider.name !== "mock")
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

    function renderProviderSettings() {
      const list = $("#providerSettingsList");
      const status = $("#providerSettingsStatus");
      if (!state.providerSettings) {
        status.textContent = state.errors.providerSettings ? "Unavailable" : "Not loaded";
        status.className = `status-chip ${state.errors.providerSettings ? "is-bad" : "is-muted"}`;
        list.innerHTML = `<div class="${state.errors.providerSettings ? "error-state" : "empty-state"}">${escapeHtml(state.errors.providerSettings || "Provider settings have not loaded yet.")}</div>`;
        return;
      }

      const providers = asArray(state.providerSettings.providers).filter((provider) => state.health?.mockMode || provider.id !== "mock");
      const configuredHosted = providers.filter((provider) => provider.locality === "hosted" && provider.readiness?.configured).length;
      status.textContent = configuredHosted ? `${configuredHosted} hosted configured` : "SAM setup";
      status.className = `status-chip ${configuredHosted ? "is-warn" : "is-ready"}`;
      list.innerHTML = providers.map(renderProviderSettingsRow).join("");
    }

    function renderModelSetup() {
      const status = $("#modelSetupStatus");
      const choices = $("#modelSetupChoices");
      const detail = $("#modelSetupDetail");
      if (!status || !choices || !detail) return;

      if (!state.providerSettings) {
        status.textContent = state.errors.providerSettings ? "Unavailable" : "Not loaded";
        status.className = `status-chip ${state.errors.providerSettings ? "is-bad" : "is-muted"}`;
        choices.innerHTML = "";
        detail.innerHTML = `<div class="${state.errors.providerSettings ? "error-state" : "empty-state"}">${escapeHtml(state.errors.providerSettings || "Provider information has not loaded yet.")}</div>`;
        return;
      }

      if (!goalRequiresModel(state.selectedPreset)) {
        status.textContent = "Not needed";
        status.className = "status-chip is-ready";
        choices.innerHTML = "";
        detail.innerHTML = `<div class="empty-state">This workflow does not need a SAM model. Continue to prepare the run.</div>`;
        return;
      }

      const compatibleConnections = compatibleModelConnectionsForPreset(state.selectedPreset, { includeAdvanced: state.workflowDashboard || state.modelSetupAlternativesOpen });
      if (!compatibleConnections.length) {
        status.textContent = "Unavailable";
        status.className = "status-chip is-bad";
        choices.innerHTML = "";
        detail.innerHTML = `<div class="error-state">No compatible model connection is available for ${escapeHtml(currentPresetLabel())}.</div>`;
        return;
      }

      if (!compatibleConnections.some((connection) => connection.id === state.selectedModelSetupProviderId)) {
        state.selectedModelSetupProviderId = recommendedConnectionIdForPreset();
      }
      const selected = modelConnectionById(state.selectedModelSetupProviderId);
      const selectedReadiness = connectionReadiness(selected);
      const selectedProvider = providerSettingsById(selected.providerId);
      const selectedSetupState = modelSetupStateForConnection(selected, selectedProvider, setupJobForProvider(selected.providerId));
      const selectedSetupTone =
        selectedSetupState.status === "ready"
          ? "ready"
          : selectedSetupState.status === "failed_recoverable"
            ? "bad"
            : "warn";
      status.textContent = selectedSetupState.label || selectedReadiness.label;
      status.className = `status-chip is-${selectedSetupTone}`;

      const recommendedId = recommendedConnectionIdForPreset();
      const normalConnections = state.modelSetupAlternativesOpen || state.workflowDashboard
        ? compatibleConnections
        : compatibleConnections.filter((connection) => connection.id === state.selectedModelSetupProviderId || connection.id === recommendedId).slice(0, 1);
      choices.innerHTML = normalConnections.map((connection) => {
          const provider = providerSettingsById(connection.providerId);
          const readinessSummary = connectionReadiness(connection);
          const setupState = modelSetupStateForConnection(connection, provider, setupJobForProvider(connection.providerId));
          const setupReady = setupState.status === "ready";
          const summary = {
            label: setupState.label || readinessSummary.label,
            status: setupState.status || readinessSummary.status,
            tone: setupReady ? "ready" : setupState.status === "failed_recoverable" ? "bad" : readinessSummary.tone === "bad" ? "bad" : "warn",
          };
          const active = connection.id === selected.id;
          const hosted = provider?.locality === "hosted";
          const profile = connection.profileId
            ? asArray(provider?.hostedProfiles).find((item) => item.id === connection.profileId)
            : null;
          return `
            <button class="model-choice-card ${active ? "is-active" : ""} ${hosted ? "is-hosted" : "is-local"}" type="button" data-model-setup-provider="${escapeAttribute(connection.id)}" aria-pressed="${active}">
              <span class="model-choice-topline">
                <strong>${escapeHtml(connection.displayLabel || connection.title)}</strong>
                ${statusChip(summary.label, summary.status, summary.tone === "ready")}
              </span>
              <span class="model-choice-copy">${escapeHtml(connection.recommendation)}</span>
              <span class="model-choice-meta">${escapeHtml(`${connection.workflow} - ${profile?.name || provider?.name || connection.providerId}`)}</span>
            </button>
          `;
        })
        .join("");

      detail.innerHTML = renderModelSetupDetail(selected, selectedReadiness);
    }

    function renderModelSetupDetail(connection, summary) {
      const settingsProvider = providerSettingsById(connection.providerId);
      const hosted = settingsProvider?.locality === "hosted";
      const resultTone = state.modelSetupTone || summary.tone || "neutral";
      const resultMessage = state.modelSetupMessage || summary.message;
      const readiness = settingsProvider?.readiness || {};
      const settings = settingsProvider?.settings || {};
      const credentials = asArray(settingsProvider?.credentials);
      const modelOptions = asArray(settingsProvider?.modelOptions);
      const selectedModel = settings.selectedModel || settingsProvider?.defaultModel || "";
      const selectedProfile = connection.profileId || settings.hostedProfileId || settingsProvider?.defaultHostedProfile || "";
      const customHidden = selectedModel !== "__custom__";
      const guide = connection.profileId
        ? asArray(settingsProvider?.hostedProfiles).find((item) => item.id === connection.profileId)?.setupGuide || {}
        : settingsProvider?.setupGuide || {};
      const readinessDetails = [
        hosted ? "hosted API" : "local model",
        readiness.status || summary.status,
        providerEffectiveModel(settingsProvider),
        connection.profileId || "",
      ].filter(Boolean);
      const commandRows = asArray(guide.commands)
        .map((command) => `<code>${escapeHtml(command)}</code>`)
        .join("");
      const profileField =
        hosted && asArray(settingsProvider?.hostedProfiles).length
          ? `<label>
              <span>API provider</span>
              <select data-model-setup-field="hostedProfileId" ${connection.profileId ? "disabled" : ""}>
                ${asArray(settingsProvider.hostedProfiles)
                  .filter((profile) => !connection.profileId || profile.id === connection.profileId)
                  .map((profile) => `<option value="${escapeAttribute(profile.id)}" ${profile.id === selectedProfile ? "selected" : ""}>${escapeHtml(profile.name || profile.id)}</option>`)
                  .join("")}
              </select>
              ${connection.profileId ? `<input type="hidden" data-model-setup-field="hostedProfileId" value="${escapeAttribute(selectedProfile)}" />` : ""}
            </label>`
          : "";
      const localFields = asArray(settingsProvider?.localConfigFields)
        .map((field) => {
          const fieldName = field.name || "";
          const camelName =
            fieldName === "sam2_checkpoint_path"
              ? "sam2CheckpointPath"
              : fieldName === "sam2_model_config_path"
                ? "sam2ModelConfigPath"
                : fieldName === "sam2_device"
                  ? "sam2Device"
                  : fieldName === "sam2_hf_device"
                    ? "sam2HfDevice"
                  : fieldName === "sam3_model_path"
                    ? "sam3ModelPath"
                    : fieldName === "sam3_device"
                      ? "sam3Device"
                      : fieldName;
          let value = settings[camelName] || "";
          if (connection.providerId === "sam3-local" && camelName === "sam3Device" && !value && environmentRecommendationSummary().accelerator === "cuda") {
            value = "cuda";
          }
          const type = fieldName.endsWith("_device") ? "text" : "text";
          const placeholder = field.placeholder || field.env || "";
          const helper = field.helpText ? `<span class="field-helper">${escapeHtml(field.helpText)}</span>` : "";
          return `<label>
            <span>${escapeHtml(field.label || fieldName)}</span>
            <input data-model-setup-field="${escapeAttribute(camelName)}" type="${type}" value="${escapeAttribute(value)}" placeholder="${escapeAttribute(placeholder)}" />
            ${helper}
          </label>`;
        })
        .join("");
      const advancedLocalPath = state.advancedLocalPaths?.[connection.providerId] || {};
      const cachedSceneSweepPath = connection.providerId === "sam3-local"
        ? String(advancedLocalPath.cachedSceneSweepModelDir || advancedLocalPath.localModelDirDisplayRaw || "")
        : "";
      const cachedSceneSweepPathField = connection.providerId === "sam3-local"
        ? `<label class="model-setup-readonly-path">
            <span>Cached SAM3 Scene Sweep model directory</span>
            <div class="readonly-path-control">
              <input type="text" readonly value="${escapeAttribute(cachedSceneSweepPath || (settingsProvider?.modelCache?.localPathKnown ? "[LOCAL_PATH_REDACTED]" : ""))}" placeholder="Cache facebook/sam3 to record the local runtime directory" aria-label="Cached SAM3 Scene Sweep model directory" />
              <button type="button" data-copy-advanced-model-path="${escapeAttribute(connection.providerId)}" ${cachedSceneSweepPath ? "" : "disabled"}>${state.copiedAdvancedPathProviderId === connection.providerId ? "Copied" : "Copy path"}</button>
            </div>
            <span class="field-helper">${cachedSceneSweepPath ? "Used automatically for Scene Sweep. Do not paste this into the checkpoint path." : "This appears after Cache model records the server-side Scene Sweep directory."}</span>
          </label>`
        : "";
      const credentialSummary = credentials.length
        ? credentials
            .map((credential) => {
              const display = credential.configured ? `${credential.source}: ${credential.display || "configured"}` : `missing ${credential.env || credential.name}`;
              return `<span class="row-meta">${escapeHtml(credential.label || credential.name)} - ${escapeHtml(display)}</span>`;
            })
            .join("")
        : `<span class="row-meta">No API key required.</span>`;
      const credentialInputName = (name) => {
        if (name === "api_key") return "apiKey";
        if (name === "hf_token") return "hfToken";
        return String(name || "").replace(/_([a-z])/g, (_match, char) => char.toUpperCase());
      };
      const credentialInputMarkup = (credential, options = {}) => {
        const name = credential?.name || "";
        const fieldName = credentialInputName(name);
        const fieldAttribute = name === "api_key" ? 'data-model-setup-field="apiKey"' : `data-model-setup-field="${escapeAttribute(fieldName)}"`;
        const label = credential?.label || (name === "hf_token" ? "Hugging Face token" : "API key");
        const placeholder =
          name === "hf_token"
            ? "Paste a Hugging Face token for facebook/sam3"
            : credential?.configured
              ? "Paste key to replace saved key"
              : "Paste key";
        const helper =
          name === "hf_token"
            ? `<span class="field-helper">Stored locally, redacted in the browser, and used only by allowlisted Hugging Face access/cache jobs.</span>`
            : "";
        return `<label class="${options.normal ? "model-setup-access-token" : ""}">
          <span>${escapeHtml(label)}</span>
          <input ${fieldAttribute} type="password" autocomplete="off" value="" placeholder="${escapeAttribute(placeholder)}" aria-label="${escapeAttribute(label)}" />
          ${helper}
        </label>`;
      };
      const endpointField = settingsProvider?.endpointField
        ? `<label>
            <span>${escapeHtml(settingsProvider.endpointField.label || "Endpoint URL")}</span>
            <input data-model-setup-field="endpoint" type="url" value="${escapeAttribute(settings.endpoint || "")}" placeholder="${escapeAttribute(settingsProvider.endpointField.env || "")}" />
          </label>`
        : "";
      const hfCredential = credentials.find((credential) => credential.name === "hf_token");
      const showNormalHfAccess = connection.providerId === "sam3-local" && state.selectedPreset === "trace_all_objects" && hfCredential && !hfCredential.configured;
      const credentialField = credentials
        .filter((credential) => !(showNormalHfAccess && credential.name === "hf_token"))
        .map((credential) => credentialInputMarkup(credential))
        .join("");
      const setupJob = setupJobForProvider(connection.providerId);
      const setupJobSummary = setupJobStatusSummary(setupJob);
      const setupState = modelSetupStateForConnection(connection, settingsProvider, setupJob);
      const primarySetupAction = modelSetupPrimaryActionForState(setupState, connection);
      const setupStateTone =
        setupState.status === "ready"
          ? "ready"
          : setupState.status === "failed_recoverable"
            ? "bad"
            : ["checking_environment", "caching_model", "installing_runtime", "preparing_model", "smoke_testing"].includes(setupState.status)
              ? "neutral"
              : "warn";
      const hasAlternatives = compatibleModelConnectionsForPreset(state.selectedPreset, { includeAdvanced: true }).length > 1;
      const local = !hosted;
      const canInstall = connection.providerId === "sam3-local" || connection.providerId === "sam2-local" || connection.providerId === "sam2-hf-auto-masks";
      const canCheckAccess = connection.providerId === "sam3-local" || hosted;
      const manualCommands = commandRows
        ? `<details class="provider-setup-commands">
            <summary>Manual commands</summary>
            ${commandRows}
          </details>`
        : "";
      const normalAccessCard = showNormalHfAccess
        ? `<div class="model-setup-access-card">
            <div>
              <strong>Hugging Face access</strong>
              <p>facebook/sam3 may require Meta approval. Paste your Hugging Face token here, then use the setup action to check access before downloading weights.</p>
            </div>
            ${credentialInputMarkup(hfCredential, { normal: true })}
          </div>`
        : "";
      const setupProgressCard = setupJobProgressCard(setupJob, setupJobSummary);
      const environmentCard = environmentRecommendationCard(connection);
      const setupPlaybook = modelSetupPlaybookMarkup(connection, settingsProvider, setupState, setupJob);
      const cacheSummary = modelCacheStatusSummary(settingsProvider, setupJob);
      const cacheStatusCard = cacheSummary.required
        ? `<div class="model-cache-status is-${escapeAttribute(cacheSummary.cached ? "ready" : "warn")}">
            <div>
              <strong>${escapeHtml(cacheSummary.label)}</strong>
              <span class="row-meta">${escapeHtml(cacheSummary.message)}</span>
            </div>
            <div class="provider-detail">
              ${cacheSummary.model ? detailChip(cacheSummary.model) : ""}
              ${cacheSummary.pathKnown ? detailChip(cacheSummary.recorded ? "path recorded server-side" : "path known locally") : detailChip("path not recorded yet")}
              ${cacheSummary.updatedAt ? detailChip(`updated ${cacheSummary.updatedAt}`) : ""}
            </div>
          </div>`
        : "";
      const pendingConfirmation = state.pendingModelSetupConfirmation?.providerId === connection.providerId
        ? state.pendingModelSetupConfirmation
        : null;
      const confirmationCard = pendingConfirmation
        ? `<div class="model-setup-confirmation" role="alert">
            <div>
              <strong>${escapeHtml(pendingConfirmation.label)}</strong>
              <p>${escapeHtml(pendingConfirmation.message)}</p>
              <div class="provider-detail">
                ${detailChip(pendingConfirmation.providerLabel || connection.providerId)}
                ${pendingConfirmation.model ? detailChip(pendingConfirmation.model) : ""}
                ${asArray(pendingConfirmation.flags).map((flag) => detailChip(flag)).join("")}
              </div>
            </div>
            <div class="model-setup-confirmation-actions">
              <button type="button" data-model-setup-confirmation="cancel">Cancel</button>
              <button type="button" data-model-setup-confirmation="confirm">${escapeHtml(pendingConfirmation.label)}</button>
            </div>
          </div>`
        : "";

      return `
        <div class="model-setup-summary">
          <div class="model-setup-copy">
            <h3>${escapeHtml(connection.displayLabel || connection.title)}</h3>
            <p>${escapeHtml(connection.recommendation || guide.setupSummary)}</p>
            <div class="provider-detail">${readinessDetails.map((detail) => detailChip(detail)).join("")}</div>
          </div>
        </div>
        <form id="modelSetupForm" class="model-setup-form-shell" data-provider-settings-id="${escapeAttribute(settingsProvider?.id || connection.providerId)}">
        <div class="model-setup-state-card is-${escapeAttribute(setupStateTone)}">
          <div>
            <strong>${escapeHtml(setupState.label)}</strong>
            <span class="row-meta">${escapeHtml(resultMessage || setupState.message)}</span>
          </div>
          <div class="model-setup-normal-actions">
            <button
              type="button"
              class="${primarySetupAction.primary ? "primary-action" : ""}"
              data-model-setup-action="${escapeAttribute(primarySetupAction.id)}"
              ${primarySetupAction.id === "cancel-setup-job" && setupJob?.id ? `data-setup-job-id="${escapeAttribute(setupJob.id)}"` : ""}
            >${escapeHtml(primarySetupAction.label)}</button>
            ${hasAlternatives ? `<button type="button" data-model-setup-action="change-model">${state.modelSetupAlternativesOpen ? "Hide models" : "Change model"}</button>` : ""}
          </div>
        </div>
        ${confirmationCard}
        ${environmentCard}
        ${setupPlaybook}
        ${normalAccessCard}
        ${setupProgressCard}
        ${cacheStatusCard}
        ${hosted ? `<div class="warning-box is-warn">${escapeHtml(settingsProvider?.privacy || "Hosted calls can send frames off-device and may cost money.")}</div>` : ""}
        <div id="modelSetupResult" class="model-setup-result is-${escapeAttribute(resultTone)}" role="status" ${resultMessage ? "" : "hidden"}>${escapeHtml(resultMessage)}</div>
        <details class="advanced-panel model-setup-advanced">
          <summary>Advanced</summary>
          ${manualCommands}
          <div class="model-setup-job is-${escapeAttribute(setupJobSummary.tone)}">
            <div>
              <strong>${escapeHtml(setupJobSummary.label)}</strong>
              <span class="row-meta">${escapeHtml(setupJobSummary.message)}</span>
            </div>
            ${setupJob?.status === "running" || setupJob?.status === "queued" ? `<button type="button" data-model-setup-action="cancel-setup-job" data-setup-job-id="${escapeAttribute(setupJob.id)}">Cancel setup</button>` : ""}
          </div>
          <div class="model-setup-credentials">${credentialSummary}</div>
          <div class="model-setup-form">
            ${profileField}
            <label>
              <span>Model</span>
              <select data-model-setup-field="selectedModel">
                ${modelOptions
                  .map((option) => `<option value="${escapeAttribute(option.id)}" ${option.id === selectedModel ? "selected" : ""}>${escapeHtml(option.label || option.id)}</option>`)
                  .join("")}
              </select>
            </label>
            ${
              settingsProvider?.customModelAllowed
                ? `<label class="model-setup-custom-model" ${customHidden ? "hidden" : ""}>
                    <span>Custom model id</span>
                    <input data-model-setup-field="customModelId" type="text" value="${escapeAttribute(settings.customModelId || "")}" />
                  </label>`
                : ""
            }
            ${cachedSceneSweepPathField}
            ${localFields}
            ${endpointField}
            ${credentialField}
            ${
              hosted
                ? `<label class="track-toggle model-hosted-toggle">
                    <input data-model-setup-field="allowHosted" type="checkbox" ${settings.allowHosted ? "checked" : ""} />
                    <span>I understand hosted calls can send frames off-device and may cost money</span>
                  </label>`
                : ""
            }
            <div class="model-setup-actions">
              ${canInstall ? `<button type="button" data-model-setup-action="install">${local && connection.providerId === "sam3-local" ? "Install scene sweep" : connection.providerId === "sam2-hf-auto-masks" ? "Install SAM2 HF fallback" : "Install fallback"}</button>` : ""}
              ${canCheckAccess ? `<button type="button" data-model-setup-action="check-access">${hosted ? "Check access" : "Check HF access"}</button>` : ""}
              <button type="button" data-model-setup-action="cache-model">Cache model</button>
              <button type="button" data-model-setup-action="save">Save setup</button>
              <button type="button" data-model-setup-action="diagnose">Diagnose</button>
              <button type="button" data-model-setup-action="smoke">Run smoke test</button>
              <button type="button" data-model-setup-action="view-setup-logs">View logs</button>
              <button type="button" data-model-setup-action="reset">Reset</button>
            </div>
          </div>
          <div id="modelSetupJobLog" class="event-log setup-job-log" ${setupJob ? "" : "hidden"}>${setupJobEventsMarkup(setupJob)}</div>
        </details>
        </form>
      `;
    }

    function currentModelPlanResult() {
      return state.modelPlanRun?.result || null;
    }

    function currentModelPlanValidation() {
      return state.modelPlanValidation || currentModelPlanResult()?.validation || null;
    }

    function setModelPlanMessage(message, tone = "neutral") {
      state.modelPlanMessage = message || "";
      state.modelPlanTone = tone || "neutral";
      renderModelPlanPanel();
    }

    function renderModelPlanPanel() {
      const status = $("#modelPlanStatus");
      const detail = $("#modelPlanDetail");
      const validateButton = $("#validateModelPlanButton");
      const confirmButton = $("#confirmModelPlanButton");
      const generateButton = $("#generateModelPlanButton");
      if (!status || !detail || !validateButton || !confirmButton || !generateButton) return;

      const selectedProvider = modelConnectorById(state.modelProviders?.defaultProviderId || "fake-local-planner");
      generateButton.textContent = selectedProvider?.hostedCallsRequired ? "Generate hosted plan" : "Generate local plan";

      const run = state.modelPlanRun;
      const result = currentModelPlanResult();
      const validation = currentModelPlanValidation();
      const facts = modelPlanProviderFacts(result, validation);
      const hasProject = Boolean(state.selectedProjectId);
      const hasVideo = Boolean(state.selectedVideoId);
      const sourceIds = modelPlanSourceIds(result);
      const projectMatches = !sourceIds.projectId || !state.selectedProjectId || sourceIds.projectId === state.selectedProjectId;
      const videoMatches = !sourceIds.videoId || !state.selectedVideoId || sourceIds.videoId === state.selectedVideoId;
      const alreadyConfirmed = Boolean(state.modelPlanConfirmedJobId);
      const canConfirm = Boolean(
        run?.id &&
          result &&
          facts.valid &&
          hasProject &&
          hasVideo &&
          projectMatches &&
          videoMatches &&
          !alreadyConfirmed &&
          !state.modelPlanConfirming,
      );

      validateButton.disabled = !result;
      confirmButton.disabled = !canConfirm;

      if (!run) {
        status.textContent = "No model plan";
        status.className = "status-chip is-muted";
        detail.innerHTML = `
          <div class="empty-state">Generate a planner config from the selected goal. Nothing is enqueued until you confirm it.</div>
        `;
        return;
      }

      if (run.status === "failed") {
        status.textContent = "Plan failed";
        status.className = "status-chip is-bad";
        detail.innerHTML = `<div class="error-state">${escapeHtml(run.error || state.modelPlanMessage || "Model planning failed.")}</div>`;
        return;
      }

      if (!result) {
        status.textContent = run.status || "Planning";
        status.className = "status-chip is-neutral";
        detail.innerHTML = `<div class="empty-state">Planning is ${escapeHtml(run.status || "pending")}.</div>`;
        return;
      }

      status.textContent = alreadyConfirmed ? "Started" : facts.validationLabel;
      status.className = `status-chip ${facts.valid ? (facts.warnings.length ? "is-warn" : "is-ready") : "is-bad"}`;
      const runtime = [
        result.runConfig?.sampling?.sample_fps ? `${result.runConfig.sampling.sample_fps} fps sample` : "",
        result.runConfig?.sampling?.max_frames ? `${result.runConfig.sampling.max_frames} frame limit` : "",
        result.requiresUserConfirmation === false ? "" : "manual confirmation required",
      ].filter(Boolean);
      const planPreset = presetNameForRunPlan(result.runConfig || {}, result.request || {});
      const planGoal = RUN_PLAN_GOALS[planPreset] || RUN_PLAN_GOALS.auto_object_proposals;
      const factRows = [
        ["Planner", facts.plannerProvider],
        ["Discovery", facts.discoveryProvider],
        ["Mask provider", facts.maskProvider],
        ["Tracking", facts.trackingMode],
        ["Privacy", facts.privacy],
        ["Cost", facts.cost],
        ["Runtime", runtime.join(" - ") || "not estimated"],
        ["Source", hasVideo ? "registered local video" : "register a video before starting"],
      ]
        .map(
          ([label, value]) => `
            <div class="model-plan-fact">
              <span>${escapeHtml(label)}</span>
              <strong>${escapeHtml(value)}</strong>
            </div>
          `,
        )
        .join("");

      const messages = [
        ...facts.errors.map((message) => ({ tone: "bad", message: `Error: ${message}` })),
        ...facts.blockers.map((message) => ({ tone: "bad", message })),
        ...facts.warnings.filter((message) => !facts.blockers.includes(message)).map((message) => ({ tone: "warn", message })),
        ...asArray(result.messages).map((message) => ({ tone: "neutral", message })),
        state.modelPlanMessage ? { tone: state.modelPlanTone, message: state.modelPlanMessage } : null,
      ].filter(Boolean);

      if (!hasProject) messages.push({ tone: "bad", message: "Create or select a project before confirming this plan." });
      if (!hasVideo) messages.push({ tone: "bad", message: "Register or select a local video before confirming this plan." });
      if (!projectMatches) messages.push({ tone: "bad", message: "The selected project changed after this plan was generated. Generate a fresh plan." });
      if (!videoMatches) messages.push({ tone: "bad", message: "The selected video changed after this plan was generated. Generate a fresh plan." });

      const eventRows = asArray(run.events)
        .slice(-4)
        .map(
          (event) => `
            <div class="model-run-event">
              <strong>${escapeHtml(event.eventType || event.event_type || "event")}</strong>
              <span>${escapeHtml(event.message || event.status || "")}</span>
            </div>
          `,
        )
        .join("");

      detail.innerHTML = `
        <div class="model-plan-card">
          <div class="model-plan-card-header">
            <div>
              <h3>${escapeHtml(planGoal.title || "Model-generated plan")}</h3>
              <p>${escapeHtml(result.request?.prompt || result.request?.textPrompt || "Review the generated run plan before starting extraction.")}</p>
            </div>
            ${statusChip(result.status || "planned", result.status || "planned", facts.valid)}
          </div>
          <div class="model-plan-facts">${factRows}</div>
          ${
            messages.length
              ? `<div class="model-plan-messages">${messages
                  .map((item) => `<div class="model-plan-message is-${escapeAttribute(item.tone)}">${escapeHtml(item.message)}</div>`)
                  .join("")}</div>`
              : ""
          }
          <div class="model-plan-confirm-row">
            <span class="row-meta">${escapeHtml(
              canConfirm
                ? "This generated config has passed backend validation. Confirming will enqueue extraction and attach the model plan to the run log."
                : alreadyConfirmed
                  ? `Plan already started as ${state.modelPlanConfirmedJobId}. Watch progress in the run monitor.`
                : state.modelPlanConfirming
                  ? "Confirmation is in progress."
                : "Confirmation stays disabled until the generated config validates and a matching local project/video are selected.",
            )}</span>
            ${statusChip(alreadyConfirmed ? "Started" : canConfirm ? "Ready to start" : "Confirmation blocked", alreadyConfirmed || canConfirm ? "ready" : "blocked", alreadyConfirmed || canConfirm)}
          </div>
          ${eventRows ? `<div class="model-run-event-list">${eventRows}</div>` : ""}
        </div>
      `;
    }

    function renderCommercialReadiness() {
      const status = $("#commercialReadinessStatus");
      const summary = $("#commercialReadinessSummary");
      const list = $("#commercialReadinessList");
      if (!state.commercialReadiness) {
        status.textContent = state.errors.commercialReadiness ? "Unavailable" : "Not loaded";
        status.className = `status-chip ${state.errors.commercialReadiness ? "is-bad" : "is-muted"}`;
        setFacts(summary, {
          account: "not reported",
          billing: "not reported",
          exports: "not reported",
        });
        list.innerHTML = `<div class="${state.errors.commercialReadiness ? "error-state" : "empty-state"}">${escapeHtml(state.errors.commercialReadiness || "Commercial readiness has not loaded yet.")}</div>`;
        return;
      }
      const readiness = state.commercialReadiness;
      const usageTotals = readiness.usageCost?.totals || {};
      const providerHistory = asArray(readiness.providerRunHistory);
      const exports = asArray(readiness.exportHistory);
      const notices = [...asArray(readiness.privacyNotices), ...asArray(readiness.rightsReminders)];
      status.textContent = readiness.accountBoundary?.teamMode === "placeholder_not_enabled" ? "Local team placeholder" : "Ready";
      status.className = "status-chip is-neutral";
      setFacts(summary, {
        account: readiness.accountBoundary?.mode || "local",
        billing: readiness.accountBoundary?.billing || "not implemented",
        "provider runs": providerHistory.length,
        exports: exports.length,
        "cost policy": readiness.usageCost?.costDashboard?.policy || "local providers report zero cost",
      });
      list.innerHTML = `
        <div class="diagnostic-row">
          <strong>Usage</strong>
          <span>${escapeHtml(Object.keys(usageTotals).length ? Object.keys(usageTotals).join(", ") : "No usage recorded yet.")}</span>
        </div>
        <div class="diagnostic-row">
          <strong>Provider history</strong>
          <span>${escapeHtml(providerHistory.length ? providerHistory.map((event) => event.metadata?.provider || event.eventType).join(", ") : "No provider attempts recorded.")}</span>
        </div>
        <div class="diagnostic-row">
          <strong>Export history</strong>
          <span>${escapeHtml(exports.length ? exports.map((item) => item.kind).join(", ") : "No exports yet.")}</span>
        </div>
        ${notices.map((notice) => `<div class="diagnostic-row"><strong>Notice</strong><span>${escapeHtml(notice)}</span></div>`).join("")}
      `;
    }

    function renderProviderSettingsRow(provider) {
      const capability = providerByName(provider.capabilityName || provider.id, provider.kind);
      const readiness = provider.readiness || {};
      const settings = provider.settings || {};
      const credentials = asArray(provider.credentials);
      const hosted = provider.locality === "hosted";
      const modelOptions = asArray(provider.modelOptions);
      const selectedModel = settings.selectedModel || provider.defaultModel || "";
      const hostedProfiles = asArray(provider.hostedProfiles);
      const selectedProfile = settings.hostedProfileId || provider.defaultHostedProfile || hostedProfiles[0]?.id || "";
      const profileField = hostedProfiles.length
        ? `<label>
            <span>Hosted profile</span>
            <select data-provider-field="hostedProfileId">
              ${hostedProfiles
                .map((profile) => `<option value="${escapeAttribute(profile.id)}" ${profile.id === selectedProfile ? "selected" : ""}>${escapeHtml(profile.name || profile.id)}</option>`)
                .join("")}
            </select>
          </label>`
        : "";
      const customHidden = selectedModel !== "__custom__";
      const customModelField = provider.customModelAllowed
        ? `<label class="provider-custom-model" ${customHidden ? "hidden" : ""}>
            <span>Custom model id</span>
            <input data-provider-field="customModelId" type="text" value="${escapeAttribute(settings.customModelId || "")}" />
          </label>`
        : "";
      const cost = provider.cost?.label || (hosted ? "Provider billed" : "Free local");
      const capabilityStatus = capability?.status || (provider.implemented ? "registered" : "planned");
      const credentialSummary = credentials.length
        ? credentials
            .map((credential) => {
              const display = credential.configured ? `${credential.source}: ${credential.display || "configured"}` : `missing ${credential.env || credential.name}`;
              return `<span class="row-meta">${escapeHtml(credential.label || credential.name)} - ${escapeHtml(display)}</span>`;
            })
            .join("")
        : `<span class="row-meta">No API key required.</span>`;
      const endpointField = provider.endpointField
        ? `<label>
            <span>${escapeHtml(provider.endpointField.label || "Endpoint URL")}</span>
            <input data-provider-field="endpoint" type="url" value="${escapeAttribute(settings.endpoint || "")}" placeholder="${escapeAttribute(provider.endpointField.env || "")}" />
          </label>`
        : "";
      const baseUrlField = provider.baseUrlField
        ? `<label>
            <span>${escapeHtml(provider.baseUrlField.label || "Base URL")}</span>
            <input data-provider-field="baseUrl" type="url" value="${escapeAttribute(settings.baseUrl || "")}" placeholder="${escapeAttribute(provider.baseUrlField.env || "")}" />
          </label>`
        : "";
      const credentialField = credentials
        .map((credential) => {
          const name = credential.name || "";
          const fieldName = name === "api_key" ? "apiKey" : name === "hf_token" ? "hfToken" : String(name).replace(/_([a-z])/g, (_match, char) => char.toUpperCase());
          const fieldAttribute = name === "api_key" ? 'data-provider-field="apiKey"' : `data-provider-field="${escapeAttribute(fieldName)}"`;
          const label = credential.label || (name === "hf_token" ? "Hugging Face token" : "API key");
          const placeholder = credential.configured ? "Paste value to replace saved value" : "Paste value";
          return `<label>
            <span>${escapeHtml(label)}</span>
            <input ${fieldAttribute} type="password" autocomplete="off" value="" placeholder="${escapeAttribute(placeholder)}" aria-label="${escapeAttribute(provider.name)} ${escapeAttribute(label)}" />
          </label>`;
        })
        .join("");
      const localConfigFields = asArray(provider.localConfigFields)
        .map((field) => {
          const fieldName = String(field.name || "");
          const uiName =
            {
              sam2_checkpoint_path: "sam2CheckpointPath",
              sam2_model_config_path: "sam2ModelConfigPath",
              sam2_device: "sam2Device",
              sam2_hf_device: "sam2HfDevice",
              sam3_model_path: "sam3ModelPath",
              sam3_device: "sam3Device",
            }[fieldName] || fieldName;
          const placeholder = field.placeholder || field.env || (fieldName.includes("device") ? "auto, cpu, mps, cuda, or cuda:0" : "");
          const helper = field.helpText ? `<span class="field-helper">${escapeHtml(field.helpText)}</span>` : "";
          return `<label>
            <span>${escapeHtml(field.label || uiName)}</span>
            <input data-provider-field="${escapeAttribute(uiName)}" type="text" value="${escapeAttribute(settings[uiName] || "")}" placeholder="${escapeAttribute(placeholder)}" />
            ${helper}
          </label>`;
        })
        .join("");
      const setupGuide = provider.setupGuide || {};
      const setupGuideMarkup = asArray(setupGuide.commands).length
        ? `<div class="provider-setup-commands" aria-label="${escapeAttribute(provider.name)} setup commands">
            <strong>${escapeHtml(setupGuide.title || "Setup commands")}</strong>
            ${setupGuide.docs ? `<a href="${escapeAttribute(setupGuide.docs)}" target="_blank" rel="noreferrer">Official docs</a>` : ""}
            ${asArray(setupGuide.commands).map((command) => `<code>${escapeHtml(command)}</code>`).join("")}
          </div>`
        : "";
      const smokeButton =
        provider.id === "sam2-hosted" || provider.id === "sam3-hosted" || provider.id === "sam2-local" || provider.id === "sam3-local"
          ? `<button type="button" data-provider-action="smoke-test">${hosted ? "Run hosted smoke" : "Run local smoke"}</button>`
          : "";
      return `
        <article class="provider-settings-row ${hosted ? "is-hosted" : "is-local"}" data-provider-settings-id="${escapeAttribute(provider.id)}">
          <div class="provider-settings-header">
            <div>
              <strong>${escapeHtml(provider.name)}</strong>
              <span class="row-meta">${escapeHtml(provider.locality)} - ${escapeHtml(provider.kind || "provider")}</span>
            </div>
            ${statusChip(readiness.status || capabilityStatus, readiness.status || capabilityStatus, readiness.configured && capability?.available !== false)}
          </div>
          <div class="provider-detail">
            ${detailChip(cost)}
            ${detailChip(provider.runsInLocalWorker ? "local worker" : "settings only")}
            ${detailChip(provider.hardware || "hardware varies")}
            ${detailChip(capabilityStatus)}
          </div>
          <p class="provider-privacy">${escapeHtml(provider.privacy || "")}</p>
          ${provider.warning ? `<div class="warning-box ${hosted ? "is-warn" : ""}">${escapeHtml(provider.warning)}</div>` : ""}
          <div class="provider-credential-summary">${credentialSummary}</div>
          <div class="provider-settings-fields">
            ${profileField}
            <label>
              <span>Model</span>
              <select data-provider-field="selectedModel">
                ${modelOptions
                  .map((option) => `<option value="${escapeAttribute(option.id)}" ${option.id === selectedModel ? "selected" : ""}>${escapeHtml(option.label || option.id)}</option>`)
                  .join("")}
              </select>
            </label>
            ${customModelField}
            ${endpointField}
            ${baseUrlField}
            ${localConfigFields}
            ${credentialField}
            ${
              hosted
                ? `<label class="track-toggle provider-hosted-toggle">
                    <input data-provider-field="allowHosted" type="checkbox" ${settings.allowHosted ? "checked" : ""} />
                    <span>I understand hosted calls can send data off-device and may cost money</span>
                  </label>`
                : ""
            }
          </div>
          <div class="provider-actions">
            <button type="button" data-provider-action="save">Save</button>
            <button type="button" data-provider-action="diagnose">Diagnose</button>
            <button type="button" data-provider-action="test">Test setup</button>
            ${smokeButton}
            <button type="button" data-provider-action="reset">Reset</button>
          </div>
          ${setupGuideMarkup}
          <div class="provider-test-result" role="status">${escapeHtml(readiness.message || "Review provider settings before use.")}</div>
        </article>
      `;
    }

    function renderFirstRunChecklist() {
      const list = $("#firstRunChecklist");
      if (!state.capabilities) {
        list.innerHTML = `<div class="error-state">${escapeHtml(state.errors.capabilities || "Run diagnostics to load setup status.")}</div>`;
        return;
      }

      // Build-contract label retained for docs/onboarding checks: Debug smoke.
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
      const summary = state.capabilities.summary || {};
      const firstRun = summary.firstRun || {};
      const readyNoModel = asArray(summary.readyNoModelProviders);
      const missingOptional = asArray(summary.missingOptional);
      const debugMockMode = Boolean(state.health?.mockMode);
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
          detail: state.health?.mockMode ? "Debug mock mode is on for contributor checks." : "Use motionjson ui or module launch.",
        },
        {
          label: debugMockMode ? "Contributor smoke" : "Local worker",
          status: summary.canRunNoModelSmoke ? "ready" : "limited",
          available: Boolean(summary.canRunNoModelSmoke),
          detail: summary.canRunNoModelSmoke
            ? debugMockMode
              ? `Contributor smoke providers are importable: ${(readyNoModel.length ? readyNoModel : readyNoModelProviders.map((provider) => provider.name)).slice(0, 6).join(", ")}.`
              : "The local worker can use CPU-safe providers while you finish SAM setup."
            : debugMockMode
              ? "Install base CPU dependencies before using debug smoke providers."
              : "Install base CPU dependencies before starting local runs.",
        },
        {
          label: "SAM models",
          status: missingOptional.length ? "optional" : optionalMissing.length ? "optional" : "ready",
          available: !(missingOptional.length || optionalMissing.length),
          detail: missingOptional.length
            ? `Setup needed for real extraction: ${missingOptional.slice(0, 6).join(", ")}. Open Model setup for local paths or hosted keys.`
            : optionalMissing.length
              ? `Provider setup: ${optionalMissing.join("; ")}. Install only the SAM extras you plan to use.`
            : "Configured optional providers reported ready.",
        },
        {
          label: "Exports",
          status: ffmpeg.available ? "ready" : "optional",
          available: Boolean(ffmpeg.available),
          detail: ffmpeg.available ? "FFmpeg is available for video exports." : "MotionJSON export works; MP4/WebM encoding needs FFmpeg.",
        },
        {
          label: "Next action",
          status: summary.canRunNoModelSmoke ? "ready" : "check",
          available: Boolean(summary.canRunNoModelSmoke),
          detail: summary.canRunNoModelSmoke
            ? `Create a project or use the demo video, then open Model setup. CLI: ${firstRun.recommendedCommand || "python3 -m motionjson.cli ui --no-open"}`
            : "Run backend diagnostics --text and fix base dependency blockers first.",
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

    function renderGuidedStart() {
      const chip = $("#guidedModeChip");
      if (chip) {
        const debugMockMode = Boolean(state.health?.mockMode);
        chip.textContent = debugMockMode ? "Debug mock mode" : "Local first";
        chip.className = `status-chip ${debugMockMode ? "is-warn" : "is-neutral"}`;
      }
      const projectSummaryNote = $("#guidedProjectSummaryNote");
      if (projectSummaryNote) projectSummaryNote.textContent = defaultProjectSummaryText();
      const demoButton = $("#guidedDemoVideoButton");
      if (demoButton) demoButton.textContent = state.selectedVideoId ? "Use selected video" : "Use demo video";
      const reviewDisclosure = $("#reviewExistingDisclosure");
      if (reviewDisclosure) reviewDisclosure.open = state.selectedPreset === "review_existing";
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

    function applyProviderSettingsToRunForm() {
      const selectedProvider = $("#maskProviderSelect")?.value || "";
      const provider = providerSettingsById(selectedProvider);
      const model = providerEffectiveModel(provider);
      if (provider && ["sam2", "sam2-local", "sam2-hosted"].includes(selectedProvider) && model) {
        $("#modelName").value = model;
      }
    }

    function providerSettingsPayloadFromRow(row) {
      const value = (selector) => row.querySelector(selector)?.value?.trim() || "";
      const checked = (selector) => Boolean(row.querySelector(selector)?.checked);
      const payload = {
        providerId: row.dataset.providerSettingsId,
        hostedProfileId: value("[data-provider-field='hostedProfileId']"),
        selectedModel: cleanPublicModelValue(value("[data-provider-field='selectedModel']")),
        customModelId: cleanPublicModelValue(value("[data-provider-field='customModelId']")),
        endpoint: value("[data-provider-field='endpoint']"),
        baseUrl: value("[data-provider-field='baseUrl']"),
        allowHosted: checked("[data-provider-field='allowHosted']"),
        sam2CheckpointPath: value("[data-provider-field='sam2CheckpointPath']"),
        sam2ModelConfigPath: value("[data-provider-field='sam2ModelConfigPath']"),
        sam2Device: value("[data-provider-field='sam2Device']"),
        sam2HfDevice: value("[data-provider-field='sam2HfDevice']"),
        sam3ModelPath: value("[data-provider-field='sam3ModelPath']"),
        sam3Device: value("[data-provider-field='sam3Device']"),
      };
      const key = value("[data-provider-field='apiKey']");
      if (key) payload.apiKey = key;
      const hfToken = value("[data-provider-field='hfToken']");
      if (hfToken) payload.hfToken = hfToken;
      for (const localPathField of ["customModelId", "sam2CheckpointPath", "sam2ModelConfigPath", "sam3ModelPath"]) {
        if (payload[localPathField] === "[LOCAL_PATH_REDACTED]") delete payload[localPathField];
      }
      if (!payload.customModelId) delete payload.customModelId;
      if (payload.selectedModel === "[LOCAL_PATH_REDACTED]") delete payload.selectedModel;
      return payload;
    }

    function modelSetupPayloadFromForm(form) {
      const value = (selector) => form.querySelector(selector)?.value?.trim() || "";
      const checked = (selector) => Boolean(form.querySelector(selector)?.checked);
      return modelSetupPayloadFromValues(form.dataset.providerSettingsId, {
        hostedProfileId: value("[data-model-setup-field='hostedProfileId']"),
        selectedModel: value("[data-model-setup-field='selectedModel']"),
        customModelId: value("[data-model-setup-field='customModelId']"),
        endpoint: value("[data-model-setup-field='endpoint']"),
        baseUrl: value("[data-model-setup-field='baseUrl']"),
        allowHosted: checked("[data-model-setup-field='allowHosted']"),
        apiKey: value("[data-model-setup-field='apiKey']"),
        hfToken: value("[data-model-setup-field='hfToken']"),
        sam2CheckpointPath: value("[data-model-setup-field='sam2CheckpointPath']"),
        sam2ModelConfigPath: value("[data-model-setup-field='sam2ModelConfigPath']"),
        sam2Device: value("[data-model-setup-field='sam2Device']"),
        sam2HfDevice: value("[data-model-setup-field='sam2HfDevice']"),
        sam3ModelPath: value("[data-model-setup-field='sam3ModelPath']"),
        sam3Device: value("[data-model-setup-field='sam3Device']"),
      });
    }

    function modelSetupPayloadForAction(form, action, providerId, confirmed = false) {
      const snapshot = confirmed ? state.confirmedModelSetupAction : null;
      if (
        snapshot &&
        snapshot.action === action &&
        snapshot.providerId === providerId &&
        snapshot.settingsPayload &&
        typeof snapshot.settingsPayload === "object"
      ) {
        return { ...snapshot.settingsPayload };
      }
      return form ? modelSetupPayloadFromForm(form) : {};
    }

    function setModelSetupMessage(message, tone = "neutral") {
      state.modelSetupMessage = message || "";
      state.modelSetupTone = tone || "neutral";
      const result = $("#modelSetupResult");
      if (result) {
        result.textContent = state.modelSetupMessage;
        result.className = `model-setup-result is-${state.modelSetupTone}`;
      }
    }

    async function startProviderSetupJob(providerId, action, payload = {}) {
      const response = await api(`/api/provider-settings/${encodeURIComponent(providerId)}/setup/start`, {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          action,
        }),
      });
      const job = response.setupJob;
      if (response.providerSettings) {
        state.providerSettings = response.providerSettings;
        await refreshAdvancedLocalPaths();
      }
      if (job?.id) {
        state.providerSetupJobs[job.id] = job;
        state.selectedProviderSetupJobId = job.id;
      }
      renderModelSetup();
      renderWorkflowStepper();
      if (job?.id && !job.terminal) pollProviderSetupJob(job.id);
      return job;
    }

    async function pollProviderSetupJob(jobId) {
      const initialJob = state.providerSetupJobs[jobId] || {};
      const maxWaitMs =
        initialJob.action === "prepare_model" || initialJob.action === "cache_model"
          ? 60 * 60 * 1000
          : initialJob.action === "install"
            ? 30 * 60 * 1000
            : 5 * 60 * 1000;
      const deadline = Date.now() + maxWaitMs;
      while (Date.now() < deadline) {
        await new Promise((resolvePromise) => window.setTimeout(resolvePromise, 900));
        const payload = await api(`/api/provider-settings/setup-jobs/${encodeURIComponent(jobId)}`);
        const job = payload.setupJob;
        if (!job?.id) return null;
        if (payload.providerSettings) {
          state.providerSettings = payload.providerSettings;
          await refreshAdvancedLocalPaths();
        }
        state.providerSetupJobs[job.id] = job;
        const summary = setupJobStatusSummary(job);
        setModelSetupMessage(summary.message, summary.tone);
        renderModelSetup();
        renderWorkflowStepper();
        if (job.terminal) {
          await refreshAll();
          renderModelSetup();
          renderWorkflowStepper();
          return job;
        }
      }
      return state.providerSetupJobs[jobId] || null;
    }

    async function cancelProviderSetupJob(jobId) {
      const payload = await api(`/api/provider-settings/setup-jobs/${encodeURIComponent(jobId)}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason: "user_canceled" }),
      });
      if (payload.setupJob?.id) state.providerSetupJobs[payload.setupJob.id] = payload.setupJob;
      renderModelSetup();
      renderWorkflowStepper();
      return payload.setupJob;
    }

    async function saveProviderSettingsFromRow(row) {
      const payload = providerSettingsPayloadFromRow(row);
      const response = await api("/api/provider-settings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.providerSettings = response;
      row.querySelectorAll("[data-provider-field='apiKey']").forEach((input) => {
        input.value = "";
      });
      await refreshAll();
    }

    function renderProjects() {
      const select = $("#projectSelect");
      const railList = $("#projectRailList");
      $("#projectCount").textContent = `${state.projects.length} project${state.projects.length === 1 ? "" : "s"}`;
      if (!state.projects.length) {
        if (select) select.innerHTML = `<option value="">${escapeHtml(state.errors.projects || "No local projects yet")}</option>`;
        if (railList) {
          railList.innerHTML = `<div class="project-rail-empty">No projects yet.</div>`;
        }
        state.selectedProjectId = "";
        renderGuidedStart();
        renderWorkflowStepper();
        return;
      }
      if (!state.selectedProjectId || !state.projects.some((project) => project.id === state.selectedProjectId)) {
        state.selectedProjectId = state.projects[0].id;
      }
      if (select) {
        select.innerHTML = state.projects
          .map((project) => `<option value="${escapeAttribute(project.id)}">${escapeHtml(project.name)}</option>`)
          .join("");
        select.value = state.selectedProjectId;
      }
      if (railList) {
        railList.innerHTML = state.projects
          .slice(0, 7)
          .map((project, index) => {
            const active = project.id === state.selectedProjectId;
            const created = project.created_at || project.createdAt || "";
            const meta = active ? "Current project" : created ? created.split("T")[0] : index === 0 ? "Recent project" : "Local project";
            return `
              <button class="project-rail-item ${active ? "is-active" : ""}" type="button" data-project-rail-id="${escapeAttribute(project.id)}" aria-pressed="${active}">
                <span class="project-rail-folder" aria-hidden="true"></span>
                <span>
                  <strong>${escapeHtml(project.name || "Untitled project")}</strong>
                  <small>${escapeHtml(meta)}</small>
                </span>
              </button>
            `;
          })
          .join("");
      }
      renderGuidedStart();
      renderWorkflowStepper();
    }

    function renderBrowserPreviewCard() {
      const card = $("#browserPreviewCard");
      const poster = $("#browserPreviewPoster");
      const title = $("#browserPreviewTitle");
      const message = $("#browserPreviewMessage");
      const meta = $("#browserPreviewMeta");
      const retryButton = $("#retryPreviewButton");
      if (!card || !poster || !title || !message || !meta || !retryButton) return;

      const video = selectedVideo();
      const preview = selectedVideoBrowserPreview(video);
      const posterUrl = selectedVideoPosterUrl(video);
      poster.hidden = !posterUrl;
      poster.src = posterUrl || "";
      const filename = video?.metadata?.filename || video?.filename || "";
      const dimensions =
        preview?.width && preview?.height ? `${preview.width}x${preview.height}` : "";
      const duration =
        typeof preview?.duration === "number" && preview.duration > 0 ? `${Math.round(preview.duration * 10) / 10}s` : "";
      meta.textContent = [filename, preview?.codec || "", dimensions, duration].filter(Boolean).join(" • ");

      const status = String(preview?.status || "");
      if (!video) {
        title.textContent = "Preview not ready";
        message.textContent = "Add a source video to prepare a browser-safe preview.";
        retryButton.hidden = true;
        return;
      }
      if (status === "ready") {
        title.textContent = "Preview ready";
        message.textContent =
          preview?.kind === "transcoded"
            ? "MotionJSON prepared a browser-safe preview for this source video."
            : "This source video is already safe to play in the browser.";
        retryButton.hidden = true;
        return;
      }
      if (status === "failed" || status === "blocked") {
        title.textContent = "Preview failed";
        message.textContent = preview?.reason || preview?.errorMessage || "The browser preview could not be prepared for this video.";
        retryButton.hidden = false;
        return;
      }
      title.textContent = "Preparing preview";
      message.textContent = "Preparing a browser-safe preview for this source video.";
      retryButton.hidden = true;
    }

    function renderVideos() {
      const select = $("#videoSelect");
      $("#videoCount").textContent = `${state.videos.length} video${state.videos.length === 1 ? "" : "s"}`;
      if (state.errors.videos) {
        select.innerHTML = `<option value="">Video unavailable</option>`;
        $("#videoList").innerHTML = `<div class="error-state">${escapeHtml(state.errors.videos)}</div>`;
        renderGuidedStart();
        renderWorkflowStepper();
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
        : `<div class="empty-state">Add a local video path or use the demo video to create the guided workspace.</div>`;
      loadSelectedVideoPreview();
      renderBrowserPreviewCard();
      renderGuidedStart();
      renderConfigPreview();
    }

    function renderJobs() {
      const jobCenter = jobCenterStateFromSnapshot({ jobs: state.jobs, selectedJobId: state.selectedJobId });
      const activeCount = jobCenter.activeJobsCount;
      const activeLabel = `${activeCount} active`;
      $("#jobSummary").textContent = activeLabel;
      if ($("#mainJobSummary")) $("#mainJobSummary").textContent = activeLabel;
      renderShellIndicators();

      if (state.errors.jobs) {
        const markup = `<div class="error-state">${escapeHtml(state.errors.jobs)}</div>`;
        $("#jobList").innerHTML = markup;
        if ($("#mainJobList")) $("#mainJobList").innerHTML = markup;
        renderWorkflowStepper();
        return;
      }

      const markup = jobCenter.recentJobs.length
        ? jobCenter.recentJobs
            .map((job) => {
              const id = job.id;
              const progress = job.progress.percent;
              const progressText = jobProgressText(job);
              const status = job.status || "unknown";
              const selected = id && id === state.selectedJobId;
              const diagnostics = [
                job.stale?.stale ? job.stale.label : "",
                job.failure?.message,
                job.latestEvent?.message,
                job.rawJob?.error,
                job.rawJob?.message,
                job.rawJob?.vectorUnavailableReason,
                job.rawJob?.vector_unavailable_reason,
                job.rawJob?.rasterOnlyReason,
                job.rawJob?.raster_only_reason,
              ].filter(Boolean);
              return `
                <button class="artifact-row job-choice ${selected ? "is-selected" : ""}" type="button" data-job-id="${escapeAttribute(id)}" aria-pressed="${selected}">
                  <strong>${escapeHtml(job.type || "job")}</strong>
                  ${statusChip(status, status, /complete|succeeded/.test(String(status).toLowerCase()))}
                  <span class="row-meta">${escapeHtml(id || "no id reported")} - ${escapeHtml(job.phase || job.latestEvent?.message || status)}</span>
                  <div class="job-progress" role="group" aria-label="${escapeAttribute(`${job.type || "job"} progress`)}">
                    <div class="job-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}">
                      <div class="job-progress-bar" style="--progress: ${progress}%"></div>
                    </div>
                    <span class="job-progress-text">${escapeHtml(progressText)}${diagnostics.length ? ` - ${escapeHtml(diagnostics.join(" "))}` : ""}</span>
                  </div>
                </button>
              `;
            })
            .join("")
        : `<div class="empty-state">Jobs will appear here with status, progress, and export diagnostics.</div>`;
      $("#jobList").innerHTML = markup;
      if ($("#mainJobList")) $("#mainJobList").innerHTML = markup;
      renderWorkflowStepper();
    }

    function renderSelectedJobFacts() {
      const job = selectedJob();
      const statusChipElement = $("#runStatus");
      const mainStatusChipElement = $("#mainRunStatus");
      const cancelButton = $("#cancelJobButton");
      const mainCancelButton = $("#mainCancelJobButton");
      const failedActionGroups = [$("#failedRunActions"), $("#mainFailedRunActions")].filter(Boolean);
      if (!job) {
        statusChipElement.textContent = "No run";
        statusChipElement.className = "status-chip is-muted";
        if (mainStatusChipElement) {
          mainStatusChipElement.textContent = "No run";
          mainStatusChipElement.className = "status-chip is-muted";
        }
        cancelButton.disabled = true;
        cancelButton.textContent = "Cancel run";
        if (mainCancelButton) {
          mainCancelButton.disabled = true;
          mainCancelButton.textContent = "Cancel run";
        }
        failedActionGroups.forEach((group) => {
          group.hidden = true;
        });
        const facts = {
          status: "select or start a run",
          provider: "not reported",
          progress: "0%",
          updated: "not reported",
        };
        setFacts($("#selectedJobFacts"), facts);
        if ($("#mainSelectedJobFacts")) setFacts($("#mainSelectedJobFacts"), facts);
        return;
      }

      const lifecycle = normalizeJobLifecycle({ ...job, events: state.jobEvents });
      const status = lifecycle.status || "unknown";
      statusChipElement.textContent = status;
      statusChipElement.className = `status-chip ${statusClass(status, /succeeded|complete/.test(String(status).toLowerCase()))}`;
      if (mainStatusChipElement) {
        mainStatusChipElement.textContent = status;
        mainStatusChipElement.className = statusChipElement.className;
      }
      const normalizedStatus = String(status).toLowerCase();
      const cancelDisabled = !lifecycle.actions.canCancel || normalizedStatus === "cancel_requested";
      const terminalFailure = isFailedJobStatus(normalizedStatus);
      const hasSelectedRun = Boolean(lifecycle.id);
      cancelButton.disabled = cancelDisabled;
      cancelButton.textContent = normalizedStatus === "cancel_requested" ? "Cancel requested" : "Cancel run";
      if (mainCancelButton) {
        mainCancelButton.disabled = cancelDisabled;
        mainCancelButton.textContent = normalizedStatus === "cancel_requested" ? "Cancel requested" : "Cancel run";
      }
      failedActionGroups.forEach((group) => {
        group.hidden = !hasSelectedRun;
        group.querySelectorAll("#runAgainButton, #mainRunAgainButton, #changeSetupButton, #mainChangeSetupButton, #chooseModelButton, #mainChooseModelButton").forEach((button) => {
          button.hidden = !terminalFailure;
        });
      });
      const payload = job.payload || {};
      const result = job.result || {};
      const facts = {
        id: lifecycle.id,
        type: lifecycle.type || "job",
        provider: lifecycle.provider.displayLabel || payload.mask_provider || jobConfig(job)?.provider?.name || "not reported",
        progress: lifecycle.progress.known ? `${lifecycle.progress.percent}%` : `${lifecycle.progress.percent}% estimated`,
        phase: lifecycle.phase || "not reported",
        artifacts: state.jobArtifacts.length,
        objects: result.scene?.objects ?? result.objects ?? state.reviewTracks.length,
        "last event": lifecycle.latestEvent.createdAt || job.lastEventAt || job.last_event_at || "not reported",
        updated: job.updated_at || job.updatedAt || "not reported",
      };
      if (lifecycle.stale?.stale) facts.watchdog = lifecycle.stale.label;
      setFacts($("#selectedJobFacts"), facts);
      if ($("#mainSelectedJobFacts")) setFacts($("#mainSelectedJobFacts"), facts);
    }

    function emptyEventLogMarkup(job, errorMessage = "") {
      const lifecycle = job ? normalizeJobLifecycle({ ...job, events: state.jobEvents }) : null;
      const detail = job
        ? `Selected run ${lifecycle?.id || jobIdentifier(job) || ""} is ${lifecycle?.status || job.status || "unknown"}; no job events were returned by the backend yet.`
        : "Select or start a run to show backend events.";
      if (errorMessage) {
        return `<div class="error-state">Could not load job events: ${escapeHtml(errorMessage)}</div>`;
      }
      return `<div class="empty-state">${escapeHtml(detail)}</div>`;
    }

    function renderEventLog() {
      const job = selectedJob();
      const events = state.jobEvents.length ? state.jobEvents : asArray(job?.events);
      const errorMessage = state.errors.selectedJob || "";
      const countLabel = `${events.length} event${events.length === 1 ? "" : "s"}`;
      const markup = `${eventLogOverviewMarkup(job, events, errorMessage)}${events.length ? eventRowsMarkup(events) : emptyEventLogMarkup(job, errorMessage)}`;
      $("#eventCount").textContent = countLabel;
      $("#jobEventLog").innerHTML = markup;
      if ($("#mainEventCount")) $("#mainEventCount").textContent = countLabel;
      if ($("#mainJobEventLog")) $("#mainJobEventLog").innerHTML = markup;
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
              const contentUrl = safeLocalContentUrl(artifact.contentUrl);
              const contentLink = contentUrl
                ? `<a class="artifact-link" href="${escapeAttribute(contentUrl)}" target="_blank" rel="noopener noreferrer">Open</a>`
                : artifact.contentUrl
                  ? `<span class="artifact-link" aria-disabled="true">Blocked remote link</span>`
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

    function libraryAssetRoute() {
      const params = new URLSearchParams();
      const query = $("#librarySearch")?.value?.trim();
      const tag = $("#libraryTagFilter")?.value?.trim();
      if (query) params.set("q", query);
      if (tag) params.set("tag", tag);
      const suffix = params.toString();
      return suffix ? `/api/library/assets?${suffix}` : "/api/library/assets";
    }

    function libraryArtifactIsSaveable(artifact) {
      return Boolean(artifact?.id && LIBRARY_SAVEABLE_ARTIFACT_KINDS.has(String(artifact.kind || "")));
    }

    function librarySourceArtifacts() {
      return state.jobArtifacts.filter(libraryArtifactIsSaveable);
    }

    function libraryUnsupportedArtifactCount() {
      return state.jobArtifacts.filter((artifact) => artifact?.id && !libraryArtifactIsSaveable(artifact)).length;
    }

    function selectedLibraryArtifactId(sourceArtifacts = librarySourceArtifacts()) {
      if (!state.selectedLibraryArtifactId || !sourceArtifacts.some((artifact) => artifact.id === state.selectedLibraryArtifactId)) {
        state.selectedLibraryArtifactId = sourceArtifacts[0]?.id || "";
      }
      return state.selectedLibraryArtifactId;
    }

    function selectedLibraryCollectionId() {
      if (
        !state.selectedLibraryCollectionId ||
        !state.libraryCollections.some((collection) => collection.id === state.selectedLibraryCollectionId)
      ) {
        state.selectedLibraryCollectionId = state.libraryCollections[0]?.id || "";
      }
      return state.selectedLibraryCollectionId;
    }

    function selectedLibraryAsset() {
      return state.libraryAssets.find((asset) => asset.id === state.selectedLibraryAssetId) || state.libraryAssets[0] || null;
    }

    function libraryTagsFromInput() {
      return String($("#libraryAssetTags")?.value || "")
        .split(/[,\s]+/)
        .map((tag) => tag.trim())
        .filter(Boolean);
    }

    function libraryRightsStatus(asset) {
      if (asset?.creatorApproved && asset?.commercialUseStatus === "approved") return "approved";
      return asset?.commercialUseStatus || asset?.creatorApprovalStatus || "review_required";
    }

    function renderAssetLibraryPanel() {
      const status = $("#libraryStatus");
      const sourceArtifacts = librarySourceArtifacts();
      const unsupportedArtifactCount = libraryUnsupportedArtifactCount();
      if (state.errors.library) {
        status.textContent = "Unavailable";
        status.className = "status-chip is-bad";
      } else {
        status.textContent = `${state.libraryAssets.length} saved`;
        status.className = `status-chip ${state.libraryAssets.length ? "is-ready" : "is-muted"}`;
      }

      const libraryError = $("#libraryError");
      libraryError.hidden = !state.errors.library;
      libraryError.textContent = state.errors.library || "";

      const artifactNotice = $("#libraryArtifactNotice");
      artifactNotice.hidden = unsupportedArtifactCount === 0;
      artifactNotice.textContent = unsupportedArtifactCount
        ? `${unsupportedArtifactCount} current artifacts are diagnostics, logs, or unsupported files and cannot be saved as motion layers.`
        : "";

      const selectedArtifactId = selectedLibraryArtifactId(sourceArtifacts);
      const artifactSelect = $("#libraryArtifactSelect");
      artifactSelect.disabled = !sourceArtifacts.length;
      artifactSelect.innerHTML = sourceArtifacts.length
        ? sourceArtifacts
            .map((artifact) => {
              const relPath = artifact.metadata?.rel_path || artifact.path || artifact.kind || artifact.id;
              const selected = artifact.id === selectedArtifactId ? " selected" : "";
              return `<option value="${escapeAttribute(artifact.id)}"${selected}>${escapeHtml(`${artifact.kind || "artifact"} - ${relPath}`)}</option>`;
            })
            .join("")
        : `<option value="">No reusable layer/export artifacts</option>`;
      $("#saveLibraryAssetButton").disabled = !state.selectedProjectId || !sourceArtifacts.length;

      if (!state.selectedLibraryAssetId || !state.libraryAssets.some((asset) => asset.id === state.selectedLibraryAssetId)) {
        state.selectedLibraryAssetId = state.libraryAssets[0]?.id || "";
      }
      const selectedAsset = selectedLibraryAsset();
      const collectionId = selectedLibraryCollectionId();
      $("#addLibraryAssetToCollectionButton").disabled = !selectedAsset || !state.libraryCollections.length;

      $("#libraryAssetList").innerHTML = state.libraryAssets.length
        ? state.libraryAssets
            .map((asset) => {
              const selected = asset.id === state.selectedLibraryAssetId;
              const details = [
                asset.type,
                asset.license || "license not reported",
                asset.licenseScope || "scope unknown",
                asArray(asset.tags).length ? `tags: ${asset.tags.join(", ")}` : "",
              ]
                .filter(Boolean)
                .join(" - ");
              return `
                <button class="library-row ${selected ? "is-selected" : ""}" type="button" data-library-asset-id="${escapeAttribute(asset.id)}" aria-pressed="${selected}">
                  <strong>${escapeHtml(asset.title || asset.id)}</strong>
                  ${statusChip(libraryRightsStatus(asset), libraryRightsStatus(asset), asset.creatorApproved && asset.commercialUseStatus === "approved")}
                  <span class="row-meta">${escapeHtml(details)}</span>
                </button>
              `;
            })
            .join("")
        : `<div class="empty-state">${escapeHtml(state.errors.library || "Save a generated artifact as a reusable motion layer after a run.")}</div>`;

      const collectionSelect = $("#libraryCollectionSelect");
      collectionSelect.innerHTML = state.libraryCollections.length
        ? state.libraryCollections
            .map((collection) => {
              const selected = collection.id === collectionId ? " selected" : "";
              return `<option value="${escapeAttribute(collection.id)}"${selected}>${escapeHtml(collection.title || collection.id)}</option>`;
            })
            .join("")
        : `<option value="">No collection</option>`;
      $("#libraryCollectionList").innerHTML = state.libraryCollections.length
        ? state.libraryCollections
            .map(
              (collection) => `
                <div class="library-row">
                  <strong>${escapeHtml(collection.title || collection.id)}</strong>
                  ${statusChip(`${collection.assetCount || 0} layers`, "ready", true)}
                  <span class="row-meta">${escapeHtml(collection.description || collection.id)}</span>
                </div>
              `,
            )
            .join("")
        : `<div class="empty-state">Create a brand collection before assembling packs.</div>`;

      $("#libraryPackForm button").disabled = !state.libraryCollections.length;
      $("#libraryPackList").innerHTML = state.libraryPacks.length
        ? state.libraryPacks
            .map(
              (pack) => `
                <div class="library-row">
                  <strong>${escapeHtml(pack.title || pack.id)}</strong>
                  ${statusChip(`${pack.assetCount || 0} approved`, pack.assetCount ? "ready" : "warn", pack.assetCount > 0)}
                  <span class="row-meta">${escapeHtml(`collection: ${pack.collectionId || "not reported"}`)}</span>
                </div>
              `,
            )
            .join("")
        : `<div class="empty-state">Creator-approved packs appear after all selected collection assets pass rights checks.</div>`;
    }

    function artifactById(id) {
      const wanted = String(id || "");
      return state.jobArtifacts.find((artifact) => String(artifact.id || "") === wanted) || null;
    }

    function candidatePreviewImage(candidate, key, label) {
      const artifact = artifactById(candidate?.[key]);
      const contentUrl = safeLocalContentUrl(artifact?.contentUrl);
      return contentUrl ? `<img src="${escapeAttribute(contentUrl)}" alt="${escapeAttribute(label)}" loading="lazy" />` : "";
    }

    function candidatePreviewSlot(candidate, key, label) {
      const image = candidatePreviewImage(candidate, key, label);
      return `
        <div class="candidate-preview-slot">
          ${image || `<span>${escapeHtml(label)}</span>`}
        </div>
      `;
    }

    function candidateScoreLabel(candidate, key, label) {
      return typeof candidate?.[key] === "number" ? `${label} ${Math.round(candidate[key] * 100)}%` : "";
    }

    function renderCandidateSummary() {
      const summary = state.jobReview?.candidateSummary || null;
      const candidates = reviewCandidates();
      syncCandidateSelection(candidates);
      const filters = readCandidateFilters();
      const visibleCandidates = filterReviewCandidates(candidates, state.candidateSelection, filters);
      const selectedIds = selectedCandidateIds(candidates);
      const selectedCount = selectedIds.length;
      const statusCounts = candidateStatusCounts(candidates, state.candidateSelection);
      const candidateCount = summary?.candidateCount ?? candidates.length;
      const provider = summary?.providerName || summary?.provider || "none";
      const qualityPreset = summary?.qualityPreset || "unknown";
      const suggestions = candidateRetrySuggestions({ candidates, visibleCandidates, summary, filters });
      const trackButton = $("#trackSelectedCandidatesButton");
      const status = $("#candidateActionStatus");
      trackButton.disabled = !state.selectedJobId || selectedCount === 0 || state.candidateTrackingStatus === "tracking";
      trackButton.textContent = state.candidateTrackingStatus === "tracking" ? "Tracking..." : "Track selected";
      status.textContent =
        state.candidateTrackingStatus && state.candidateTrackingStatus !== "tracking"
          ? state.candidateTrackingStatus
          : candidates.length
            ? `${selectedCount} kept, ${statusCounts.needsReview} need review, ${statusCounts.rejected} rejected.`
            : "No API candidates loaded.";
      $("#candidateSummaryStatus").textContent = candidates.length
        ? `${selectedCount}/${candidateCount} kept`
        : summary
          ? "No candidates"
          : "Not loaded";
      $("#candidateSummaryStatus").className = `status-chip ${candidates.length ? "is-ready" : summary ? "is-warn" : "is-muted"}`;
      $("#candidateRetrySuggestions").innerHTML = suggestions.length
        ? suggestions
            .map(
              (suggestion) => `
                <div class="suggestion-row candidate-suggestion is-${escapeAttribute(suggestion.tone || "warn")}">
                  <strong>${escapeHtml(suggestion.title)}</strong>
                  <span class="row-meta">${escapeHtml(suggestion.detail)}</span>
                </div>
              `,
            )
            .join("")
        : "";
      $("#candidateSummaryList").innerHTML = visibleCandidates.length
        ? visibleCandidates
            .map((candidate) => {
              const id = candidateId(candidate);
              const selected = state.candidateSelection[id] === true;
              const rejected = candidateRejected(candidate);
              const statuses = candidateStatusItems(candidate, { selected });
              const box = candidate.box
                ? `box x:${candidate.box.x}, y:${candidate.box.y}, ${candidate.box.w}x${candidate.box.h}`
                : "geometry unavailable";
              const sourceDetail = [
                candidate.source || provider,
                candidate.providerName ? `via ${candidate.providerName}` : "",
                candidate.frameIndex != null ? `frame ${candidate.frameIndex}` : "",
              ]
                .filter(Boolean)
                .join(" - ");
              const scoreDetail = [
                box,
                candidateScoreLabel(candidate, "confidence", "confidence"),
                candidateScoreLabel(candidate, "stabilityScore", "stable"),
                candidateScoreLabel(candidate, "motionScore", "motion"),
                candidateScoreLabel(candidate, "frameCoverageEstimate", "coverage"),
              ]
                .filter(Boolean)
                .join(" - ");
              const preview = [
                candidatePreviewSlot(candidate, "thumbnailArtifactId", "thumbnail"),
                candidatePreviewSlot(candidate, "maskPreviewArtifactId", "mask"),
              ]
                .join("");
              return `
                <div class="candidate-row ${selected ? "is-selected" : ""} ${rejected ? "is-rejected" : ""}" data-candidate-row="${escapeAttribute(id)}">
                  <div class="candidate-preview">${preview}</div>
                  <div class="candidate-body">
                    <div class="candidate-topline">
                      <div class="candidate-title-group">
                        <strong>${escapeHtml(candidate.label || id || "candidate")}</strong>
                        <span class="row-meta">${escapeHtml(sourceDetail || id || "candidate source")}</span>
                      </div>
                      <div class="candidate-status-list">${statuses.map(candidateStatusChip).join("")}</div>
                    </div>
                    <span class="row-meta">${escapeHtml(scoreDetail || `quality ${qualityPreset}`)}</span>
                    <div class="track-actions">
                      <label class="track-toggle">
                        <input type="checkbox" data-candidate-select="${escapeAttribute(id)}" ${selected ? "checked" : ""} ${candidateSelectable(candidate) ? "" : "disabled"} />
                        <span>keep</span>
                      </label>
                      ${candidate.rejectionReason ? detailChip(candidate.rejectionReason) : ""}
                      ${asArray(candidate.warnings).map((warning) => detailChip(warning)).join("")}
                    </div>
                  </div>
                </div>
              `;
            })
            .join("")
        : candidates.length
          ? `<div class="empty-state">No API candidates match the current filters.</div>`
          : summary
          ? `<div class="empty-state">No discovery candidates were reported for this run.</div>`
          : `<div class="empty-state">API candidates appear here after discovery writes candidates.json.</div>`;
      renderWorkflowStepper();
    }

    function renderTrackList() {
      $("#trackCount").textContent = `${state.reviewTracks.length} track${state.reviewTracks.length === 1 ? "" : "s"}`;
      $("#trackList").innerHTML = state.reviewTracks.length
        ? state.reviewTracks
            .map((track) => {
              const visible = isTrackVisibleInReview(track);
              const exportIncluded = isTrackExportIncluded(track);
              const selectedForMerge = state.mergeSelection.has(track.id);
              const selected = state.selectedCorrectionTrackId === track.id;
              const confidence = typeof track.confidence === "number" ? `${Math.round(track.confidence * 100)}%` : "not reported";
              const warnings = asArray(track.warnings);
              return `
                <div class="track-row ${visible ? "" : "is-muted"} ${track.deleted ? "is-deleted" : ""} ${selected ? "is-selected" : ""}" data-track-row="${escapeAttribute(track.id)}" style="--track-color: ${escapeAttribute(track.color)}">
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
      renderWorkflowStepper();
    }

    function studioWorkflowStep(activeStep = normalizeWorkflowStepId(state.activeWorkflowStep)) {
      return workflowScreenForStep(activeStep);
    }

    function renderStudioProgress(activeStep = normalizeWorkflowStepId(state.activeWorkflowStep)) {
      const snapshot = workflowSnapshot();
      const readiness = workflowReadinessFromSnapshot(snapshot);
      const activeIndex = workflowStepIndex(activeStep);
      document.querySelectorAll("#studioProgressStepper [data-studio-step]").forEach((item, index) => {
        const stepId = normalizeWorkflowStepId(item.dataset.studioStep, "choose_goal");
        const stepIndex = workflowStepIndex(stepId);
        const stepReadiness = readiness[stepId] || {};
        const active = index === activeIndex;
        const complete = Boolean(stepReadiness.complete) && stepIndex < activeIndex;
        const button = item.querySelector("[data-workflow-step]");
        item.classList.toggle("is-complete", complete);
        item.classList.toggle("is-active", active);
        item.classList.toggle("is-pending", !active && !complete);
        item.setAttribute("aria-current", active ? "step" : "false");
        if (button) {
          button.disabled = false;
          button.setAttribute("aria-pressed", String(active));
          if (active) button.setAttribute("aria-current", "step");
          else button.removeAttribute("aria-current");
          button.setAttribute("title", stepReadiness.message || "");
        }
      });
    }

    function studioConfidenceLabel(value) {
      return typeof value === "number" ? `${Math.round(value * 100)}%` : "not reported";
    }

    function studioTrackStatus(track) {
      const status = String(track?.exportStatus || "").toLowerCase();
      if (track?.deleted || /deleted|rejected|failed|fallback_raster/.test(status)) {
        return { label: /background|ground|floor|lawn|fence|plant/.test(`${track?.label || ""} ${track?.warnings || ""}`.toLowerCase()) ? "Rejected background" : "Rejected", tone: "bad" };
      }
      if (trackUsesStaticKeyframeFallback(track)) return { label: "Static fallback blocked", tone: "bad" };
      if (isTrackExportIncluded(track)) {
        const motion = trackMotionMetrics(track);
        return motion.moving ? { label: "Reviewed moving track", tone: "ready" } : { label: "Reviewed for export", tone: "ready" };
      }
      return { label: "Needs review", tone: "warn" };
    }

    function studioCandidateStatus(candidate) {
      const reason = candidateReasonText(candidate);
      if (candidateRejected(candidate)) {
        return { label: /background|whole_frame|wall|floor|ground|lawn|plant|fence/.test(reason) ? "Rejected background" : "Rejected", tone: "bad" };
      }
      return { label: "Needs review", tone: "warn" };
    }

    function studioObjectRows() {
      const rows = state.reviewTracks.map((track, index) => {
        const objectId = trackObjectId(track);
        const status = studioTrackStatus(track);
        return {
          kind: "track",
          id: track.id,
          objectId,
          label: track.label || objectId || `Object ${index + 1}`,
          confidence: track.confidence,
          frameCount: toInteger(track.frameCount, toInteger(track.visibleFrameCount, 0)),
          motion: trackMotionMetrics(track),
          staticFallback: trackUsesStaticKeyframeFallback(track),
          color: track.color || TRACK_COLORS[index % TRACK_COLORS.length],
          visible: isTrackVisibleInReview(track),
          exportIncluded: isTrackExportIncluded(track),
          exportable: track.exportable !== false && track.demoMode !== true && !track.deleted,
          status,
        };
      });
      const seen = new Set(rows.map((row) => row.objectId).filter(Boolean));
      for (const candidate of reviewCandidates()) {
        const objectId = String(candidate.objectId || candidate.object_id || candidateId(candidate)).trim();
        if (!objectId || seen.has(objectId)) continue;
        const index = rows.length;
        rows.push({
          kind: "candidate",
          id: candidateId(candidate),
          objectId,
          label: candidate.label || objectId || `Candidate ${index + 1}`,
          confidence: candidateConfidenceScore(candidate),
          frameCount: toInteger(candidate.frameCount ?? candidate.frame_count, 0) || toInteger(state.jobReview?.source?.frameCount ?? state.jobReview?.source?.frame_count, 0) || 450,
          color: TRACK_COLORS[index % TRACK_COLORS.length],
          visible: false,
          exportIncluded: false,
          exportable: false,
          status: studioCandidateStatus(candidate),
        });
        seen.add(objectId);
      }
      return rows.slice(0, 12);
    }

    function renderStudioReviewPanel() {
      const list = $("#studioObjectList");
      const summary = $("#studioReviewSummary");
      if (!list || !summary) return;
      const rows = studioObjectRows();
      const reviewedCount = rows.filter((row) => row.kind === "track" && row.exportIncluded && row.exportable).length;
      const movingReviewedCount = rows.filter((row) => row.kind === "track" && row.exportIncluded && row.exportable && row.motion?.moving).length;
      summary.textContent = rows.length
        ? movingReviewedCount
          ? `${movingReviewedCount} moving track${movingReviewedCount === 1 ? "" : "s"} ready for MotionJSON export`
          : `${reviewedCount} reviewed object${reviewedCount === 1 ? "" : "s"} ready`
        : "Object masks appear here after a run completes.";
      const job = selectedJob();
      const exported = state.exportResult?.jobId === state.selectedJobId ? state.exportResult : null;
      const validation = state.exportValidation?.jobId === state.selectedJobId ? state.exportValidation : null;
      const exportState = exported || validation || {};
      const status = exported?.validation || validation?.validation || null;
      const { includedIds, pendingIds } = buildExportPanelSummary({
        exportState,
        reviewExport: state.jobReview?.export,
        reviewTracks: state.reviewTracks,
        reviewObjects: state.jobReview?.objects,
      });
      const staticFallbackCount = state.reviewTracks.filter((track) => isTrackExportIncluded(track) && trackUsesStaticKeyframeFallback(track)).length;
      const exportAction = exportActionState({
        job,
        includedIds,
        pendingIds,
        trackCount: state.reviewTracks.length,
        status,
        staticFallbackCount,
      });
      const canValidate = Boolean(state.selectedJobId && reviewedCount);
      const canExport = !exportAction.disabled;
      $("#studioExportAllButton").disabled = !canExport;
      $("#studioExportAllButton").textContent = exportAction.label || "Export MotionJSON";
      $("#studioExportSelectedButton").disabled = !canValidate;
      $("#studioCreatePackageButton").disabled = !canExport;
      if ($("#studioValidateExportButton")) {
        $("#studioValidateExportButton").disabled = !canValidate;
        $("#studioValidateExportButton").textContent = status ? "Validate again" : "Validate export";
      }
      if ($("#studioExportMotionJsonButton")) {
        $("#studioExportMotionJsonButton").disabled = !canExport;
        $("#studioExportMotionJsonButton").textContent = exportAction.label || "Export MotionJSON";
        $("#studioExportMotionJsonButton").dataset.tooltip = exportAction.reason || "Write validated MotionJSON artifacts";
      }
      if ($("#studioExportStatus")) {
        $("#studioExportStatus").textContent = !job ? "No run" : status?.ok === true ? "Valid" : status ? "Needs review" : "Not validated";
        $("#studioExportStatus").className = `status-chip ${!job ? "is-muted" : status?.ok === true ? "is-ready" : status ? "is-warn" : "is-muted"}`;
      }
      if ($("#studioExportChecklistNote")) {
        $("#studioExportChecklistNote").textContent = exportAction.reason || (status?.ok === true ? "Moving tracks are validated for MotionJSON export." : "Validate moving tracks before writing MotionJSON.");
      }
      if ($("#studioExportChecklist")) {
        $("#studioExportChecklist").innerHTML = exportReadinessSummary({
          job,
          includedIds,
          pendingIds,
          reviewTracks: state.reviewTracks,
          status,
        })
          .map((row) => {
            const className = row.status === "ready" ? "is-ready" : row.status === "blocked" ? "is-bad" : "is-warn";
            return `
              <div class="studio-export-check-row ${className}">
                <span aria-hidden="true"></span>
                <strong>${escapeHtml(row.title)}</strong>
                <small>${escapeHtml(row.detail)}</small>
              </div>
            `;
          })
          .join("");
      }
      list.innerHTML = rows.length
        ? rows
            .map((row, index) => {
              const selected = row.kind === "track" && (state.selectedCorrectionTrackId === row.id || state.selectedCorrectionTrackId === row.objectId);
              const frames = row.frameCount ? `${row.frameCount} frames` : row.kind === "track" ? trackCoverageLabel(row) : "frames unavailable";
              const motionLabel = row.kind === "track"
                ? row.staticFallback
                  ? "static fallback blocked"
                  : row.motion?.moving
                    ? `${Math.round(row.motion.maxCenterShiftPx)} px motion`
                    : "motion not verified"
                : "candidate only";
              const statusTone = row.status.tone === "bad" ? "is-bad" : row.status.tone === "warn" ? "is-warn" : "";
              return `
                <div class="studio-object-row ${row.visible ? "" : "is-muted"} ${selected ? "is-selected" : ""}" data-studio-track-row="${row.kind === "track" ? escapeAttribute(row.id) : ""}" style="--studio-track-color: ${escapeAttribute(row.color)}">
                  <span class="studio-object-color" aria-hidden="true"></span>
                  <span class="studio-object-number">${index + 1}</span>
                  <span class="studio-object-copy">
                    <strong class="studio-object-title">${escapeHtml(row.label)}</strong>
                    <span class="studio-object-meta">Confidence ${escapeHtml(studioConfidenceLabel(row.confidence))} &nbsp; - &nbsp; ${escapeHtml(frames)} &nbsp; - &nbsp; ${escapeHtml(motionLabel)}</span>
                  </span>
                  <span class="studio-status-chip ${statusTone}">${escapeHtml(row.status.label)}</span>
                  <button
                    class="studio-icon-toggle"
                    type="button"
                    data-studio-track-visible="${row.kind === "track" ? escapeAttribute(row.id) : ""}"
                    data-visible="${row.visible ? "true" : "false"}"
                    aria-label="${escapeAttribute(row.visible ? `Hide ${row.label}` : `Show ${row.label}`)}"
                    aria-pressed="${row.visible ? "true" : "false"}"
                    ${row.kind === "track" ? "" : "disabled"}
                  ></button>
                  <input
                    class="studio-export-check"
                    type="checkbox"
                    data-studio-track-export="${row.kind === "track" ? escapeAttribute(row.id) : ""}"
                    aria-label="${escapeAttribute(`Export ${row.label}`)}"
                    ${row.exportIncluded ? "checked" : ""}
                    ${row.kind === "track" && row.exportable ? "" : "disabled"}
                  />
                </div>
              `;
            })
            .join("")
        : `<div class="empty-state">Start a run to review objects before export.</div>`;
    }

    function renderStudioShell(activeStep = normalizeWorkflowStepId(state.activeWorkflowStep)) {
      const resultMode = activeStep === "review_export";
      const prepareFormFirst = activeStep === "prompt_preview" && state.selectedPreset !== "trace_one_object";
      shell?.classList.toggle("is-result-mode", resultMode && !state.workflowDashboard);
      shell?.classList.toggle("is-prepare-form-first", prepareFormFirst && !state.workflowDashboard);
      renderStudioProgress(activeStep);
      renderStudioReviewPanel();
    }

    function relatedArtifactsForTrack(track) {
      const objectId = trackObjectId(track);
      return state.jobArtifacts.filter((artifact) => {
        const relPath = String(artifact.metadata?.rel_path || artifact.path || "");
        const artifactObject = String(artifact.object_id || artifact.objectId || artifact.metadata?.objectId || artifact.metadata?.object_id || "");
        return artifactObject === objectId || relPath.includes(`objects/${objectId}/`) || relPath.includes(`masks/${objectId}/`);
      });
    }

    function renderSelectedTrackDetail() {
      const track = state.reviewTracks.find((item) => item.id === state.selectedCorrectionTrackId) || state.reviewTracks[0] || null;
      if (track && !state.selectedCorrectionTrackId) state.selectedCorrectionTrackId = track.id;
      const status = track ? track.exportStatus || "review" : "No track";
      $("#selectedTrackStatus").textContent = status;
      $("#selectedTrackStatus").className = `status-chip ${track ? statusClass(status, isTrackExportIncluded(track)) : "is-muted"}`;
      if (!track) {
        $("#selectedTrackDetail").innerHTML = `<div class="empty-state">Select a completed run and choose a track to inspect correction and export state.</div>`;
        renderWorkflowStepper();
        return;
      }
      const frames = asArray(track.frames);
      const polygonFrames = frames.filter((frame) => asArray(frame.polygon).length >= 3).length;
      const motion = trackMotionMetrics(track);
      const motionSummary = trackUsesStaticKeyframeFallback(track)
        ? "static keyframe fallback blocked"
        : motion.moving
          ? `${Math.round(motion.maxCenterShiftPx)} px center shift across ${motion.visibleFrameCount} sampled frames`
          : "not verified from sampled frames";
      const warningChips = asArray(track.warnings).map((warning) => detailChip(warning)).join("");
      const relatedArtifacts = relatedArtifactsForTrack(track);
      const rights = track.rightsSummary || {};
      const sourceAttribution = rights.sourceAttribution || {};
      const rightsStatus = rights.commercialUseStatus || rights.creatorApprovalStatus || "not reported";
      const artifactLinks = relatedArtifacts
        .slice(0, 4)
        .map((artifact) => {
          const relPath = artifact.metadata?.rel_path || artifact.kind || artifact.id;
          const contentUrl = safeLocalContentUrl(artifact.contentUrl);
          return contentUrl
            ? `<a class="artifact-link" href="${escapeAttribute(contentUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(relPath)}</a>`
            : `<span>${escapeHtml(relPath)}</span>`;
        })
        .join("");
      $("#selectedTrackDetail").innerHTML = `
        <dl class="track-detail-grid">
          <dt>Object ID</dt><dd>${escapeHtml(track.objectId || track.id)}</dd>
          <dt>Source</dt><dd>${escapeHtml(track.source || track.providerName || "not reported")}</dd>
          <dt>Coverage</dt><dd>${escapeHtml(trackCoverageLabel(track))}</dd>
          <dt>Geometry</dt><dd>${escapeHtml(polygonFrames ? `${polygonFrames} polygon frame${polygonFrames === 1 ? "" : "s"}` : "box overlay")}</dd>
          <dt>Motion</dt><dd>${escapeHtml(motionSummary)}</dd>
          <dt>Preview</dt><dd>${escapeHtml(isTrackVisibleInReview(track) ? "visible" : "hidden")}</dd>
          <dt>Export</dt><dd>${escapeHtml(isTrackExportIncluded(track) ? "included" : "excluded")}</dd>
          <dt>Rights</dt><dd>${escapeHtml(rightsStatus)}</dd>
          <dt>License</dt><dd>${escapeHtml(rights.license || "not reported")}</dd>
          <dt>Attribution</dt><dd>${escapeHtml(sourceAttribution.displayText || (rights.attributionRequired ? "required" : "not reported"))}</dd>
        </dl>
        <div class="track-actions">
          ${detailChip(track.reviewSource || "review")}
          ${track.repairRequested ? detailChip("repair requested") : ""}
          ${track.deleted ? detailChip("deleted") : ""}
          ${track.mergedInto ? detailChip(`merged into ${track.mergedInto}`) : ""}
          ${warningChips}
        </div>
        ${
          artifactLinks
            ? `<div class="artifact-row"><strong>Related artifacts</strong><span class="row-meta">${artifactLinks}</span></div>`
            : `<div class="empty-state">No object-specific artifacts are linked to this track yet.</div>`
        }
      `;
      renderWorkflowStepper();
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
      const guidance = correctionGuidanceForTrack(selected, {
        promptCount,
        mergeSelectionSize: state.mergeSelection.size,
        status,
      });
      $("#correctionGuidance").innerHTML = `
        <div class="diagnostic-row is-${escapeAttribute(guidance.tone || "warn")}">
          <strong>${escapeHtml(guidance.title)}</strong>
          <span class="row-meta">${escapeHtml(guidance.items[0] || "Review the selected track before exporting.")}</span>
        </div>
        ${
          guidance.items.length > 1
            ? `<ul class="guidance-list">${guidance.items
                .slice(1)
                .map((item) => `<li>${escapeHtml(item)}</li>`)
                .join("")}</ul>`
            : ""
        }
      `;

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
      renderWorkflowStepper();
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
      renderWorkflowStepper();
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
      const captureMode = document.documentElement.dataset.capture || "";
      state.exportValidation = null;
      if (captureMode !== "export-success" && captureMode !== "copyable-snippet") state.exportResult = null;
      if (captureMode !== "copyable-snippet") state.exportCopiedHandoffId = "";
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

    function exportValidationMessageRows(messages) {
      return asArray(messages)
        .slice(0, 5)
        .map((message) => {
          const severity = message.severity === "bad" || message.severity === "error" ? "bad" : "warn";
          return `<div class="diagnostic-row is-${severity}"><strong>${escapeHtml(message.code || "export message")}</strong><span class="row-meta">${escapeHtml(message.message || message.suggestedAction || "review export state")}</span></div>`;
        })
        .join("");
    }

    function exportRouteLabel(value) {
      return String(value || "")
        .replace(/[_-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim() || "not selected";
    }

    function qualityRoutingRows(qualityRouting) {
      if (!qualityRouting) return "";
      const objects = asArray(qualityRouting.objects);
      const firstObject = objects[0] || {};
      const delivery = firstObject.selectedDelivery || {};
      const mp4Preview = qualityRouting.preview?.mp4Preview || {};
      const mp4Status = String(mp4Preview.status || "not requested");
      const mp4Class = mp4Status === "ready" ? "ready" : mp4Status === "error" ? "bad" : "warn";
      const routeSummary = objects.length
        ? `${objects.length} object route${objects.length === 1 ? "" : "s"} from cached quality scores`
        : "no object routes available";
      return `
        <div class="diagnostic-row is-${objects.length ? "ready" : "warn"}">
          <strong>quality routing</strong>
          <span class="row-meta">${escapeHtml(routeSummary)}</span>
        </div>
        ${
          objects.length
            ? `<div class="diagnostic-row is-ready"><strong>${escapeHtml(exportRouteLabel(firstObject.selectedOutput))}</strong><span class="row-meta">${escapeHtml(`delivery: ${exportRouteLabel(delivery.route || "raster_alpha_sequence")}`)}</span></div>`
            : ""
        }
        <div class="diagnostic-row is-${mp4Class}">
          <strong>MP4 preview ${escapeHtml(mp4Status)}</strong>
          <span class="row-meta">${escapeHtml(mp4Preview.reason || "local FFmpeg preview route checked")}</span>
        </div>
      `;
    }

    function qualityRoutingMatchesControls(qualityRouting) {
      if (!qualityRouting) return false;
      const controls = exportPayloadFromControls();
      return (
        String(qualityRouting.preset || "") === String(controls.preset || "") &&
        qualityRouting.includeMasks === controls.includeMasks &&
        qualityRouting.includeContours === controls.includeContours &&
        qualityRouting.includePreview === controls.includePreview
      );
    }

    function rightsWarningRows(rightsReport, exportWarnings) {
      const warnings = asArray(exportWarnings).length ? asArray(exportWarnings) : asArray(rightsReport?.warnings);
      if (!rightsReport && !warnings.length) return "";
      const summary = rightsReport?.summary || {};
      const status = summary.commercialUseApproved === true ? "ready" : "warn";
      const commercialDetail = summary.commercialUseApproved === true
        ? "commercial use approved for included objects"
        : `${asArray(summary.commercialUseReviewRequired).length || warnings.length} rights item${(asArray(summary.commercialUseReviewRequired).length || warnings.length) === 1 ? "" : "s"} need review`;
      const warningRows = warnings
        .slice(0, 4)
        .map((warning) => {
          const severity = warning.severity === "info" ? "warn" : warning.severity === "bad" ? "bad" : "warn";
          return `<div class="diagnostic-row is-${severity}"><strong>${escapeHtml(warning.code || "rights warning")}</strong><span class="row-meta">${escapeHtml(warning.message || warning.suggestedAction || "review rights metadata")}</span></div>`;
        })
        .join("");
      return `
        <div class="diagnostic-row is-${status}">
          <strong>rights and lineage</strong>
          <span class="row-meta">${escapeHtml(commercialDetail)}</span>
        </div>
        ${warningRows}
      `;
    }

    function clearExportPreflightState() {
      state.exportValidation = null;
      state.exportResult = null;
      state.exportCopiedHandoffId = "";
      renderExportPanel();
    }

    function renderExportPanel() {
      const job = selectedJob();
      const validation = state.exportValidation?.jobId === state.selectedJobId ? state.exportValidation : null;
      const exported = state.exportResult?.jobId === state.selectedJobId ? state.exportResult : null;
      const exportArtifactKinds = [
        "validated_motionjson_scene",
        "final_export_manifest",
        "export_validation_report",
        "export_quality_routing",
        "preview_overlay",
        "mp4_preview",
        "contours_boxes",
        "object_layer_pack",
        "remotion_plan",
        "website_package",
        "motionjson_export_zip",
      ];
      const storedExportArtifacts = state.jobArtifacts.filter((artifact) =>
        exportArtifactKinds.includes(artifact.kind),
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
      const staticFallbackCount = state.reviewTracks.filter((track) => isTrackExportIncluded(track) && trackUsesStaticKeyframeFallback(track)).length;
      const exportAction = exportActionState({ job, includedIds, pendingIds, trackCount: state.reviewTracks.length, status, staticFallbackCount });
      $("#exportStatus").textContent = !job ? "No run" : ok ? "Valid" : status ? "Needs review" : "Not validated";
      $("#exportStatus").className = `status-chip ${!job ? "is-muted" : ok ? "is-ready" : status ? "is-warn" : "is-muted"}`;
      $("#validateExportButton").disabled = !job;
      $("#validateExportButton").textContent = status ? "Validate again" : "Validate export";
      $("#exportMotionJsonButton").disabled = exportAction.disabled;
      $("#exportMotionJsonButton").textContent = exportAction.label;
      $("#exportMotionJsonButton").dataset.tooltip = exportAction.reason || "Write validated MotionJSON artifacts";
      $("#exportStatusSummary").innerHTML = exportReadinessSummaryCards({
        job,
        includedIds,
        pendingIds,
        reviewTracks: state.reviewTracks,
        status,
      });

      const exportArtifacts = asArray(exported?.assets).length ? asArray(exported?.assets) : storedExportArtifacts;
      const objectLayerPack = exportState.objectLayerPack || exported?.objectLayerPack || validation?.objectLayerPack || null;
      const handoffCards = exportHandoffCards({
        job,
        includedIds,
        pendingIds,
        trackCount: state.reviewTracks.length,
        assets: exportArtifacts,
        objectLayerPack,
        status,
        copiedId: state.exportCopiedHandoffId,
      });
      state.exportCopyPayloads = {};
      for (const card of handoffCards) {
        if (card.copyText) state.exportCopyPayloads[card.id] = card.copyText;
      }
      $("#exportHandoffCards").innerHTML = job
        ? handoffCards
            .map(
              (card) => `
                <div class="handoff-card is-${escapeAttribute(card.tone)}">
                  <div class="handoff-card-topline">
                    <strong>${escapeHtml(card.title)}</strong>
                    <span class="status-chip is-${escapeAttribute(card.tone)}">${escapeHtml(card.status)}</span>
                  </div>
                  <span class="row-meta">${escapeHtml(card.detail)}</span>
                  ${card.copied ? `<span class="copy-status">Copied to clipboard.</span>` : ""}
                  <button
                    type="button"
                    class="${card.ready ? "" : "primary-action"}"
                    data-export-handoff-action="${escapeAttribute(card.action)}"
                    data-export-handoff-id="${escapeAttribute(card.id)}"
                    ${card.url ? `data-export-handoff-url="${escapeAttribute(card.url)}"` : ""}
                    ${card.disabled ? "disabled" : ""}
                  >${escapeHtml(card.actionLabel)}</button>
                </div>
              `,
            )
            .join("")
        : "";
      const nextStepsText = exported ? exportNextStepText({ exportState, assets: exportArtifacts, objectLayerPack }) : "";
      if (nextStepsText) state.exportCopyPayloads.nextSteps = nextStepsText;
      $("#exportNextSteps").innerHTML = nextStepsText
        ? `
            <div class="export-next-steps-card">
              <div class="handoff-card-topline">
                <strong>Next steps</strong>
                <button class="mini-action" type="button" data-export-handoff-action="copy" data-export-handoff-id="nextSteps">${state.exportCopiedHandoffId === "nextSteps" ? "Copied" : "Copy"}</button>
              </div>
              ${state.exportCopiedHandoffId === "nextSteps" ? `<span class="copy-status">Next steps copied to clipboard.</span>` : ""}
              <textarea readonly>${escapeHtml(nextStepsText)}</textarea>
            </div>
          `
        : "";
      const artifactLinks = exportArtifacts
        .map((asset) => {
          const relPath = asset.metadata?.rel_path || asset.path || asset.kind || asset.id;
          const contentUrl = safeLocalContentUrl(asset.contentUrl);
          if (!contentUrl) return "";
          return `<a class="artifact-link" href="${escapeAttribute(contentUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(relPath)}</a>`;
        })
        .filter(Boolean)
        .join("");
      const issueRows = exportIssueRows(status?.issues);
      const validationMessageRows = exportValidationMessageRows(exportState.exportValidationMessages);
      const candidateRouting = exportState.qualityRouting || storedValidationArtifact?.metadata?.qualityRouting;
      const routingRows = qualityRoutingMatchesControls(candidateRouting)
        ? qualityRoutingRows(candidateRouting)
        : candidateRouting
          ? `<div class="diagnostic-row is-warn"><strong>quality routing changed</strong><span class="row-meta">Validate again to refresh routes for the current export settings.</span></div>`
          : "";
      const rightsRows = rightsWarningRows(exportState.rightsSummary || storedValidationArtifact?.metadata?.rightsSummary || state.jobReview?.rightsSummary, exportState.exportWarnings);
      const gateRows = exportGateSummary({ includedIds, excludedIds, pendingIds, status })
        .map(
          (row) => `
            <div class="diagnostic-row is-${escapeAttribute(row.tone)} export-gate-row">
              <strong>${escapeHtml(row.title)}</strong>
              <span class="row-meta">${escapeHtml(row.detail)}</span>
            </div>
          `,
        )
        .join("");
      $("#exportSummary").innerHTML = job
        ? `
            ${gateRows}
            ${issueRows}
            ${validationMessageRows}
            ${rightsRows}
            ${routingRows}
            ${artifactLinks ? `<div class="artifact-row"><strong>Export artifacts</strong><span class="row-meta export-artifact-links">${artifactLinks}</span></div>` : ""}
          `
        : `<div class="empty-state">Select a completed run before validating or exporting MotionJSON.</div>`;
      renderWorkflowStepper();
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
      renderShellIndicators();
      renderWorkflowStepper();
    }

    function renderJobReview() {
      renderSelectedJobFacts();
      renderEventLog();
      renderArtifactBrowser();
      renderAssetLibraryPanel();
      renderCandidateSummary();
      renderCorrectionPanel();
      renderTrackList();
      renderSelectedTrackDetail();
      renderExportPanel();
      renderCorrectionHistory();
      renderFallbackDiagnostics();
      renderTimelinePanel();
      renderWorkflowStepper();
      scheduleDrawOverlay();
    }

    function renderMaskProviderOptions() {
      const select = $("#maskProviderSelect");
      const defaults = state.runDefaults?.defaults || {};
      const debugMock = Boolean(state.health?.mockMode);
      const providerNames = (state.runDefaults?.maskProviders || ["external", "mock", "motion", "sam2", "sam2-hosted", "sam2-local", "sam3-hosted", "sam3-local", "threshold"]).filter(
        (provider) => debugMock || provider !== "mock",
      );
      const fallbackDefault = debugMock ? "mock" : "sam2-local";
      const enginePlan = guidedEnginePlan({ preset: state.selectedPreset, modelConnectionId: state.selectedModelSetupProviderId });
      const current =
        select.dataset.userSelected === "true"
          ? select.value
          : enginePlan.providerName || PRESETS[state.selectedPreset]?.maskProvider || (defaults.maskProvider === "mock" && !debugMock ? fallbackDefault : defaults.maskProvider) || fallbackDefault;
      select.innerHTML = providerNames
        .map((provider) => {
          const capability = providerByName(provider, "mask_provider");
          const suffix = capability && !capability.available ? ` (${capability.status})` : "";
          return `<option value="${escapeAttribute(provider)}">${escapeHtml(provider + suffix)}</option>`;
        })
        .join("");
      select.value = providerNames.includes(current) ? current : providerNames.includes(fallbackDefault) ? fallbackDefault : defaults.maskProvider || providerNames[0] || "threshold";
    }

    function renderPresetFields() {
      const preset = PRESETS[state.selectedPreset] || PRESETS.auto_object_proposals;
      const enginePlan = guidedEnginePlan(collectFormState($));
      const sam3SingleObject = state.selectedPreset === "trace_one_object" && /^sam3-/.test(String(enginePlan.providerName || ""));
      const reviewingExisting = state.selectedPreset === "review_existing";
      const showLegacyTextProvider = state.selectedPreset === "text_detector" && state.workflowDashboard;
      const showAdvancedProviderInternals = Boolean(state.workflowDashboard);
      const showSceneSweepControls = state.selectedPreset === "trace_all_objects";
      const showPromptFields = state.selectedPreset === "trace_one_object";
      $("#presetSummary").textContent = preset.label;
      $("#presetSummary").className = "status-chip is-neutral";
      const isObjectDiscovery = state.selectedPreset === "auto_object_proposals" || state.selectedPreset === "trace_all_objects";
      $("#qualityPresetField").classList.toggle("is-hidden", !isObjectDiscovery);
      $("#traceEverythingDisclosure").classList.toggle("is-hidden", !isObjectDiscovery);
      $("#textPromptField").classList.toggle("is-hidden", state.selectedPreset !== "text_detector");
      $("#textDiscoveryProviderField").classList.toggle("is-hidden", !showLegacyTextProvider);
      if (state.selectedPreset === "text_detector" && showLegacyTextProvider) {
        const textProviderSelect = $("#textDiscoveryProviderSelect");
        if (textProviderSelect && (!textProviderSelect.value || textProviderSelect.value === "mock")) {
          textProviderSelect.value = "sam3-hosted";
        }
      }
      $("#classPresetField").classList.toggle("is-hidden", state.selectedPreset !== "class_detector");
      $("#classListField").classList.toggle("is-hidden", state.selectedPreset !== "class_detector");
      $("#externalMaskField").classList.toggle("is-hidden", state.selectedPreset !== "external_masks");
      $("#objectLabelField").classList.toggle("is-hidden", !showPromptFields && state.selectedPreset !== "external_masks");
      $("#objectIdField").classList.toggle("is-hidden", !showAdvancedProviderInternals);
      $("#maskProviderField").classList.toggle("is-hidden", !showAdvancedProviderInternals);
      $("#deviceField").classList.toggle("is-hidden", !showAdvancedProviderInternals && !showSceneSweepControls);
      const sceneSweepDisclosure = $("#traceEverythingDisclosure");
      if (sceneSweepDisclosure && showSceneSweepControls) sceneSweepDisclosure.open = true;
      $("#videoForm")?.classList.toggle("is-hidden", reviewingExisting);
      $("#videoSelect")?.classList.toggle("is-hidden", reviewingExisting);
      $("#videoList")?.classList.toggle("is-hidden", reviewingExisting);
      $("#guidedDemoVideoButton")?.classList.toggle("is-hidden", reviewingExisting);
      $("#reviewExistingDisclosure")?.classList.toggle("is-hidden", !reviewingExisting && !state.workflowDashboard);
      $("#outputMode").value = preset.outputMode || "authoring";
      document.querySelector(".viewer-toolbar")?.classList.toggle("is-hidden", state.selectedPreset !== "trace_one_object");
      document.querySelector("[data-tool='point']")?.classList.toggle("is-hidden", sam3SingleObject);
      document.querySelector("[data-tool='brush']")?.classList.toggle("is-hidden", sam3SingleObject);
      document.querySelector("[data-tool='eraser']")?.classList.toggle("is-hidden", sam3SingleObject);
      document.querySelector("[data-tool='keyframe']")?.classList.toggle("is-hidden", sam3SingleObject);
      document.querySelector(".secondary-tools")?.classList.toggle("is-hidden", sam3SingleObject || state.selectedPreset !== "trace_one_object");
      if (sam3SingleObject && state.activeTool === "point") {
        updateTool("box");
      }
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

    function renderTimelinePanel() {
      const timeline = timelineMarkersForDisplay(state.jobReview, state.reviewTracks, state.keyframes);
      const currentFrame = state.video.currentFrame;
      const markerTrack = $("#timelineMarkerTrack");
      const markerList = $("#timelineMarkerList");
      const summary = $("#timelineSummary");
      const suggestionsButton = $("#useSuggestedKeyframesButton");
      const frameCount = Math.max(1, timeline.frameCount || 0, toInteger($("#frameSlider").max, 0) + 1);
      const visibleMarkers = timeline.markers.slice(0, 80);
      markerTrack.innerHTML = visibleMarkers.length
        ? visibleMarkers
            .map((marker) => {
              const left = frameCount <= 1 ? 0 : (clamp(marker.frameIndex, 0, frameCount - 1) / Math.max(1, frameCount - 1)) * 100;
              const active = marker.frameIndex === currentFrame;
              const title = `${marker.label} - frame ${marker.frameIndex}${marker.apiOwned ? " - API" : " - selected keyframe"}`;
              return `
                <button
                  class="timeline-marker is-${escapeAttribute(marker.kind)} ${active ? "is-active" : ""} ${marker.apiOwned ? "is-api" : "is-local"}"
                  type="button"
                  role="listitem"
                  style="left: ${left.toFixed(3)}%"
                  data-timeline-frame="${escapeAttribute(marker.frameIndex)}"
                  data-timeline-object="${escapeAttribute(marker.objectId || "")}"
                  title="${escapeAttribute(title)}"
                  aria-label="${escapeAttribute(title)}"
                ></button>
              `;
            })
            .join("")
        : `<span class="timeline-empty-marker" aria-hidden="true"></span>`;

      const apiCount = timeline.markers.filter((marker) => marker.apiOwned).length;
      const localCount = timeline.markers.length - apiCount;
      summary.textContent = timeline.hasApiTimeline
        ? `${apiCount} API marker${apiCount === 1 ? "" : "s"}; ${timeline.suggestedKeyframes.length} suggested keyframe${timeline.suggestedKeyframes.length === 1 ? "" : "s"}.`
        : localCount
          ? `${localCount} selected keyframe${localCount === 1 ? "" : "s"}; API timeline appears after review artifacts load.`
          : "No API timeline loaded.";
      suggestionsButton.disabled = timeline.suggestedKeyframes.length === 0;
      suggestionsButton.textContent = timeline.suggestedKeyframes.length
        ? `Use ${timeline.suggestedKeyframes.length} suggestion${timeline.suggestedKeyframes.length === 1 ? "" : "s"}`
        : "Use suggestions";
      markerList.innerHTML = timeline.hasApiTimeline && visibleMarkers.length
        ? visibleMarkers
            .filter((marker) => marker.apiOwned)
            .slice(0, 8)
            .map(
              (marker) => `
                <button class="timeline-marker-row" type="button" data-timeline-frame="${escapeAttribute(marker.frameIndex)}" data-timeline-object="${escapeAttribute(marker.objectId || "")}">
                  <strong>${escapeHtml(marker.label || marker.kind)}</strong>
                  <span class="row-meta">${escapeHtml(`frame ${marker.frameIndex} - ${marker.kind}${marker.status ? ` - ${marker.status}` : ""}`)}</span>
                </button>
              `,
            )
            .join("")
        : `<div class="empty-state">Review markers come from the API review timeline; local keyframes are only config input.</div>`;
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
      renderTimelinePanel();
    }

    function loadSelectedVideoPreview() {
      const video = selectedVideo();
      const preview = selectedVideoBrowserPreview(video);
      const rawContentUrl = preview?.contentUrl || video?.contentUrl || video?.content_url;
      const contentUrl = safeLocalContentUrl(rawContentUrl);
      const posterUrl = selectedVideoPosterUrl(video);
      if (posterUrl) elements.video.poster = posterUrl;
      else elements.video.removeAttribute("poster");
      if (!contentUrl && (preview?.status === "failed" || preview?.status === "blocked")) {
        $("#emptyViewerState strong").textContent = "Preview failed";
        $("#emptyViewerState span").textContent = preview?.reason || preview?.errorMessage || "The browser preview could not be prepared for this source video.";
        elements.stage.classList.remove("has-video");
        elements.video.removeAttribute("src");
        elements.video.load();
        return;
      }
      if (!contentUrl && video?.id) {
        $("#emptyViewerState strong").textContent = "Preparing preview";
        $("#emptyViewerState span").textContent = "MotionJSON is preparing a browser-safe preview for this source video.";
        elements.stage.classList.remove("has-video");
        elements.video.removeAttribute("src");
        elements.video.load();
        return;
      }
      if (rawContentUrl && !contentUrl) {
        setRunAlert("Preview blocked a non-local video content URL.", "warning-box is-bad");
      }
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

    function drawTrackBox(track, frame, view, index = 0) {
      const box = frame?.bbox;
      const polygon = normalizePolygonPoints(frame?.polygon);
      if (!box && !polygon) return;
      const bounds = box || polygonBounds(polygon, state.video.width || 1920, state.video.height || 1080);
      const start = videoPointToCanvas({ x: bounds.x, y: bounds.y }, view);
      const end = videoPointToCanvas({ x: bounds.x + bounds.w, y: bounds.y + bounds.h }, view);
      const center = videoPointToCanvas({ x: bounds.x + bounds.w / 2, y: bounds.y + bounds.h / 2 }, view);
      const resultMode = shell?.classList.contains("is-result-mode");
      ctx.save();
      ctx.lineWidth = resultMode ? 4 : 3;
      ctx.strokeStyle = track.color || "#10a37f";
      ctx.fillStyle = `${track.color || "#10a37f"}${resultMode ? "45" : "26"}`;
      if (resultMode && trackMotionMetrics(track).moving) {
        const trail = asArray(track.frames)
          .filter((item) => item?.visible !== false)
          .map((item) => {
            const itemPolygon = normalizePolygonPoints(item?.polygon);
            const itemBounds = item?.bbox || (itemPolygon ? polygonBounds(itemPolygon, state.video.width || 1920, state.video.height || 1080) : null);
            if (!itemBounds) return null;
            return {
              frame: toInteger(item.frame ?? item.frameIndex ?? item.out_index, 0),
              point: videoPointToCanvas({ x: itemBounds.x + itemBounds.w / 2, y: itemBounds.y + itemBounds.h / 2 }, view),
            };
          })
          .filter(Boolean)
          .sort((a, b) => a.frame - b.frame);
        if (trail.length >= 2) {
          ctx.save();
          ctx.globalAlpha = 0.72;
          ctx.strokeStyle = track.color || "#10a37f";
          ctx.lineWidth = 2;
          ctx.setLineDash([8, 7]);
          ctx.beginPath();
          trail.forEach(({ point }, itemIndex) => {
            if (itemIndex === 0) ctx.moveTo(point.x, point.y);
            else ctx.lineTo(point.x, point.y);
          });
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.globalAlpha = 0.9;
          for (const { point } of [trail[0], trail[trail.length - 1]]) {
            ctx.beginPath();
            ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
            ctx.fillStyle = track.color || "#10a37f";
            ctx.fill();
          }
          ctx.restore();
        }
      }
      if (polygon) {
        polygon.forEach((point, index) => {
          const canvasPoint = videoPointToCanvas(point, view);
          if (index === 0) ctx.beginPath();
          if (index === 0) ctx.moveTo(canvasPoint.x, canvasPoint.y);
          else ctx.lineTo(canvasPoint.x, canvasPoint.y);
        });
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.strokeRect(start.x, start.y, end.x - start.x, end.y - start.y);
        ctx.fillRect(start.x, start.y, end.x - start.x, end.y - start.y);
      }
      if (resultMode) {
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(center.x, center.y, 18, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(24, 32, 42, 0.16)";
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.fillStyle = "#1c2530";
        ctx.font = "700 16px ui-sans-serif, system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(index + 1), center.x, center.y + 1);
      } else {
        ctx.fillStyle = "rgba(20, 28, 32, 0.86)";
        const label = `${track.label || track.objectId} - ${track.reviewSource || "track"}`;
        ctx.font = "12px ui-sans-serif, system-ui, sans-serif";
        const textWidth = Math.min(ctx.measureText(label).width + 14, Math.max(60, view.width - start.x - 8));
        const labelY = Math.max(view.y + 18, start.y - 24);
        ctx.fillRect(start.x, labelY, textWidth, 20);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(label, start.x + 7, labelY + 14, textWidth - 12);
      }
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

      state.reviewTracks.forEach((track, index) => {
        if (!isTrackVisibleInReview(track)) return;
        drawTrackBox(track, trackFrameForDisplay(track, state.video.currentFrame), view, index);
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

    function scheduleDrawOverlay() {
      if (overlayFrame) return;
      overlayFrame = window.requestAnimationFrame(() => {
        overlayFrame = 0;
        drawOverlay();
      });
    }

    function renderRunPlanSummary(plan) {
      const container = $("#runPlanSummary");
      if (!container) return;
      const statusLabel = plan.errors.length
        ? `${plan.errors.length} validation error${plan.errors.length === 1 ? "" : "s"}`
        : plan.warnings.length
          ? `${plan.warnings.length} warning${plan.warnings.length === 1 ? "" : "s"}`
          : plan.privacy;
      const statusClassName = plan.errors.length ? "is-bad" : plan.warnings.length ? "is-warn" : "is-ready";
      const stepRows = plan.steps
        .map(
          (step) => `
            <li class="run-plan-step is-${escapeAttribute(step.status)}">
              <span class="run-plan-step-label">${escapeHtml(step.label)}</span>
              <strong>${escapeHtml(step.value)}</strong>
              <span>${escapeHtml(step.detail)}</span>
            </li>
          `,
        )
        .join("");
      const nextRows = plan.nextSteps.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      container.innerHTML = `
        <div class="run-plan-intro">
          <div>
            <p class="section-kicker">Reviewable plan</p>
            <h3>${escapeHtml(plan.title)}</h3>
            <p>${escapeHtml(plan.summary)}</p>
          </div>
          <span class="status-chip ${statusClassName}">${escapeHtml(statusLabel)}</span>
        </div>
        <ol class="run-plan-list">${stepRows}</ol>
        <div class="run-plan-next">
          <strong>Next</strong>
          <ul>${nextRows}</ul>
        </div>
      `;
    }

    function renderRunPlanError(message) {
      const container = $("#runPlanSummary");
      if (!container) return;
      container.innerHTML = `
        <div class="run-plan-intro">
          <div>
            <p class="section-kicker">Reviewable plan</p>
            <h3>Plan needs attention</h3>
            <p>${escapeHtml(message)}</p>
          </div>
          <span class="status-chip is-bad">Invalid</span>
        </div>
      `;
    }

    function renderConfigPreview() {
      const formState = collectFormState($);
      state.configValidation = null;
      let config;
      try {
        config = buildRunConfig(formState);
      } catch (error) {
        $("#configStatus").textContent = "Invalid";
        $("#configStatus").className = "status-chip is-bad";
        $("#configPreview").textContent = error.message;
        renderRunPlanError(error.message);
        renderShellIndicators();
        renderWorkflowStepper();
        return;
      }

      const warnings = selectedCapabilityWarnings(config, $);
      if (warnings.length) {
        const blocked = warnings.some((warning) => /requires|needs|unavailable|missing|not_configured|not runnable/.test(warning));
        setRunAlert(warnings.join(" "), `warning-box ${blocked ? "is-bad" : "is-warn"}`);
      } else {
        setRunAlert("", "warning-box is-ready");
      }

      const configWarnings = [];
      if (config.discovery.mode === "manual_prompt" && !config.prompts.length && config.provider.name !== "mock") {
        configWarnings.push("manual prompt config has no point, box, or mask prompt yet");
      }

      $("#configStatus").textContent = configWarnings.length ? "Needs prompt" : warnings.length ? "Warn" : "Valid";
      $("#configStatus").className = `status-chip ${configWarnings.length || warnings.length ? "is-warn" : "is-ready"}`;
      $("#configPreview").textContent = JSON.stringify(config, null, 2);
      renderRunPlanSummary(
        buildRunPlan(config, formState, {
          errors: [],
          warnings: [...warnings.map((message) => ({ message })), ...configWarnings.map((message) => ({ message }))],
        }),
      );
      renderPromptList();
      renderCorrectionPanel();
      renderModelPlanPanel();
      renderShellIndicators();
      renderWorkflowStepper();
      scheduleDrawOverlay();
    }

    function renderBackendValidation(validation) {
      state.configValidation = validation || null;
      const errors = asArray(validation.errors).map((item) => item.message || String(item));
      const warnings = asArray(validation.warnings).map((item) => {
        const reasons = asArray(item.reasons).join(" ");
        return [item.message || String(item), reasons, item.installHint].filter(Boolean).join(" ");
      });
      const valid = validation.valid === true && !errors.length;

      $("#configStatus").textContent = valid ? (warnings.length ? "Valid with warnings" : "Validated") : "Invalid";
      $("#configStatus").className = `status-chip ${valid ? (warnings.length ? "is-warn" : "is-ready") : "is-bad"}`;

      if (errors.length || warnings.length) {
        setRunAlert([...errors.map((message) => `Error: ${message}`), ...warnings].map(escapeHtml).join("<br />"), `warning-box ${errors.length ? "is-bad" : "is-warn"}`, { html: true });
      } else {
        setRunAlert("Backend validation accepted this config and reported no provider warnings.", "warning-box is-ready");
      }

      const config = validation.runConfig || buildRunConfig(collectFormState($));
      $("#configPreview").textContent = JSON.stringify(config, null, 2);
      renderRunPlanSummary(buildRunPlan(config, collectFormState($), validation));
      renderModelPlanPanel();
      renderShellIndicators();
      renderWorkflowStepper();
    }

    async function validateConfigWithBackend() {
      const formState = collectFormState($);
      let config;
      try {
        config = buildRunConfig(formState);
      } catch (error) {
        $("#configStatus").textContent = "Invalid";
        $("#configStatus").className = "status-chip is-bad";
        $("#configPreview").textContent = error.message;
        renderRunPlanError(error.message);
        renderShellIndicators();
        renderWorkflowStepper();
        return;
      }

      $("#configStatus").textContent = "Validating";
      $("#configStatus").className = "status-chip is-neutral";
      renderWorkflowStepper();
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
        setRunAlert(error.message, "warning-box is-bad");
        renderWorkflowStepper();
      }
    }

    async function validateCurrentModelPlan() {
      const result = currentModelPlanResult();
      if (!result?.runConfig) {
        setModelPlanMessage("Generate a model plan before validating its config.", "bad");
        return null;
      }
      state.modelPlanValidation = await api("/api/run-config/validate", {
        method: "POST",
        body: JSON.stringify({ runConfig: result.runConfig }),
      });
      const facts = modelPlanProviderFacts(result, state.modelPlanValidation);
      setModelPlanMessage(
        facts.valid ? "Backend validation accepted the generated config. Review details before confirming." : "Backend validation blocked this generated config.",
        facts.valid ? (facts.warnings.length ? "warn" : "ready") : "bad",
      );
      return state.modelPlanValidation;
    }

    async function generateModelPlanFromIntent() {
      const providerId = state.modelProviders?.defaultProviderId || "fake-local-planner";
      const formState = {
        ...collectFormState($),
        modelIntent: $("#modelIntent")?.value.trim() || "",
      };
      const payload = modelPlanRequestFromInput(formState, providerId);
      state.modelPlanRun = { id: "", providerId, status: "running", request: payload.request, result: null, events: [] };
      state.modelPlanValidation = null;
      state.modelPlanConfirmedJobId = "";
      state.modelPlanConfirming = false;
      state.modelPlanMessage = "Generating a plan. No extraction job has been created.";
      state.modelPlanTone = "neutral";
      renderModelPlanPanel();
      try {
        const response = await api("/api/model-runs", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        state.modelPlanRun = response.modelRun || null;
        state.modelPlanValidation = null;
        if (state.modelPlanRun?.result?.runConfig) {
          await validateCurrentModelPlan();
        } else {
          renderModelPlanPanel();
        }
      } catch (error) {
        state.modelPlanRun = { id: "", providerId, status: "failed", result: null, error: error.message, events: [] };
        state.modelPlanValidation = null;
        state.modelPlanMessage = error.message;
        state.modelPlanTone = "bad";
        renderModelPlanPanel();
      }
    }

    async function confirmModelPlanAndStart() {
      const run = state.modelPlanRun;
      const result = currentModelPlanResult();
      if (state.modelPlanConfirming) return;
      if (!run?.id || !result) {
        setModelPlanMessage("Generate a model plan before confirming extraction.", "bad");
        return;
      }
      let validation = currentModelPlanValidation();
      if (!validation) validation = await validateCurrentModelPlan();
      const facts = modelPlanProviderFacts(result, validation);
      if (!facts.valid) {
        setModelPlanMessage("Fix validation blockers before starting extraction.", "bad");
        return;
      }

      let payload;
      try {
        payload = modelPlanConfirmPayload({
          projectId: state.selectedProjectId,
          videoId: state.selectedVideoId,
          run: true,
        });
      } catch (error) {
        setModelPlanMessage(error.message, "bad");
        return;
      }

      setModelPlanMessage("Starting extraction from the confirmed model plan...", "neutral");
      state.modelPlanConfirming = true;
      renderModelPlanPanel();
      try {
        const response = await api(`/api/model-runs/${encodeURIComponent(run.id)}/confirm-job`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        state.modelPlanRun = response.modelRun || state.modelPlanRun;
        state.modelPlanValidation = response.validation || validation;
        const job = response.job;
        const id = jobIdentifier(job);
        if (id) {
          state.modelPlanConfirmedJobId = id;
          state.runConfigsByJob[id] = response.validation?.runConfig || response.modelPlan?.runConfig || result.runConfig;
          state.selectedJobId = id;
          state.selectedJob = job;
          state.jobs = [job, ...state.jobs.filter((item) => jobIdentifier(item) !== id)];
          state.jobEvents = asArray(job.events);
          state.jobArtifacts = [];
          state.correctionState = emptyCorrectionState(id);
          state.reviewTracks = buildReviewTracks({ job, config: state.runConfigsByJob[id], artifacts: [] });
          for (const track of state.reviewTracks) state.trackVisibility[track.id] = true;
          renderJobs();
          renderJobReview();
          await refreshSelectedJobReview();
          startPolling();
        }
        setModelPlanMessage("Extraction started from the confirmed plan. The run monitor now includes the attached model plan.", "ready");
      } catch (error) {
        setModelPlanMessage(error.message, "bad");
      } finally {
        state.modelPlanConfirming = false;
        renderModelPlanPanel();
      }
    }

    function configForLocalJob(forceMock = false) {
      const config = buildRunConfig(collectFormState($));
      if (forceMock) {
        config.provider.name = "mock";
        config.provider.fallback_mask_provider = null;
      }
      if (!LOCAL_JOB_PROVIDERS.has(config.provider.name)) {
        throw new Error(`${config.provider.name} cannot run in the local UI worker yet. Choose a compatible SAM2 or SAM3 engine, motion, threshold, mock, or external masks.`);
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
        state.candidateSelection = {};
        state.candidateSelectionJobId = "";
        state.candidateTrackingStatus = "";
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
      state.jobEvents = asArray(eventsBody.events).length ? asArray(eventsBody.events) : asArray(jobBody.job?.events);
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
        setRunAlert(error.message, "warning-box is-bad");
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
        setRunAlert("Create or select a project before starting a run.", "warning-box is-bad");
        return;
      }
      if (!state.selectedVideoId) {
        setRunAlert("Register or select a video before starting a run.", "warning-box is-bad");
        return;
      }

      let config;
      try {
        config = configForLocalJob(forceMock);
      } catch (error) {
        setRunAlert(error.message, "warning-box is-bad");
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
        maybeAdvanceWorkflowAfterResultLoad();
      } catch (error) {
        $("#runStatus").textContent = "Failed";
        $("#runStatus").className = "status-chip is-bad";
        setRunAlert(error.message, "warning-box is-bad");
      }
    }

    function applyPreset(presetName, options = {}) {
      state.selectedPreset = PRESETS[presetName] ? presetName : "auto_object_proposals";
      state.modelSetupAlternativesOpen = false;
      if (goalRequiresModel(state.selectedPreset)) {
        if (!options.keepProvider) state.selectedModelSetupProviderId = recommendedConnectionIdForPreset(state.selectedPreset);
      } else if (state.activeWorkflowStep === "provider_settings") {
        state.activeWorkflowStep = "prompt_preview";
      }
      document.querySelectorAll(".goal, .goal-card").forEach((button) => {
        const active = button.dataset.preset === state.selectedPreset;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
        if (active) button.setAttribute("aria-current", "step");
        else button.removeAttribute("aria-current");
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
      renderShellIndicators();
      renderModelSetup();
      renderConfigPreview();
      renderWorkflowStepper();
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
      renderTimelinePanel();
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
      scheduleDrawOverlay();
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
      scheduleDrawOverlay();
    }

    function seekToFrame(frame) {
      const fps = Math.max(0.1, toNumber($("#sampleFps").value, 12));
      const sliderMax = toInteger($("#frameSlider").max, 0);
      const durationMax = Number.isFinite(elements.video.duration) && elements.video.duration > 0 ? Math.round(elements.video.duration * fps) : sliderMax;
      const maxFrame = Math.max(0, sliderMax, durationMax);
      const nextFrame = clamp(Math.round(toNumber(frame, state.video.currentFrame)), 0, maxFrame);
      if (Number.isFinite(elements.video.duration) && elements.video.duration > 0) {
        elements.video.currentTime = clamp(nextFrame / fps, 0, elements.video.duration);
      }
      state.video.currentFrame = nextFrame;
      $("#frameSlider").max = String(maxFrame);
      $("#frameSlider").value = String(nextFrame);
      $("#frameReadout").textContent = `frame ${nextFrame}`;
      renderTimelinePanel();
      renderVideoMetrics();
      renderConfigPreview();
      scheduleDrawOverlay();
    }

    async function togglePreviewPlayback() {
      if (!elements.video.src) return;
      if (elements.video.paused) await elements.video.play();
      else elements.video.pause();
    }

    function isShortcutTypingTarget(target) {
      return Boolean(target?.closest?.("input, textarea, select, button, a, summary, [contenteditable='true']"));
    }

    function handleKeyboardShortcut(event) {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || isShortcutTypingTarget(event.target)) return;
      const key = String(event.key || "").toLowerCase();
      const maxFrame = toInteger($("#frameSlider").max, state.video.currentFrame);
      if (key === "arrowleft" || key === "arrowright") {
        event.preventDefault();
        const step = event.shiftKey ? 10 : 1;
        const delta = key === "arrowleft" ? -step : step;
        seekToFrame(clamp(state.video.currentFrame + delta, 0, maxFrame));
        return;
      }
      if (key === " " || key === "spacebar") {
        event.preventDefault();
        togglePreviewPlayback();
        return;
      }
      if (key === "m") {
        event.preventDefault();
        markKeyframe();
        return;
      }
      const toolByKey = { b: "box", e: "eraser", p: "point" };
      if (toolByKey[key]) {
        event.preventDefault();
        updateTool(toolByKey[key]);
      }
    }

    function applyLoadedConfig(config) {
      const presetEntry = Object.entries(PRESETS).find(([, preset]) => preset.discoveryMode === config.discovery?.mode);
      applyPreset(presetEntry?.[0] || "auto_object_proposals", { keepProvider: true });
      $("#objectId").value = config.objects?.[0]?.object_id || "object_0";
      $("#objectLabel").value = config.objects?.[0]?.label || "selected_object";
      $("#sampleFps").value = config.sampling?.sample_fps ?? 12;
      $("#maxFrames").value = config.sampling?.max_frames ?? 48;
      $("#minArea").value = config.filters?.min_area ?? 100;
      $("#outputMode").value = config.export?.output_mode || "authoring";
      $("#maskProviderSelect").value = config.provider?.name || $("#maskProviderSelect").value;
      $("#externalMaskDir").value = config.provider?.external?.mask_dir || config.objects?.[0]?.mask_dir || "masks/object_0";
      $("#textPrompt").value = config.discovery?.config?.text || $("#textPrompt").value;
      $("#discoveryQualityPreset").value = ["clean", "balanced", "maximum_recall"].includes(config.discovery?.config?.qualityPreset)
        ? config.discovery.config.qualityPreset
        : "clean";
      $("#traceEverythingMode").checked = config.discovery?.config?.qualityPreset === "trace_everything";
      $("#traceEverythingAck").checked = config.discovery?.config?.costWarningAcknowledged === true;
      $("#classPreset").value = config.discovery?.config?.class_preset || "common_objects";
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
          ["workspace", "/api/workspace"],
          ["commercialReadiness", "/api/commercial-readiness"],
          ["capabilities", capabilityRoute],
          ["providerSettings", "/api/provider-settings"],
          ["modelProviders", "/api/model-providers"],
          ["runDefaults", "/api/run-config/defaults"],
          ["exportFormats", "/api/exports/formats"],
          ["projects", "/api/projects"],
          ["libraryAssets", libraryAssetRoute()],
          ["libraryCollections", "/api/library/collections"],
          ["libraryPacks", "/api/library/packs"],
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
        if (key === "workspace") state.workspace = payload;
        if (key === "commercialReadiness") state.commercialReadiness = payload;
        if (key === "capabilities") state.capabilities = payload;
        if (key === "providerSettings") state.providerSettings = payload;
        if (key === "modelProviders") state.modelProviders = payload;
        if (key === "runDefaults") state.runDefaults = payload;
        if (key === "exportFormats") state.exportFormats = payload;
        if (key === "projects") state.projects = payload?.projects || [];
        if (key === "libraryAssets") state.libraryAssets = payload?.assets || [];
        if (key === "libraryCollections") state.libraryCollections = payload?.collections || [];
        if (key === "libraryPacks") state.libraryPacks = payload?.packs || [];
      }
      state.errors.library = [state.errors.libraryAssets, state.errors.libraryCollections, state.errors.libraryPacks].filter(Boolean).join(" ");
      await refreshAdvancedLocalPaths();
    }

    async function refreshAdvancedLocalPaths() {
      const providers = asArray(state.providerSettings?.providers).filter(
        (provider) => provider?.id === "sam3-local" && provider?.modelCache?.localPathKnown,
      );
      const next = {};
      await Promise.all(
        providers.map(async (provider) => {
          try {
            next[provider.id] = await api(`/api/provider-settings/${encodeURIComponent(provider.id)}/advanced-local-paths`);
          } catch (error) {
            next[provider.id] = {
              providerId: provider.id,
              available: false,
              message: error.message,
            };
          }
        }),
      );
      state.advancedLocalPaths = next;
    }

    function mergeProgressJobs(jobs, progress) {
      const lookup = new Map(asArray(progress).map((job) => [jobIdentifier(job), job]));
      return asArray(jobs).map((job) => ({ ...job, ...(lookup.get(jobIdentifier(job)) || {}) }));
    }

    function ensureSelectedJob() {
      const center = jobCenterStateFromSnapshot({ jobs: state.jobs, selectedJobId: state.selectedJobId });
      state.selectedJobId = center.selectedJobId;
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
        state.candidateSelection = {};
        state.candidateSelectionJobId = "";
        state.candidateTrackingStatus = "";
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
      const eventsFromRoute = asArray(eventsResult[1]?.events);
      state.jobEvents = eventsFromRoute.length ? eventsFromRoute : asArray(state.selectedJob?.events);
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
      maybeAdvanceWorkflowAfterResultLoad();
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
      renderWorkspace();
      renderCapabilities();
      renderProviderSettings();
      renderModelSetup();
      renderModelPlanPanel();
      renderCommercialReadiness();
      renderFirstRunChecklist();
      renderRunDefaults();
      renderProjects();
      renderAssetLibraryPanel();
      renderExportPresetOptions();
      renderMaskProviderOptions();
      applyProviderSettingsToRunForm();
      renderPresetFields();
      renderApiStatus(state.errors.health ? "is-bad" : "is-ready", state.errors.health ? "API unavailable" : "API ready");
      await refreshProjectData();
      reconcileWorkflowProgress();
      renderGuidedStart();
      renderWorkflowStepper();
      renderConfigPreview();
    }

    function starterProjectName() {
      return $("#projectName")?.value?.trim() || "MotionJSON local project";
    }

    function matchesBundledDemoVideo(video) {
      const values = [
        video?.path,
        video?.filename,
        video?.metadata?.filename,
        video?.metadata?.source_uri,
        video?.metadata?.rights_context?.source_uri,
      ]
        .filter(Boolean)
        .join(" ");
      return /demo_red_ball\.mp4/i.test(values);
    }

    async function ensureStarterProject() {
      if (state.selectedProjectId) return state.selectedProjectId;
      const created = await api("/api/projects", {
        method: "POST",
        body: JSON.stringify({ name: starterProjectName() }),
      });
      state.selectedProjectId = created.project.id;
      await refreshAll();
      return state.selectedProjectId;
    }

    async function ensureBundledDemoVideo() {
      if (!state.selectedProjectId) await ensureStarterProject();
      if (!state.videos.length) await refreshProjectData();
      const existing = state.videos.find(matchesBundledDemoVideo);
      if (existing?.id) {
        state.selectedVideoId = existing.id;
        renderVideos();
        return existing;
      }
      await api("/api/videos", {
        method: "POST",
        body: JSON.stringify({ projectId: state.selectedProjectId, path: BUNDLED_DEMO_VIDEO_PATH }),
      });
      await refreshProjectData();
      return selectedVideo();
    }

    async function retrySelectedVideoPreview() {
      if (!state.selectedVideoId) return;
      $("#retryPreviewButton").disabled = true;
      try {
        await api(`/api/videos/${encodeURIComponent(state.selectedVideoId)}/prepare-browser-preview`, {
          method: "POST",
          body: JSON.stringify({ force: true }),
        });
        await refreshProjectData();
        setRunAlert("", "warning-box");
      } catch (error) {
        setRunAlert(error.message, "warning-box is-bad");
      } finally {
        $("#retryPreviewButton").disabled = false;
      }
    }

    async function startGuidedDemoVideoFlow() {
      const button = $("#guidedDemoVideoButton");
      if (button) button.disabled = true;
      try {
        if (state.selectedVideoId) {
          setWorkflowStep("source_video", { focusStep: true });
          return;
        }
        await ensureBundledDemoVideo();
        setRunAlert("", "warning-box is-ready");
        setWorkflowStep("source_video", { focusStep: true });
      } catch (error) {
        setRunAlert(error.message, "warning-box is-bad");
      } finally {
        if (button) button.disabled = false;
      }
    }

    function applyReviewCaptureFixture(capture) {
      const jobId = `job_${capture}_layout`;
      const failedCapture = capture === "workflow-review-failure";
      const candidateOnlyCapture = capture === "candidate-review";
      const runConfig = buildRunConfig({
        preset: "auto_object_proposals",
        discoveryMode: "auto_object_proposals",
        projectId: "project_layout",
        videoId: "video_layout",
        sourcePath: "local-ui://assets/video_layout",
        videoPath: "local-ui://assets/video_layout",
        outputDirectory: "out/ui-runs/project_layout",
        objectLabel: "red ball",
        objectId: "red_ball",
        currentFrame: 152,
        keyframes: new Set([0, 152, 300]),
        prompts: [],
        strokes: [],
        maskProvider: "mock",
        device: "auto",
        sampleFps: "12",
        maxFrames: "450",
        minArea: "100",
        maxAreaRatio: "0.45",
        stabilityThreshold: "0.82",
        overlapThreshold: "0.72",
        boxThreshold: "0.35",
        textThreshold: "0.25",
        motionSensitivity: "32",
        maxObjects: "5",
        modelName: "auto",
        outputMode: "authoring",
        qualityPreset: "balanced",
      });
      const job = {
        id: jobId,
        type: "extract",
        status: failedCapture ? "failed" : "succeeded",
        progress: failedCapture ? 64 : 100,
        percent: failedCapture ? 64 : 100,
        payload: { mask_provider: "mock", run_config: runConfig },
        result: failedCapture || candidateOnlyCapture ? { objects: 0, frames: 450, rasterFallback: failedCapture } : { objects: 4, frames: 450 },
        updated_at: "2026-05-20T12:00:00Z",
        message: failedCapture ? "SAM3 Scene Sweep runtime unavailable; vector tracks were not produced." : "review fixture ready",
        error: failedCapture ? "SAM3 Tracker mask generation is not ready; install scene sweep or choose SAM2 fallback before retrying." : "",
      };
      const candidates = [
        {
          candidateId: "cand_red_ball",
          objectId: "red_ball",
          label: "Red ball",
          source: "auto_object_proposals",
          providerName: "mock detector",
          frameIndex: 152,
          box: { x: 250, y: 650, w: 230, h: 230 },
          confidence: 0.92,
          stabilityScore: 0.91,
          motionScore: 0.22,
          frameCoverageEstimate: 1,
          frameCount: 452,
          reviewStatus: "accepted",
          defaultSelected: true,
        },
        {
          candidateId: "cand_person",
          objectId: "hand_person",
          label: "Hand / Person",
          source: "auto_object_proposals",
          providerName: "mock detector",
          frameIndex: 152,
          box: { x: 510, y: 110, w: 760, h: 900 },
          confidence: 0.87,
          stabilityScore: 0.88,
          motionScore: 0.34,
          frameCoverageEstimate: 1,
          frameCount: 450,
          reviewStatus: "accepted",
          defaultSelected: true,
        },
        {
          candidateId: "cand_cup",
          objectId: "cup",
          label: "Cup",
          source: "auto_object_proposals",
          providerName: "mock detector",
          frameIndex: 152,
          box: { x: 1590, y: 650, w: 260, h: 210 },
          confidence: 0.81,
          stabilityScore: 0.82,
          motionScore: 0.14,
          frameCoverageEstimate: 0.98,
          frameCount: 441,
          reviewStatus: "accepted",
          defaultSelected: true,
        },
        {
          candidateId: "cand_moving_object",
          objectId: "moving_object",
          label: "Moving object",
          source: "motion_foreground",
          providerName: "CPU motion",
          frameIndex: 152,
          box: { x: 1395, y: 390, w: 125, h: 220 },
          confidence: 0.74,
          stabilityScore: 0.74,
          motionScore: 0.52,
          frameCoverageEstimate: 0.69,
          frameCount: 312,
          reviewStatus: "accepted",
          defaultSelected: true,
        },
        {
          candidateId: "cand_plant",
          objectId: "plant_background",
          label: "Plant (background)",
          source: "sam_auto_masks",
          providerName: "mock masks",
          frameIndex: 152,
          box: { x: 55, y: 260, w: 190, h: 520 },
          confidence: 0.42,
          stabilityScore: 0.7,
          motionScore: 0.01,
          frameCoverageEstimate: 1,
          frameCount: 450,
          reviewStatus: "needs_review",
          warnings: ["background_like"],
          defaultSelected: false,
        },
        {
          candidateId: "cand_fence",
          objectId: "fence_background",
          label: "Fence",
          source: "sam_auto_masks",
          providerName: "mock masks",
          frameIndex: 152,
          box: { x: 0, y: 175, w: 1920, h: 310 },
          confidence: 0.38,
          stabilityScore: 0.78,
          motionScore: 0.01,
          frameCoverageEstimate: 1,
          frameCount: 450,
          reviewStatus: "needs_review",
          warnings: ["background_like", "whole_frame_like"],
          defaultSelected: false,
        },
        {
          candidateId: "cand_ground",
          objectId: "ground_lawn",
          label: "Ground / Lawn",
          source: "sam_auto_masks",
          providerName: "mock masks",
          frameIndex: 152,
          box: { x: 0, y: 570, w: 1500, h: 510 },
          confidence: 0.28,
          stabilityScore: 0.76,
          motionScore: 0.01,
          frameCoverageEstimate: 1,
          frameCount: 450,
          reviewStatus: "rejected",
          rejectionReason: "background_like",
          warnings: ["whole_frame_like"],
          defaultSelected: false,
        },
      ];
      const reviewTracks = [
        {
          id: "red_ball",
          objectId: "red_ball",
          label: "Red ball",
          source: "selected-candidate-tracker",
          providerName: "mock tracker",
          confidence: 0.92,
          frameStart: 0,
          frameEnd: 451,
          visibleFrameCount: 452,
          frameCount: 452,
          exportStatus: "accepted",
          exportIncluded: true,
          reviewSource: "reviewed",
          color: "#20c4cf",
          rightsSummary: {
            commercialUseStatus: "review_required",
            license: "user_uploaded_unverified",
            attributionRequired: true,
            sourceAttribution: { displayText: "User uploaded source video" },
          },
          frames: [
            { frame: 0, bbox: { x: 150, y: 690, w: 220, h: 220 }, visible: true },
            { frame: 152, bbox: { x: 250, y: 650, w: 230, h: 230 }, visible: true },
            { frame: 300, bbox: { x: 370, y: 612, w: 230, h: 230 }, visible: true },
            { frame: 451, bbox: { x: 520, y: 565, w: 225, h: 225 }, visible: true },
          ],
        },
        {
          id: "hand_person",
          objectId: "hand_person",
          label: "Hand / Person",
          source: "selected-candidate-tracker",
          providerName: "mock tracker",
          confidence: 0.87,
          frameStart: 0,
          frameEnd: 449,
          visibleFrameCount: 450,
          frameCount: 450,
          exportStatus: "accepted",
          exportIncluded: true,
          reviewSource: "reviewed",
          color: "#45b844",
          frames: [{ frame: 152, bbox: { x: 510, y: 110, w: 760, h: 900 }, visible: true }],
        },
        {
          id: "cup",
          objectId: "cup",
          label: "Cup",
          source: "selected-candidate-tracker",
          providerName: "mock tracker",
          confidence: 0.81,
          frameStart: 0,
          frameEnd: 440,
          visibleFrameCount: 441,
          frameCount: 441,
          exportStatus: "accepted",
          exportIncluded: true,
          reviewSource: "reviewed",
          color: "#2f8dea",
          frames: [{ frame: 152, bbox: { x: 1590, y: 650, w: 260, h: 210 }, visible: true }],
        },
        {
          id: "moving_object",
          objectId: "moving_object",
          label: "Moving object",
          source: "selected-candidate-tracker",
          providerName: "mock tracker",
          confidence: 0.74,
          frameStart: 0,
          frameEnd: 311,
          visibleFrameCount: 312,
          frameCount: 312,
          exportStatus: "accepted",
          exportIncluded: true,
          reviewSource: "reviewed",
          color: "#f9bd0a",
          frames: [
            { frame: 24, bbox: { x: 1310, y: 430, w: 125, h: 220 }, visible: true },
            { frame: 152, bbox: { x: 1395, y: 390, w: 125, h: 220 }, visible: true },
            { frame: 311, bbox: { x: 1515, y: 350, w: 125, h: 220 }, visible: true },
          ],
        },
      ];
      state.selectedProjectId = "project_layout";
      state.selectedVideoId = "video_layout";
      state.jobs = [job];
      state.selectedJobId = job.id;
      state.selectedJob = job;
      state.video = {
        ...state.video,
        width: 1920,
        height: 1080,
        duration: 15,
        currentFrame: 152,
        loadedName: "review-demo.mp4",
      };
      elements.stage.classList.add("has-video", "has-studio-demo");
      $("#frameSlider").max = "450";
      $("#frameSlider").value = "152";
      $("#frameReadout").textContent = "frame 152";
      $("#videoMetricReadout").textContent = "1920x1080 px";
      state.jobEvents = failedCapture
        ? [
            {
              event_type: "mask_provider_failed",
              status: "failed",
              stage: "mask_provider",
              message: "SAM3 Scene Sweep runtime unavailable; vector tracks were not produced.",
              metadata: {
                reasonCode: "sam3_scene_sweep_unavailable",
                message: "SAM3 Scene Sweep runtime unavailable; vector tracks were not produced.",
                suggestedFixes: ["Install SAM3 Scene Sweep in Model setup.", "Choose SAM2 fallback or mock provider before retrying."],
              },
            },
            {
              event_type: "raster_fallback",
              status: "warning",
              stage: "export",
              message: "Raster fallback output was retained because object tracks were unavailable.",
              metadata: {
                reasonCode: "raster_fallback",
                message: "Raster-only fallback explains why object/vector tracks are unavailable.",
                suggestedFixes: ["Open fallback diagnostics before export.", "Add prompts or choose a ready local provider."],
              },
            },
          ]
        : [
            { event_type: "candidate_discovery", message: "7 candidates proposed for review" },
            { event_type: "track_linking", message: "4 selected candidates tracked" },
            { event_type: "review_gate", message: "export includes reviewed selected objects only" },
          ];
      state.jobArtifacts = failedCapture
        ? [
            { id: "failure_diag_layout", kind: "failure_diagnostics", path: "failure_diagnostics.json" },
            { id: "fallback_diag_layout", kind: "fallback_diagnostics", path: "fallback_diagnostics.json" },
          ]
        : [];
      state.jobReview = {
        candidates: failedCapture ? [] : candidates,
        candidateSummary: {
          provider: "auto_object_proposals",
          providerName: "mock detector",
          qualityPreset: "balanced",
          candidateCount: failedCapture ? 0 : candidates.length,
          acceptedCandidateCount: failedCapture ? 0 : 4,
          rejectedCandidateCount: failedCapture ? 0 : 1,
          defaultSelectedCount: failedCapture ? 0 : 4,
          rejectionReasons: failedCapture ? {} : { background_like: 3 },
        },
        tracks: failedCapture || candidateOnlyCapture ? [] : reviewTracks,
        objects: failedCapture || candidateOnlyCapture
          ? []
          : [
              { objectId: "red_ball", id: "red_ball", label: "Red ball" },
              { objectId: "hand_person", id: "hand_person", label: "Hand / Person" },
              { objectId: "cup", id: "cup", label: "Cup" },
              { objectId: "moving_object", id: "moving_object", label: "Moving object" },
            ],
        export: {
          includedObjectIds: failedCapture || candidateOnlyCapture ? [] : ["red_ball", "hand_person", "cup", "moving_object"],
          excludedObjectIds: failedCapture ? [] : candidateOnlyCapture ? candidates.map(candidateId).filter(Boolean) : ["plant_background", "fence_background", "ground_lawn"],
          exportReviewRequired: true,
        },
        rightsSummary: {
          format: "motionjson.export_rights_summary.v0.1",
          summary: { commercialUseApproved: false, commercialUseReviewRequired: ["red_ball", "hand_person", "cup", "moving_object"] },
          warnings: [{ code: "commercial_use_review_required", message: "Review source rights before publishing." }],
        },
        fallbackDiagnostics: failedCapture
          ? [
              {
                reasonCode: "sam3_scene_sweep_unavailable",
                severity: "error",
                message: "SAM3 Scene Sweep runtime unavailable, so vector/object tracks were not produced.",
                suggestedFixes: ["Install SAM3 Scene Sweep in Model setup.", "Choose SAM2 fallback or mock provider before retrying."],
              },
            ]
          : [],
        vectorUnavailableReason: failedCapture ? "Vector/object tracks are unavailable because the mask provider failed." : "",
        rasterFallbackReason: failedCapture ? "Raster-only fallback was retained so the failed run still has inspectable output." : "",
        failure: failedCapture ? { message: "SAM3 Scene Sweep runtime unavailable; vector tracks were not produced." } : null,
      };
      state.reviewTracks = failedCapture || candidateOnlyCapture ? [] : reviewTracks;
      state.trackVisibility = failedCapture || candidateOnlyCapture ? {} : { red_ball: true, hand_person: true, cup: true, moving_object: true };
      state.candidateSelection = failedCapture
        ? {}
        : { cand_red_ball: true, cand_person: true, cand_cup: true, cand_moving_object: true, cand_plant: false, cand_fence: false, cand_ground: false };
      state.candidateSelectionJobId = job.id;
      state.candidateTrackingStatus = failedCapture ? "" : candidateOnlyCapture ? "4 candidates kept; track selected to create object tracks." : "4 reviewed candidates tracked; export remains reviewed-only.";
      state.selectedCorrectionTrackId = failedCapture || candidateOnlyCapture ? "" : "red_ball";
      state.mergeSelection = !failedCapture && !candidateOnlyCapture && capture === "correction-tools" ? new Set(["red_ball", "moving_object"]) : new Set();
      state.prompts = failedCapture
        ? []
        : [
            { id: "prompt_layout_point", kind: "positive_point", frame_index: 152, object_id: "red_ball", label: "Red ball", data: { x: 365, y: 765 } },
          ];
      state.strokes = [];
      state.correctionState = {
        ...emptyCorrectionState(job.id),
        loaded: true,
        persistenceStatus: "loaded",
        persistenceMessage: failedCapture
          ? "No correction state is available because the run did not produce object tracks."
          : "Correction state loaded from the local backend. Edits are saved locally before export.",
        mergeSuggestions: failedCapture ? [] : [{ keepObjectId: "red_ball", mergeObjectId: "moving_object", meanIou: 0.42 }],
        history: failedCapture
          ? []
          : [
              {
                type: "relabel_track",
                trackId: "red_ball",
                label: "Red ball",
                frameRange: [0, 451],
                createdAt: "2026-05-20T12:00:00Z",
                persistenceStatus: "saved",
              },
            ],
      };
      state.exportValidation =
        capture === "export-gate"
          ? {
              jobId: job.id,
              includedObjectIds: ["red_ball", "hand_person", "cup", "moving_object"],
              excludedObjectIds: ["plant_background", "fence_background", "ground_lawn"],
              validation: { ok: false, issueCount: 1, checked: 7, issues: [{ path: "background_candidates", message: "Background-like candidates stay excluded until reviewed." }] },
              exportValidationMessages: [{ code: "reviewed_only_export", severity: "warn", message: "Only reviewed selected tracks are eligible for export." }],
              rightsSummary: state.jobReview.rightsSummary,
              exportWarnings: [{ code: "commercial_use_review_required", severity: "warn", message: "Confirm source rights before public distribution." }],
            }
          : null;
      if (capture === "export-success" || capture === "copyable-snippet") {
        const assets = [
          { id: "asset_scene_layout", kind: "validated_motionjson_scene", contentUrl: "/api/artifacts/asset_scene_layout/content", path: "scene_graph.json", metadata: { rel_path: "exports/layout/scene_graph.json" } },
          { id: "asset_pack_layout", kind: "object_layer_pack", contentUrl: "/api/artifacts/asset_pack_layout/content", path: "object_layer_pack.json", metadata: { rel_path: "exports/layout/object_layer_pack.json" } },
          { id: "asset_remotion_layout", kind: "remotion_plan", contentUrl: "/api/artifacts/asset_remotion_layout/content", path: "remotion_export_plan.json", metadata: { rel_path: "exports/layout/remotion_export_plan.json" } },
          { id: "asset_website_layout", kind: "website_package", contentUrl: "/api/artifacts/asset_website_layout/content", path: "website_package.zip", metadata: { rel_path: "exports/layout/website_package.zip" } },
          { id: "asset_bundle_layout", kind: "motionjson_export_zip", contentUrl: "/api/artifacts/asset_bundle_layout/content", path: "motionjson_export.zip", metadata: { rel_path: "exports/layout/motionjson_export.zip" } },
        ];
        const objectLayerPack = {
          format: "motionjson.object_layer_pack.v0.1",
          selectedObjectIds: ["red_ball", "hand_person", "cup", "moving_object"],
          excludedObjectIds: ["plant_background", "fence_background", "ground_lawn"],
          objectCount: 4,
          snippets: {
            plainJs: 'import { mountMotionJSON } from "./runtime/index.js";\n\nawait mountMotionJSON("#motion", "./scene_graph.json", { objectIds: ["red_ball", "hand_person", "cup", "moving_object"] });',
            remotion: 'const selectedObjectIds = ["red_ball", "hand_person", "cup", "moving_object"];\n<MotionJSONComposition sceneGraphPath="./scene_graph.json" objectIds={selectedObjectIds} assetBasePath="." />',
          },
        };
        state.exportResult = {
          jobId: job.id,
          validation: { ok: true, issueCount: 0, checked: 4 },
          includedObjectIds: ["red_ball", "hand_person", "cup", "moving_object"],
          excludedObjectIds: ["plant_background", "fence_background", "ground_lawn"],
          assets,
          objectLayerPack,
          rightsSummary: state.jobReview.rightsSummary,
          exportWarnings: state.jobReview.rightsSummary.warnings,
          qualityRouting: {
            format: "motionjson.export_quality_routing.v0.1",
            preset: "compact",
            includeMasks: false,
            includeContours: false,
            includePreview: true,
            objects: ["red_ball", "hand_person", "cup", "moving_object"].map((objectId) => ({
              objectId,
              selectedOutput: "hybrid_vector_silhouette_plus_raster",
              selectedDelivery: { route: "sprite_atlas_webp" },
            })),
            preview: { mp4Preview: { status: "ready", reason: "preview route available" } },
          },
        };
        state.exportValidation = {
          jobId: job.id,
          validation: state.exportResult.validation,
          includedObjectIds: state.exportResult.includedObjectIds,
          excludedObjectIds: state.exportResult.excludedObjectIds,
        };
        state.jobArtifacts = assets;
        state.exportCopiedHandoffId = capture === "copyable-snippet" ? "runtime-snippet" : "";
      } else {
        state.exportResult = null;
        state.exportCopiedHandoffId = "";
      }
      renderJobs();
      renderJobReview();
    }

    function applyDocsCaptureMode() {
      const params = new URLSearchParams(window.location.search);
      const capture = params.get("capture");
      if (!capture) return;

      document.documentElement.dataset.capture = capture;
      const shell = document.querySelector(".app-shell");
      const sidebar = document.querySelector(".sidebar");
      const workspace = document.querySelector(".workspace");
      const rightRail = document.querySelector(".right-rail");
      const goalList = document.querySelector(".goal-list");
      const firstRunPanel = document.querySelector("#firstRunChecklist")?.closest(".compact-panel");
      const wizardPanel = document.querySelector(".wizard-panel");
      const guidedStart = document.querySelector(".guided-start");
      const workflowSteps = document.querySelector(".workflow-steps");
      const workspaceGrid = document.querySelector(".workspace-grid");
      const viewerPanel = document.querySelector(".viewer-panel");
      const configPanel = document.querySelector(".config-panel");
      const modelSetupPanel = document.querySelector("#modelSetupPanel");
      const modelPlanPanel = document.querySelector("#modelPlanPanel");
      const rawConfigDisclosure = document.querySelector("#rawConfigDisclosure");
      const captureUsesSam3Prepare = ["prepare-sam3-single", "prepare-sam3-text", "prepare-sam3-trace-all", "prepare-sam3-trace-all-runtime-ready", "prepare-sam3-trace-all-missing-runtime"].includes(capture);
      const markCaptureCapabilityReady = (capabilityName, { message = "Ready for this workflow." } = {}) => {
        if (!state.capabilities?.providers) return;
        state.capabilities.providers = state.capabilities.providers.map((provider) =>
          provider.name === capabilityName
            ? {
                ...provider,
                available: true,
                configured: true,
                installed: true,
                runnable: true,
                status: "ready",
                reasons: [],
                installHint: provider.installHint || message,
              }
            : provider,
        );
      };
      const markCaptureCapabilityBlocked = (capabilityName, { status = "missing_dependency", reasons = [], installHint = "Complete Model setup before running." } = {}) => {
        if (!state.capabilities?.providers) return;
        state.capabilities.providers = state.capabilities.providers.map((provider) =>
          provider.name === capabilityName
            ? {
                ...provider,
                available: false,
                configured: false,
                installed: false,
                runnable: false,
                status,
                reasons: asArray(reasons),
                installHint,
              }
            : provider,
        );
      };
      const markCaptureProviderReady = (providerId, { hostedProfileId = "", allowHosted = false, message = "Ready for this workflow." } = {}) => {
        if (!state.providerSettings?.providers) return;
        state.providerSettings.providers = state.providerSettings.providers.map((provider) =>
          provider.id === providerId
            ? {
                ...provider,
                readiness: {
                  ...(provider.readiness || {}),
                  configured: true,
                  status: "ready",
                  runnable: true,
                  message,
                },
                settings: {
                  ...(provider.settings || {}),
                  hostedProfileId: hostedProfileId || provider.settings?.hostedProfileId || "",
                  allowHosted: allowHosted || provider.settings?.allowHosted || false,
                },
              }
            : provider,
        );
        if (state.capabilities?.providers) {
          const readyCapabilityNames = providerId === "sam3-local" ? new Set(["sam3-local", "sam3-auto-masks"]) : new Set([providerId]);
          state.capabilities.providers = state.capabilities.providers.map((provider) =>
            readyCapabilityNames.has(provider.name)
              ? {
                  ...provider,
                  available: true,
                  configured: true,
                  installed: true,
                  runnable: true,
                  status: "ready",
                  reasons: [],
                }
              : provider,
          );
        }
      };
      if (capture.startsWith("model-setup")) {
        setWorkflowStep("provider_settings", { persist: false });
      } else if (capture.startsWith("model-plan")) {
        setWorkflowStep("prompt_preview", { persist: false });
      } else if (["workflow-review", "workflow-correct", "workflow-export"].includes(capture)) {
        setWorkflowStep("review_export", { persist: false });
      } else if (capture === "workflow-run") {
        setWorkflowStep("run_monitor", { persist: false });
      } else if (capture === "workflow-review-failure") {
        setWorkflowStep("run_monitor", { persist: false });
      } else if (captureUsesSam3Prepare) {
        setWorkflowStep("prompt_preview", { persist: false });
      } else if (capture === "advanced-config") {
        setWorkflowDashboard(true, { persist: false });
      } else if (capture === "new-project") {
        setWorkflowStep("source_video", { persist: false });
      } else if (capture === "extraction-wizard" || capture === "provider-diagnostics" || capture === "provider-settings") {
        setWorkflowStep("provider_settings", { persist: false });
      }

      if (capture.startsWith("model-setup")) {
        if (shell) {
          shell.style.display = "grid";
          shell.style.minHeight = "100vh";
        }
        if (sidebar) sidebar.style.display = "";
        if (rightRail) rightRail.style.display = "none";
        if (guidedStart) guidedStart.style.display = "none";
        if (workflowSteps) workflowSteps.style.display = "none";
        if (workspaceGrid) workspaceGrid.style.display = "none";
        state.jobs = [];
        state.selectedJobId = "";
        state.selectedJob = null;
        state.jobEvents = [];
        state.jobArtifacts = [];
        state.jobReview = null;
        state.reviewTracks = [];
        state.providerSetupJobs = {};
        state.selectedProviderSetupJobId = "";
        state.pendingModelSetupConfirmation = null;
        state.confirmedModelSetupAction = null;
        if (modelSetupPanel) {
          modelSetupPanel.style.display = "grid";
          modelSetupPanel.style.maxWidth = "1040px";
        }
        const captureState = {
          "model-setup": ["sam2-local", "", "neutral"],
          "model-setup-local": ["sam2-local", "Local SAM2 is selected. Save checkpoint and model config paths, then diagnose setup.", "warn"],
          "model-setup-hosted-warning": ["sam2-hosted:replicate-sam2-video", "Replicate SAM2 is selected. Save a token and confirm hosted cost/privacy before smoke tests or extraction.", "warn"],
          "model-setup-sam3-local": ["sam3-local", "SAM3 Scene Sweep is selected. Install the sam3-transformers extra, check Hugging Face access if needed, then diagnose setup before running.", "warn", "trace_all_objects"],
          "model-setup-sam3-roboflow": ["sam3-hosted:roboflow-sam3-pcs", "Roboflow SAM3 is selected. Paste an API key, save, then test setup before discovery.", "warn", "text_detector"],
          "model-setup-sam3-custom": ["sam3-hosted:custom-sam3-compatible", "Custom hosted SAM3 is selected. Save endpoint, key, and hosted opt-in before testing.", "warn", "trace_one_object"],
          "model-setup-missing": ["sam3-hosted:roboflow-sam3-pcs", "Paste a server-side Roboflow API key before hosted SAM3 concept discovery can run.", "bad"],
          "model-setup-invalid": ["sam3-hosted:roboflow-sam3-pcs", "Roboflow API key is invalid or too short. Paste the key without spaces.", "bad"],
          "model-setup-confirm-access": ["sam3-local", "Confirm the Hugging Face access check before caching facebook/sam3.", "warn", "trace_all_objects"],
          "model-setup-confirm-cache": ["sam2-hf-auto-masks", "SAM2 HF fallback is selected. Confirm the model cache action before using automatic masks.", "warn", "trace_all_objects"],
          "model-setup-cache-running": ["sam3-local", "Caching facebook/sam3 for scene sweep.", "neutral", "trace_all_objects"],
          "model-setup-cache-failed": ["sam3-local", "Model cache failed before verification. Review the message and cache again.", "bad", "trace_all_objects"],
          "model-setup-cache-success": ["sam3-local", "facebook/sam3 is cached and ready for scene sweep.", "ready", "trace_all_objects"],
          "model-setup-sam3-missing-runtime": ["sam3-local", "Install the SAM3 Scene Sweep runtime before caching facebook/sam3.", "bad", "trace_all_objects"],
          "model-setup-sam3-missing-cache": ["sam3-local", "SAM3 Scene Sweep runtime is installed. Cache facebook/sam3 before running.", "warn", "trace_all_objects"],
          "model-setup-success": ["sam2-local", "Diagnose found the local SAM2 paths and package imports needed for extraction.", "ready"],
        }[capture];
        if (captureState) {
          if (captureState[3]) applyPreset(captureState[3], { keepProvider: true });
          state.selectedModelSetupProviderId = captureState[0];
          state.modelSetupMessage = captureState[1];
          state.modelSetupTone = captureState[2];
          if (captureState[0] === "sam3-hosted:custom-sam3-compatible") state.modelSetupAlternativesOpen = true;
          if (captureState[0] === "sam3-local") markCaptureProviderReady("sam3-local");
          if (capture === "model-setup-sam3-missing-runtime") {
            markCaptureCapabilityBlocked("sam3-auto-masks", {
              reasons: ["SAM3 Tracker automatic-mask Transformers classes are not importable."],
              installHint: "Install MotionJSON's independent SAM3 Transformers runtime. SAM2 is not required.",
            });
          }
          if (capture === "model-setup-sam3-missing-cache") {
            markCaptureCapabilityReady("sam3-auto-masks", { message: "SAM3 Scene Sweep runtime is installed." });
          }
          if (captureState[0] === "sam2-local") markCaptureProviderReady("sam2-local");
          if (captureState[0] === "sam2-hf-auto-masks") markCaptureProviderReady("sam2-hf-auto-masks", { message: "SAM2 HF fallback runtime is available. Cache the selected model before running automatic masks." });
          if (captureState[0] === "sam3-hosted:custom-sam3-compatible") markCaptureProviderReady("sam3-hosted", { hostedProfileId: "custom-sam3-compatible", allowHosted: true });
          if (captureState[0] === "sam3-hosted:roboflow-sam3-pcs") markCaptureProviderReady("sam3-hosted", { hostedProfileId: "roboflow-sam3-pcs", allowHosted: true });
          if (captureState[0] === "sam2-hosted:replicate-sam2-video") markCaptureProviderReady("sam2-hosted", { hostedProfileId: "replicate-sam2-video", allowHosted: true });
          if (capture === "model-setup-confirm-cache") {
            state.pendingModelSetupConfirmation = modelSetupConfirmationForAction("cache-model", "sam2-hf-auto-masks", {
              model: "facebook/sam2.1-hiera-large",
              settingsPayload: modelSetupPayloadFromValues("sam2-hf-auto-masks", {
                selectedModel: "facebook/sam2.1-hiera-large",
              }),
            });
          }
          if (capture === "model-setup-confirm-access") {
            state.pendingModelSetupConfirmation = modelSetupConfirmationForAction("check-access", "sam3-local", {
              model: "facebook/sam3",
              settingsPayload: modelSetupPayloadFromValues("sam3-local", {
                selectedModel: "facebook/sam3",
              }),
            });
          }
          if (capture === "model-setup-cache-running" || capture === "model-setup-cache-failed" || capture === "model-setup-cache-success") {
            const status = capture === "model-setup-cache-running" ? "running" : capture === "model-setup-cache-failed" ? "failed" : "succeeded";
            const terminal = status !== "running";
            const toneProgress =
              status === "succeeded"
                ? { known: true, percent: 100, label: "Model cached" }
                : status === "failed"
                  ? { known: false, percent: 0, label: "Model cache failed" }
                  : { known: false, percent: 35, label: "Downloading or resolving Hugging Face snapshot" };
            const jobId = `capture-${capture}`;
            state.providerSetupJobs[jobId] = {
              id: jobId,
              providerId: "sam3-local",
              action: "cache_model",
              status,
              terminal,
              result: {
                ready: status === "succeeded",
                message:
                  status === "succeeded"
                    ? "Model cached. Continue to run when you are ready."
                    : status === "failed"
                      ? "Download was interrupted before verification. Cache model again after the network is stable."
                      : "Downloading or resolving the selected model cache.",
                progress: toneProgress,
              },
              progress: toneProgress,
              setupState: {
                status: status === "running" ? "caching_model" : status === "succeeded" ? "ready" : "failed_recoverable",
                label: status === "running" ? "Caching model" : status === "succeeded" ? "Ready" : "Needs recovery",
                message:
                  status === "running"
                    ? "Downloading or resolving the selected model cache."
                    : status === "succeeded"
                      ? "Model cached. Continue to run when you are ready."
                      : "Download was interrupted before verification. Cache model again after the network is stable.",
              },
              events: [
                {
                  id: `${jobId}-progress`,
                  type: status === "running" ? "downloading_cache" : status === "succeeded" ? "cached" : "failed",
                  message: toneProgress.label,
                  metadata: { progress: toneProgress },
                  createdAt: "2026-05-27T18:00:00Z",
                },
              ],
              createdAt: "2026-05-27T18:00:00Z",
              updatedAt: "2026-05-27T18:00:01Z",
            };
            state.selectedProviderSetupJobId = jobId;
          }
          renderModelSetup();
          if (capture === "model-setup-invalid") {
            const keyInput = document.querySelector("[data-model-setup-field='apiKey']");
            const hostedToggle = document.querySelector("[data-model-setup-field='allowHosted']");
            if (keyInput) keyInput.value = "bad key";
            if (hostedToggle) hostedToggle.checked = true;
          }
          if (capture === "model-setup-hosted-warning" || capture === "model-setup-missing") {
            const hostedToggle = document.querySelector("[data-model-setup-field='allowHosted']");
            if (hostedToggle) hostedToggle.checked = capture === "model-setup-missing";
          }
        }
      } else if (captureUsesSam3Prepare) {
        if (shell) {
          shell.style.display = "grid";
          shell.style.minHeight = "100vh";
        }
        if (sidebar) sidebar.style.display = "";
        if (rightRail) rightRail.style.display = "none";
        state.selectedProjectId = "project_layout";
        state.selectedVideoId = "video_layout";
        state.jobs = [];
        state.selectedJobId = "";
        state.selectedJob = null;
        state.jobEvents = [];
        state.jobArtifacts = [];
        state.jobReview = null;
        state.reviewTracks = [];
        state.video = {
          ...state.video,
          width: 1920,
          height: 1080,
          duration: 15,
          currentFrame: 36,
          loadedName: "prepare-demo.mp4",
        };
        elements.stage.classList.add("has-video", "has-studio-demo");
        $("#frameSlider").max = "180";
        $("#frameSlider").value = "36";
        $("#frameReadout").textContent = "frame 36";
        $("#videoMetricReadout").textContent = "1920x1080 px";
        state.prompts = [];
        state.strokes = [];
        state.keyframes = new Set([36]);
        if (capture === "prepare-sam3-single") {
          applyPreset("trace_one_object", { keepProvider: true });
          state.selectedModelSetupProviderId = "sam3-local";
          state.modelSetupAlternativesOpen = true;
          markCaptureProviderReady("sam3-local");
          state.prompts = [
            { id: "prompt_prepare_box", kind: "box", frame_index: 36, object_id: "selected_object", label: "Selected object", data: { x: 610, y: 248, w: 410, h: 468 } },
          ];
          $("#objectLabel").value = "Selected object";
        } else if (capture === "prepare-sam3-text") {
          applyPreset("text_detector", { keepProvider: true });
          state.selectedModelSetupProviderId = "sam3-hosted:roboflow-sam3-pcs";
          markCaptureProviderReady("sam3-hosted", { hostedProfileId: "roboflow-sam3-pcs", allowHosted: true });
          $("#textPrompt").value = "red ball";
        } else if (capture === "prepare-sam3-trace-all" || capture === "prepare-sam3-trace-all-runtime-ready" || capture === "prepare-sam3-trace-all-missing-runtime") {
          applyPreset("trace_all_objects", { keepProvider: true });
          state.selectedModelSetupProviderId = "sam3-local";
          if (capture === "prepare-sam3-trace-all-missing-runtime") {
            markCaptureCapabilityBlocked("sam3-auto-masks", {
              reasons: ["SAM3 Tracker automatic-mask Transformers classes are not importable."],
              installHint: "Install MotionJSON's independent SAM3 Transformers runtime. SAM2 is not required.",
            });
          } else if (capture === "prepare-sam3-trace-all-runtime-ready") {
            markCaptureCapabilityReady("sam3-auto-masks", { message: "SAM3 Scene Sweep runtime is ready." });
            markCaptureCapabilityBlocked("sam3-local", {
              reasons: ["Python module 'sam3' is not importable. SAM3_LOCAL_MODEL is only required for concept and exemplar workflows."],
              installHint: "Install the official SAM3 package and configure sam3.pt only for advanced concept/exemplar workflows.",
            });
          } else {
            markCaptureProviderReady("sam3-local");
          }
          $("#discoveryQualityPreset").value = "balanced";
        }
        renderModelSetup();
        renderPresetFields();
        renderConfigPreview();
        if (capture !== "prepare-sam3-trace-all-missing-runtime") setRunAlert("", "warning-box");
      } else if (["workflow-run", "workflow-run-stale", "workflow-run-logs-open"].includes(capture)) {
        if (shell) {
          shell.style.display = "grid";
          shell.style.minHeight = "100vh";
        }
        if (sidebar) sidebar.style.display = "";
        if (rightRail) rightRail.style.display = "none";
        const staleRunCapture = capture === "workflow-run-stale" || capture === "workflow-run-logs-open";
        if (capture === "workflow-run-logs-open" && rightRail) {
          rightRail.style.display = "";
        }
        applyPreset(staleRunCapture ? "trace_all_objects" : "trace_one_object", { keepProvider: true });
        state.selectedModelSetupProviderId = staleRunCapture ? "sam3-local" : "sam2-local";
        markCaptureProviderReady(staleRunCapture ? "sam3-local" : "sam2-local");
        state.selectedProjectId = "project_layout";
        state.projects = [{ id: "project_layout", name: "MotionJSON local project" }];
        state.selectedVideoId = "video_layout";
        state.jobs = [];
        state.selectedJobId = "";
        state.selectedJob = null;
        state.jobEvents = [];
        state.jobArtifacts = [];
        state.jobReview = null;
        state.reviewTracks = [];
        state.videos = [
          {
            id: "video_layout",
            project_id: "project_layout",
            kind: "source_video",
            contentUrl: "/api/videos/video_layout/content",
            metadata: { filename: "prepare-demo.mp4" },
            browserPreview: {
              status: "ready",
              kind: "native",
              contentUrl: "/api/videos/video_layout/content",
              posterUrl: "",
              width: 1920,
              height: 1080,
              duration: 15,
              codec: "h264",
            },
          },
        ];
        state.video = {
          ...state.video,
          width: 1920,
          height: 1080,
          duration: 15,
          currentFrame: 36,
          loadedName: "prepare-demo.mp4",
        };
        elements.stage.classList.add("has-video", "has-studio-demo");
        state.prompts = staleRunCapture
          ? []
          : [{ id: "prompt_run_point", kind: "positive_point", frame_index: 36, object_id: "selected_object", label: "Selected object", data: { x: 820, y: 520 } }];
        if (staleRunCapture) {
          const runConfig = buildRunConfig({
            preset: "trace_all_objects",
            discoveryMode: "sam3_auto_masks",
            projectId: "project_layout",
            videoId: "video_layout",
            sourcePath: "local-ui://assets/video_layout",
            videoPath: "local-ui://assets/video_layout",
            outputDirectory: "out/ui-runs/project_layout",
            objectLabel: "scene object",
            objectId: "scene_object",
            currentFrame: 36,
            keyframes: new Set([0, 36]),
            prompts: [],
            strokes: [],
            maskProvider: "sam3-local",
            device: "auto",
            sampleFps: "12",
            maxFrames: "48",
            minArea: "100",
            maxAreaRatio: "0.45",
            stabilityThreshold: "0.82",
            overlapThreshold: "0.72",
            maxObjects: "5",
            modelName: "facebook/sam3",
            outputMode: "authoring",
            qualityPreset: "clean",
          });
          const staleEventAt = new Date(Date.now() - 5 * 60 * 1000).toISOString();
          const jobEvent = {
            event_type: "progress",
            status: "running",
            stage: "candidate_discovery",
            message: "discovering object candidates",
            created_at: staleEventAt,
            metadata: {
              progress: { overallRatio: 0.31 },
              stage: "candidate_discovery",
              provider: "sam3-auto-masks",
            },
          };
          const loadingEvent = {
            event_type: "progress",
            status: "running",
            stage: "candidate_discovery",
            message: "loading SAM3 Tracker scene-sweep model",
            created_at: staleEventAt,
            metadata: {
              progress: { overallRatio: 0.31 },
              stage: "candidate_discovery",
              provider: "sam3-local",
            },
          };
          const job = {
            id: `job_${capture}_layout`,
            type: "extract",
            status: "running",
            progress: 31,
            percent: 31,
            payload: { mask_provider: "sam3-local", run_config: runConfig },
            result: { objects: 1 },
            updated_at: staleEventAt,
            lastEventAt: staleEventAt,
            message: "discovering object candidates",
            events: [loadingEvent, jobEvent],
          };
          state.jobs = [job];
          state.selectedJobId = job.id;
          state.selectedJob = job;
          state.lastRunConfig = runConfig;
          state.runConfigsByJob[job.id] = runConfig;
          state.jobEvents = [loadingEvent, jobEvent];
          state.reviewTracks = buildReviewTracks({ job, config: runConfig, artifacts: [] });
        }
        state.strokes = [];
        state.keyframes = new Set([36]);
        $("#frameSlider").max = "180";
        $("#frameSlider").value = "36";
        $("#frameReadout").textContent = "frame 36";
        $("#videoMetricReadout").textContent = "1920x1080 px";
        renderVideos();
        renderModelSetup();
        renderPresetFields();
        renderPromptList();
        renderConfigPreview();
        renderJobs();
        renderJobReview();
        if (capture === "workflow-run-logs-open" && $("#runLogsDisclosure")) {
          $("#runLogsDisclosure").open = true;
          if ($("#mainRunLogsDisclosure")) $("#mainRunLogsDisclosure").open = true;
          const parentDetails = $("#runLogsDisclosure").closest("details");
          if (parentDetails) parentDetails.open = true;
          $("#mainRunLogsDisclosure")?.scrollIntoView?.({ block: "start" });
        }
        setRunAlert("", "warning-box");
      } else if (capture.startsWith("model-plan")) {
        const showRunMonitor = ["model-plan-queued", "model-plan-running", "model-plan-succeeded"].includes(capture);
        if (shell) {
          shell.style.display = "grid";
          if (showRunMonitor && window.innerWidth >= 980) {
            shell.style.gridTemplateColumns = "minmax(0, 1fr) 420px";
          }
          shell.style.minHeight = "100vh";
        }
        if (sidebar) sidebar.style.display = "";
        if (guidedStart) guidedStart.style.display = "none";
        if (workflowSteps) workflowSteps.style.display = "none";
        if (modelSetupPanel) modelSetupPanel.style.display = "none";
        if (workspaceGrid) workspaceGrid.style.display = "none";
        if (modelPlanPanel) {
          modelPlanPanel.style.display = "grid";
          modelPlanPanel.style.maxWidth = "1040px";
        }
        if (rightRail) {
          rightRail.style.display = showRunMonitor ? "grid" : "none";
          rightRail.style.gridTemplateColumns = "1fr";
          rightRail.style.gap = "16px";
          rightRail.style.borderLeft = "0";
        }
        document.querySelectorAll(".right-rail > details").forEach((details) => {
          const summary = details.querySelector("summary")?.textContent?.trim().toLowerCase() || "";
          details.open = showRunMonitor && summary === "run monitor";
        });

        state.selectedProjectId = "project_layout";
        state.selectedVideoId = capture === "model-plan-preview" ? "" : "video_layout";
        const runConfig = buildRunConfig({
          preset: "text_detector",
          discoveryMode: "text_detector",
          projectId: state.selectedProjectId,
          videoId: state.selectedVideoId,
          sourcePath: state.selectedVideoId ? `local-ui://assets/${state.selectedVideoId}` : "examples/demo_red_ball.mp4",
          videoPath: state.selectedVideoId ? `local-ui://assets/${state.selectedVideoId}` : "examples/demo_red_ball.mp4",
          outputDirectory: "out/ui-runs/project_layout",
          objectLabel: "red ball",
          objectId: "red_ball",
          currentFrame: 0,
          keyframes: new Set([0]),
          prompts: [],
          strokes: [],
          maskProvider: "mock",
          device: "auto",
          sampleFps: "12",
          maxFrames: "48",
          minArea: "100",
          maxAreaRatio: "0.65",
          stabilityThreshold: "0.82",
          overlapThreshold: "0.72",
          boxThreshold: "0.35",
          textThreshold: "0.25",
          motionSensitivity: "32",
          maxObjects: "3",
          modelName: "auto",
          outputMode: "authoring",
          qualityPreset: "balanced",
          traceEverythingMode: false,
          traceEverythingAcknowledged: false,
          textPrompt: "red ball",
          classPreset: "common_objects",
          classList: "",
          externalMaskDir: "masks/object_0",
        });
        const warningRunConfig =
          capture === "model-plan-warning"
            ? { ...runConfig, provider: { ...runConfig.provider, name: "sam2-local" } }
            : runConfig;
        const warningValidation = {
          valid: true,
          errors: [],
          warnings: [
            {
              severity: "error",
              message: "sam2-local is not available on this machine. Choose mock/local before starting.",
              action: "Choose a ready no-model provider before confirming.",
            },
          ],
          runConfig: warningRunConfig,
        };
        const validation =
          capture === "model-plan-warning"
            ? warningValidation
            : { valid: true, errors: [], warnings: [], runConfig };
        const modelPlan = {
          providerId: "fake-local-planner",
          status: "planned",
          goal: "find_objects_from_text",
          request: {
            goal: "find_objects_from_text",
            prompt: "Find the red ball and keep only reviewed tracks.",
            projectId: state.selectedProjectId,
            videoId: state.selectedVideoId || null,
            objectLabel: "red ball",
            objectId: "red_ball",
            textPrompt: "red ball",
          },
          providerPlan: {
            reasoningProvider: "fake-local-planner",
            discoveryProvider: "text_detector",
            maskProvider: warningRunConfig.provider.name,
            trackingMode: "selected_only",
            reviewRequired: true,
          },
          privacy: {
            framesLeaveDevice: false,
            hostedCallsRequired: false,
            summary: "Fake/local planning keeps frames and prompts on this machine.",
          },
          estimatedCost: {
            status: "zero_local",
            message: "No hosted provider cost.",
          },
          requiresUserConfirmation: true,
          runConfig: warningRunConfig,
          validation,
          messages: ["Review the generated plan, then confirm before extraction starts."],
        };
        state.modelPlanRun = {
          id: "model_run_layout",
          providerId: "fake-local-planner",
          status: "succeeded",
          result: modelPlan,
          events: [
            { eventType: "queued", message: "model planning request queued" },
            { eventType: "running", message: "fake local planner generated a run plan" },
            { eventType: "planned", message: "run plan ready for confirmation" },
          ],
        };
        state.modelPlanValidation = validation;
        state.modelPlanConfirmedJobId = "";
        state.modelPlanMessage =
          capture === "model-plan-warning"
            ? "Backend validation found a provider blocker before any job was started."
            : capture === "model-plan-confirmation"
              ? "Generated config validated. Confirmation will create the extraction job."
              : "";
        state.modelPlanTone = capture === "model-plan-warning" ? "bad" : "ready";
        const jobStatus = {
          "model-plan-queued": ["queued", 0, "model plan attached; worker waiting"],
          "model-plan-running": ["running", 42, "extracting object tracks"],
          "model-plan-succeeded": ["succeeded", 100, "job completed"],
        }[capture];
        if (jobStatus) {
          const [status, progress, message] = jobStatus;
          const job = {
            id: "job_model_plan_layout",
            type: "extract",
            status,
            progress,
            percent: progress,
            payload: { mask_provider: "mock", run_config: runConfig },
            result: status === "succeeded" ? { objects: 1 } : {},
            updated_at: "2026-05-20T12:00:00Z",
            message,
          };
          state.jobs = [job];
          state.selectedJobId = job.id;
          state.modelPlanConfirmedJobId = job.id;
          state.selectedJob = job;
          state.jobEvents = [
            { event_type: "model_plan_attached", message: "model-generated plan attached for user review", metadata: { modelRunId: state.modelPlanRun.id } },
            { event_type: "worker_start_requested", message: "local UI worker start requested after model-plan confirmation", metadata: { progress: { overallRatio: progress / 100 } } },
          ];
          state.jobArtifacts = [];
          state.reviewTracks = buildReviewTracks({ job, config: runConfig, artifacts: [] });
          renderJobs();
          renderJobReview();
        }
        renderModelPlanPanel();
      } else if (capture === "first-run" || capture === "preview-failed") {
        if (shell) {
          shell.style.display = "grid";
          shell.style.minHeight = "100vh";
        }
        if (sidebar) sidebar.style.display = "";
        if (rightRail) rightRail.style.display = "none";
        if (capture === "preview-failed") {
          applyPreset("trace_one_object", { keepProvider: true, skipAutoAdvance: true });
          state.selectedProjectId = "project_layout";
          state.projects = [{ id: "project_layout", name: "MotionJSON local project" }];
          state.videos = [
            {
              id: "video_preview_failed",
              project_id: "project_layout",
              kind: "source_video",
              contentUrl: "/api/videos/video_preview_failed/content",
              metadata: { filename: "legacy_clip.mp4" },
              browserPreview: {
                status: "failed",
                kind: "transcoded",
                contentUrl: "",
                posterUrl: "",
                width: 640,
                height: 360,
                duration: 4,
                codec: "mpeg4",
                reason: "ffmpeg executable was not found while preparing a browser-safe preview.",
                errorMessage: "ffmpeg executable was not found while preparing a browser-safe preview.",
              },
            },
          ];
          state.selectedVideoId = "video_preview_failed";
          setWorkflowStep("source_video", { persist: false });
          renderVideos();
          renderWorkflowStepper();
        }
      } else if (capture === "extraction-wizard") {
        applyPreset("text_detector");
      } else if (capture === "provider-diagnostics") {
        applyPreset("motion_foreground");
        if (goalList) goalList.style.display = "none";
        if (firstRunPanel) firstRunPanel.style.display = "none";
      } else if (capture === "provider-settings") {
        if (shell) {
          shell.style.display = "grid";
          shell.style.minHeight = "100vh";
        }
        if (sidebar) sidebar.style.display = "";
        if (workspace) workspace.style.display = "none";
        if (rightRail) {
          rightRail.style.display = "block";
          rightRail.style.borderLeft = "0";
          rightRail.style.minHeight = "100vh";
        }
        document.querySelectorAll(".right-rail > details").forEach((details) => {
          details.open = details.querySelector("#providerSettingsPanel") !== null;
        });
      } else if (capture === "new-project") {
        if (shell && window.innerWidth > 860) shell.style.gridTemplateColumns = "260px minmax(0, 1fr)";
        if (rightRail) rightRail.style.display = "none";
        if (wizardPanel) wizardPanel.style.display = "none";
      } else if (capture === "advanced-config") {
        applyPreset("text_detector");
        if (shell) {
          shell.style.display = "grid";
          shell.style.minHeight = "100vh";
        }
        if (sidebar) sidebar.style.display = "";
        if (rightRail) rightRail.style.display = "none";
        if (guidedStart) guidedStart.style.display = "none";
        if (workflowSteps) workflowSteps.style.display = "none";
        if (viewerPanel) viewerPanel.style.display = "none";
        if (workspaceGrid) {
          workspaceGrid.style.gridTemplateColumns = "minmax(0, 1fr)";
          workspaceGrid.style.gridTemplateAreas = '"config" "setup" "wizard"';
        }
        if (configPanel) configPanel.style.order = "-1";
        if (rawConfigDisclosure) rawConfigDisclosure.open = true;
      } else if (["workflow-review", "workflow-correct", "workflow-export"].includes(capture)) {
        applyReviewCaptureFixture(capture);
        markCaptureProviderReady("sam2-local");
        setWorkflowStep("review_export", { persist: false });
        setRunAlert("", "warning-box");
      } else if (capture === "workflow-review-failure") {
        applyReviewCaptureFixture(capture);
        markCaptureProviderReady("sam3-local");
        setWorkflowStep("run_monitor", { persist: false });
        setRunAlert("", "warning-box");
      } else if (["candidate-review", "correction-tools", "export-gate", "export-handoff", "export-success", "copyable-snippet"].includes(capture)) {
        applyReviewCaptureFixture(capture);
        markCaptureProviderReady("sam2-local");
        setWorkflowStep("review_export", { persist: false });
        setRunAlert("", "warning-box");
        if (capture === "candidate-review") {
          const backgroundFilter = document.querySelector("#candidateFilterNotBackground");
          const duplicateFilter = document.querySelector("#candidateFilterNotDuplicate");
          if (backgroundFilter) backgroundFilter.checked = false;
          if (duplicateFilter) duplicateFilter.checked = false;
          renderCandidateSummary();
        }
      } else if (capture === "job-review") {
        if (shell) {
          shell.style.display = "grid";
          shell.style.minHeight = "100vh";
        }
        if (sidebar) sidebar.style.display = "";
        if (workspace) workspace.style.display = "none";
        if (rightRail) {
          rightRail.style.display = "grid";
          rightRail.style.gridTemplateColumns = window.innerWidth < 760 ? "1fr" : "repeat(2, minmax(0, 1fr))";
          rightRail.style.gap = "16px";
          rightRail.style.borderLeft = "0";
          rightRail.style.minHeight = "100vh";
        }
        document.querySelectorAll(".right-rail > details").forEach((details) => {
          const summary = details.querySelector("summary")?.textContent?.trim().toLowerCase() || "";
          details.open = ["run monitor", "review", "review candidates and tracks", "artifacts and exports", "preview and export"].includes(summary);
        });
      }

      window.setTimeout(() => {
        window.scrollTo({ top: 0, left: 0 });
        document.documentElement.dataset.captureReady = "true";
      }, 800);
    }

    async function startJobFromConfig({ forceMock = false } = {}) {
      if (!state.selectedProjectId) {
        setRunAlert("Create or select a local project before starting a run.", "warning-box is-bad");
        $("#runStatus").textContent = "No project";
        $("#runStatus").className = "status-chip is-bad";
        $("#fallbackDiagnostics").innerHTML = `<div class="diagnostic-row is-bad"><strong>project required</strong><span class="row-meta">Create or select a local project before starting a run.</span></div>`;
        return;
      }
      if (!state.selectedVideoId) {
        setRunAlert("Register and select a local source video before starting a run.", "warning-box is-bad");
        $("#runStatus").textContent = "No video";
        $("#runStatus").className = "status-chip is-bad";
        $("#fallbackDiagnostics").innerHTML = `<div class="diagnostic-row is-bad"><strong>video required</strong><span class="row-meta">Register and select a local source video before starting a run.</span></div>`;
        return;
      }

      let config;
      try {
        config = buildRunConfig(collectFormState($));
      } catch (error) {
        setRunAlert(error.message, "warning-box is-bad");
        $("#runStatus").textContent = "Config invalid";
        $("#runStatus").className = "status-chip is-bad";
        $("#fallbackDiagnostics").innerHTML = `<div class="diagnostic-row is-bad"><strong>config</strong><span class="row-meta">${escapeHtml(error.message)}</span></div>`;
        return;
      }

      const requestedProvider = forceMock ? "mock" : config.provider.name;
      const runtimeConfig = forceMock ? { ...config, provider: { ...config.provider, name: "mock" } } : config;
      state.lastRunConfig = runtimeConfig;

      if (!forceMock && !LOCAL_JOB_PROVIDERS.has(requestedProvider)) {
        setRunAlert(
          `Local UI job execution currently accepts SAM2 local/hosted, threshold, motion, or external providers. ${requestedProvider} remains capability-gated.`,
          "warning-box is-bad",
        );
        $("#runStatus").textContent = "Provider gated";
        $("#runStatus").className = "status-chip is-bad";
        $("#fallbackDiagnostics").innerHTML = `
          <div class="diagnostic-row is-bad">
            <strong>${escapeHtml(requestedProvider)}</strong>
            <span class="row-meta">Choose a configured SAM2 local/hosted provider, motion, threshold, or external masks before starting this job.</span>
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
        setRunAlert(error.message, "warning-box is-bad");
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

    async function cancelSelectedJob() {
      const job = selectedJob();
      const id = jobIdentifier(job);
      if (!id || $("#cancelJobButton").disabled) return;
      $("#cancelJobButton").disabled = true;
      $("#cancelJobButton").textContent = "Cancel requested";
      try {
        const response = await api(`/api/jobs/${encodeURIComponent(id)}/cancel`, {
          method: "POST",
          body: JSON.stringify({ reason: "user_canceled" }),
        });
        state.selectedJob = response.job || state.selectedJob;
        state.jobs = state.jobs.map((item) => (jobIdentifier(item) === id ? state.selectedJob : item));
        await refreshProjectData({ quiet: true });
        await refreshSelectedJobReview();
      } catch (error) {
        $("#runStatus").textContent = "Cancel failed";
        $("#runStatus").className = "status-chip is-bad";
        setRunAlert(error.message, "warning-box is-bad");
        renderSelectedJobFacts();
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

    async function trackSelectedCandidatesWithApi() {
      if (!state.selectedJobId) {
        state.candidateTrackingStatus = "Select a run before tracking candidates.";
        renderCandidateSummary();
        return;
      }
      const candidates = reviewCandidates();
      const ids = selectedCandidateIds(candidates);
      if (!ids.length) {
        state.candidateTrackingStatus = "Select at least one reviewable API candidate.";
        renderCandidateSummary();
        return;
      }
      state.candidateTrackingStatus = "tracking";
      renderCandidateSummary();
      try {
        const response = await api(trackSelectedRoute(state.selectedJobId), {
          method: "POST",
          body: JSON.stringify(trackSelectedPayload(ids)),
        });
        if (response?.review) state.jobReview = response.review;
        if (response?.artifacts) state.jobArtifacts = asArray(response.artifacts);
        if (response?.job) {
          state.selectedJob = response.job;
          state.jobs = state.jobs.map((item) => (jobIdentifier(item) === state.selectedJobId ? response.job : item));
        }
        await refreshProjectData({ quiet: true });
        state.candidateTrackingStatus = `Tracked ${ids.length} selected candidate${ids.length === 1 ? "" : "s"}; export remains review-gated.`;
        renderJobReview();
      } catch (error) {
        state.candidateTrackingStatus = error.message;
        renderCandidateSummary();
      }
    }

    async function markReviewedTracksForExport() {
      const eligibleTracks = state.reviewTracks.filter((track) => track.exportable !== false && track.demoMode !== true && !track.deleted);
      if (!eligibleTracks.length) {
        setRunAlert("No materialized object tracks are available to mark for export.", "warning-box is-bad");
        focusReviewDetail("tracks");
        return;
      }
      const pendingTracks = eligibleTracks.filter((track) => !isTrackExportIncluded(track));
      if (!pendingTracks.length) {
        setRunAlert("Reviewed tracks are already marked for export.", "warning-box is-ready");
        renderWorkflowStepper();
        return;
      }
      for (const track of pendingTracks) {
        await submitCorrectionAction({
          type: "set_export_inclusion",
          trackId: track.id,
          included: true,
        });
      }
      setRunAlert(`${pendingTracks.length} reviewed track${pendingTracks.length === 1 ? "" : "s"} marked for export.`, "warning-box is-ready");
      renderJobReview();
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

    async function copyTextToClipboard(text) {
      if (!text) return false;
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      const copied = document.execCommand("copy");
      textarea.remove();
      return copied;
    }

    async function handleExportHandoffAction(event) {
      const button = event.target.closest("[data-export-handoff-action]");
      if (!button) return;
      const action = button.dataset.exportHandoffAction || "";
      const id = button.dataset.exportHandoffId || "";
      if (action === "export") {
        await exportSelectedMotionJson();
        return;
      }
      if (action === "open") {
        const url = safeLocalContentUrl(button.dataset.exportHandoffUrl);
        if (url) window.open(url, "_blank", "noopener,noreferrer");
        return;
      }
      if (action === "copy") {
        const copied = await copyTextToClipboard(state.exportCopyPayloads[id] || "");
        state.exportCopiedHandoffId = copied ? id : "";
        renderExportPanel();
        $("#exportStatus").textContent = copied ? "Copied" : "Copy failed";
        $("#exportStatus").className = `status-chip ${copied ? "is-ready" : "is-bad"}`;
      }
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
      if (!state.selectedProjectId) await ensureStarterProject();
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
        setWorkflowStep("review_export", { focusStep: true });
      } catch (error) {
        state.importStatus = error.message;
        $("#importStatus").textContent = "Import failed";
      }
    }

    async function refreshLibraryData() {
      const entries = await Promise.all(
        [
          ["libraryAssets", libraryAssetRoute()],
          ["libraryCollections", "/api/library/collections"],
          ["libraryPacks", "/api/library/packs"],
        ].map(async ([key, route]) => {
          try {
            return [key, await api(route), null];
          } catch (error) {
            return [key, null, error.message];
          }
        }),
      );
      state.errors.library = "";
      for (const [key, payload, error] of entries) {
        if (error) state.errors.library = [state.errors.library, error].filter(Boolean).join(" ");
        if (key === "libraryAssets") state.libraryAssets = payload?.assets || [];
        if (key === "libraryCollections") state.libraryCollections = payload?.collections || [];
        if (key === "libraryPacks") state.libraryPacks = payload?.packs || [];
      }
      renderAssetLibraryPanel();
    }

    async function saveSelectedLibraryAsset() {
      const artifactId = selectedLibraryArtifactId();
      if (!state.selectedProjectId || !artifactId) return;
      $("#libraryStatus").textContent = "Saving";
      $("#libraryStatus").className = "status-chip is-neutral";
      try {
        const response = await api(`/api/projects/${encodeURIComponent(state.selectedProjectId)}/library-assets`, {
          method: "POST",
          body: JSON.stringify({
            assetId: artifactId,
            type: "motion_sticker",
            title: $("#libraryAssetTitle").value.trim() || "Reusable motion layer",
            description: "Saved from the local UI asset library panel.",
            tags: libraryTagsFromInput(),
            metadata: { source: "local_ui_asset_library" },
          }),
        });
        state.selectedLibraryAssetId = response.libraryAsset?.id || response.asset?.id || state.selectedLibraryAssetId;
        await refreshLibraryData();
      } catch (error) {
        state.errors.library = error.message;
        renderAssetLibraryPanel();
      }
    }

    async function createLibraryCollection() {
      const title = $("#libraryCollectionTitle").value.trim();
      if (!title) return;
      $("#libraryStatus").textContent = "Creating";
      $("#libraryStatus").className = "status-chip is-neutral";
      try {
        await api("/api/library/collections", {
          method: "POST",
          body: JSON.stringify({
            projectId: state.selectedProjectId || null,
            title,
            metadata: { source: "local_ui_asset_library" },
          }),
        });
        state.selectedLibraryCollectionId = "";
        await refreshLibraryData();
      } catch (error) {
        state.errors.library = error.message;
        renderAssetLibraryPanel();
      }
    }

    async function addSelectedLibraryAssetToCollection() {
      const asset = selectedLibraryAsset();
      const collectionId = selectedLibraryCollectionId();
      if (!asset || !collectionId) return;
      $("#libraryStatus").textContent = "Adding";
      $("#libraryStatus").className = "status-chip is-neutral";
      try {
        await api(`/api/library/collections/${encodeURIComponent(collectionId)}/assets`, {
          method: "POST",
          body: JSON.stringify({ libraryAssetId: asset.id }),
        });
        await refreshLibraryData();
      } catch (error) {
        state.errors.library = error.message;
        renderAssetLibraryPanel();
      }
    }

    async function createCreatorPackFromCollection() {
      const collectionId = selectedLibraryCollectionId();
      const title = $("#libraryPackTitle").value.trim();
      if (!collectionId || !title) return;
      $("#libraryStatus").textContent = "Creating pack";
      $("#libraryStatus").className = "status-chip is-neutral";
      try {
        await api("/api/library/packs", {
          method: "POST",
          body: JSON.stringify({
            collectionId,
            title,
            metadata: { source: "local_ui_asset_library" },
          }),
        });
        await refreshLibraryData();
      } catch (error) {
        state.errors.library = error.message;
        renderAssetLibraryPanel();
      }
    }

    $("#refreshButton").addEventListener("click", refreshAll);
    $("#workspaceRecent").addEventListener("click", (event) => {
      const button = event.target.closest("[data-preset]");
      if (!button) return;
      applyPreset(button.dataset.preset);
    });
    $("#workspacePreferencesForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = {
        preferences: {
          defaultGoal: $("#preferenceDefaultGoal").value,
          defaultExportPreset: $("#preferenceExportPreset").value,
          lastProjectId: state.selectedProjectId || null,
        },
      };
      const response = await api("/api/preferences", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (state.workspace) state.workspace.preferences = response;
      await refreshAll();
    });
    $("#startRunButton").addEventListener("click", () => startJobFromConfig({ forceMock: false }));
    $("#startMockRunButton").addEventListener("click", () => startJobFromConfig({ forceMock: true }));
    $("#cancelJobButton").addEventListener("click", cancelSelectedJob);
    $("#mainCancelJobButton")?.addEventListener("click", cancelSelectedJob);
    $("#openLogsButton")?.addEventListener("click", openRunLogsAndDiagnostics);
    $("#mainOpenLogsButton")?.addEventListener("click", openRunLogsAndDiagnostics);
    $("#runAgainButton")?.addEventListener("click", runAgainFromTerminalJob);
    $("#mainRunAgainButton")?.addEventListener("click", runAgainFromTerminalJob);
    $("#changeSetupButton")?.addEventListener("click", () => prepareNewGuidedRun("prompt_preview"));
    $("#mainChangeSetupButton")?.addEventListener("click", () => prepareNewGuidedRun("prompt_preview"));
    $("#chooseModelButton")?.addEventListener("click", () => prepareNewGuidedRun("provider_settings"));
    $("#mainChooseModelButton")?.addEventListener("click", () => prepareNewGuidedRun("provider_settings"));
    $("#validateExportButton").addEventListener("click", validateSelectedExport);
    $("#exportMotionJsonButton").addEventListener("click", exportSelectedMotionJson);
    $("#exportPresetSelect").addEventListener("change", applyExportPresetDefaults);
    $("#exportHandoffCards").addEventListener("click", handleExportHandoffAction);
    $("#exportNextSteps").addEventListener("click", handleExportHandoffAction);
    ["exportIncludeMasks", "exportIncludeContours", "exportIncludePreview"].forEach((id) => {
      $(`#${id}`).addEventListener("change", clearExportPreflightState);
    });

    $("#librarySearchForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await refreshLibraryData();
    });
    $("#saveLibraryAssetButton").addEventListener("click", saveSelectedLibraryAsset);
    $("#libraryArtifactSelect").addEventListener("change", (event) => {
      state.selectedLibraryArtifactId = event.target.value;
      renderAssetLibraryPanel();
    });
    $("#libraryAssetList").addEventListener("click", (event) => {
      const row = event.target.closest("[data-library-asset-id]");
      if (!row) return;
      state.selectedLibraryAssetId = row.dataset.libraryAssetId;
      renderAssetLibraryPanel();
    });
    $("#libraryCollectionSelect").addEventListener("change", (event) => {
      state.selectedLibraryCollectionId = event.target.value;
      renderAssetLibraryPanel();
    });
    $("#libraryCollectionForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await createLibraryCollection();
    });
    $("#addLibraryAssetToCollectionButton").addEventListener("click", addSelectedLibraryAssetToCollection);
    $("#libraryPackForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await createCreatorPackFromCollection();
    });

    async function handleJobChoiceClick(event) {
      const choice = event.target.closest("[data-job-id]");
      if (!choice) return;
      state.selectedJobId = choice.dataset.jobId;
      state.candidateTrackingStatus = "";
      renderJobs();
      await refreshSelectedJobReview();
      if (shouldPollJobs()) startPolling();
    }

    $("#jobList").addEventListener("click", handleJobChoiceClick);
    $("#mainJobList")?.addEventListener("click", handleJobChoiceClick);

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
        renderSelectedTrackDetail();
        renderCorrectionPanel();
      }
    });

    $("#candidateSummaryList").addEventListener("change", (event) => {
      const checkbox = event.target.closest("[data-candidate-select]");
      if (!checkbox) return;
      state.candidateSelection[checkbox.dataset.candidateSelect] = checkbox.checked;
      state.candidateTrackingStatus = "";
      renderCandidateSummary();
    });

    $("#candidateSummaryList").addEventListener("click", (event) => {
      const row = event.target.closest("[data-candidate-row]");
      if (!row || event.target.closest("input, a, button, label")) return;
      const id = row.dataset.candidateRow;
      const candidate = reviewCandidates().find((item) => candidateId(item) === id);
      if (!candidateSelectable(candidate)) return;
      state.candidateSelection[id] = state.candidateSelection[id] !== true;
      state.candidateTrackingStatus = "";
      renderCandidateSummary();
    });

    [
      "candidateFilterSelected",
      "candidateFilterStable",
      "candidateFilterMoving",
      "candidateFilterNotBackground",
      "candidateFilterNotDuplicate",
      "candidateMinCoverage",
    ].forEach((id) => {
      $(`#${id}`).addEventListener("input", renderCandidateSummary);
      $(`#${id}`).addEventListener("change", renderCandidateSummary);
    });

    $("#trackSelectedCandidatesButton").addEventListener("click", trackSelectedCandidatesWithApi);

    $("#trackList").addEventListener("click", (event) => {
      const editButton = event.target.closest("[data-track-edit]");
      if (editButton) {
        state.selectedCorrectionTrackId = editButton.dataset.trackEdit;
        renderTrackList();
        renderSelectedTrackDetail();
        renderCorrectionPanel();
        return;
      }

      const deleteButton = event.target.closest("[data-track-delete]");
      if (deleteButton) {
        submitCorrectionAction({ type: "delete_track", trackId: deleteButton.dataset.trackDelete });
        return;
      }

      const row = event.target.closest("[data-track-row]");
      if (row) {
        state.selectedCorrectionTrackId = row.dataset.trackRow;
        renderTrackList();
        renderSelectedTrackDetail();
        renderCorrectionPanel();
      }
    });

    $("#studioObjectList").addEventListener("change", (event) => {
      const exportToggle = event.target.closest("[data-studio-track-export]");
      if (!exportToggle || !exportToggle.dataset.studioTrackExport) return;
      submitCorrectionAction({
        type: "set_export_inclusion",
        trackId: exportToggle.dataset.studioTrackExport,
        included: exportToggle.checked,
      });
    });

    $("#studioObjectList").addEventListener("click", (event) => {
      const visibleToggle = event.target.closest("[data-studio-track-visible]");
      if (visibleToggle && visibleToggle.dataset.studioTrackVisible) {
        const trackId = visibleToggle.dataset.studioTrackVisible;
        const visible = visibleToggle.dataset.visible !== "true";
        state.trackVisibility[trackId] = visible;
        submitCorrectionAction({ type: "set_track_visibility", trackId, visible });
        return;
      }

      const row = event.target.closest("[data-studio-track-row]");
      if (!row || !row.dataset.studioTrackRow || event.target.closest("input, button")) return;
      state.selectedCorrectionTrackId = row.dataset.studioTrackRow;
      renderTrackList();
      renderSelectedTrackDetail();
      renderCorrectionPanel();
      renderStudioReviewPanel();
      scheduleDrawOverlay();
    });

    $("#studioRejectBackgroundButton").addEventListener("click", () => {
      for (const candidate of reviewCandidates()) {
        const id = candidateId(candidate);
        if (id && /background|whole_frame|wall|floor|ground|lawn|plant|fence/.test(candidateReasonText(candidate) || String(candidate.label || "").toLowerCase())) {
          state.candidateSelection[id] = false;
        }
      }
      $("#candidateFilterNotBackground").checked = true;
      renderCandidateSummary();
      renderStudioReviewPanel();
    });

    $("#studioMergeDuplicatesButton").addEventListener("click", () => {
      const duplicateTracks = state.reviewTracks.filter((track) => /duplicate|overlap|same object/i.test(`${track.label || ""} ${asArray(track.warnings).join(" ")}`));
      const mergeTargets = duplicateTracks.length >= 2 ? duplicateTracks.slice(0, 2) : state.reviewTracks.slice(0, 2);
      state.mergeSelection = new Set(mergeTargets.map((track) => track.id).filter(Boolean));
      setWorkflowStep("review_export", { focusStep: true });
      renderTrackList();
      renderSelectedTrackDetail();
      renderCorrectionPanel();
      renderStudioReviewPanel();
    });

    $("#studioSegmentEditButton").addEventListener("click", () => {
      setWorkflowStep("provider_settings", { focusStep: true });
      const disclosure = $("#traceEverythingDisclosure");
      disclosure.open = true;
      disclosure.scrollIntoView({ behavior: "smooth", block: "center" });
    });

    $("#studioExportSelectedButton").addEventListener("click", validateSelectedExport);
    $("#studioExportAllButton").addEventListener("click", exportSelectedMotionJson);
    $("#studioCreatePackageButton").addEventListener("click", exportSelectedMotionJson);
    $("#studioValidateExportButton").addEventListener("click", validateSelectedExport);
    $("#studioExportMotionJsonButton").addEventListener("click", exportSelectedMotionJson);

    $("#correctionTrackSelect").addEventListener("change", (event) => {
      state.selectedCorrectionTrackId = event.target.value;
      renderTrackList();
      renderSelectedTrackDetail();
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
      renderSelectedTrackDetail();
      renderCorrectionPanel();
    });

    document.querySelectorAll(".goal, .goal-card").forEach((button) => {
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
        setWorkflowStep("source_video", { focusStep: true });
      } catch (error) {
        state.errors.projects = error.message;
        renderProjects();
      }
    });

    $("#projectRailNewButton")?.addEventListener("click", () => {
      setWorkflowStep("choose_goal", { focusStep: true });
      $("#projectName")?.focus?.({ preventScroll: false });
    });

    $("#projectRailList")?.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-project-rail-id]");
      if (!button) return;
      state.selectedProjectId = button.dataset.projectRailId || "";
      state.selectedVideoId = "";
      state.selectedJobId = "";
      state.selectedJob = null;
      state.jobEvents = [];
      state.jobArtifacts = [];
      state.reviewTracks = [];
      await refreshProjectData();
      renderProjects();
      renderVideos();
      setWorkflowStep("source_video", { focusStep: true });
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
      try {
        if (!state.selectedProjectId) await ensureStarterProject();
        await api("/api/videos", {
          method: "POST",
          body: JSON.stringify({ projectId: state.selectedProjectId, path: $("#videoPath").value.trim() }),
        });
        await refreshProjectData();
        setRunAlert("", "warning-box is-ready");
        setWorkflowStep("source_video", { focusStep: true });
      } catch (error) {
        $("#videoList").innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
      }
    });

    $("#importMotionJsonForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await importExistingMotionJson();
    });

    $("#retryPreviewButton").addEventListener("click", retrySelectedVideoPreview);

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
      scheduleDrawOverlay();
    });

    elements.video.addEventListener("error", () => {
      state.video.width = 0;
      state.video.height = 0;
      state.video.duration = 0;
      elements.stage.classList.remove("has-video");
      const preview = selectedVideoBrowserPreview();
      $("#emptyViewerState strong").textContent = preview?.status === "ready" ? "Playback unavailable" : "Preview failed";
      $("#emptyViewerState span").textContent =
        preview?.reason ||
        preview?.errorMessage ||
        "This browser could not play the prepared preview for the selected video.";
      renderVideoMetrics();
    });

    elements.video.addEventListener("timeupdate", () => {
      renderVideoMetrics();
      scheduleDrawOverlay();
    });

    elements.video.addEventListener("seeked", () => {
      renderVideoMetrics();
      scheduleDrawOverlay();
    });

    elements.video.addEventListener("play", () => {
      $("#playPauseButton").textContent = "Pause";
    });

    elements.video.addEventListener("pause", () => {
      $("#playPauseButton").textContent = "Play";
    });

    $("#playPauseButton").addEventListener("click", togglePreviewPlayback);

    $("#frameSlider").addEventListener("input", (event) => {
      seekToFrame(event.target.value);
    });

    $("#markKeyframeButton").addEventListener("click", () => markKeyframe());

    function jumpToTimelineMarker(target) {
      const frame = toInteger(target?.dataset?.timelineFrame, state.video.currentFrame);
      const objectId = target?.dataset?.timelineObject || "";
      seekToFrame(frame);
      if (objectId && state.reviewTracks.some((track) => track.id === objectId || track.objectId === objectId)) {
        state.selectedCorrectionTrackId = objectId;
        renderTrackList();
        renderSelectedTrackDetail();
        renderCorrectionPanel();
      }
    }

    $("#timelineMarkerTrack").addEventListener("click", (event) => {
      const marker = event.target.closest("[data-timeline-frame]");
      if (marker) jumpToTimelineMarker(marker);
    });

    $("#timelineMarkerList").addEventListener("click", (event) => {
      const marker = event.target.closest("[data-timeline-frame]");
      if (marker) jumpToTimelineMarker(marker);
    });

    $("#useSuggestedKeyframesButton").addEventListener("click", () => {
      const timeline = timelineMarkersForDisplay(state.jobReview, state.reviewTracks, state.keyframes);
      const suggestions = timeline.suggestedKeyframes.map((item) => item.frameIndex);
      if (!suggestions.length) return;
      state.keyframes = new Set(suggestions);
      renderTimelinePanel();
      renderConfigPreview();
    });

    document.addEventListener("keydown", handleKeyboardShortcut);

    elements.canvas.addEventListener("pointerdown", onCanvasPointerDown);
    elements.canvas.addEventListener("pointermove", onCanvasPointerMove);
    elements.canvas.addEventListener("pointerup", onCanvasPointerUp);
    elements.canvas.addEventListener("pointercancel", onCanvasPointerUp);
    elements.canvas.addEventListener("pointerleave", () => {
      state.pointer = null;
      $("#coordinateReadout").textContent = "x: -, y: -";
      scheduleDrawOverlay();
    });

    $("#promptList").addEventListener("click", (event) => {
      const row = event.target.closest("[data-prompt-id]");
      if (!row) return;
      state.selectedPromptId = row.dataset.promptId;
      renderPromptList();
    });

    $("#maskProviderSelect").addEventListener("change", () => {
      $("#maskProviderSelect").dataset.userSelected = "true";
      applyProviderSettingsToRunForm();
      renderConfigPreview();
    });

    $("#providerSettingsList").addEventListener("change", (event) => {
      const row = event.target.closest("[data-provider-settings-id]");
      if (!row) return;
      const customModel = row.querySelector(".provider-custom-model");
      const select = row.querySelector("[data-provider-field='selectedModel']");
      if (customModel && select) customModel.hidden = select.value !== "__custom__";
    });

    $("#providerSettingsList").addEventListener("click", async (event) => {
      const button = event.target.closest("[data-provider-action]");
      if (!button) return;
      const row = button.closest("[data-provider-settings-id]");
      if (!row) return;
      const providerId = row.dataset.providerSettingsId;
      const result = row.querySelector(".provider-test-result");
      const action = button.dataset.providerAction;
      button.disabled = true;
      if (result) result.textContent = `${action} in progress...`;
      try {
        if (action === "save") {
          await saveProviderSettingsFromRow(row);
          if (result) result.textContent = "Provider settings saved.";
        } else if (action === "diagnose") {
          const payload = await api(`/api/provider-settings/${encodeURIComponent(providerId)}/diagnose`, {
            method: "POST",
            body: JSON.stringify(providerSettingsPayloadFromRow(row)),
          });
          const missing = asArray(payload.checklist)
            .filter((item) => !item.ok)
            .map((item) => item.label)
            .join(", ");
          if (result) result.textContent = payload.message || (payload.ready ? "Provider setup is ready." : `Needs setup: ${missing || "review checklist"}`);
        } else if (action === "test") {
          const payload = await api(`/api/provider-settings/${encodeURIComponent(providerId)}/test`, { method: "POST", body: JSON.stringify({}) });
          if (result) result.textContent = payload.message || payload.status || "Provider setup checked.";
        } else if (action === "smoke-test") {
          const provider = providerSettingsById(providerId);
          const hosted = provider?.locality === "hosted";
          const hostedProfileId = provider?.settings?.hostedProfileId || provider?.defaultHostedProfile || "";
          state.selectedModelSetupProviderId =
            providerId === "sam3-hosted"
              ? `sam3-hosted:${hostedProfileId || "roboflow-sam3-pcs"}`
              : providerId === "sam2-hosted"
                ? `sam2-hosted:${hostedProfileId || "replicate-sam2-video"}`
                : providerId;
          state.pendingModelSetupConfirmation = modelSetupConfirmationForAction("smoke", providerId, {
            hosted,
            model: providerEffectiveModel(provider),
          });
          if (result) result.textContent = "Confirm the smoke test in Model setup.";
          setWorkflowStep("provider_settings", { focusStep: true });
          renderModelSetup();
          renderWorkflowStepper();
          return;
        } else if (action === "reset") {
          await api(`/api/provider-settings/${encodeURIComponent(providerId)}`, { method: "DELETE", body: JSON.stringify({}) });
          await refreshAll();
          return;
        }
      } catch (error) {
        if (result) result.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });

    $("#modelSetupPanel").addEventListener("click", async (event) => {
      const choice = event.target.closest("[data-model-setup-provider]");
      if (choice) {
        state.selectedModelSetupProviderId = choice.dataset.modelSetupProvider;
        state.modelSetupAlternativesOpen = false;
        state.modelSetupMessage = "";
        state.modelSetupTone = "neutral";
        state.pendingModelSetupConfirmation = null;
        renderModelSetup();
        renderModelPlanPanel();
        renderWorkflowStepper();
        return;
      }

      const copyPathButton = event.target.closest("[data-copy-advanced-model-path]");
      if (copyPathButton) {
        const providerId = copyPathButton.dataset.copyAdvancedModelPath || "";
        const payload = state.advancedLocalPaths?.[providerId] || {};
        const path = String(payload.cachedSceneSweepModelDir || payload.localModelDirDisplayRaw || "");
        if (!path) {
          setModelSetupMessage("No cached SAM3 Scene Sweep path is recorded yet.", "warn");
          return;
        }
        const copied = await copyTextToClipboard(path);
        state.copiedAdvancedPathProviderId = copied ? providerId : "";
        setModelSetupMessage(copied ? "Cached Scene Sweep path copied." : "Could not copy the cached path.", copied ? "ready" : "bad");
        renderModelSetup();
        return;
      }

      const confirmationButton = event.target.closest("[data-model-setup-confirmation]");
      if (confirmationButton) {
        const pending = state.pendingModelSetupConfirmation;
        if (!pending) return;
        if (confirmationButton.dataset.modelSetupConfirmation === "cancel") {
          state.pendingModelSetupConfirmation = null;
          setModelSetupMessage(`${pending.label} canceled.`, "neutral");
          renderModelSetup();
          renderWorkflowStepper();
          return;
        }
        state.confirmedModelSetupAction = {
          action: pending.action,
          providerId: pending.providerId,
          model: pending.model,
          flags: asArray(pending.flags),
          settingsPayload: pending.settingsPayload && typeof pending.settingsPayload === "object" ? { ...pending.settingsPayload } : {},
        };
        state.pendingModelSetupConfirmation = null;
        renderModelSetup();
        renderWorkflowStepper();
        const setupButton = [...document.querySelectorAll("#modelSetupPanel [data-model-setup-action]")]
          .find((item) => item.dataset.modelSetupAction === pending.action);
        if (!setupButton) {
          state.confirmedModelSetupAction = null;
          throw new Error("Model setup action is not available for the selected provider.");
        }
        setupButton.dataset.modelSetupConfirmed = "true";
        setupButton.click();
        return;
      }

      const button = event.target.closest("[data-model-setup-action]");
      if (!button) return;
      const action = button.dataset.modelSetupAction;
      const confirmed = button.dataset.modelSetupConfirmed === "true";
      if (confirmed) delete button.dataset.modelSetupConfirmed;
      const confirmedSnapshot = confirmed ? state.confirmedModelSetupAction : null;
      const connection = modelConnectionById(state.selectedModelSetupProviderId);
      if (!connection) return;
      const form = $("#modelSetupForm");
      const providerId = confirmedSnapshot?.providerId || form?.dataset.providerSettingsId || connection.providerId;
      button.disabled = true;
      setModelSetupMessage(`${action} in progress...`, "neutral");
      try {
        if (confirmed && (!confirmedSnapshot || confirmedSnapshot.action !== action || confirmedSnapshot.providerId !== providerId)) {
          throw new Error("Confirmed setup action no longer matches the selected provider.");
        }
        if (action === "change-model") {
          state.modelSetupAlternativesOpen = !state.modelSetupAlternativesOpen;
          setModelSetupMessage(state.modelSetupAlternativesOpen ? "Choose a different compatible model." : "", "neutral");
          renderModelSetup();
        } else if (action === "continue-to-run" || action === "continue-to-prepare") {
          setWorkflowStep("prompt_preview", { focusStep: true });
          setModelSetupMessage("Model setup is ready. Prepare the run inputs, then start extraction.", "ready");
        } else if (action === "cancel-setup-job") {
          await cancelProviderSetupJob(button.dataset.setupJobId || state.selectedProviderSetupJobId);
        } else if (action === "view-setup-logs") {
          const log = $("#modelSetupJobLog");
          if (log) {
            log.hidden = false;
            log.focus?.({ preventScroll: false });
          }
          const job = setupJobForProvider(providerId);
          setModelSetupMessage(job ? setupJobStatusSummary(job).message : "No setup logs for this provider yet.", job ? setupJobStatusSummary(job).tone : "neutral");
        } else if (action === "save") {
          if (!form) throw new Error("Select a SAM provider before saving setup.");
          const response = await api("/api/provider-settings", {
            method: "POST",
            body: JSON.stringify(modelSetupPayloadFromForm(form)),
          });
          state.providerSettings = response;
          form.querySelectorAll("[data-model-setup-field='apiKey'], [data-model-setup-field='hfToken']").forEach((input) => {
            input.value = "";
          });
          state.modelSetupMessage = "Model connection saved. Diagnose checks saved settings without making a hosted network call.";
          state.modelSetupTone = "ready";
          await refreshAll();
        } else if (action === "diagnose") {
          await startProviderSetupJob(providerId, "diagnose", {
            settings: form ? modelSetupPayloadFromForm(form) : {},
            saveFirst: true,
          });
        } else if (action === "check-access" || action === "test") {
          const provider = providerSettingsById(providerId);
          const hosted = provider?.locality === "hosted";
          const formPayload = modelSetupPayloadForAction(form, action, providerId, confirmed);
          if (!hosted && !confirmed && !state.health?.mockMode) {
            state.pendingModelSetupConfirmation = modelSetupConfirmationForAction(action, providerId, {
              hosted,
              model: providerEffectiveModel(provider),
              settingsPayload: formPayload,
            });
            setModelSetupMessage("Confirm Hugging Face access check before continuing.", "warn");
            renderModelSetup();
            renderWorkflowStepper();
            return;
          }
          const body = hosted
            ? { settings: formPayload, saveFirst: true }
            : {
                settings: formPayload,
                saveFirst: true,
                allowNetwork: Boolean(state.health?.mockMode) || confirmed,
              };
          await startProviderSetupJob(providerId, hosted ? "test" : "check_access", body);
        } else if (action === "prepare-model") {
          const provider = providerSettingsById(providerId);
          const formPayload = modelSetupPayloadForAction(form, action, providerId, confirmed);
          const selectedCacheModel =
            cleanPublicModelValue(formPayload.customModelId) ||
            (formPayload.selectedModel === "__custom__" ? "" : cleanPublicModelValue(formPayload.selectedModel)) ||
            cleanPublicModelValue(providerEffectiveModel(provider)) ||
            (providerId === "sam2-hf-auto-masks" ? "facebook/sam2.1-hiera-large" : "facebook/sam3");
          if (!confirmed && !state.health?.mockMode) {
            state.pendingModelSetupConfirmation = modelSetupConfirmationForAction(action, providerId, {
              hosted: false,
              model: selectedCacheModel,
              settingsPayload: formPayload,
            });
            setModelSetupMessage("Confirm guided local setup before continuing.", "warn");
            renderModelSetup();
            renderWorkflowStepper();
            return;
          }
          await startProviderSetupJob(providerId, "prepare_model", {
            allowNetwork: true,
            allowDisk: true,
            allowHeavyLocal: true,
            useSubprocessSmoke: providerId === "sam3-local",
            dryRun: Boolean(state.health?.mockMode),
            model: selectedCacheModel,
            sceneSweep: providerId === "sam3-local",
            settings: formPayload,
            saveFirst: true,
          });
        } else if (action === "install") {
          const formPayload = modelSetupPayloadForAction(form, action, providerId, confirmed);
          if (!confirmed && !state.health?.mockMode) {
            state.pendingModelSetupConfirmation = modelSetupConfirmationForAction(action, providerId, {
              hosted: false,
              model: providerEffectiveModel(providerSettingsById(providerId)),
              settingsPayload: formPayload,
            });
            setModelSetupMessage("Confirm install before continuing.", "warn");
            renderModelSetup();
            renderWorkflowStepper();
            return;
          }
          await startProviderSetupJob(providerId, "install", {
            dryRun: Boolean(state.health?.mockMode),
            settings: formPayload,
            saveFirst: true,
          });
        } else if (action === "cache-model") {
          const formPayload = modelSetupPayloadForAction(form, action, providerId, confirmed);
          const selectedCacheModel =
            cleanPublicModelValue(formPayload.customModelId) ||
            (formPayload.selectedModel === "__custom__" ? "" : cleanPublicModelValue(formPayload.selectedModel)) ||
            cleanPublicModelValue(providerEffectiveModel(providerSettingsById(providerId))) ||
            (providerId === "sam2-hf-auto-masks" ? "facebook/sam2.1-hiera-large" : "facebook/sam3");
          if (!confirmed && !state.health?.mockMode) {
            state.pendingModelSetupConfirmation = modelSetupConfirmationForAction(action, providerId, {
              hosted: false,
              model: selectedCacheModel,
              settingsPayload: formPayload,
            });
            setModelSetupMessage("Confirm model cache before continuing.", "warn");
            renderModelSetup();
            renderWorkflowStepper();
            return;
          }
          await startProviderSetupJob(providerId, "cache_model", {
            allowNetwork: true,
            allowDisk: true,
            dryRun: Boolean(state.health?.mockMode),
            model: selectedCacheModel,
            settings: formPayload,
            saveFirst: true,
          });
        } else if (action === "smoke") {
          const provider = providerSettingsById(providerId);
          const hosted = provider?.locality === "hosted";
          const formPayload = modelSetupPayloadForAction(form, action, providerId, confirmed);
          if (!confirmed && !state.health?.mockMode) {
            state.pendingModelSetupConfirmation = modelSetupConfirmationForAction(action, providerId, {
              hosted,
              model: providerEffectiveModel(provider),
              settingsPayload: formPayload,
            });
            setModelSetupMessage("Confirm smoke test before continuing.", "warn");
            renderModelSetup();
            renderWorkflowStepper();
            return;
          }
          const body = hosted
            ? { allowNetwork: true, allowHosted: true, acknowledgeCostPrivacy: true, prompt: $("#textPrompt")?.value || "object" }
            : { allowHeavyLocal: true, useSubprocessSmoke: providerId === "sam3-local", dryRun: Boolean(state.health?.mockMode), sceneSweep: providerId === "sam3-local" && state.selectedPreset === "trace_all_objects", videoPath: selectedVideoPath() };
          await startProviderSetupJob(providerId, "smoke", {
            ...body,
            settings: formPayload,
            saveFirst: true,
          });
        } else if (action === "reset") {
          await api(`/api/provider-settings/${encodeURIComponent(providerId)}`, { method: "DELETE", body: JSON.stringify({}) });
          state.modelSetupMessage = "Model connection reset.";
          state.modelSetupTone = "neutral";
          await refreshAll();
        }
      } catch (error) {
        setModelSetupMessage(error.message, "bad");
      } finally {
        if (confirmed) state.confirmedModelSetupAction = null;
        button.disabled = false;
      }
    });

    $("#modelSetupPanel").addEventListener("change", (event) => {
      const form = event.target.closest("#modelSetupForm");
      if (!form) return;
      const customModel = form.querySelector(".model-setup-custom-model");
      const select = form.querySelector("[data-model-setup-field='selectedModel']");
      if (customModel && select) customModel.hidden = select.value !== "__custom__";
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
      "discoveryQualityPreset",
      "traceEverythingMode",
      "traceEverythingAck",
      "textPrompt",
      "textDiscoveryProviderSelect",
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
    $("#guidedDemoVideoButton").addEventListener("click", startGuidedDemoVideoFlow);
    $("#generateModelPlanButton").addEventListener("click", generateModelPlanFromIntent);
    $("#validateModelPlanButton").addEventListener("click", validateCurrentModelPlan);
    $("#confirmModelPlanButton").addEventListener("click", confirmModelPlanAndStart);

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

    window.addEventListener("resize", scheduleDrawOverlay);

    initShellNavigation();
    initWorkflowController();
    updatePointKind("positive_point");
    updateTool("point");
    renderMaskProviderOptions();
    renderPresetFields();
    renderVideoMetrics();
    renderConfigPreview();
    refreshAll().then(applyDocsCaptureMode);
  }

  const publicApi = {
    API_ROUTES,
    CORRECTION_STATE_FORMAT,
    PRESETS,
    RUN_CONFIG_SCHEMA,
    WORKFLOW_STEPS,
    applyCorrectionStateToTracks,
    buildCorrectionRequestFromPrompts,
    buildExportPanelSummary,
    buildRunConfig,
    buildRunPlan,
    buildReviewTracks,
    candidateRetrySuggestions,
    candidateStatusCounts,
    candidateStatusItems,
    containedVideoRect,
    correctionDiagnosticMessages,
    correctionGuidanceForTrack,
    correctionResponseMessage,
    diagnosticNeedsImmediateAttention,
    environmentRecommendationSummary,
    eventRowsMarkup,
    eventSeverity,
    exportActionState,
    exportGateSummary,
    exportHandoffCards,
    exportNextStepText,
    exportReadinessSummary,
    filterReviewCandidates,
    jobStaleNotice,
    jobProgressText,
    modelConnectorsForSetup,
    modelPlanConfirmPayload,
    modelPlanGoalForPreset,
    modelPlanProviderFacts,
    modelPlanRequestFromInput,
    modelPlanSourceIds,
    modelSetupPayloadFromValues,
    modelSetupConfirmationForAction,
    modelSetupProviderSummary,
    setupJobProgressSummary,
    setupJobStatusSummary,
    modelSetupDecisionForConnection,
    modelSetupPlaybookSteps,
    modelSetupStateForConnection,
    modelSetupPrimaryActionForState,
    capabilityWarningNamesForConfig,
    jobCenterStateFromSnapshot,
    normalizedModelConnection,
    normalizeJobLifecycle,
    normalizeCorrectionState,
    normalizeWorkflowStepId,
    objectDiscoveryConfig,
    providerContractForInput,
    providerIdFromConnectionId,
    mapClientPointToVideo,
    normalizePrompt,
    parseCsv,
    parseKeyframes,
    postRunWorkflowSummaryFromSnapshot,
    reviewGateFromSnapshot,
    reviewCandidates,
    reviewFlowStateFromSnapshot,
    safeLocalContentUrl,
    runMonitorStageFromSnapshot,
    slugObjectId,
    timelineMarkersForDisplay,
    trackFrameForDisplay,
    trackMotionMetrics,
    trackSelectedPayload,
    trackUsesStaticKeyframeFallback,
    workflowNextStepId,
    workflowStepContractFromSnapshot,
    workflowReadinessFromSnapshot,
    workflowRestoredStepFromSnapshot,
    workflowSummaryCardsFromSnapshot,
    guidedEnginePlan,
    compatibleModelConnectionsForPreset,
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
