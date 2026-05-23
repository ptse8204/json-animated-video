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
assert.ok(ui.API_ROUTES.includes("/api/provider-settings/{providerId}/diagnose"));
assert.ok(ui.API_ROUTES.includes("/api/model-runs/{runId}/confirm-job"));
assert.equal(ui.WORKFLOW_STEPS.length, 5);
assert.deepEqual(ui.WORKFLOW_STEPS.map((step) => step.id), [
  "choose_goal",
  "source_video",
  "provider_settings",
  "prompt_preview",
  "review_export",
]);
assert.equal(ui.normalizeWorkflowStepId("bad-step"), "choose_goal");
assert.equal(ui.workflowNextStepId("source_video", 1), "provider_settings");
assert.equal(ui.workflowNextStepId("source_video", -1), "choose_goal");
assert.equal(ui.workflowRestoredStepFromSnapshot({ selectedPreset: "trace_one_object" }, "review_export"), "source_video");
assert.equal(ui.workflowRestoredStepFromSnapshot({ selectedPreset: "motion_foreground", selectedProjectId: "project_1" }, "review_export"), "source_video");
assert.equal(
  ui.workflowRestoredStepFromSnapshot({ selectedPreset: "trace_one_object", selectedProjectId: "project_1", selectedVideoId: "video_1" }, "review_export"),
  "provider_settings",
);
const blockedWorkflow = ui.workflowReadinessFromSnapshot({
  selectedPreset: "trace_one_object",
  selectedVideoId: "",
  providerBlocked: true,
  promptCount: 0,
});
assert.equal(blockedWorkflow.source_video.status, "needs-action");
assert.equal(blockedWorkflow.provider_settings.status, "blocked");
assert.equal(blockedWorkflow.prompt_preview.complete, false);
const previewOnlyWorkflow = ui.workflowReadinessFromSnapshot({
  selectedPreset: "motion_foreground",
  selectedProjectId: "project_1",
  previewName: "browser-preview.mp4",
  providerWarning: "Selected providers are ready.",
  providerTone: "is-ready",
});
assert.equal(previewOnlyWorkflow.source_video.complete, false);
assert.equal(previewOnlyWorkflow.source_video.status, "needs-action");
assert.equal(previewOnlyWorkflow.provider_settings.status, "done");
const readyWorkflow = ui.workflowReadinessFromSnapshot({
  selectedPreset: "motion_foreground",
  selectedProjectId: "project_1",
  selectedVideoId: "video_1",
  configValid: true,
  selectedJobId: "job_1",
  candidateCount: 2,
  trackCount: 1,
  exportValidated: true,
  exportOk: true,
});
assert.equal(readyWorkflow.source_video.complete, true);
assert.equal(readyWorkflow.prompt_preview.complete, true);
assert.equal(readyWorkflow.review_export.status, "done");
const sam3SingleNeedsBox = ui.workflowReadinessFromSnapshot({
  selectedPreset: "trace_one_object",
  selectedProjectId: "project_1",
  selectedVideoId: "video_1",
  providerName: "SAM3 local",
  hasPointPrompt: true,
  hasBoxPrompt: false,
  promptCount: 1,
});
assert.equal(sam3SingleNeedsBox.prompt_preview.status, "needs-action");
const progressCards = ui.workflowSummaryCardsFromSnapshot(
  {
    selectedPreset: "motion_foreground",
    presetLabel: "Find moving objects",
    selectedProjectId: "project_1",
    projectName: "Demo project",
    selectedVideoId: "video_1",
    videoName: "demo_red_ball.mp4",
    providerName: "mock",
    providerDevice: "cpu",
    configValid: true,
  },
  "prompt_preview",
);
assert.deepEqual(progressCards.map((card) => card.id), ["choose_goal", "source_video", "provider_settings"]);
assert.equal(progressCards[0].value, "Find moving objects");
assert.equal(progressCards[1].value, "demo_red_ball.mp4");
assert.equal(progressCards[2].value, "mock on cpu");
assert.equal(ui.workflowSummaryCardsFromSnapshot({}, "choose_goal").length, 0);
const videoStepContract = ui.workflowStepContractFromSnapshot(
  {
    selectedPreset: "trace_one_object",
    selectedVideoId: "",
  },
  "source_video",
);
assert.equal(videoStepContract.primaryLabel, "Add video");
assert.equal(videoStepContract.enabled, false);
const readyPrepareContract = ui.workflowStepContractFromSnapshot(
  {
    selectedPreset: "trace_all_objects",
    selectedVideoId: "video_1",
    providerName: "SAM3 local",
    promptCount: 0,
  },
  "prompt_preview",
);
assert.equal(readyPrepareContract.primaryLabel, "Run trace all");
assert.equal(readyPrepareContract.enabled, true);
const postRunSummary = ui.postRunWorkflowSummaryFromSnapshot({
  selectedJobStatus: "succeeded",
  hasSelectedJob: true,
  candidateCount: 3,
  selectedCandidateCount: 2,
  trackCount: 2,
  exportIncludedCount: 1,
  correctionCount: 1,
  exportValidated: false,
});
assert.deepEqual(postRunSummary.map((stage) => stage.id), ["run", "candidates", "tracks", "corrections", "export"]);
assert.equal(postRunSummary.find((stage) => stage.id === "run").status, "done");
assert.equal(postRunSummary.find((stage) => stage.id === "candidates").value, "2/3 kept");
assert.equal(postRunSummary.find((stage) => stage.id === "tracks").value, "2 tracks");
assert.equal(postRunSummary.find((stage) => stage.id === "corrections").status, "done");
assert.equal(postRunSummary.find((stage) => stage.id === "export").status, "needs-action");
const failedPostRunSummary = ui.postRunWorkflowSummaryFromSnapshot({
  selectedJobStatus: "failed",
  hasFailure: true,
  diagnosticCount: 2,
});
assert.equal(failedPostRunSummary.find((stage) => stage.id === "run").status, "blocked");
assert.match(failedPostRunSummary.find((stage) => stage.id === "run").detail, /failure|diagnostics|logs/i);
const fallbackPostRunSummary = ui.postRunWorkflowSummaryFromSnapshot({
  selectedJobStatus: "succeeded",
  diagnosticCount: 2,
  attentionDiagnosticCount: 1,
});
assert.equal(fallbackPostRunSummary.find((stage) => stage.id === "run").status, "warning");
assert.match(fallbackPostRunSummary.find((stage) => stage.id === "run").detail, /fallback|provider diagnostic/i);
assert.equal(ui.diagnosticNeedsImmediateAttention({ severity: "bad", kind: "job", message: "provider failed" }), true);
assert.equal(ui.diagnosticNeedsImmediateAttention({ severity: "warn", kind: "fallback_diagnostics", message: "Raster fallback was written." }), true);
assert.equal(ui.diagnosticNeedsImmediateAttention({ severity: "warn", kind: "status", message: "Quality note only." }), false);
assert.equal(ui.diagnosticNeedsImmediateAttention({ severity: "ready", kind: "status", message: "No fallback diagnostics reported." }), false);
const validExportSummary = ui.postRunWorkflowSummaryFromSnapshot({
  selectedJobStatus: "succeeded",
  trackCount: 1,
  exportIncludedCount: 1,
  exportValidated: true,
  exportOk: true,
});
assert.equal(validExportSummary.find((stage) => stage.id === "export").status, "done");

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

const hostedSam2Config = ui.buildRunConfig({
  preset: "trace_one_object",
  maskProvider: "sam2-hosted",
  objectId: "object_0",
  objectLabel: "selected object",
  prompts: [{ kind: "positive_point", frame_index: 0, object_id: "object_0", label: "selected object", data: { x: 10, y: 12 } }],
  hostedSam2ProfileId: "replicate-sam2-video",
  hostedSam2AllowHosted: true,
  modelName: "meta/sam-2-video",
});
assert.equal(hostedSam2Config.provider.sam2.hosted_config.profile, "replicate-sam2-video");
assert.equal(hostedSam2Config.provider.sam2.hosted_allow_network, true);
assert.equal(JSON.stringify(hostedSam2Config).includes("replicate-profile-secret"), false);

const hostedSam3Config = ui.buildRunConfig({
  preset: "text_detector",
  textDiscoveryProvider: "sam3-hosted",
  textPrompt: "red ball",
  hostedSam3ProfileId: "roboflow-sam3-pcs",
  hostedSam3AllowHosted: true,
  hostedSam3Model: "sam3/sam3_final",
});
assert.equal(hostedSam3Config.provider.name, "sam3-hosted");
assert.equal(hostedSam3Config.discovery.mode, "sam3_concept");
assert.equal(hostedSam3Config.discovery.config.providerPreference, "sam3-hosted");
assert.equal(hostedSam3Config.discovery.config.hostedProfile, "roboflow-sam3-pcs");
assert.equal(hostedSam3Config.discovery.config.allowNetwork, true);
assert.equal(hostedSam3Config.provider.sam3.hosted_config.profile, "roboflow-sam3-pcs");

const sam3SingleObjectConfig = ui.buildRunConfig({
  preset: "trace_one_object",
  modelConnectionId: "sam3-local",
  objectId: "object_0",
  objectLabel: "selected object",
  currentFrame: 12,
  prompts: [{ kind: "box", frame_index: 12, object_id: "object_0", label: "selected object", data: { x: 120, y: 90, w: 180, h: 220 } }],
});
assert.equal(sam3SingleObjectConfig.provider.name, "sam3-local");
assert.equal(sam3SingleObjectConfig.discovery.mode, "sam3_exemplar");
assert.deepEqual(sam3SingleObjectConfig.discovery.config.box, { x: 120, y: 90, w: 180, h: 220 });

const sam3TraceAllConfig = ui.buildRunConfig({
  preset: "trace_all_objects",
  modelConnectionId: "sam3-local",
  objectId: "object_0",
  objectLabel: "all objects",
  keyframes: new Set([0, 12]),
  qualityPreset: "balanced",
});
assert.equal(sam3TraceAllConfig.provider.name, "sam3-local");
assert.equal(sam3TraceAllConfig.discovery.mode, "sam3_auto_masks");

assert.equal(ui.modelPlanGoalForPreset("text_detector"), "find_objects_from_text");
assert.equal(ui.modelPlanGoalForPreset("motion_foreground"), "find_moving_things");
assert.equal(ui.modelPlanGoalForPreset("trace_all_objects"), "discover_objects");
const modelPlanPayload = ui.modelPlanRequestFromInput(
  {
    preset: "text_detector",
    modelIntent: "Find the red ball",
    projectId: "project_1",
    videoId: "video_1",
    sourcePath: "local-ui://assets/video_1",
    outputDirectory: "out/ui-runs/project_1",
    objectLabel: "red ball",
    objectId: "red_ball",
    textPrompt: "red ball",
    sampleFps: "8",
    maxFrames: "16",
    maxObjects: "3",
  },
  "fake-local-planner",
);
assert.equal(modelPlanPayload.providerId, "fake-local-planner");
assert.equal(modelPlanPayload.request.goal, "find_objects_from_text");
assert.equal(modelPlanPayload.request.prompt, "Find the red ball");
assert.equal(modelPlanPayload.request.videoId, "video_1");
assert.equal(modelPlanPayload.request.sampleFps, 8);
assert.equal(modelPlanPayload.request.maxFrames, 16);
assert.equal(modelPlanPayload.request.maxObjects, 3);

const blockedPlanFacts = ui.modelPlanProviderFacts(
  {
    providerId: "fake-local-planner",
    providerPlan: { discoveryProvider: "text_detector", maskProvider: "sam2-local", trackingMode: "selected_only" },
    privacy: { summary: "Local only" },
    estimatedCost: { message: "Zero local" },
    requiresUserConfirmation: true,
  },
  {
    valid: true,
    errors: [],
    warnings: [{ severity: "error", message: "sam2-local is unavailable" }],
  },
);
assert.equal(blockedPlanFacts.valid, false);
assert.deepEqual(blockedPlanFacts.blockers, ["sam2-local is unavailable"]);
assert.deepEqual(ui.modelPlanConfirmPayload({ projectId: "project_1", videoId: "video_1", run: true }), {
  confirmed: true,
  projectId: "project_1",
  videoId: "video_1",
  run: true,
});
assert.throws(() => ui.modelPlanConfirmPayload({ projectId: "", videoId: "video_1" }), /project/);
assert.deepEqual(
  ui.modelPlanSourceIds({
    request: { projectId: "project_1" },
    runConfig: { input: { path: "local-ui://assets/video_1" }, rights: {} },
  }),
  { projectId: "project_1", videoId: "video_1" },
);

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
  debugMockMode: true,
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

const traceAllConfig = ui.buildRunConfig({
  preset: "trace_all_objects",
  discoveryMode: "auto_object_proposals",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "object_0",
  objectLabel: "all objects",
  keyframes: new Set([0, 12]),
  maskProvider: "mock",
  debugMockMode: true,
  sampleFps: 8,
  maxFrames: 24,
  minArea: 90,
  maxAreaRatio: 0.6,
  stabilityThreshold: 0.8,
  overlapThreshold: 0.7,
  boxThreshold: 0.4,
  textThreshold: 0.3,
  motionSensitivity: 30,
  maxObjects: 8,
  outputMode: "authoring",
  qualityPreset: "balanced",
});
assert.equal(traceAllConfig.discovery.mode, "auto_object_proposals");
assert.equal(traceAllConfig.discovery.config.qualityPreset, "balanced");
assert.equal(traceAllConfig.discovery.config.trackSelectedOnly, true);
assert.equal(traceAllConfig.discovery.config.requireReview, true);
assert.equal(traceAllConfig.provider.name, "mock");
assert.equal(ui.buildRunPlan(traceAllConfig, { preset: "trace_all_objects" }).title, "Trace all objects");

const maximumRecallConfig = ui.buildRunConfig({
  preset: "auto_object_proposals",
  discoveryMode: "auto_object_proposals",
  videoPath: "examples/demo_red_ball.mp4",
  objectId: "object_0",
  objectLabel: "discovered object",
  keyframes: new Set([0]),
  maskProvider: "mock",
  debugMockMode: true,
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
  debugMockMode: true,
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
  debugMockMode: true,
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
  debugMockMode: true,
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
  debugMockMode: true,
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
  [traceAllConfig, "auto_object_proposals", "mock"],
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
const candidateStatuses = ui.candidateStatusItems(
  { candidateId: "cand_review", confidence: 0.32, reviewStatus: "needs_review", warnings: ["low_confidence"] },
  { selected: false },
);
assert.deepEqual(
  candidateStatuses.map((status) => status.key),
  ["low_confidence", "needs_review"],
);
assert.deepEqual(ui.candidateStatusItems({ reviewStatus: "accepted" }, { selected: true }).map((status) => status.key), [
  "selected",
  "reviewed_for_export",
]);
const reviewStatusCounts = ui.candidateStatusCounts(
  [
    { candidateId: "cand_selected", reviewStatus: "accepted" },
    { candidateId: "cand_background", reviewStatus: "rejected", rejectionReason: "background_like" },
    { candidateId: "cand_duplicate", reviewStatus: "rejected", rejectionReason: "duplicate_mask" },
  ],
  { cand_selected: true },
);
assert.equal(reviewStatusCounts.selected, 1);
assert.equal(reviewStatusCounts.rejected, 2);
assert.equal(reviewStatusCounts.backgroundLike, 1);
assert.equal(reviewStatusCounts.duplicate, 1);
const retrySuggestions = ui.candidateRetrySuggestions({
  candidates: [
    { candidateId: "cand_background", reviewStatus: "rejected", rejectionReason: "background_like" },
    { candidateId: "cand_low", reviewStatus: "needs_review", confidence: 0.2 },
  ],
  visibleCandidates: [],
  summary: { candidateCount: 2 },
  filters: { movingOnly: true },
});
assert.ok(retrySuggestions.some((suggestion) => suggestion.key === "maximum_recall"));
assert.ok(retrySuggestions.some((suggestion) => suggestion.key === "smaller_max_area"));
assert.ok(retrySuggestions.some((suggestion) => suggestion.key === "add_prompt"));
assert.ok(retrySuggestions.some((suggestion) => suggestion.key === "moving_workflow"));
assert.ok(ui.candidateRetrySuggestions({ candidates: [], summary: { candidateCount: 0 } }).some((suggestion) => suggestion.key === "import_masks"));

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
assert.deepEqual(
  ui.exportGateSummary({
    includedIds: ["object_0"],
    excludedIds: ["object_1"],
    pendingIds: ["manual_object"],
    status: { ok: false, issueCount: 1, checked: 3 },
  }).map((row) => row.key),
  ["reviewed_selected_only", "excluded", "pending_corrections", "validation"],
);
assert.deepEqual(ui.exportActionState({ job: null, includedIds: ["object_0"] }), {
  disabled: true,
  label: "Export MotionJSON",
  reason: "Select a completed run before exporting.",
});
assert.deepEqual(ui.exportActionState({ job: { id: "job_1" }, includedIds: ["object_0"], status: { ok: false } }), {
  disabled: true,
  label: "Resolve validation first",
  reason: "Fix or validate the reviewed export state before writing MotionJSON.",
});
assert.equal(ui.exportActionState({ job: { id: "job_1" }, includedIds: ["object_0"], status: { ok: true } }).disabled, false);
const handoffCards = ui.exportHandoffCards({
  job: { id: "job_1" },
  includedIds: ["object_0"],
  status: { ok: true },
  copiedId: "runtime-snippet",
  assets: [
    { kind: "website_package", contentUrl: "/api/artifacts/website_package/content", path: "website_package.zip" },
    { kind: "validated_motionjson_scene", contentUrl: "/api/artifacts/scene_graph/content", path: "scene_graph.json" },
    { kind: "remotion_plan", contentUrl: "/api/artifacts/remotion/content", path: "remotion_export_plan.json" },
    { kind: "motionjson_export_zip", contentUrl: "/api/artifacts/bundle/content", path: "motionjson_export.zip" },
  ],
  objectLayerPack: { snippets: { plainJs: "mountMotionJSON();", remotion: "<MotionJSONComposition />" } },
});
assert.deepEqual(handoffCards.map((card) => card.id), [
  "website-package",
  "motionjson-scene",
  "runtime-snippet",
  "remotion-plan",
  "developer-handoff",
]);
assert.equal(handoffCards.find((card) => card.id === "runtime-snippet").action, "copy");
assert.equal(handoffCards.find((card) => card.id === "runtime-snippet").actionLabel, "Copied");
assert.equal(handoffCards.find((card) => card.id === "remotion-plan").action, "open");
assert.match(
  ui.exportNextStepText({
    exportState: { includedObjectIds: ["object_0"] },
    assets: [{ kind: "website_package", contentUrl: "/api/artifacts/website_package/content" }],
    objectLayerPack: { snippets: { plainJs: "mountMotionJSON();" } },
  }),
  /Runtime snippet/,
);

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
const correctionGuidance = ui.correctionGuidanceForTrack(
  { id: "red_ball", objectId: "red_ball", label: "red ball", exportStatus: "review_pending" },
  { promptCount: 0, mergeSelectionSize: 1, status: "loaded" },
);
assert.equal(correctionGuidance.tone, "warn");
assert.ok(correctionGuidance.items.some((item) => item.includes("will not export")));
assert.ok(correctionGuidance.items.some((item) => item.includes("Draw a point")));

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
        "review-ux-guidance",
        "model-setup-flow",
        "model-plan-confirmation",
        "python-config-validation",
      ],
    },
    null,
    2,
  ),
);
