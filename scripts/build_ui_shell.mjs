import { readFile } from "node:fs/promises";
import { join } from "node:path";

const root = process.cwd();
const staticDir = join(root, "src", "motionjson", "ui", "static");
const files = ["index.html", "app.css", "app.js", "config_builder.js"];
const contents = new Map();

for (const file of files) {
  const content = await readFile(join(staticDir, file), "utf8");
  if (!content.trim()) {
    throw new Error(`${file} is empty`);
  }
  contents.set(file, content);
}

const index = contents.get("index.html");
const script = contents.get("app.js");
const style = contents.get("app.css");
const configBuilder = contents.get("config_builder.js");
const combined = [...contents.values()].join("\n");

for (const reference of ["/ui/app.css", "/ui/app.js"]) {
  if (!index.includes(reference)) {
    throw new Error(`index.html does not reference ${reference}`);
  }
}

for (const id of [
  "healthStatus",
  "firstRunChecklist",
  "apiStatus",
  "providerWarning",
  "capabilityList",
  "projectForm",
  "projectSelect",
  "videoForm",
  "videoSelect",
  "videoFileInput",
  "videoList",
  "viewerStage",
  "previewVideo",
  "overlayCanvas",
  "coordinateReadout",
  "frameReadout",
  "videoMetricReadout",
  "frameSlider",
  "objectLabel",
  "objectId",
  "maskProviderSelect",
  "deviceSelect",
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
  "configPreview",
  "validateConfigButton",
  "startRunButton",
  "startMockRunButton",
  "saveConfigButton",
  "loadConfigInput",
  "jobSummary",
  "jobList",
  "runStatus",
  "selectedJobFacts",
  "cancelJobButton",
  "eventCount",
  "jobEventLog",
  "artifactCount",
  "artifactBrowser",
  "trackCount",
  "trackList",
  "correctionStatus",
  "correctionPersistenceMessage",
  "correctionTrackSelect",
  "correctionLabelInput",
  "relabelTrackButton",
  "correctionFrameStart",
  "correctionFrameEnd",
  "useCurrentFrameRangeButton",
  "mergeTracksButton",
  "splitTrackButton",
  "addObjectButton",
  "repairTrackButton",
  "mergeSelectionCount",
  "correctionPromptCount",
  "mergeSuggestionList",
  "correctionHistoryCount",
  "correctionHistory",
  "fallbackDiagnostics",
  "routeList",
]) {
  if (!index.includes(`id="${id}"`)) {
    throw new Error(`index.html is missing #${id}`);
  }
}

for (const route of [
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
  "/api/progress",
  "/api/artifacts",
]) {
  if (!script.includes(route)) {
    throw new Error(`app.js does not call ${route}`);
  }
}

for (const affordance of [
  "buildRunConfig",
  "validateRunConfigShape",
  "providerWarnings",
  "clientPointToVideoPoint",
  "mapClientPointToVideo",
  "containedVideoRect",
  "trace_one_object",
  "text_detector",
  "sam_auto_masks",
  "motion_foreground",
  "external_masks",
  "positive_point",
  "negative_point",
  "maskProviderSelect",
  "providerWarning",
  "native video pixels",
  "job-progress",
  "rasterOnlyReason",
  "fallbackDiagnostics",
  "trackVisibility",
  "buildReviewTracks",
  "trackFrameForDisplay",
  "startJobFromConfig",
  "CORRECTION_STATE_FORMAT",
  "buildCorrectionRequestFromPrompts",
  "normalizeCorrectionState",
  "applyCorrectionStateToTracks",
  "set_track_visibility",
  "set_export_inclusion",
  "relabel_track",
  "delete_track",
  "merge_tracks",
  "split_track",
  "add_object",
  "repair_track",
  "repair_provider_unavailable",
  "partial rerun unavailable",
  "Correction History",
  "Repair with prompts",
  "data-track-export",
  "data-track-merge",
  "Start mock job",
  "artifactBrowser",
  "jobEventLog",
  "selectedVideoId",
  "video-choice",
  "skip-link",
  "workspaceMain",
  "Local release candidate",
  "Object tracing workspace",
  "aria-keyshortcuts",
  "aria-current",
  "data-tooltip",
  "safeLocalContentUrl",
  "rel=\"noopener noreferrer\"",
  "cancelSelectedJob",
  "/api/jobs/{jobId}/cancel",
  "requestAnimationFrame",
  "validateConfigWithBackend",
  "renderFirstRunChecklist",
  "No-model smoke",
  "Optional models",
  "local/free",
  "configured, not runnable",
]) {
  if (!combined.includes(affordance)) {
    throw new Error(`UI shell is missing ${affordance}`);
  }
}

if (!configBuilder.includes("export function buildRunConfig") || !configBuilder.includes("export function clientPointToVideoPoint")) {
  throw new Error("config_builder.js must export the Phase 8 config builder and coordinate mapper");
}

const remotePattern = /https?:\/\//;
for (const [file, content] of contents) {
  if (remotePattern.test(content)) {
    throw new Error(`local UI shell must not load remote resources: ${file}`);
  }
}

console.log(
  JSON.stringify(
    {
      status: "ok",
      checkedFiles: files,
      mode: "dependency-free-static-ui",
    },
    null,
    2,
  ),
);
