import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { api, artifactRelPath, localApiUrl, previewFileUrl, reviewToolUrl, safeLocalContentUrl } from "../src/motionjson/ui/static/modules/api_client.js";
import {
  MODEL_CONNECTIONS,
  MODEL_CONNECTION_PRIORITY,
  engineFromProviderId,
  localityFromProviderId,
  modelConnectionByConnectionId,
  normalizedModelConnection,
  providerIdFromConnectionId,
} from "../src/motionjson/ui/static/modules/provider_connections.js";
import {
  CORRECTION_STATE_FORMAT,
  applyModelSetupRecommendationToState,
  defaultState,
  emptyCorrectionState,
} from "../src/motionjson/ui/static/modules/state_store.js";
import {
  WORKFLOW_STEPS,
  normalizeWorkflowStepId,
  workflowNextStepId,
  workflowScreenForStep,
  workflowStepForScreen,
} from "../src/motionjson/ui/static/modules/workflow.js";

await import("../src/motionjson/ui/static/app.js");

const ui = globalThis.MotionJSONUI;
assert.ok(ui, "MotionJSONUI facade remains available after module extraction");

assert.equal(ui.localApiUrl, localApiUrl);
assert.equal(ui.safeLocalContentUrl, safeLocalContentUrl);
assert.equal(ui.reviewToolUrl, reviewToolUrl);
assert.equal(ui.CORRECTION_STATE_FORMAT, CORRECTION_STATE_FORMAT);
assert.equal(ui.MODEL_CONNECTIONS, MODEL_CONNECTIONS);
assert.equal(ui.MODEL_CONNECTION_PRIORITY, MODEL_CONNECTION_PRIORITY);
assert.equal(ui.WORKFLOW_STEPS, WORKFLOW_STEPS);
assert.equal(ui.normalizeWorkflowStepId, normalizeWorkflowStepId);
assert.equal(ui.workflowNextStepId, workflowNextStepId);

const originalLocationDescriptor = Object.getOwnPropertyDescriptor(globalThis, "location");
Object.defineProperty(globalThis, "location", {
  value: new URL("https://workspace.example.test/proxy/8766/ui/"),
  configurable: true,
});
assert.equal(localApiUrl("/api/jobs?limit=2"), "/proxy/8766/api/jobs?limit=2");
assert.equal(safeLocalContentUrl("/api/jobs/job_1/preview-files/preview/canvas_player.html"), "/proxy/8766/api/jobs/job_1/preview-files/preview/canvas_player.html");
assert.equal(previewFileUrl("job_1", "preview/canvas_player.html"), "/proxy/8766/api/jobs/job_1/preview-files/preview/canvas_player.html");
assert.equal(safeLocalContentUrl("https://example.test/video.mp4"), "");
assert.equal(safeLocalContentUrl("file:///Users/example/private.mp4"), "");
if (originalLocationDescriptor) {
  Object.defineProperty(globalThis, "location", originalLocationDescriptor);
} else {
  delete globalThis.location;
}

const freshState = defaultState();
assert.equal(freshState.selectedModelSetupProviderId, "");
assert.equal(freshState.modelSetupSelectionMode, "auto");
applyModelSetupRecommendationToState(freshState, {
  format: "motionjson.model_setup_recommendation.v0.1",
  goal: "trace_all_objects",
  selectedConnectionId: "sam3-local",
});
assert.equal(freshState.selectedModelSetupProviderId, freshState.selectedPreset === "trace_all_objects" ? "sam3-local" : "");
assert.equal(freshState.modelSetupRecommendations.trace_all_objects.selectedConnectionId, "sam3-local");
freshState.selectedPreset = "trace_all_objects";
applyModelSetupRecommendationToState(freshState, {
  format: "motionjson.model_setup_recommendation.v0.1",
  goal: "trace_all_objects",
  selectedConnectionId: "sam3-local",
});
assert.equal(freshState.selectedModelSetupProviderId, "sam3-local");
freshState.modelSetupSelectionMode = "user_override";
freshState.selectedModelSetupProviderId = "sam2-hf-auto-masks";
applyModelSetupRecommendationToState(freshState, {
  format: "motionjson.model_setup_recommendation.v0.1",
  goal: "trace_all_objects",
  selectedConnectionId: "sam3-local",
});
assert.equal(freshState.selectedModelSetupProviderId, "sam2-hf-auto-masks");
applyModelSetupRecommendationToState(freshState, {
  format: "motionjson.model_setup_recommendation.v0.1",
  goal: "pick_objects_from_frame",
  selectedConnectionId: "sam3-local",
});
assert.equal(freshState.modelSetupRecommendations.pick_objects_from_frame.selectedConnectionId, "sam3-local");

assert.deepEqual(WORKFLOW_STEPS.map((step) => step.id), [
  "choose_goal",
  "source_video",
  "provider_settings",
  "prompt_preview",
  "candidate_selection",
  "run_monitor",
  "review_export",
]);
assert.equal(normalizeWorkflowStepId("not-real"), "choose_goal");
assert.equal(workflowNextStepId("review_export", 1), "review_export");
assert.equal(workflowNextStepId("choose_goal", -1), "choose_goal");
assert.equal(workflowScreenForStep("provider_settings"), "model");
assert.equal(workflowStepForScreen("review"), "review_export");
assert.equal(workflowScreenForStep("candidate_selection"), "select");
assert.equal(workflowStepForScreen("select"), "candidate_selection");

const hostedConnection = modelConnectionByConnectionId("sam3-hosted:roboflow-sam3-pcs");
assert.equal(hostedConnection.providerId, "sam3-hosted");
assert.equal(hostedConnection.profileId, "roboflow-sam3-pcs");
assert.equal(hostedConnection.locality, "hosted");
assert.equal(providerIdFromConnectionId("sam2-hosted:replicate-sam2-video"), "sam2-hosted");
assert.equal(engineFromProviderId("sam3-local"), "sam3");
assert.equal(localityFromProviderId("mock"), "no_model");
assert.deepEqual(normalizedModelConnection({ id: "motion", capabilities: "motion" }).capabilities, ["motion"]);

const firstState = defaultState();
const secondState = defaultState();
firstState.prompts.push({ id: "prompt_1" });
firstState.keyframes.add(9);
firstState.mergeSelection.add("track_1");
firstState.correctionState.history.push({ action: "edit" });
assert.equal(secondState.prompts.length, 0);
assert.deepEqual([...secondState.keyframes], [0]);
assert.equal(secondState.mergeSelection.size, 0);
assert.equal(secondState.correctionState.history.length, 0);
assert.equal(emptyCorrectionState("job_1").format, CORRECTION_STATE_FORMAT);
assert.equal(artifactRelPath({ metadata: { rel_path: "/preview/overlay.png" } }), "preview/overlay.png");
assert.ok(reviewToolUrl("job_1", { relPath: "preview/canvas_player.html" }).includes("review=%2Fapi%2Fjobs%2Fjob_1%2Freview"));

const originalFetch = globalThis.fetch;
globalThis.fetch = async (url, options = {}) => ({
  ok: true,
  status: 200,
  text: async () => JSON.stringify({ url, contentType: options.headers?.["content-type"] || "" }),
});
assert.deepEqual(await api("/api/health"), { url: "/api/health", contentType: "application/json" });
globalThis.fetch = async () => ({
  ok: false,
  status: 503,
  text: async () => JSON.stringify({ detail: "runtime unavailable" }),
});
await assert.rejects(() => api("/api/health"), /runtime unavailable/);
globalThis.fetch = originalFetch;

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const indexHtml = readFileSync(resolve(repoRoot, "src/motionjson/ui/static/index.html"), "utf8");
const appSource = readFileSync(resolve(repoRoot, "src/motionjson/ui/static/app.js"), "utf8");
for (const testId of [
  "local-ui-shell",
  "goal-trace-one-object",
  "workflow-primary",
  "model-setup-panel",
  "model-setup-choices",
  "video-file-input",
  "register-video-path",
  "provider-warning",
  "start-run",
  "generate-model-plan",
  "validate-model-plan",
  "confirm-model-plan",
  "run-monitor-status",
  "job-event-log",
  "track-list",
  "correction-track-select",
  "correction-label-input",
  "relabel-track",
  "use-current-frame-range",
  "merge-tracks",
  "split-track",
  "add-object",
  "repair-track",
  "export-motionjson",
  "correction-guidance",
]) {
  assert.ok(indexHtml.includes(`data-testid="${testId}"`), `missing static data-testid ${testId}`);
}
for (const dynamicTestId of [
  'data-testid="model-choice-',
  'data-testid="model-setup-allow-hosted"',
  'action === "auto-setup"',
  'action === "save-and-auto-setup"',
  'action === "use-fallback-now"',
  'data-model-setup-action="rescan-runtime"',
  'data-model-setup-action="acknowledge-override"',
  'data-testid="provider-settings-',
  'data-testid="provider-allow-hosted-',
]) {
  assert.ok(appSource.includes(dynamicTestId), `missing dynamic data-testid marker ${dynamicTestId}`);
}
