import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

await import("../src/motionjson/ui/static/app.js");

const ui = globalThis.MotionJSONUI;
assert.ok(ui, "MotionJSONUI helper API should be exposed for JS checks");
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
assert.ok(ui.API_ROUTES.includes("/api/jobs/{jobId}/track-selected"));
assert.ok(ui.API_ROUTES.includes("/api/model-providers/{providerId}/test"));
assert.ok(ui.API_ROUTES.includes("/api/provider-settings/{providerId}/diagnose"));
assert.ok(ui.API_ROUTES.includes("/api/provider-settings/{providerId}/setup/start"));
assert.ok(ui.API_ROUTES.includes("/api/provider-settings/setup-jobs/{jobId}"));
assert.ok(ui.API_ROUTES.includes("/api/provider-settings/setup-jobs/{jobId}/cancel"));
assert.ok(ui.API_ROUTES.includes("/api/model-runs/{runId}/confirm-job"));
assert.equal(ui.WORKFLOW_STEPS.length, 6);
assert.deepEqual(ui.WORKFLOW_STEPS.map((step) => step.id), [
  "choose_goal",
  "source_video",
  "provider_settings",
  "prompt_preview",
  "run_monitor",
  "review_export",
]);
assert.equal(ui.normalizeWorkflowStepId("bad-step"), "choose_goal");
assert.equal(ui.workflowNextStepId("source_video", 1), "provider_settings");
assert.equal(ui.workflowNextStepId("source_video", -1), "choose_goal");
assert.equal(ui.workflowNextStepId("prompt_preview", 1), "run_monitor");
assert.equal(ui.workflowRestoredStepFromSnapshot({ selectedPreset: "trace_one_object" }, "review_export"), "choose_goal");
assert.equal(ui.workflowRestoredStepFromSnapshot({ selectedPreset: "motion_foreground", selectedProjectId: "project_1" }, "review_export"), "choose_goal");
assert.equal(
  ui.workflowRestoredStepFromSnapshot({ selectedPreset: "trace_one_object", selectedProjectId: "project_1", selectedVideoId: "video_1" }, "review_export"),
  "source_video",
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
  videoPreviewReady: true,
  configValid: true,
  selectedJobId: "job_1",
  candidateCount: 2,
  trackCount: 1,
  exportValidated: true,
  exportOk: true,
});
assert.equal(readyWorkflow.source_video.complete, true);
assert.equal(readyWorkflow.prompt_preview.complete, true);
assert.equal(readyWorkflow.run_monitor.status, "done");
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
assert.equal(readyPrepareContract.primaryLabel, "Run scene sweep");
assert.equal(readyPrepareContract.enabled, true);
const failedRunContract = ui.workflowStepContractFromSnapshot(
  {
    selectedPreset: "trace_all_objects",
    selectedVideoId: "video_1",
    selectedJobId: "job_failed",
    selectedJobStatus: "failed",
    hasFailure: true,
  },
  "run_monitor",
);
assert.equal(failedRunContract.primaryLabel, "Change setup");
assert.equal(failedRunContract.primaryAction, "prepare_new_run");
assert.equal(failedRunContract.enabled, true);
const completedRunContract = ui.workflowStepContractFromSnapshot(
  {
    selectedPreset: "trace_all_objects",
    selectedVideoId: "video_1",
    selectedJobId: "job_done",
    selectedJobStatus: "succeeded",
    candidateCount: 4,
  },
  "run_monitor",
);
assert.equal(completedRunContract.primaryLabel, "Continue to review");
assert.equal(completedRunContract.primaryAction, "continue_to_review");
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
assert.deepEqual(postRunSummary.map((stage) => stage.id), ["candidates", "track_selected", "tracks", "corrections", "export"]);
assert.equal(postRunSummary.find((stage) => stage.id === "candidates").value, "2/3 kept");
assert.equal(postRunSummary.find((stage) => stage.id === "track_selected").status, "done");
assert.equal(postRunSummary.find((stage) => stage.id === "tracks").value, "2 tracks");
assert.equal(postRunSummary.find((stage) => stage.id === "corrections").status, "done");
assert.equal(postRunSummary.find((stage) => stage.id === "export").status, "needs-action");
const candidateOnlyFlow = ui.reviewFlowStateFromSnapshot({
  job: { id: "job_candidates", status: "succeeded" },
  candidateCount: 3,
  selectedCandidateCount: 2,
  trackCount: 0,
});
assert.equal(candidateOnlyFlow.gate.primaryAction, "track_selected");
assert.equal(candidateOnlyFlow.stages.find((stage) => stage.id === "track_selected").value, "2 ready");
const failedPostRunSummary = ui.postRunWorkflowSummaryFromSnapshot({
  selectedJobStatus: "failed",
  hasFailure: true,
  diagnosticCount: 2,
});
assert.equal(failedPostRunSummary.find((stage) => stage.id === "candidates").status, "blocked");
const failedRunSummary = ui.runMonitorStageFromSnapshot({
  selectedJobStatus: "failed",
  hasFailure: true,
  diagnosticCount: 2,
});
assert.equal(failedRunSummary.status, "blocked");
assert.match(failedRunSummary.detail, /failure|diagnostics|logs/i);
const fallbackPostRunSummary = ui.postRunWorkflowSummaryFromSnapshot({
  selectedJobStatus: "succeeded",
  diagnosticCount: 2,
  attentionDiagnosticCount: 1,
});
assert.equal(fallbackPostRunSummary.find((stage) => stage.id === "candidates").value, "None reported");
const fallbackRunSummary = ui.runMonitorStageFromSnapshot({
  selectedJobStatus: "succeeded",
  diagnosticCount: 2,
  attentionDiagnosticCount: 1,
});
assert.equal(fallbackRunSummary.status, "warning");
assert.match(fallbackRunSummary.detail, /fallback|provider diagnostic/i);
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

const sam3NeedsAccessState = ui.modelSetupStateForConnection(
  { id: "sam3-local", providerId: "sam3-local", locality: "local" },
  {
    id: "sam3-local",
    readiness: { configured: true, status: "ready" },
    setupState: {
      status: "needs_access",
      label: "Needs Hugging Face access",
      message: "Paste a Hugging Face token for facebook/sam3.",
      runnable: false,
      nextAction: "check_access",
    },
    modelCache: { cached: false },
  },
  null,
);
assert.equal(sam3NeedsAccessState.status, "needs_access");
assert.notEqual(sam3NeedsAccessState.message, "Ready for this workflow.");
assert.equal(ui.modelSetupPrimaryActionForState(sam3NeedsAccessState, { providerId: "sam3-local" }).label, "Check Hugging Face access");

const sam3BlockedAccessJobState = ui.modelSetupStateForConnection(
  { id: "sam3-local", providerId: "sam3-local", locality: "local" },
  {
    id: "sam3-local",
    readiness: { configured: true, status: "ready" },
    setupState: {
      status: "needs_access",
      label: "Needs Hugging Face access",
      message: "Paste a Hugging Face token for facebook/sam3.",
      runnable: false,
      nextAction: "check_access",
    },
  },
  {
    action: "check_access",
    status: "blocked",
    terminal: true,
    result: {
      message: "Paste a Hugging Face token in Model setup after Meta approves facebook/sam3 access, then run Check access again.",
    },
  },
);
assert.equal(sam3BlockedAccessJobState.status, "needs_access");
assert.equal(ui.modelSetupPrimaryActionForState(sam3BlockedAccessJobState, { providerId: "sam3-local" }).label, "Check Hugging Face access");

const sam3ActiveAccessJobState = ui.modelSetupStateForConnection(
  { id: "sam3-local", providerId: "sam3-local", locality: "local" },
  {
    id: "sam3-local",
    readiness: { configured: true, status: "ready" },
  },
  {
    action: "check_access",
    status: "running",
    terminal: false,
    setupState: {
      status: "needs_access",
      label: "Checking access",
      message: "Checking Hugging Face access.",
    },
    result: {},
  },
);
assert.equal(sam3ActiveAccessJobState.status, "checking_environment");
assert.equal(ui.modelSetupPrimaryActionForState(sam3ActiveAccessJobState, { providerId: "sam3-local" }).label, "Cancel setup");

const sam3CacheAccessBlockedState = ui.modelSetupStateForConnection(
  { id: "sam3-local", providerId: "sam3-local", locality: "local" },
  {
    id: "sam3-local",
    readiness: { configured: true, status: "ready" },
  },
  {
    action: "cache_model",
    status: "blocked",
    terminal: true,
    result: {
      message: "Hugging Face returned 403 for facebook/sam3. Confirm access with a configured token before caching.",
    },
  },
);
assert.equal(sam3CacheAccessBlockedState.status, "needs_access");
assert.equal(ui.modelSetupPrimaryActionForState(sam3CacheAccessBlockedState, { providerId: "sam3-local" }).label, "Check Hugging Face access");

const sam2CacheState = ui.modelSetupStateForConnection(
  { id: "sam2-hf-auto-masks", providerId: "sam2-hf-auto-masks", locality: "local" },
  {
    id: "sam2-hf-auto-masks",
    readiness: { configured: true, status: "ready" },
    setupState: {
      status: "needs_download_confirmation",
      label: "Confirm model cache",
      message: "Cache facebook/sam2.1-hiera-large before running.",
      runnable: false,
      nextAction: "cache_model",
    },
    modelCache: { cached: false },
  },
  null,
);
assert.equal(sam2CacheState.status, "needs_download_confirmation");
assert.equal(ui.modelSetupPrimaryActionForState(sam2CacheState, { providerId: "sam2-hf-auto-masks" }).label, "Cache model");

const staleNotConfiguredState = ui.modelSetupStateForConnection(
  { id: "sam2-local", providerId: "sam2-local", locality: "local" },
  {
    id: "sam2-local",
    readiness: { configured: true, status: "ready", message: "Runtime ready." },
    setupState: { status: "not_configured", label: "Needs setup", message: "Historical stale setup state." },
  },
  null,
);
assert.equal(staleNotConfiguredState.status, "ready");
assert.equal(ui.modelSetupPrimaryActionForState(staleNotConfiguredState, { providerId: "sam2-local" }).label, "Continue to prepare");

const cacheConfirmation = ui.modelSetupConfirmationForAction("cache-model", "sam2-hf-auto-masks", {
  model: "facebook/sam2.1-hiera-large",
});
assert.equal(cacheConfirmation.requiresConfirmation, true);
assert.equal(cacheConfirmation.providerId, "sam2-hf-auto-masks");
assert.ok(cacheConfirmation.flags.includes("disk"));
assert.ok(cacheConfirmation.flags.includes("network"));

const accessConfirmation = ui.modelSetupConfirmationForAction("check-access", "sam3-local", {
  model: "facebook/sam3",
  settingsPayload: ui.modelSetupPayloadFromValues("sam3-local", {
    selectedModel: "facebook/sam3",
    hfToken: "hf_snapshot_only_for_test",
  }),
});
assert.equal(accessConfirmation.providerId, "sam3-local");
assert.equal(accessConfirmation.action, "check-access");
assert.equal(accessConfirmation.model, "facebook/sam3");
assert.equal(accessConfirmation.settingsPayload.hfToken, "hf_snapshot_only_for_test");

const activeCacheJob = {
  action: "cache_model",
  status: "running",
  terminal: false,
  progress: { known: false, percent: 35, label: "Downloading or resolving Hugging Face snapshot" },
  result: {},
};
const activeCacheState = ui.modelSetupStateForConnection(
  { id: "sam3-local", providerId: "sam3-local", locality: "local" },
  { id: "sam3-local", readiness: { configured: true, status: "ready" } },
  activeCacheJob,
);
assert.equal(activeCacheState.status, "caching_model");
assert.equal(ui.modelSetupPrimaryActionForState(activeCacheState, { providerId: "sam3-local" }).label, "Cancel setup");
assert.deepEqual(ui.setupJobProgressSummary(activeCacheJob), {
  known: false,
  percent: 35,
  label: "Downloading or resolving Hugging Face snapshot",
});

const appJs = readFileSync(resolve(repoRoot, "src/motionjson/ui/static/app.js"), "utf8");
assert.equal(appJs.includes("window.confirm"), false);
const confirmationHandler = appJs.slice(
  appJs.indexOf("const confirmationButton = event.target.closest"),
  appJs.indexOf("const button = event.target.closest(\"[data-model-setup-action]\")"),
);
assert.ok(confirmationHandler.includes("state.confirmedModelSetupAction"));
assert.ok(confirmationHandler.includes("state.confirmedModelSetupAction = null;"));
assert.ok(appJs.includes("function modelSetupPayloadForAction"));
assert.ok(appJs.includes("model-setup-progress-card"));
assert.equal(/state\.pendingModelSetupConfirmation = null;\s*renderModelSetup\(\);\s*const setupButton/.test(confirmationHandler), false);

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
const hostedSam2Contract = ui.providerContractForInput({
  preset: "trace_one_object",
  modelConnectionId: "sam2-hosted:replicate-sam2-video",
  hostedSam2AllowHosted: true,
});
assert.equal(hostedSam2Contract.connectionId, "sam2-hosted:replicate-sam2-video");
assert.equal(hostedSam2Contract.providerId, "sam2-hosted");
assert.equal(hostedSam2Contract.displayLabel, "Replicate SAM2 video");
assert.equal(hostedSam2Contract.engine, "sam2");
assert.equal(hostedSam2Contract.locality, "hosted");
assert.equal(hostedSam2Contract.hostedCallsAllowed, true);

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
const hostedSam3BlockedConfig = ui.buildRunConfig({
  preset: "text_detector",
  modelConnectionId: "sam3-hosted:roboflow-sam3-pcs",
  textPrompt: "red ball",
  hostedSam3ProfileId: "roboflow-sam3-pcs",
  hostedSam3AllowHosted: false,
});
assert.equal(hostedSam3BlockedConfig.discovery.config.allowNetwork, false);
assert.equal(hostedSam3BlockedConfig.provider.sam3.hosted_allow_network, false);
const hostedSam3Plan = ui.guidedEnginePlan({
  preset: "text_detector",
  modelConnectionId: "sam3-hosted:roboflow-sam3-pcs",
  hostedSam3AllowHosted: false,
});
assert.equal(hostedSam3Plan.providerId, "sam3-hosted");
assert.equal(hostedSam3Plan.connectionId, "sam3-hosted:roboflow-sam3-pcs");
assert.equal(hostedSam3Plan.displayLabel, "Roboflow SAM3");
assert.equal(hostedSam3Plan.discoveryMode, "sam3_concept");
assert.equal(hostedSam3Plan.hostedCallsAllowed, false);

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
assert.equal(sam3TraceAllConfig.discovery.config.sceneSweep, true);
assert.equal(sam3TraceAllConfig.discovery.config.useTransformersTracker, true);
assert.equal(sam3TraceAllConfig.discovery.config.sam3TrackerModel, "facebook/sam3");
assert.equal("sam3ModelPath" in sam3TraceAllConfig.discovery.config, false);
assert.equal("model" in sam3TraceAllConfig.discovery.config, false);
assert.equal("concept" in sam3TraceAllConfig.discovery.config, false);
assert.equal("text" in sam3TraceAllConfig.discovery.config, false);

const sam2HfTraceAllConfig = ui.buildRunConfig({
  preset: "trace_all_objects",
  modelConnectionId: "sam2-hf-auto-masks",
  objectId: "object_0",
  objectLabel: "all objects",
  keyframes: new Set([0, 12]),
  qualityPreset: "balanced",
});
assert.equal(sam2HfTraceAllConfig.provider.name, "sam2-hf-auto-masks");
assert.equal(sam2HfTraceAllConfig.discovery.mode, "sam2_hf_auto_masks");
assert.equal(sam2HfTraceAllConfig.discovery.config.providerPreference, "sam2-hf-auto-masks");
assert.equal(sam2HfTraceAllConfig.discovery.config.sam2HfModel, "facebook/sam2.1-hiera-large");

const textPromptDefaultsToSam3 = ui.guidedEnginePlan({
  preset: "text_detector",
  maskProvider: "sam2-local",
  textDiscoveryProvider: "detector",
});
assert.equal(textPromptDefaultsToSam3.providerId, "sam3-local");
assert.equal(textPromptDefaultsToSam3.displayLabel, "SAM3 Scene Sweep");
assert.equal(textPromptDefaultsToSam3.discoveryMode, "sam3_concept");

const advancedDetectorFallback = ui.guidedEnginePlan({
  preset: "text_detector",
  maskProvider: "threshold",
  textDiscoveryProvider: "detector",
  allowLegacyTextDetector: true,
});
assert.equal(advancedDetectorFallback.providerId, "threshold");
assert.equal(advancedDetectorFallback.discoveryMode, "text_detector");
assert.equal(advancedDetectorFallback.locality, "no_model");

const motionContract = ui.providerContractForInput({
  preset: "motion_foreground",
  maskProvider: "motion",
});
assert.equal(motionContract.providerId, "motion");
assert.equal(motionContract.displayLabel, "Motion foreground");
assert.equal(motionContract.locality, "no_model");

const runPlanUsesProviderIdForLogic = ui.buildRunPlan(hostedSam3Config, {
  preset: "text_detector",
  modelConnectionId: "sam3-hosted:roboflow-sam3-pcs",
  hostedSam3AllowHosted: true,
  videoId: "video_1",
  previewName: "preview.mp4",
});
assert.equal(runPlanUsesProviderIdForLogic.providerName, "Roboflow SAM3");
assert.equal(runPlanUsesProviderIdForLogic.providerId, "sam3-hosted");
assert.equal(runPlanUsesProviderIdForLogic.providerLocality, "hosted");
assert.equal(runPlanUsesProviderIdForLogic.privacy, "Hosted calls allowed after confirmation");

const PROVIDER_STATE_FIXTURES = [
  {
    name: "SAM2 local prompt tracking",
    input: { preset: "trace_one_object", modelConnectionId: "sam2-local" },
    expected: {
      connectionId: "sam2-local",
      providerId: "sam2-local",
      profileId: "",
      displayLabel: "SAM2 prompt tracking",
      engine: "sam2",
      locality: "local",
      hostedCallsAllowed: false,
      discoveryMode: "manual_prompt",
    },
  },
  {
    name: "Replicate SAM2 hosted prompt tracking",
    input: { preset: "trace_one_object", modelConnectionId: "sam2-hosted:replicate-sam2-video", hostedSam2AllowHosted: true },
    expected: {
      connectionId: "sam2-hosted:replicate-sam2-video",
      providerId: "sam2-hosted",
      profileId: "replicate-sam2-video",
      displayLabel: "Replicate SAM2 video",
      engine: "sam2",
      locality: "hosted",
      hostedCallsAllowed: true,
      discoveryMode: "manual_prompt",
    },
  },
  {
    name: "SAM3 local exemplar tracking",
    input: { preset: "trace_one_object", modelConnectionId: "sam3-local" },
    expected: {
      connectionId: "sam3-local",
      providerId: "sam3-local",
      profileId: "",
      displayLabel: "SAM3 Scene Sweep",
      engine: "sam3",
      locality: "local",
      hostedCallsAllowed: false,
      discoveryMode: "sam3_exemplar",
    },
  },
  {
    name: "Roboflow SAM3 hosted concept search",
    input: { preset: "text_detector", modelConnectionId: "sam3-hosted:roboflow-sam3-pcs", hostedSam3AllowHosted: false },
    expected: {
      connectionId: "sam3-hosted:roboflow-sam3-pcs",
      providerId: "sam3-hosted",
      profileId: "roboflow-sam3-pcs",
      displayLabel: "Roboflow SAM3",
      engine: "sam3",
      locality: "hosted",
      hostedCallsAllowed: false,
      discoveryMode: "sam3_concept",
    },
  },
  {
    name: "SAM2 HF automatic masks fallback",
    input: { preset: "trace_all_objects", modelConnectionId: "sam2-hf-auto-masks" },
    expected: {
      connectionId: "sam2-hf-auto-masks",
      providerId: "sam2-hf-auto-masks",
      profileId: "",
      displayLabel: "SAM2 HF automatic masks",
      engine: "sam2",
      locality: "local",
      hostedCallsAllowed: false,
      discoveryMode: "sam2_hf_auto_masks",
    },
  },
  {
    name: "Motion foreground no-model path",
    input: { preset: "motion_foreground", maskProvider: "motion_foreground" },
    expected: {
      connectionId: "",
      planConnectionId: "motion_foreground",
      providerId: "motion_foreground",
      profileId: "",
      displayLabel: "Motion foreground",
      engine: "motion",
      locality: "no_model",
      hostedCallsAllowed: false,
      discoveryMode: "motion_foreground",
    },
  },
  {
    name: "Imported masks no-model path",
    input: { preset: "external_masks", maskProvider: "external_masks" },
    expected: {
      connectionId: "",
      planConnectionId: "external_masks",
      providerId: "external_masks",
      profileId: "",
      displayLabel: "Imported masks",
      engine: "external_masks",
      locality: "no_model",
      hostedCallsAllowed: false,
      discoveryMode: "external_masks",
    },
  },
];

for (const fixture of PROVIDER_STATE_FIXTURES) {
  const contract = ui.providerContractForInput(fixture.input);
  const plan = ui.guidedEnginePlan(fixture.input);
  assert.equal(contract.connectionId, fixture.expected.connectionId, `${fixture.name}: contract connection id`);
  assert.equal(contract.providerId, fixture.expected.providerId, `${fixture.name}: contract provider id`);
  assert.equal(contract.profileId, fixture.expected.profileId, `${fixture.name}: contract profile id`);
  assert.equal(contract.displayLabel, fixture.expected.displayLabel, `${fixture.name}: contract label`);
  assert.equal(contract.engine, fixture.expected.engine, `${fixture.name}: contract engine`);
  assert.equal(contract.locality, fixture.expected.locality, `${fixture.name}: contract locality`);
  assert.equal(contract.hostedCallsAllowed, fixture.expected.hostedCallsAllowed, `${fixture.name}: hosted opt-in`);
  assert.equal(plan.providerId, fixture.expected.providerId, `${fixture.name}: plan provider id`);
  assert.equal(plan.connectionId, fixture.expected.planConnectionId ?? fixture.expected.connectionId, `${fixture.name}: plan connection id`);
  assert.equal(plan.displayLabel, fixture.expected.displayLabel, `${fixture.name}: plan label`);
  assert.equal(plan.discoveryMode, fixture.expected.discoveryMode, `${fixture.name}: discovery mode`);
}

const compatibleConnectionExpectations = {
  trace_one_object: ["sam2-local", "sam2-hosted:replicate-sam2-video"],
  text_detector: ["sam3-local", "sam3-hosted:roboflow-sam3-pcs", "sam3-hosted:custom-sam3-compatible", "sam3-hosted:fal-sam3-image"],
  trace_all_objects: ["sam3-local", "sam2-hf-auto-masks", "sam3-hosted:custom-sam3-compatible"],
  motion_foreground: [],
  external_masks: [],
};

for (const [preset, expectedIds] of Object.entries(compatibleConnectionExpectations)) {
  assert.deepEqual(
    ui.compatibleModelConnectionsForPreset(preset).map((connection) => connection.id),
    expectedIds,
    `${preset}: compatible guided model connections`,
  );
}

assert.deepEqual(
  ui.compatibleModelConnectionsForPreset("trace_one_object", { includeAdvanced: true }).map((connection) => connection.id),
  ["sam2-local", "sam2-hosted:replicate-sam2-video", "sam3-local", "sam3-hosted:custom-sam3-compatible"],
  "SAM3 one-object connections stay available only in the Advanced model list",
);

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
assert.equal(ui.buildRunPlan(traceAllConfig, { preset: "trace_all_objects" }).title, "Find everything in scene");

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
  [hostedSam2Config, "manual_prompt", "sam2-hosted"],
  [sam3SingleObjectConfig, "sam3_exemplar", "sam3-local"],
  [sam3TraceAllConfig, "sam3_auto_masks", "sam3-local"],
  [hostedSam3Config, "sam3_concept", "sam3-hosted"],
  [hostedSam3BlockedConfig, "sam3_concept", "sam3-hosted"],
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
  reason: "No completed run is selected.",
});
assert.deepEqual(ui.exportActionState({ job: { id: "job_1", status: "succeeded" }, includedIds: ["object_0"], trackCount: 1, status: { ok: false } }), {
  disabled: true,
  label: "Resolve validation first",
  reason: "Resolve export validation issues before writing MotionJSON.",
});
assert.deepEqual(ui.exportActionState({ job: { id: "job_1", status: "succeeded" }, includedIds: [], trackCount: 1 }), {
  disabled: true,
  label: "Export MotionJSON",
  reason: "Mark at least one reviewed track for export.",
});
assert.equal(ui.exportActionState({ job: { id: "job_1", status: "succeeded" }, includedIds: ["object_0"], trackCount: 1, status: { ok: true } }).disabled, false);
const handoffCards = ui.exportHandoffCards({
  job: { id: "job_1", status: "succeeded" },
  includedIds: ["object_0"],
  trackCount: 1,
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
for (const card of handoffCards) {
  assert.ok(card.title, `${card.id}: handoff card should have a title`);
  assert.ok(card.status, `${card.id}: handoff card should have a short status`);
  assert.ok(card.actionLabel, `${card.id}: handoff card should expose one direct action label`);
  assert.ok(String(card.description || "").split(/\s+/).filter(Boolean).length <= 18, `${card.id}: handoff description should stay compact`);
  assert.doesNotMatch(String(card.description || ""), /\n/, `${card.id}: handoff description should not become paragraph copy`);
}
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

const lifecycleQueued = ui.normalizeJobLifecycle({
  id: "job_queued",
  type: "extract",
  status: "queued",
  createdAt: "2026-05-20T10:00:00Z",
  lifecycle: {
    status: "queued",
    phase: "queued",
    progress: { known: false, percent: 0, label: "Queued" },
    provider: { providerId: "sam2-local", displayLabel: "SAM2 local", engine: "sam2", locality: "local" },
  },
});
assert.equal(lifecycleQueued.status, "queued");
assert.equal(lifecycleQueued.progress.known, false);
assert.equal(lifecycleQueued.provider.displayLabel, "SAM2 local");

const lifecycleBackendShape = ui.normalizeJobLifecycle({
  id: "job_waiting_review",
  type: "extract",
  status: "succeeded",
  lifecycle: {
    status: "waiting_review",
    rawStatus: "succeeded",
    phase: "review_ready",
    provider: {
      id: "sam3-hosted",
      connectionId: "sam3-hosted:roboflow-sam3-pcs",
      label: "Roboflow SAM3",
      engine: "sam3",
      locality: "hosted",
      hostedCallsAllowed: true,
    },
    review: { candidateCount: 2, selectedCandidateCount: 1, trackCount: 0, exportableTrackCount: 0 },
    actions: { canCancel: false, canTrackSelected: true, canExport: false },
  },
});
assert.equal(lifecycleBackendShape.status, "waiting_review");
assert.equal(lifecycleBackendShape.provider.providerId, "sam3-hosted");
assert.equal(lifecycleBackendShape.provider.displayLabel, "Roboflow SAM3");
assert.equal(lifecycleBackendShape.actions.canCancel, false);

const lifecycleRunning = ui.normalizeJobLifecycle({
  id: "job_running",
  type: "extract",
  status: "running",
  updatedAt: "2026-05-20T10:05:00Z",
  events: [{ metadata: { progress: { overallRatio: 0.42 }, stage: "tracking" }, message: "tracking object" }],
});
assert.equal(lifecycleRunning.progress.percent, 42);
assert.equal(lifecycleRunning.progress.known, true);
assert.equal(lifecycleRunning.phase, "tracking");

const lifecycleFailed = ui.normalizeJobLifecycle({
  id: "job_failed",
  type: "extract",
  status: "failed",
  error: "SAM2 checkpoint missing.",
});
assert.equal(lifecycleFailed.failure.reasonCode, "job_failed");
assert.match(lifecycleFailed.failure.message, /checkpoint/);

const lifecycleCanceled = ui.normalizeJobLifecycle({ id: "job_canceled", status: "canceled" });
assert.equal(lifecycleCanceled.status, "canceled");
assert.equal(lifecycleCanceled.actions.canCancel, false);

const LIFECYCLE_STATE_FIXTURES = [
  {
    name: "queued job",
    job: { id: "job_fixture_queued", type: "extract", status: "queued" },
    expected: { status: "queued", phase: "queued", progressKnown: false, progressPercent: 0, canCancel: true, canExport: false, primaryAction: "watch_job", primaryLabel: "Watch job" },
  },
  {
    name: "running job with event progress",
    job: {
      id: "job_fixture_running",
      type: "extract",
      status: "running",
      events: [{ metadata: { stage: "tracking", progress: { overallRatio: 0.42 } }, message: "tracking object" }],
    },
    expected: { status: "running", phase: "tracking", progressKnown: true, progressPercent: 42, canCancel: true, canExport: false, primaryAction: "watch_job", primaryLabel: "Watch job" },
  },
  {
    name: "candidate review gate",
    job: {
      id: "job_fixture_candidates",
      type: "extract",
      status: "succeeded",
      lifecycle: {
        status: "waiting_review",
        phase: "review_ready",
        review: { candidateCount: 2, selectedCandidateCount: 1, trackCount: 0, exportableTrackCount: 0 },
        actions: { canCancel: false, canTrackSelected: true, canExport: false },
      },
    },
    expected: { status: "waiting_review", phase: "review_ready", progressKnown: false, progressPercent: 100, canCancel: false, canExport: false, primaryAction: "track_selected", primaryLabel: "Track selected" },
  },
  {
    name: "failed job",
    job: { id: "job_fixture_failed", type: "extract", status: "failed", error: "SAM2 model weights unavailable." },
    expected: { status: "failed", phase: "failed", progressKnown: false, progressPercent: 0, canCancel: false, canExport: false, primaryAction: "prepare_new_run", primaryLabel: "Change setup", reasonCode: "job_failed" },
  },
  {
    name: "canceled job",
    job: { id: "job_fixture_canceled", type: "extract", status: "canceled" },
    expected: { status: "canceled", phase: "canceled", progressKnown: false, progressPercent: 0, canCancel: false, canExport: false, primaryAction: "prepare_new_run", primaryLabel: "Change setup", reasonCode: "user_canceled" },
  },
  {
    name: "export-ready reviewed job",
    job: {
      id: "job_fixture_export",
      type: "extract",
      status: "succeeded",
      lifecycle: {
        status: "succeeded",
        phase: "complete",
        review: { candidateCount: 0, selectedCandidateCount: 0, trackCount: 2, exportableTrackCount: 1 },
        actions: { canCancel: false, canExport: true },
      },
    },
    expected: { status: "succeeded", phase: "complete", progressKnown: false, progressPercent: 100, canCancel: false, canExport: true, primaryAction: "export_reviewed", primaryLabel: "Export reviewed objects" },
  },
];

for (const fixture of LIFECYCLE_STATE_FIXTURES) {
  const lifecycle = ui.normalizeJobLifecycle(fixture.job);
  const gate = ui.reviewGateFromSnapshot({ job: fixture.job });
  assert.equal(lifecycle.status, fixture.expected.status, `${fixture.name}: normalized status`);
  assert.equal(lifecycle.phase, fixture.expected.phase, `${fixture.name}: normalized phase`);
  assert.equal(lifecycle.progress.known, fixture.expected.progressKnown, `${fixture.name}: progress precision`);
  assert.equal(lifecycle.progress.percent, fixture.expected.progressPercent, `${fixture.name}: progress percent`);
  assert.equal(lifecycle.actions.canCancel, fixture.expected.canCancel, `${fixture.name}: can cancel`);
  assert.equal(Boolean(lifecycle.actions.canExport), fixture.expected.canExport, `${fixture.name}: can export`);
  assert.equal(gate.primaryAction, fixture.expected.primaryAction, `${fixture.name}: review gate primary action`);
  assert.equal(gate.primaryLabel, fixture.expected.primaryLabel, `${fixture.name}: review gate primary label`);
  if (fixture.expected.reasonCode) assert.equal(lifecycle.failure.reasonCode, fixture.expected.reasonCode, `${fixture.name}: failure reason`);
}

const jobCenter = ui.jobCenterStateFromSnapshot({
  selectedJobId: "",
  jobs: [
    { id: "job_old", status: "failed", updatedAt: "2026-05-20T09:00:00Z" },
    { id: "job_new_running", status: "running", updatedAt: "2026-05-20T10:10:00Z" },
    { id: "job_queued", status: "queued", updatedAt: "2026-05-20T10:00:00Z" },
  ],
});
assert.equal(jobCenter.activeJobsCount, 2);
assert.equal(jobCenter.selectedJobId, "job_new_running");
assert.deepEqual(jobCenter.activeJobs.map((job) => job.id), ["job_new_running", "job_queued"]);

const manualJobCenter = ui.jobCenterStateFromSnapshot({
  selectedJobId: "job_old",
  jobs: [
    { id: "job_old", status: "failed", updatedAt: "2026-05-20T09:00:00Z" },
    { id: "job_new_running", status: "running", updatedAt: "2026-05-20T10:10:00Z" },
  ],
});
assert.equal(manualJobCenter.selectedJobId, "job_old");

assert.deepEqual(ui.reviewGateFromSnapshot({ job: null }), {
  status: "blocked",
  primaryAction: "start_run",
  primaryLabel: "Start a run",
  reason: "Run extraction before reviewing results.",
});
assert.equal(ui.reviewGateFromSnapshot({ job: { id: "job_running", status: "running" } }).primaryAction, "watch_job");
assert.equal(ui.reviewGateFromSnapshot({ job: { id: "job_failed", status: "failed", error: "provider failed" } }).primaryAction, "prepare_new_run");
assert.equal(
  ui.reviewGateFromSnapshot({ job: { id: "job_done", status: "succeeded" }, candidateCount: 3, selectedCandidateCount: 2 }).primaryAction,
  "track_selected",
);
assert.equal(ui.reviewGateFromSnapshot({ job: lifecycleBackendShape }).primaryAction, "track_selected");
assert.equal(
  ui.reviewGateFromSnapshot({
    job: {
      id: "job_backend_tracks",
      status: "succeeded",
      lifecycle: {
        status: "waiting_review",
        rawStatus: "succeeded",
        review: { candidateCount: 0, selectedCandidateCount: 0, trackCount: 2, exportableTrackCount: 0 },
        actions: { canCancel: false, canExport: false },
      },
    },
  }).primaryAction,
  "mark_reviewed",
);
assert.equal(
  ui.reviewGateFromSnapshot({
    job: {
      id: "job_backend_export",
      status: "succeeded",
      lifecycle: {
        status: "waiting_review",
        rawStatus: "succeeded",
        review: { candidateCount: 0, selectedCandidateCount: 0, trackCount: 2, exportableTrackCount: 1 },
        actions: { canCancel: false, canExport: true },
      },
    },
  }).primaryAction,
  "export_reviewed",
);
assert.match(
  ui.reviewGateFromSnapshot({
    job: {
      id: "job_backend_raster",
      status: "succeeded",
      lifecycle: {
        status: "waiting_review",
        rawStatus: "succeeded",
        review: { candidateCount: 0, trackCount: 0, diagnosticCount: 1, hasRasterFallback: true, vectorUnavailableReason: "masks too large" },
        actions: { canCancel: false, canExport: false },
      },
    },
  }).reason,
  /masks too large/,
);
assert.equal(
  ui.reviewGateFromSnapshot({ job: { id: "job_tracks", status: "succeeded" }, trackCount: 2, exportIncludedCount: 0 }).primaryAction,
  "mark_reviewed",
);
assert.equal(
  ui.reviewGateFromSnapshot({ job: { id: "job_export", status: "succeeded" }, trackCount: 2, exportIncludedCount: 1 }).primaryAction,
  "export_reviewed",
);

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
        "provider-state-fixtures",
        "lifecycle-state-fixtures",
        "job-center-regression-gates",
        "export-handoff-minimal-copy",
        "python-config-validation",
      ],
    },
    null,
    2,
  ),
);
