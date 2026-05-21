import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

await import("../src/motionjson/ui/static/app.js");

const ui = globalThis.MotionJSONUI;
assert.ok(ui, "MotionJSONUI helper API should be exposed for JS checks");
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
assert.ok(ui.API_ROUTES.includes("/api/jobs/{jobId}/track-selected"));
assert.ok(ui.API_ROUTES.includes("/api/model-providers/{providerId}/test"));

const sortedModelProviders = ui.modelConnectorsForSetup({
  providers: [
    { id: "openrouter-planner", name: "OpenRouter" },
    { id: "fake-local-planner", name: "Mock local" },
    { id: "openai-planner", name: "OpenAI" },
    { id: "unrelated", name: "Unrelated" },
  ],
});
assert.deepEqual(sortedModelProviders.map((provider) => provider.id), ["fake-local-planner", "openai-planner", "openrouter-planner"]);

const localModelSummary = ui.modelSetupProviderSummary({
  id: "fake-local-planner",
  name: "Mock local planner",
  hostedCallsRequired: false,
  readiness: { status: "ready", runnable: true, networkAttempted: false },
  estimatedCost: { label: "Free local" },
});
assert.equal(localModelSummary.tone, "ready");
assert.match(localModelSummary.message, /No API key/);

const hostedMissingSummary = ui.modelSetupProviderSummary(
  { id: "openai-planner", name: "OpenAI planner", hostedCallsRequired: true, readiness: { status: "missing_key" } },
  { id: "openai", locality: "hosted", cost: { label: "Provider billed" }, privacy: "Text prompts are sent to OpenAI after opt-in." },
);
assert.equal(hostedMissingSummary.tone, "bad");
assert.equal(hostedMissingSummary.action, "Add key");

const hostedWarningSummary = ui.modelSetupProviderSummary(
  {
    id: "openai-planner",
    name: "OpenAI planner",
    hostedCallsRequired: true,
    readiness: { status: "hosted_opt_in_required", configured: true, hostedCallsAllowed: false },
  },
  { id: "openai", locality: "hosted", cost: { label: "Provider billed" } },
);
assert.equal(hostedWarningSummary.tone, "warn");
assert.equal(hostedWarningSummary.action, "Confirm");

const hostedReadySummary = ui.modelSetupProviderSummary(
  {
    id: "openai-planner",
    name: "OpenAI planner",
    hostedCallsRequired: true,
    readiness: { status: "ready", configured: true, runnable: true, hostedCallsAllowed: true },
  },
  { id: "openai", locality: "hosted", cost: { label: "Provider billed" } },
);
assert.equal(hostedReadySummary.tone, "ready");
assert.equal(hostedReadySummary.action, "Test setup");

const modelSetupPayload = ui.modelSetupPayloadFromValues("openai", {
  selectedModel: " gpt-5.4-mini ",
  customModelId: " ",
  baseUrl: " https://api.openai.com/v1 ",
  allowHosted: true,
  apiKey: " model-setup-placeholder ",
});
assert.deepEqual(modelSetupPayload, {
  providerId: "openai",
  selectedModel: "gpt-5.4-mini",
  customModelId: "",
  baseUrl: "https://api.openai.com/v1",
  endpoint: "",
  allowHosted: true,
  apiKey: "model-setup-placeholder",
});
const noSecretPayload = ui.modelSetupPayloadFromValues("openai", { selectedModel: "gpt-5.4-mini", apiKey: " " });
assert.equal(Object.hasOwn(noSecretPayload, "apiKey"), false);

assert.equal(ui.safeLocalContentUrl("/api/videos/asset_123/content"), "/api/videos/asset_123/content");
assert.equal(ui.safeLocalContentUrl("/api/artifacts/export_123/content?download=1"), "/api/artifacts/export_123/content?download=1");
assert.equal(ui.safeLocalContentUrl("https://example.test/video.mp4"), "");
assert.equal(ui.safeLocalContentUrl("file:///Users/alice/private.mp4"), "");

const center = ui.mapClientPointToVideo(
  400,
  300,
  { left: 0, top: 0, width: 800, height: 600 },
  1920,
  1080,
);
assert.equal(center.inside, true);
assert.equal(center.x, 960);
assert.equal(center.y, 540);

const letterboxed = ui.mapClientPointToVideo(
  10,
  10,
  { left: 0, top: 0, width: 800, height: 600 },
  1920,
  1080,
);
assert.equal(letterboxed.inside, false);
assert.equal(letterboxed.y, 0);

const manualConfig = ui.buildRunConfig({
  preset: "trace_one_object",
  discoveryMode: "manual_prompt",
  projectId: "project_1",
  videoId: "asset_1",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "Red Ball",
  objectLabel: "red ball",
  currentFrame: 7,
  keyframes: new Set([0, 7]),
  maskProvider: "sam2-local",
  device: "cpu",
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
  modelName: "sam2.1",
  outputMode: "authoring",
  prompts: [
    { kind: "positive_point", frame_index: 7, object_id: "red_ball", label: "red ball", data: { x: 960, y: 540 } },
    { kind: "box", frame_index: 7, object_id: "red_ball", label: "red ball", data: { x: 900, y: 480, w: 120, h: 120 } },
  ],
  strokes: [
    { mode: "paint", brush_size: 18, points: [{ x: 930, y: 520 }, { x: 950, y: 540 }] },
  ],
});

assert.equal(manualConfig.schema, ui.RUN_CONFIG_SCHEMA);
assert.equal(manualConfig.objects[0].object_id, "Red_Ball");
assert.equal(manualConfig.provider.name, "sam2-local");
assert.equal(manualConfig.provider.sam2.prompt_frame, 7);
assert.equal(manualConfig.prompts.length, 3);
assert.equal(manualConfig.prompts[0].data.x, 960);

const manualPlan = ui.buildRunPlan(manualConfig, {
  preset: "trace_one_object",
  videoId: "asset_1",
  previewName: "demo_red_ball.mp4",
});
assert.equal(manualPlan.title, "Cut out one object");
assert.equal(manualPlan.privacy, "Frames stay local for this plan");
assert.ok(manualPlan.steps.some((step) => step.label === "Review gate" && step.status === "ready"));

const autoObjectConfig = ui.buildRunConfig({
  preset: "auto_object_proposals",
  discoveryMode: "auto_object_proposals",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "object_0",
  objectLabel: "discovered object",
  keyframes: new Set([0]),
  maskProvider: "mock",
  sampleFps: 8,
  maxFrames: 24,
  minArea: 90,
  maxAreaRatio: 0.6,
  stabilityThreshold: 0.8,
  overlapThreshold: 0.7,
  boxThreshold: 0.4,
  textThreshold: 0.3,
  motionSensitivity: 30,
  maxObjects: 5,
  outputMode: "authoring",
  qualityPreset: "clean",
});

assert.equal(autoObjectConfig.discovery.mode, "auto_object_proposals");
assert.equal(autoObjectConfig.discovery.config.qualityPreset, "clean");
assert.deepEqual(autoObjectConfig.discovery.config.keyframes, [0]);
assert.equal(autoObjectConfig.discovery.config.maxKeyframes, 3);
assert.equal(autoObjectConfig.discovery.config.maxObjects, 5);
assert.equal(autoObjectConfig.discovery.config.trackSelectedOnly, true);
assert.equal(autoObjectConfig.discovery.config.requireReview, true);
assert.equal(autoObjectConfig.provider.name, "mock");

const firstRunPlan = ui.buildRunPlan(autoObjectConfig, { preset: "auto_object_proposals" });
assert.equal(firstRunPlan.title, "Discover objects");
assert.ok(firstRunPlan.steps.some((step) => step.label === "Source" && step.status === "needs-action"));
assert.ok(firstRunPlan.nextSteps.some((step) => step.includes("Choose a video preview")));

const maximumRecallConfig = ui.buildRunConfig({
  preset: "auto_object_proposals",
  discoveryMode: "auto_object_proposals",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "object_0",
  objectLabel: "discovered object",
  keyframes: new Set([0]),
  maskProvider: "mock",
  sampleFps: 8,
  maxFrames: 24,
  minArea: 90,
  maxAreaRatio: 0.6,
  stabilityThreshold: 0.8,
  overlapThreshold: 0.7,
  boxThreshold: 0.4,
  textThreshold: 0.3,
  motionSensitivity: 30,
  maxObjects: 5,
  outputMode: "authoring",
  qualityPreset: "maximum_recall",
});
assert.equal(maximumRecallConfig.discovery.config.qualityPreset, "maximum_recall");
assert.equal(maximumRecallConfig.discovery.config.maxKeyframes, 8);
assert.equal(maximumRecallConfig.discovery.config.maxObjects, 64);
assert.equal(maximumRecallConfig.discovery.config.trackSelectedOnly, true);

const traceEverythingConfig = ui.buildRunConfig({
  preset: "auto_object_proposals",
  discoveryMode: "auto_object_proposals",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "object_0",
  objectLabel: "discovered object",
  keyframes: new Set([0]),
  maskProvider: "mock",
  sampleFps: 8,
  maxFrames: 24,
  minArea: 90,
  maxAreaRatio: 0.6,
  stabilityThreshold: 0.8,
  overlapThreshold: 0.7,
  boxThreshold: 0.4,
  textThreshold: 0.3,
  motionSensitivity: 30,
  maxObjects: 5,
  outputMode: "authoring",
  traceEverythingMode: true,
  traceEverythingAcknowledged: true,
});
assert.equal(traceEverythingConfig.discovery.config.qualityPreset, "trace_everything");
assert.equal(traceEverythingConfig.discovery.config.requireExplicitCostWarning, true);
assert.equal(traceEverythingConfig.discovery.config.costWarningAcknowledged, true);
assert.equal(traceEverythingConfig.discovery.config.trackSelectedOnly, false);

const textConfig = ui.buildRunConfig({
  preset: "text_detector",
  discoveryMode: "text_detector",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "object_0",
  objectLabel: "selected_object",
  keyframes: new Set([0]),
  maskProvider: "mock",
  sampleFps: 8,
  maxFrames: 24,
  minArea: 90,
  maxAreaRatio: 0.6,
  stabilityThreshold: 0.8,
  overlapThreshold: 0.7,
  boxThreshold: 0.4,
  textThreshold: 0.3,
  motionSensitivity: 30,
  maxObjects: 5,
  outputMode: "authoring",
  textPrompt: "red ball . hand . cup",
});

assert.deepEqual(textConfig.discovery.config.labels, ["red ball", "hand", "cup"]);
assert.equal(textConfig.discovery.config.max_candidates, 5);
assert.equal(textConfig.discovery.config.mock, true);
assert.equal(textConfig.provider.name, "mock");

const classConfig = ui.buildRunConfig({
  preset: "class_detector",
  discoveryMode: "class_detector",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "known_class",
  objectLabel: "known class",
  keyframes: new Set([0]),
  maskProvider: "mock",
  sampleFps: 8,
  maxFrames: 24,
  minArea: 90,
  maxAreaRatio: 0.6,
  stabilityThreshold: 0.8,
  overlapThreshold: 0.7,
  boxThreshold: 0.42,
  textThreshold: 0.3,
  motionSensitivity: 30,
  maxObjects: 5,
  classPreset: "vehicles",
  classList: "forklift, cart",
  outputMode: "authoring",
});

assert.equal(classConfig.discovery.mode, "class_detector");
assert.equal(classConfig.discovery.config.class_preset, "vehicles");
assert.deepEqual(classConfig.discovery.config.classes, ["forklift", "cart"]);
assert.equal(classConfig.discovery.config.confidence_threshold, 0.42);
assert.equal(classConfig.discovery.config.max_candidates, 5);
assert.equal(classConfig.discovery.config.mock, true);
assert.equal(classConfig.provider.name, "mock");

const autoMasksConfig = ui.buildRunConfig({
  preset: "sam_auto_masks",
  discoveryMode: "sam_auto_masks",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "auto_segment",
  objectLabel: "auto segment",
  keyframes: new Set([0, 12]),
  maskProvider: "mock",
  sampleFps: 12,
  maxFrames: 48,
  minArea: 120,
  maxAreaRatio: 0.55,
  stabilityThreshold: 0.86,
  overlapThreshold: 0.68,
  boxThreshold: 0.35,
  textThreshold: 0.25,
  motionSensitivity: 32,
  maxObjects: 9,
  outputMode: "authoring",
});

assert.equal(autoMasksConfig.discovery.mode, "sam_auto_masks");
assert.equal(autoMasksConfig.discovery.config.max_candidates, 9);
assert.equal(autoMasksConfig.discovery.config.mock, true);
assert.equal(autoMasksConfig.discovery.config.reject_background, true);
assert.equal(autoMasksConfig.provider.name, "mock");

const motionConfig = ui.buildRunConfig({
  preset: "motion_foreground",
  discoveryMode: "motion_foreground",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "moving_object",
  objectLabel: "moving object",
  keyframes: new Set([0]),
  maskProvider: "motion",
  sampleFps: 12,
  maxFrames: 48,
  minArea: 80,
  maxAreaRatio: 0.65,
  stabilityThreshold: 0.82,
  overlapThreshold: 0.72,
  boxThreshold: 0.35,
  textThreshold: 0.25,
  motionSensitivity: 28,
  maxObjects: 7,
  outputMode: "authoring",
});

assert.equal(motionConfig.discovery.mode, "motion_foreground");
assert.equal(motionConfig.discovery.config.threshold, 28);
assert.equal(motionConfig.discovery.config.max_candidates, 7);
assert.equal(motionConfig.provider.name, "motion");

const externalConfig = ui.buildRunConfig({
  preset: "external_masks",
  discoveryMode: "external_masks",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "object_0",
  objectLabel: "selected_object",
  keyframes: new Set([0]),
  maskProvider: "external",
  externalMaskDir: "masks/object_0",
  sampleFps: 12,
  maxFrames: 48,
  minArea: 100,
  outputMode: "authoring",
});

assert.equal(externalConfig.provider.external.mask_dir, "masks/object_0");
assert.equal(externalConfig.objects[0].mask_dir, "masks/object_0");

const presetExpectations = [
  [autoObjectConfig, "auto_object_proposals", "mock"],
  [maximumRecallConfig, "auto_object_proposals", "mock"],
  [traceEverythingConfig, "auto_object_proposals", "mock"],
  [manualConfig, "manual_prompt", "sam2-local"],
  [textConfig, "text_detector", "mock"],
  [classConfig, "class_detector", "mock"],
  [autoMasksConfig, "sam_auto_masks", "mock"],
  [motionConfig, "motion_foreground", "motion"],
  [externalConfig, "external_masks", "external"],
];

for (const [config, discoveryMode, providerName] of presetExpectations) {
  assert.equal(config.discovery.mode, discoveryMode);
  assert.equal(config.provider.name, providerName);
  const validation = spawnSync(
    "python3",
    [
      "-c",
      "import json, sys; from motionjson.config import ExtractionRunConfig; ExtractionRunConfig.from_dict(json.load(sys.stdin)); print('ok')",
    ],
    {
      cwd: repoRoot,
      input: JSON.stringify(config),
      encoding: "utf8",
      env: {
        ...process.env,
        PYTHONPATH: "src",
        PYTHONDONTWRITEBYTECODE: "1",
      },
    },
  );
  assert.equal(validation.status, 0, validation.stderr || validation.stdout);
}

const pendingPreviewTracks = ui.buildReviewTracks({
  job: { status: "pending" },
  config: textConfig,
  artifacts: [],
  review: {},
});
assert.ok(pendingPreviewTracks.length > 0, "pending jobs may show estimated review tracks");
assert.equal(pendingPreviewTracks[0].demoMode, true);
assert.equal(pendingPreviewTracks[0].source, "demo-only");
assert.equal(pendingPreviewTracks[0].exportable, false);

const fallbackTerminalTracks = ui.buildReviewTracks({
  job: { status: "failed" },
  config: textConfig,
  artifacts: [],
  review: {
    rasterFallback: true,
    vectorUnavailableReason: "masks_too_large_whole_frame",
    fallbackDiagnostics: [{ reasonCode: "masks_too_large_whole_frame" }],
  },
});
assert.deepEqual(fallbackTerminalTracks, [], "terminal fallback jobs must not synthesize fake overlay tracks");

const terminalNoApiTracks = ui.buildReviewTracks({
  job: { status: "succeeded", result: { objects: 2, frames: 3 } },
  config: textConfig,
  artifacts: [],
  review: {},
});
assert.deepEqual(terminalNoApiTracks, [], "normal terminal jobs without API tracks must not synthesize final tracks");

const filteredCandidates = ui.filterReviewCandidates(
  [
    { candidateId: "cand_1", stabilityScore: 0.92, motionScore: 0.2, frameCoverageEstimate: 0.8, reviewStatus: "pending" },
    { candidateId: "cand_2", stabilityScore: 0.94, motionScore: 0.3, frameCoverageEstimate: 0.8, rejectionReason: "background_like" },
    { candidateId: "cand_3", stabilityScore: 0.6, motionScore: 0.2, frameCoverageEstimate: 0.8, reviewStatus: "pending" },
  ],
  { cand_1: true, cand_2: true, cand_3: true },
  { selectedOnly: true, stableOnly: true, movingOnly: true, notBackground: true, notDuplicate: true, minCoverage: 0.5 },
);
assert.deepEqual(filteredCandidates.map((candidate) => candidate.candidateId), ["cand_1"]);
assert.deepEqual(
  ui.reviewCandidates({ candidateSummary: { candidates: [{ candidateId: "legacy_only" }] } }),
  [],
  "candidate browser must not select from legacy candidateSummary.candidates",
);
assert.deepEqual(ui.reviewCandidates({ candidates: [{ candidateId: "api_cand" }] }), [{ candidateId: "api_cand" }]);
assert.deepEqual(ui.trackSelectedPayload(["cand_1", "cand_1", "cand_2"]), {
  candidateIds: ["cand_1", "cand_2"],
  trackMode: "selected_only",
  exportReviewRequired: true,
});

const timeline = ui.timelineMarkersForDisplay(
  {
    timeline: {
      format: "motionjson.review_timeline.v0.1",
      frameCount: 5,
      markers: [
        { id: "candidate:cand_1:0", kind: "candidate", frameIndex: 0, label: "candidate one", candidateId: "cand_1" },
        { id: "track:object_0:start:1", kind: "track_start", frameIndex: 1, label: "object appears", objectId: "object_0" },
      ],
      suggestedKeyframes: [{ frameIndex: 1, reason: "scene_change_policy_review_marker", source: "review.timeline" }],
    },
  },
  [{ id: "object_0", objectId: "object_0", frameEnd: 4 }],
  new Set([0, 4]),
);
assert.equal(timeline.hasApiTimeline, true);
assert.deepEqual(timeline.suggestedKeyframes.map((item) => item.frameIndex), [1]);
assert.deepEqual(
  timeline.markers.map((marker) => marker.kind),
  ["candidate", "configured_keyframe", "track_start", "configured_keyframe"],
);

const correctionRequest = ui.buildCorrectionRequestFromPrompts(
  "red_ball",
  [
    { kind: "positive_point", frame_index: 2, data: { x: 120, y: 90 } },
    { kind: "negative_point", frame_index: 2, data: { x: 8, y: 10 } },
    { kind: "box", frame_index: 2, data: { x: 100, y: 80, w: 40, h: 38 } },
  ],
  [2, 4],
);
assert.equal(correctionRequest.schema, "motionjson.correction_request.v0.1");
assert.equal(correctionRequest.aiUsage, "none");
assert.deepEqual(correctionRequest.propagation.frameRange, [3, 5]);
assert.deepEqual(
  correctionRequest.operations.map((operation) => operation.type),
  ["add_point", "remove_point", "box"],
);

const normalizedCorrectionState = ui.normalizeCorrectionState(
  {
    history: [
      { type: "relabel_track", trackId: "red_ball", label: "ball corrected" },
      { type: "set_export_inclusion", trackId: "red_ball", included: false },
    ],
  },
  "job_1",
);
const correctedTracks = ui.applyCorrectionStateToTracks(
  [
    {
      id: "red_ball",
      objectId: "red_ball",
      label: "red ball",
      source: "mock",
      confidence: 0.9,
      frameCount: 3,
      visibleFrameCount: 3,
      frameStart: 0,
      frameEnd: 2,
      warnings: [],
      exportStatus: "accepted",
      color: "#10a37f",
      frames: [{ frame: 0, bbox: { x: 10, y: 10, w: 30, h: 30 }, visible: true }],
    },
  ],
  normalizedCorrectionState,
);
assert.equal(correctedTracks[0].label, "ball corrected");
assert.equal(correctedTracks[0].exportIncluded, false);
assert.equal(correctedTracks[0].exportStatus, "excluded");
assert.equal(ui.trackFrameForDisplay(correctedTracks[0], 99), null);
assert.deepEqual(ui.trackFrameForDisplay(correctedTracks[0], 0).bbox, { x: 10, y: 10, w: 30, h: 30 });

const pendingExportSummary = ui.buildExportPanelSummary({
  exportState: {},
  reviewExport: { includedObjectIds: ["object_0", "manual_object"], excludedObjectIds: [] },
  reviewTracks: [
    { id: "object_0", objectId: "object_0", exportStatus: "accepted" },
    { id: "manual_object", objectId: "manual_object", exportStatus: "accepted" },
  ],
  reviewObjects: [{ objectId: "object_0" }],
});
assert.deepEqual(pendingExportSummary.includedIds, ["object_0"]);
assert.deepEqual(pendingExportSummary.pendingIds, ["manual_object"]);
assert.deepEqual(pendingExportSummary.excludedIds, ["manual_object"]);

const validatedExportSummary = ui.buildExportPanelSummary({
  exportState: { includedObjectIds: ["object_0"], excludedObjectIds: ["manual_object"] },
  reviewExport: { includedObjectIds: ["object_0", "manual_object"] },
  reviewObjects: [{ objectId: "object_0" }],
});
assert.deepEqual(validatedExportSummary.includedIds, ["object_0"]);
assert.deepEqual(validatedExportSummary.pendingIds, ["manual_object"]);
assert.deepEqual(validatedExportSummary.excludedIds, ["manual_object"]);

const repairMessage = ui.correctionResponseMessage({
  repairDiagnostics: {
    status: "unavailable",
    diagnostics: [
      {
        code: "repair_provider_unavailable",
        provider: "sam2-local",
        message: "SAM2 local repair is not configured.",
      },
    ],
    partialRerun: {
      available: false,
      status: "not_enqueued",
      reason: "Partial rerun worker is not implemented.",
    },
  },
});
assert.match(repairMessage, /repair_provider_unavailable/);
assert.match(repairMessage, /sam2-local/);

console.log(
  JSON.stringify(
    {
      status: "ok",
      checked: [
        "coordinate-mapping",
        "run-config-builder",
        "object-discovery-presets",
        "api-candidate-filtering",
        "api-review-timeline",
        "review-track-gating",
        "correction-state",
        "model-setup-flow",
        "python-config-validation",
      ],
    },
    null,
    2,
  ),
);
