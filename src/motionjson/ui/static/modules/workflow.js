import { MODEL_FREE_PRESETS } from "./provider_connections.js";

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const toInteger = (value, fallback = 0) => {
  const number = Number.parseInt(value, 10);
  return Number.isFinite(number) ? number : fallback;
};

const humanizeReviewCode = (value) =>
  String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim() || "review";

export const WORKFLOW_STEPS = [
  {
    id: "choose_goal",
    title: "Choose goal",
    label: "Goal",
    description: "Pick the kind of object tracing workflow before setup details appear.",
    nextHint: "Choose a tracing goal to continue.",
  },
  {
    id: "source_video",
    title: "Choose source",
    label: "Source",
    description: "Add a video or open an existing result. Guided mode creates a workspace automatically.",
    nextHint: "Add a video or existing result to continue.",
  },
  {
    id: "provider_settings",
    title: "Prepare model path",
    label: "Model",
    description: "Install, check, or select one compatible SAM engine for the selected workflow.",
    nextHint: "Choose one compatible model connection to continue.",
  },
  {
    id: "prompt_preview",
    title: "Define target and preflight",
    label: "Target",
    description: "Define the object or discovery mode, then confirm the truthful run plan.",
    nextHint: "Define the target object and confirm preflight before running.",
  },
  {
    id: "candidate_selection",
    title: "Review candidates",
    label: "Review",
    description: "Inspect the keyframe scan, rename the right objects, and choose only what should be tracked.",
    nextHint: "Choose the objects to track through the video.",
  },
  {
    id: "run_monitor",
    title: "Extraction cockpit",
    label: "Run",
    description: "Watch visual evidence, readable events, usage, health, and recovery actions while extraction runs.",
    nextHint: "Start a run before reviewing tracks and exporting.",
  },
  {
    id: "review_export",
    title: "Review, correct, export, reuse",
    label: "Review",
    description: "Validate produced objects, correct enough to export, package the layer, and copy reuse steps.",
    nextHint: "Run extraction before reviewing tracks and exporting.",
  },
];

export const JOURNEY_PHASES = [
  {
    id: "goal",
    label: "Goal",
    workflowStep: "choose_goal",
    question: "What am I trying to make?",
  },
  {
    id: "source",
    label: "Source",
    workflowStep: "source_video",
    question: "Which video am I extracting from?",
  },
  {
    id: "target",
    label: "Target",
    workflowStep: "prompt_preview",
    question: "What object should be traced?",
  },
  {
    id: "model",
    label: "Model",
    workflowStep: "provider_settings",
    question: "Can the recommended model path run?",
  },
  {
    id: "preflight",
    label: "Preflight",
    workflowStep: "prompt_preview",
    question: "What will happen if I press Run?",
  },
  {
    id: "run",
    label: "Run",
    workflowStep: "run_monitor",
    question: "What is happening, and is the result becoming useful?",
  },
  {
    id: "review",
    label: "Review",
    workflowStep: "review_export",
    question: "Which produced objects are valid?",
  },
  {
    id: "correct",
    label: "Correct",
    workflowStep: "review_export",
    question: "How do I fix enough to export?",
  },
  {
    id: "export",
    label: "Export",
    workflowStep: "review_export",
    question: "What am I exporting?",
  },
  {
    id: "reuse",
    label: "Reuse",
    workflowStep: "review_export",
    question: "How can the exported object layer be reused?",
  },
];

export const JOURNEY_PHASE_ORDER = JOURNEY_PHASES.map((phase) => phase.id);

export const WORKFLOW_PANEL_STEP_ALIASES = {
  choose_goal: ["choose_goal"],
  source_video: ["project_video", "source_video"],
  provider_settings: ["provider_settings"],
  prompt_preview: ["prompt_preview", "validate_run"],
  candidate_selection: ["review_candidates"],
  run_monitor: ["run_monitor"],
  review_export: ["correct_tracks", "export"],
};

export const WORKFLOW_FRAGMENT_STEP_ALIASES = {
  choose_goal: ["choose_goal"],
  source_video: ["source_video"],
  provider_settings: ["provider_settings"],
  prompt_preview: ["prompt_preview"],
  candidate_selection: ["review_candidates"],
  run_monitor: ["run_monitor"],
  review_export: ["correct_tracks", "export"],
};

export const SCREEN_STEPS = [
  { id: "start", label: "Goal", workflowSteps: ["choose_goal"] },
  { id: "video", label: "Source", workflowSteps: ["source_video"] },
  { id: "model", label: "Model", workflowSteps: ["provider_settings"] },
  { id: "prepare", label: "Target", workflowSteps: ["prompt_preview"] },
  { id: "select", label: "Review", workflowSteps: ["candidate_selection"] },
  { id: "run", label: "Run", workflowSteps: ["run_monitor"] },
  { id: "review", label: "Review", workflowSteps: ["review_export"] },
];

export function normalizeWorkflowStepId(value, fallback = "choose_goal") {
  const id = String(value || "").trim();
  return WORKFLOW_STEPS.some((step) => step.id === id) ? id : fallback;
}

export function normalizeJourneyPhaseId(value, fallback = "goal") {
  const id = String(value || "").trim();
  return JOURNEY_PHASE_ORDER.includes(id) ? id : fallback;
}

export function journeyPhaseIndex(phaseId) {
  return Math.max(0, JOURNEY_PHASE_ORDER.indexOf(normalizeJourneyPhaseId(phaseId)));
}

export function journeyPhaseForWorkflowStep(stepId, options = {}) {
  const normalized = normalizeWorkflowStepId(stepId);
  const activeJourneyPhase = normalizeJourneyPhaseId(options.activeJourneyPhase || "", "");
  const exportResultReady = Boolean(options.exportResultReady);
  const reviewExportSubscreen = String(options.reviewExportSubscreen || "");
  if (normalized === "choose_goal") return "goal";
  if (normalized === "source_video") return "source";
  if (normalized === "provider_settings") return "model";
  if (normalized === "prompt_preview") return activeJourneyPhase === "preflight" ? "preflight" : "target";
  if (normalized === "run_monitor") return "run";
  if (exportResultReady || activeJourneyPhase === "reuse") return "reuse";
  if (reviewExportSubscreen === "export" || activeJourneyPhase === "export") return "export";
  if (activeJourneyPhase === "correct") return "correct";
  return "review";
}

export function workflowStepIndex(stepId) {
  const normalized = normalizeWorkflowStepId(stepId);
  return Math.max(0, WORKFLOW_STEPS.findIndex((step) => step.id === normalized));
}

export function workflowNextStepId(stepId, direction = 1) {
  const index = workflowStepIndex(stepId);
  const nextIndex = clamp(index + (direction < 0 ? -1 : 1), 0, WORKFLOW_STEPS.length - 1);
  return WORKFLOW_STEPS[nextIndex].id;
}

export function workflowScreenForStep(stepId = "choose_goal") {
  const normalized = normalizeWorkflowStepId(stepId);
  return SCREEN_STEPS.find((screen) => screen.workflowSteps.includes(normalized))?.id || "setup";
}

export function workflowStepForScreen(screenId = "setup") {
  return SCREEN_STEPS.find((screen) => screen.id === screenId)?.workflowSteps[0] || "choose_goal";
}

export function goalRequiresModel(presetId = "trace_one_object") {
  return !MODEL_FREE_PRESETS.has(String(presetId || ""));
}

export function goalRequiresReviewExportFlow(presetId = "trace_one_object") {
  return presetId !== "review_existing";
}

export function isActiveJobStatus(status) {
  return /queued|running|pending|started|cancel_requested/.test(String(status || "").toLowerCase());
}

export function isFailedJobStatus(status) {
  return /failed|error|canceled|cancelled/.test(String(status || "").toLowerCase());
}

export function workflowRestoredStepFromSnapshot(snapshot = {}, requestedStep = "choose_goal") {
  const selectedPreset = snapshot.selectedPreset || "trace_one_object";
  const hasRunData = Boolean(snapshot.selectedJobId || toInteger(snapshot.candidateCount, 0) || toInteger(snapshot.trackCount, 0));
  if (selectedPreset === "review_existing") {
    return snapshot.selectedJobId ? "review_export" : "choose_goal";
  }
  if (selectedPreset === "pick_objects_from_frame") {
    const candidateCount = toInteger(snapshot.candidateCount, 0);
    const trackCount = toInteger(snapshot.trackCount, 0);
    const selectedJobStatus = String(snapshot.selectedJobStatus || "").toLowerCase();
    if (candidateCount > 0 && trackCount === 0 && !isActiveJobStatus(selectedJobStatus)) {
      if (workflowStepIndex(requestedStep) > workflowStepIndex("candidate_selection")) {
        return "candidate_selection";
      }
    }
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

export function workflowReadinessFromSnapshot(snapshot = {}) {
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
  const hasReviewablePartial = jobFailed && Boolean(snapshot.partialSuccess || snapshot.reviewableObjectCount || candidateCount || trackCount);
  const exportOk = Boolean(snapshot.exportOk);
  const requiresModel = goalRequiresModel(selectedPreset);
  const manualPromptRequired = selectedPreset === "trace_one_object";
  const fastFramePick = selectedPreset === "pick_objects_from_frame";
  const scanFrameConfirmed = fastFramePick ? snapshot.scanFrameConfirmed === true : true;
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
              : step("needs-action", selectedPreset === "review_existing" ? "Open an existing MotionJSON result to continue." : "Add a video or use the demo video to continue.", { complete: false }),
    provider_settings: !hasRegisteredVideo && selectedPreset !== "review_existing"
      ? step("needs-action", "Add a source video before preparing model setup.", { complete: false })
      : !requiresModel
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
      !hasRegisteredVideo && selectedPreset !== "review_existing"
        ? step("needs-action", "Add a source video before defining the target object.", { complete: false })
        : manualPromptRequired && requiresSam3Box && !hasBoxPrompt
        ? step("needs-action", "Draw one box around the object for SAM3 tracing.", { complete: false })
        : manualPromptRequired && !requiresSam3Box && !hasBoxPrompt && !hasPointPrompt
          ? step("needs-action", "Add at least one point or box prompt for this goal.", { complete: false })
          : hasJob && !jobFailed
          ? step(
              configBlocked ? "blocked" : configValid ? "ready" : "done",
              configBlocked ? "Run validation failed. Fix the generated config before retrying." : "Run started. MotionJSON will switch to review when results are ready.",
            )
            : fastFramePick && !scanFrameConfirmed
              ? step("needs-action", "Choose the exact frame to scan.", { complete: false })
              : step(
                "done",
                fastFramePick
                  ? "This workflow is ready to scan one keyframe."
                  : promptCount
                    ? `${promptCount} prompt mark${promptCount === 1 ? "" : "s"} ready.`
                    : "This workflow is ready to run without manual prompts.",
              ),
    candidate_selection:
      !fastFramePick
        ? step("done", "This workflow does not use a separate selection gate.")
        : candidateCount > 0 && trackCount === 0
          ? step("needs-action", "Inspect the keyframe scan and track only the objects you keep.", { complete: false })
          : trackCount > 0
            ? step("done", "Selected objects have been sent to full tracking.")
            : jobRunning
              ? step("needs-action", "The keyframe scan is still running.", { tone: "is-neutral", complete: false })
              : step("needs-action", "Run the keyframe scan before selecting objects.", { complete: false }),
    run_monitor: jobFailed && !hasReviewablePartial
      ? step("blocked", "Run failed or was canceled. Open logs, change setup, run again, or choose a different model.", { complete: false })
      : jobRunning
        ? step("needs-action", "Run is in progress. Watch progress and logs before review.", { tone: "is-neutral", complete: false })
        : jobSucceeded || trackCount > 0 || (hasRunData && !fastFramePick)
          ? step("done", hasReviewablePartial ? "Partial objects are reviewable. Continue to review before retrying failed frames." : "Run finished. Continue to review and export.")
          : step("needs-action", fastFramePick ? "Track selected objects before review." : "Start a run before review.", { complete: false }),
    review_export:
      (jobSucceeded || hasRunData) && (!jobFailed || hasReviewablePartial)
        ? exportOk
          ? step("done", "Reviewed objects exported successfully.")
          : step(
              correctionCount || hasReviewablePartial ? "ready" : "done",
              trackCount ? `${trackCount} reviewed track${trackCount === 1 ? "" : "s"} ready for export.` : `${candidateCount} candidate${candidateCount === 1 ? "" : "s"} ready to review.`,
            )
        : step("needs-action", selectedPreset === "review_existing" ? "Open an existing result before reviewing and exporting." : "Run extraction before reviewing tracks and exporting.", { complete: false }),
  };
}

export function journeyReadinessFromSnapshot(snapshot = {}, readiness = workflowReadinessFromSnapshot(snapshot)) {
  return {
    goal: readiness.choose_goal,
    source: readiness.source_video,
    target: readiness.prompt_preview,
    model: readiness.provider_settings,
    preflight: {
      status: snapshot.backendValidated ? "done" : readiness.prompt_preview?.status || "needs-action",
      complete: Boolean(snapshot.backendValidated || snapshot.selectedJobId),
      message: snapshot.backendValidated ? "Preflight validation passed." : "Confirm what extraction will run before starting.",
      tone: snapshot.backendValidated ? "is-ready" : "is-warn",
    },
    run: readiness.run_monitor,
    review: readiness.review_export,
    correct: {
      status: snapshot.correctionCount ? "done" : snapshot.trackCount ? "ready" : "needs-action",
      complete: Boolean(snapshot.correctionCount),
      message: snapshot.trackCount ? "Correction tools are available for reviewed tracks." : "Run extraction before correcting tracks.",
      tone: snapshot.correctionCount ? "is-ready" : snapshot.trackCount ? "is-warn" : "is-muted",
    },
    export: {
      status: snapshot.exportOk ? "done" : snapshot.exportIncludedCount ? "ready" : "needs-action",
      complete: Boolean(snapshot.exportOk),
      message: snapshot.exportOk ? "MotionJSON package is ready to write." : snapshot.exportIncludedCount ? "Validate reviewed objects before export." : "Review at least one object before export.",
      tone: snapshot.exportOk ? "is-ready" : snapshot.exportIncludedCount ? "is-warn" : "is-muted",
    },
    reuse: {
      status: snapshot.exportResultReady ? "done" : snapshot.exportOk ? "ready" : "needs-action",
      complete: Boolean(snapshot.exportResultReady),
      message: snapshot.exportResultReady ? "Reusable object layer exported with handoff instructions." : snapshot.exportOk ? "Export MotionJSON before reuse handoff." : "Validate and export before reuse.",
      tone: snapshot.exportResultReady ? "is-ready" : snapshot.exportOk ? "is-warn" : "is-muted",
    },
  };
}

export function workflowSummaryCardsFromSnapshot(snapshot = {}, activeStep = "choose_goal") {
  const activeIndex = workflowStepIndex(activeStep);
  if (activeIndex <= 0) return [];
  const readiness = workflowReadinessFromSnapshot(snapshot);
  const promptCount = toInteger(snapshot.promptCount, 0) + toInteger(snapshot.strokeCount, 0);
  const candidateCount = toInteger(snapshot.candidateCount, 0);
  const trackCount = toInteger(snapshot.trackCount, 0);
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
    prompt_preview: snapshot.selectedJobStatus
      ? humanizeReviewCode(snapshot.selectedJobStatus)
      : promptCount
        ? `${promptCount} prompt mark${promptCount === 1 ? "" : "s"}`
        : "Ready to run",
    candidate_selection: candidateCount ? `${candidateCount} candidate${candidateCount === 1 ? "" : "s"}` : "No candidates yet",
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

export function workflowJobStatusFromSnapshot(snapshot = {}, options = {}) {
  const lifecycle = snapshot.job && typeof options.normalizeJobLifecycle === "function" ? options.normalizeJobLifecycle(snapshot.job) : null;
  const status = String(snapshot.selectedJobStatus || lifecycle?.status || "").toLowerCase();
  const rawStatus = String(snapshot.selectedJobRawStatus || lifecycle?.rawStatus || status).toLowerCase();
  const failureReason = String(snapshot.selectedJobFailureReason || lifecycle?.failure?.reasonCode || "").toLowerCase();
  const hasJob = Boolean(snapshot.selectedJobId || snapshot.hasSelectedJob || lifecycle?.id || status);
  return {
    hasJob,
    id: snapshot.selectedJobId || lifecycle?.id || "",
    lifecycle,
    status,
    rawStatus,
    failureReason,
    running: isActiveJobStatus(status) || isActiveJobStatus(rawStatus),
    failed: isFailedJobStatus(status) || isFailedJobStatus(rawStatus),
    succeeded: /succeeded|completed|complete/.test(status),
  };
}

export function workflowModelSetupStatusFromSnapshot(snapshot = {}) {
  const selectedPreset = snapshot.selectedPreset || "trace_one_object";
  const requiresModel = goalRequiresModel(selectedPreset);
  const modelSetupState = snapshot.modelSetupState || {};
  const fallbackStatus = !requiresModel
    ? "ready"
    : snapshot.providerSummaryTone === "ready"
      ? "ready"
      : snapshot.providerBlocked
        ? "blocked"
        : "not_configured";
  const status = String(snapshot.modelSetupStatus || modelSetupState.status || fallbackStatus);
  const action = snapshot.modelSetupAction || {};
  const ready = !requiresModel || status === "ready";
  return {
    requiresModel,
    status,
    ready,
    message:
      modelSetupState.message ||
      snapshot.modelSetupMessage ||
      snapshot.providerSummaryMessage ||
      snapshot.providerWarning ||
      (requiresModel ? "Choose one compatible model connection before continuing." : "No model setup is needed for this workflow."),
    action: {
      id: action.id || (ready ? "continue-to-prepare" : snapshot.modelSetupActionId || "install"),
      label: action.label || (ready ? "Continue to target" : snapshot.modelSetupActionLabel || "Save setup"),
      primary: action.primary !== false,
    },
    hasForm: snapshot.hasModelSetupForm !== false,
    hasConnection: Boolean(snapshot.modelSetupConnectionId || snapshot.providerConnectionId || snapshot.providerId),
  };
}
