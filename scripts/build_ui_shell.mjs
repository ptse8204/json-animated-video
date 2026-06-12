import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const root = process.cwd();
const staticDir = join(root, "src", "motionjson", "ui", "static");
const topLevelFiles = ["index.html", "app.css", "app.js", "config_builder.js", "ui_selectors.js", "favicon.svg"];
const moduleFiles = await collectJsModules("modules");
const files = [...topLevelFiles, ...moduleFiles];
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
const uiSelectors = contents.get("ui_selectors.js");
const combined = [...contents.values()].join("\n");

async function collectJsModules(prefix) {
  const rootDir = join(staticDir, prefix);
  let entries;
  try {
    entries = await readdir(rootDir, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
  const files = [];
  for (const entry of entries) {
    const relPath = `${prefix}/${entry.name}`;
    if (entry.isDirectory()) {
      files.push(...(await collectJsModules(relPath)));
    } else if (entry.isFile() && entry.name.endsWith(".js")) {
      files.push(relPath);
    }
  }
  return files.sort();
}

for (const reference of ["/ui/app.css", "/ui/app.js", "/ui/favicon.svg"]) {
  if (!index.includes(reference)) {
    throw new Error(`index.html does not reference ${reference}`);
  }
}

for (const id of [
  "healthStatus",
  "firstRunChecklist",
  "apiStatus",
  "workspaceSidebar",
  "sidebarToggle",
  "sidebarNavigationContent",
  "collapsedGoalLabel",
  "diagnosticsSummary",
  "diagnosticsRail",
  "railCloseButton",
  "postRunGuide",
  "postRunGuideStatus",
  "postRunGuideList",
  "workflowController",
  "workflowStepper",
  "workflowTitle",
  "workflowDescription",
  "workflowStatus",
  "workflowStepSummary",
  "workflowBackButton",
  "workflowPrimaryButton",
  "workflowFooterHint",
  "workflowFooterReason",
  "providerWarning",
  "runPlanAlert",
  "keyframeScanChooser",
  "useCurrentFrameForScanButton",
  "setupPanelTitle",
  "wizardPanelTitle",
  "configPanelTitle",
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
  "timelineMarkerTrack",
  "timelineSummary",
  "useSuggestedKeyframesButton",
  "timelineMarkerList",
  "objectLabel",
  "objectId",
  "maskProviderSelect",
  "deviceSelect",
  "guidedQualityControls",
  "maskDetailNote",
  "runtimeDeviceNote",
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
  "runMonitorStatus",
  "runMonitorSummary",
  "runStatus",
  "selectedJobFacts",
  "cancelJobButton",
  "runLogsDisclosure",
  "eventCount",
  "jobEventLog",
  "reviewFlowStatus",
  "reviewStatusSummary",
  "fallbackDiagnosticsDisclosure",
  "artifactCount",
  "artifactBrowser",
  "exportStatusSummary",
  "exportArtifactsDisclosure",
  "correctionStatusSummary",
  "libraryStatus",
  "librarySearchForm",
  "librarySearch",
  "libraryTagFilter",
  "libraryArtifactSelect",
  "libraryAssetTitle",
  "libraryAssetTags",
  "saveLibraryAssetButton",
  "libraryCollectionForm",
  "libraryCollectionTitle",
  "libraryCollectionSelect",
  "addLibraryAssetToCollectionButton",
  "libraryPackForm",
  "libraryPackTitle",
  "libraryError",
  "libraryArtifactNotice",
  "libraryAssetList",
  "libraryCollectionList",
  "libraryPackList",
  "candidateSummaryStatus",
  "candidateSummaryList",
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
  "workspaceSummary",
  "workspaceRecent",
  "workspacePreferencesForm",
  "preferenceDefaultGoal",
  "preferenceExportPreset",
  "commercialReadinessPanel",
  "commercialReadinessStatus",
  "commercialReadinessSummary",
  "commercialReadinessList",
  "routeList",
]) {
  if (!index.includes(`id="${id}"`)) {
    throw new Error(`index.html is missing #${id}`);
  }
}

for (const route of [
  "/api/health",
  "/api/workspace",
  "/api/preferences",
  "/api/commercial-readiness",
  "/api/capabilities",
  "/api/projects",
  "/api/run-config/defaults",
  "/api/run-config/validate",
  "/api/videos",
  "/api/videos/upload",
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
  "/api/library/assets",
  "/api/library/assets/{libraryAssetId}",
  "/api/library/collections",
  "/api/library/collections/{collectionId}/assets",
  "/api/library/packs",
  "/api/projects/{projectId}/library-assets",
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
  "selectedTrackDetail",
  "normalizePolygonPoints",
  "review_state_manifest",
  "Start debug mock job",
  "workflowSummaryCardsFromSnapshot",
  "postRunWorkflowSummaryFromSnapshot",
  "diagnosticNeedsImmediateAttention",
  "statusCardMarkup",
  "Review before export",
  "Logs and events",
  "Artifacts and exports",
  "Generated artifacts",
  "View generated JSON",
  "artifactBrowser",
  "candidateSummary",
  "renderCandidateSummary",
  "candidateSummaryList",
  "candidate-row",
  "timelineMarkersForDisplay",
  "review_timeline",
  "data-timeline-frame",
  "Use suggestions",
  "jobEventLog",
  "selectedVideoId",
  "video-choice",
  "skip-link",
  "workspaceMain",
  "Collapse menu",
  "Main workflow",
  "Advanced tasks",
  "data-workflow-step",
  "data-workflow-panel",
  "data-workflow-fragment",
  "workflowReadinessFromSnapshot",
  "workflowNextStepId",
  "Platform release candidate",
  "Object tracing workspace",
  "aria-keyshortcuts",
  "inert = collapsed",
  "aria-current",
  "data-tooltip",
  "data-quality-preset",
  "data-device-preset",
  "Mask detail",
  "Runtime speed",
  "Refined",
  "safeLocalContentUrl",
  "rel=\"noopener noreferrer\"",
  "cancelSelectedJob",
  "/api/jobs/{jobId}/cancel",
  "requestAnimationFrame",
  "validateConfigWithBackend",
  "renderFirstRunChecklist",
  "Debug smoke",
  "SAM models",
  "runtime/free",
  "configured, not runnable",
  "Asset Library",
  "LIBRARY_SAVEABLE_ARTIFACT_KINDS",
  "librarySourceArtifacts",
  "libraryArtifactIsSaveable",
  "renderAssetLibraryPanel",
  "saveSelectedLibraryAsset",
  "selectedLibraryCollectionId",
  "selectedLibraryArtifactId",
  "createCreatorPackFromCollection",
  "motion_sticker",
  "Creator-approved packs",
  "object_layer_pack",
  "exportValidationMessageRows",
]) {
  if (!combined.includes(affordance)) {
    throw new Error(`UI shell is missing ${affordance}`);
  }
}

if (!configBuilder.includes("export function buildRunConfig") || !configBuilder.includes("export function clientPointToVideoPoint")) {
  throw new Error("config_builder.js must export the Phase 8 config builder and coordinate mapper");
}

for (const helper of [
  "export const OPTION_HELP_TEXT",
  "export function adaptiveRunDefaultsFromSnapshot",
  "export function projectShellStateFromSnapshot",
  "export function reviewExportScreenStateFromSnapshot",
]) {
  if (!uiSelectors.includes(helper)) {
    throw new Error(`ui_selectors.js must expose ${helper}`);
  }
}

if (!script.includes("from \"./ui_selectors.js\"")) {
  throw new Error("app.js must import the dependency-free UI selectors");
}

for (const moduleImport of [
  "from \"./modules/api_client.js\"",
  "from \"./modules/provider_connections.js\"",
  "from \"./modules/state_store.js\"",
  "from \"./modules/workflow.js\"",
]) {
  if (!script.includes(moduleImport)) {
    throw new Error(`app.js must import ${moduleImport}`);
  }
}

for (const testId of [
  "local-ui-shell",
  "workflow-goal-panel",
  "workflow-stepper",
  "model-setup-panel",
  "model-setup-choices",
  "video-file-input",
  "register-video-path",
  "start-run",
  "generate-model-plan",
  "validate-model-plan",
  "confirm-model-plan",
  "job-event-log",
  "track-list",
  "correction-track-select",
  "relabel-track",
  "merge-tracks",
  "split-track",
  "add-object",
  "repair-track",
  "export-motionjson",
  "provider-settings-list",
]) {
  if (!index.includes(`data-testid="${testId}"`)) {
    throw new Error(`index.html is missing data-testid="${testId}"`);
  }
}

for (const phase of ["goal", "source", "target", "model", "preflight", "run", "review", "correct", "export", "reuse"]) {
  if (!index.includes(`data-journey-phase="${phase}"`)) {
    throw new Error(`index.html is missing workflow journey phase "${phase}"`);
  }
}

if (!index.includes('id="workflowStepper"') || !index.includes("data-testid=\"workflow-stepper\"") || !index.includes("hidden")) {
  throw new Error("workflow stepper must remain an accessibility-only compatibility control");
}

const remotePattern = /https?:\/\//;
for (const [file, content] of contents) {
  const checkedContent = content.replaceAll("http://www.w3.org/2000/svg", "");
  if (remotePattern.test(checkedContent)) {
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
