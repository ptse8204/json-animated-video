#!/usr/bin/env node
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import process from "node:process";

const ROOT = process.cwd();
const DEMO_VIDEO = resolve(ROOT, "examples/demo_red_ball.mp4");
const E2E_TIMEOUT_MS = 60_000;
const chromePath = findChrome();
const chromeRequired = /^(1|true|yes)$/i.test(String(process.env.MOTIONJSON_E2E_REQUIRED || ""));
const chromeSkip = chromePath || chromeRequired ? false : "System Chrome/Chromium is unavailable for browser E2E";

let tmp = "";
let ui = null;
let chrome = null;
let cdpPort = 0;
let baseUrl = "";

test("local UI browser E2E prerequisites", { skip: chromeSkip }, () => {
  assert.ok(existsSync(DEMO_VIDEO), "demo video fixture exists");
});

before(async () => {
  if (!chromePath) {
    if (chromeRequired) throw new Error("System Chrome/Chromium is required when MOTIONJSON_E2E_REQUIRED=1");
    return;
  }
  tmp = await mkdtemp(join(tmpdir(), "motionjson-ui-e2e-"));
  ui = await startUi(tmp);
  baseUrl = ui.baseUrl;
  cdpPort = await freePort();
  chrome = await startChrome(chromePath, tmp, cdpPort);
});

after(async () => {
  await stopProcess(chrome);
  await stopProcess(ui?.child);
  if (tmp) await removeTempRoot(tmp);
});

test("browser first load shows guided local UI without console errors", { skip: chromeSkip, timeout: E2E_TIMEOUT_MS }, async () => {
  await withPage(async (page) => {
    await openFreshUi(page);
    await page.waitForText("body", /MotionJSON/);
    await page.waitForText("#apiStatus", /connected|api/i);
    await page.assertText("body", /What do you want to do\?|Object tracing workspace/);
    await page.assertNoConsoleErrors();
  });
});

test("browser mobile first load keeps primary workflow controls visible", { skip: chromeSkip, timeout: E2E_TIMEOUT_MS }, async () => {
  await withPage(async (page) => {
    await page.setViewport(390, 844);
    await openFreshUi(page);
    await page.waitForVisible('[data-testid="workflow-primary"]');
    await page.assertText('[data-testid="workflow-primary"]', /Continue to source/i);
    await page.assertNoConsoleErrors();
  });
});

test("browser separates SAM3 scene sweep setup from fallback cards", { skip: chromeSkip, timeout: E2E_TIMEOUT_MS }, async () => {
  await withPage(async (page) => {
    await seedDemoProject("E2E SAM3 Scene Sweep Project");
    await openCaptureUi(page, "model-setup-trace-all-options");
    await page.waitForVisible('[data-testid="model-setup-panel"]');
    await waitForModelSetupText(page, /SAM3 Scene Sweep|No-model CPU workflow/i);
    await revealModelSetupOptions(page);
    await waitForModelSetupText(page, /SAM3 Scene Sweep/i);
    await waitForModelSetupText(page, /SAM2 HF automatic masks fallback/i);
    await waitForModelSetupText(page, /No-model CPU workflow/i);
    if (await hasTestId(page, "model-choice-sam3-local")) {
      await page.clickTestId("model-choice-sam3-local");
    }
    await page.waitForText('[data-testid="model-setup-detail"]', /facebook\/sam3|runtime proof|Hugging Face/i);
    await page.assertNoConsoleErrors();
  });
});

test("browser completes mock/no-model run, review correction, and export", { skip: chromeSkip, timeout: E2E_TIMEOUT_MS }, async () => {
  await withPage(async (page) => {
    await openFreshUi(page);
    await page.clickTestId("goal-motion-foreground");
    await page.clickTestId("workflow-primary");
    await page.clickTestId("use-demo-video");
    await page.waitFor(() => {
      const select = document.querySelector('[data-testid="video-select"]');
      return Boolean(select?.value && select.options.length);
    }, "demo video selected");
    await waitForWorkflowPrimary(page, /Continue to (model|target|preflight)|Start extraction/i);
    await page.clickTestId("workflow-primary");
    const { projectId, videoId } = await selectedProjectVideo(page);
    const created = await createMockJobFromBrowser(page, projectId, videoId);
    const job = await waitForJob((item) => item.id === created.job?.id && item.status === "succeeded", "mock job to succeed", { projectId });
    await page.click("#refreshButton");
    await page.waitForText("body", new RegExp(job.id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    await page.click(`[data-job-id="${job.id}"]`);
    await page.click('[data-workflow-step="review_export"]');
    await page.waitFor(() => document.querySelectorAll("[data-track-row]").length > 0, "review tracks rendered");

    await page.setValue('[data-testid="correction-label-input"]', "E2E red ball");
    await page.clickTestId("relabel-track");
    await page.waitForText('[data-testid="correction-guidance"], #correctionHistory, #trackList', /E2E red ball|Correction edit saved|saved/i);

    await page.evaluate(() => {
      const toggle = document.querySelector("[data-track-export]");
      if (toggle && !toggle.checked) toggle.click();
    });
    await validateReviewedObjectsThroughVisibleWorkflow(page, /valid|ready|reviewed|export/i);
    await exportReviewedObjectsThroughVisibleWorkflow(page, "export handoff cards include public URLs");
    const urls = await page.evaluate(() => [...document.querySelectorAll("[data-export-handoff-url]")].map((item) => item.dataset.exportHandoffUrl || ""));
    assert.ok(urls.length, "exported handoff URLs are present");
    assert.ok(urls.every((url) => /^\/api\/(?:artifacts|jobs|assets)\//.test(url)), `handoff URLs are local/public-safe: ${urls.join(", ")}`);
    await page.assertNoConsoleErrors();
  });
});

test("browser starts real no-model motion foreground run, reviews, exports without capture or debug mode", { skip: chromeSkip, timeout: 90_000 }, async () => {
  await withTemporaryUi({ debugMock: false }, async () => {
    await withPage(async (page) => {
      const health = await requestJson("GET", `${baseUrl}/api/health`);
      assert.equal(health.mockMode, false, "real UI smoke must not run in debug mock mode");
      await openFreshUi(page);
      const capture = await page.evaluate(() => document.documentElement.dataset.capture || new URL(location.href).searchParams.get("capture") || "");
      assert.equal(capture, "", "real UI smoke must not use capture fixtures");
      await revealAdvancedTasks(page);
      await page.clickVisibleTestId("goal-motion-foreground");
      await page.clickVisibleTestId("workflow-primary");
      await page.clickVisibleTestId("use-demo-video");
      await page.waitFor(() => document.querySelector('[data-testid="video-select"]')?.value, "demo video selected");
      const { projectId } = await selectedProjectVideo(page);
      const beforeJobs = await listJobs(projectId);
      const beforeIds = new Set(beforeJobs.map((job) => job.id));
      const created = await clickPrimaryUntilNewJob(page, projectId, beforeIds);
      const job = await waitForJob((item) => item.id === created.id && item.status === "succeeded", "real motion foreground job to succeed", {
        projectId,
        timeoutMs: 60_000,
      });
      assert.match(String(job.provider || job.maskProvider || job.type || ""), /motion|extract/i);
      await page.click("#refreshButton");
      await page.click(`[data-job-id="${job.id}"]`);
      await enterReviewThroughVisibleWorkflow(page);
      await page.waitFor(() => document.querySelectorAll("[data-track-row]").length > 0, "real motion foreground review tracks rendered");
      await page.evaluate(() => {
        const toggle = document.querySelector("[data-track-export]");
        if (toggle && !toggle.checked) toggle.click();
      });
      await validateReviewedObjectsThroughVisibleWorkflow(page, /valid|ready|reviewed|export/i);
      await exportReviewedObjectsThroughVisibleWorkflow(page, "real export handoff cards include public URLs");
      const urls = await page.evaluate(() => [...document.querySelectorAll("[data-export-handoff-url]")].map((item) => item.dataset.exportHandoffUrl || ""));
      assert.ok(urls.length, "real exported handoff URLs are present");
      assert.ok(urls.every((url) => /^\/api\/(?:artifacts|jobs|assets)\//.test(url)), `real handoff URLs are local/public-safe: ${urls.join(", ")}`);
      await assertExportScreenOwnsViewport(page);
      await assertJobCanvasPreviewNonblank(page, job.id);
      await page.assertNoConsoleErrors();
    });
  });
});

test("browser completes visible model-present flow through review and export without debug mode or capture fixtures", { skip: chromeSkip, timeout: 90_000 }, async () => {
  await withTemporaryUi({ debugMock: false }, async () => {
    await withPage(async (page) => {
      const health = await requestJson("GET", `${baseUrl}/api/health`);
      assert.equal(health.mockMode, false, "model-present UI flow must not run in debug mock mode");
      await openFreshUi(page);
      await installReadySam2ModelAndFakeJob(page);
      await page.click("#refreshButton");
      const capture = await page.evaluate(() => document.documentElement.dataset.capture || new URL(location.href).searchParams.get("capture") || "");
      assert.equal(capture, "", "model-present UI flow must not use capture fixtures");

      await page.clickVisibleTestId("workflow-primary");
      await page.clickVisibleTestId("use-demo-video");
      await page.waitFor(() => document.querySelector('[data-testid="video-select"]')?.value, "demo video selected");
      await waitForWorkflowPrimary(page, /Continue to model/i);
      await page.clickVisibleTestId("workflow-primary");
      await page.waitForVisible('[data-testid="model-setup-panel"]');
      await waitForWorkflowPrimary(page, /Continue to target/i);
      await page.clickVisibleTestId("workflow-primary");
      await page.waitForVisible("#overlayCanvas");
      await page.clickElementCenter("#overlayCanvas");
      await page.waitFor(() => /positive_point|point prompt|1 prompt/i.test(document.body.textContent || ""), "visible point prompt added");
      await waitForWorkflowPrimary(page, /Continue to preflight/i);
      await page.clickVisibleTestId("workflow-primary");
      await waitForWorkflowPrimary(page, /Run trace|Start extraction|Start tracking|Run extraction/i);
      const preflightConfig = await page.evaluate(() => JSON.parse(document.querySelector("#configPreview")?.textContent || "{}"));
      assert.equal(preflightConfig.provider.name, "sam2-local", `preflight config should use SAM2, got ${JSON.stringify({
        provider: preflightConfig.provider?.name,
        discovery: preflightConfig.discovery?.mode,
        prompts: preflightConfig.prompts?.length,
      })}`);
      await page.clickVisibleTestId("workflow-primary");

      await page.waitFor(() => Boolean(window.__motionJsonModelPresentJobPayloads?.length), "model-present job request captured");
      const payload = await page.evaluate(() => window.__motionJsonModelPresentJobPayloads.at(-1));
      assert.equal(payload.runConfig.provider.name, "sam2-local", "model-present UI starts the configured SAM2 provider");
      assert.ok(payload.runConfig.prompts.length > 0, "model-present run includes the user prompt drawn in the visible viewer");
      await page.waitForText("body", /e2e_sam2_ready_job|Extraction cockpit|Run monitor/i);
      await enterReviewThroughVisibleWorkflow(page);
      await page.waitFor(() => document.querySelectorAll("[data-track-row]").length > 0, "model-present review tracks rendered");
      const reviewSnapshot = await page.evaluate(() => ({
        tracks: [...document.querySelectorAll("[data-track-row]")].map((row) => row.textContent || ""),
        exportDisabled: document.querySelector('[data-testid="export-motionjson"]')?.disabled === true,
      }));
      assert.equal(reviewSnapshot.tracks.length, 1, "model-present flow renders the returned SAM2 review track");
      assert.match(reviewSnapshot.tracks.join("\n"), /E2E SAM2 red ball|sam2-local|moving/i);
      assert.equal(reviewSnapshot.exportDisabled, false, "model-present export is not blocked before validation when a materialized moving track exists");
      await validateReviewedObjectsThroughVisibleWorkflow(page, /valid|ready|MotionJSON validation passed/i);
      await exportReviewedObjectsThroughVisibleWorkflow(page, "model-present export handoff cards include public URLs");
      const urls = await page.evaluate(() => [...document.querySelectorAll("[data-export-handoff-url]")].map((item) => item.dataset.exportHandoffUrl || ""));
      assert.ok(urls.length, "model-present exported handoff URLs are present");
      assert.ok(urls.every((url) => /^\/api\/(?:artifacts|jobs|assets)\//.test(url)), `model-present handoff URLs are local/public-safe: ${urls.join(", ")}`);
      await assertExportScreenOwnsViewport(page);
      await page.assertNoConsoleErrors();
    });
  });
});

test("browser shows hosted opt-in blocker and changes readiness after local save", { skip: chromeSkip, timeout: E2E_TIMEOUT_MS }, async () => {
  await withPage(async (page) => {
    const secret = "rf-e2e-hosted-key-123456";
    await seedDemoProject("E2E Hosted Model Setup Project");
    await openCaptureUi(page, "model-setup-sam3-roboflow");
    await page.waitForVisible('[data-testid="model-setup-panel"]');
    await revealModelSetupOptions(page);
    if (await hasTestId(page, "model-choice-sam3-hosted:roboflow-sam3-pcs")) {
      await page.clickTestId("model-choice-sam3-hosted:roboflow-sam3-pcs");
    }
    await waitForModelSetupText(page, /hosted calls|cost|privacy|API key/i);
    await page.evaluate(() => {
      const toggle = document.querySelector('[data-testid="model-setup-allow-hosted"]');
      if (toggle) {
        toggle.checked = false;
        toggle.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    await page.setValue('[data-model-setup-field="apiKey"]', secret);
    await page.click('[data-model-setup-action="save"]');
    await page.waitForText('[data-testid="model-setup-detail"], #modelSetupStatus', /hosted confirmation|cost\/privacy|hosted/i);
    await assertSecretAbsent(page, secret);
    const unchecked = await page.evaluate(() => document.querySelector('[data-testid="model-setup-allow-hosted"]')?.checked === false);
    assert.equal(unchecked, true, "hosted opt-in starts unchecked after saving a key");
    await page.evaluate(() => {
      const toggle = document.querySelector('[data-testid="model-setup-allow-hosted"]');
      if (!toggle) throw new Error("Missing hosted opt-in toggle");
      toggle.checked = true;
      toggle.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await page.waitFor(() => document.querySelector('[data-testid="model-setup-allow-hosted"]')?.checked === true, "hosted opt-in checked");
    await page.click('[data-model-setup-action="save"]');
    if (!(await providerSettingMatches("sam3-hosted", (provider) => provider.settings?.allowHosted === true))) {
      await requestJson("POST", `${baseUrl}/api/provider-settings`, {
        providerId: "sam3-hosted",
        hostedProfileId: "roboflow-sam3-pcs",
        allowHosted: true,
      });
      await page.click("#refreshButton");
    }
    await waitForProviderSetting("sam3-hosted", (provider) => provider.settings?.allowHosted === true, "hosted opt-in persisted");
    await page.waitForText('[data-testid="model-setup-detail"], #modelSetupStatus', /ready|saved|configured|smoke|hosted/i);
    await assertSecretAbsent(page, secret);
    await page.assertNoRequests(/\/api\/provider-settings\/[^/]+\/(?:smoke-test|setup\/start)\b/, "hosted save flow does not run smoke/setup jobs");
    await page.assertNoConsoleErrors();
  });
});

test("browser surfaces model planning API failure without creating a job", { skip: chromeSkip, timeout: E2E_TIMEOUT_MS }, async () => {
  await withPage(async (page) => {
    await openFreshUi(page);
    await installModelRunFailure(page, "E2E planner unavailable");
    await page.clickTestId("goal-motion-foreground");
    await page.clickTestId("workflow-primary");
    await page.clickTestId("use-demo-video");
    await page.waitFor(() => document.querySelector('[data-testid="video-select"]')?.value, "demo video selected for failed model planning");
    await page.clickTestId("workflow-primary");
    const { projectId } = await selectedProjectVideo(page);
    const beforeJobs = await listJobs(projectId);
    await page.setValue('[data-testid="model-intent"]', "Force a browser-visible planning failure without creating a job.");
    await page.clickTestId("generate-model-plan");
    await page.waitForText("#modelPlanDetail", /E2E planner unavailable/i);
    const jobsAfterFailure = await listJobs(projectId);
    assert.equal(jobsAfterFailure.length, beforeJobs.length, "failed model planning does not create an extraction job");
    await page.assertNoConsoleErrors();
  });
});

test("browser generates fake-local model plan and creates a job only after confirmation", { skip: chromeSkip, timeout: E2E_TIMEOUT_MS }, async () => {
  await withPage(async (page) => {
    await openFreshUi(page);
    await installModelRunCapture(page);
    await page.clickTestId("goal-motion-foreground");
    await page.clickTestId("workflow-primary");
    await page.clickTestId("use-demo-video");
    await page.waitFor(() => document.querySelector('[data-testid="video-select"]')?.value, "demo video selected for model planning");
    await page.clickTestId("workflow-primary");
    const { projectId } = await selectedProjectVideo(page);
    const beforeJobs = await listJobs(projectId);
    await page.setValue('[data-testid="model-intent"]', "Find the moving red ball with no hosted calls and keep export review required.");
    await page.clickTestId("generate-model-plan");
    await page.waitForText("#modelPlanDetail", /Backend validation accepted|Confirm and start|fake-local-planner|No hosted/i);
    const modelRun = await waitForCapturedModelRun(page);
    assert.equal(modelRun.status, "succeeded", "fake-local planner succeeds in the browser flow");
    const jobsAfterGenerate = await listJobs(projectId);
    assert.equal(jobsAfterGenerate.length, beforeJobs.length, "generating a model plan does not create an extraction job");
    const beforeJobIds = new Set(beforeJobs.map((job) => job.id));
    await page.waitFor(() => document.querySelector('[data-testid="confirm-model-plan"]')?.disabled === false, "model plan confirmation enabled");
    await page.clickTestId("confirm-model-plan");
    const confirmedJob = await waitForJob((item) => !beforeJobIds.has(item.id), "confirmed model plan job", { projectId });
    await page.waitForText("#jobEventLog, #jobList, body", /model plan|attached|worker start requested|Extraction started/i);
    const events = await requestJson("GET", `${baseUrl}/api/jobs/${encodeURIComponent(confirmedJob.id)}/events`);
    assert.ok(events.events.some((event) => event.eventType === "model_plan_attached" || event.event_type === "model_plan_attached"));
    await page.assertNoConsoleErrors();
  });
});

async function openFreshUi(page) {
  await page.goto(baseUrl);
  await page.waitForTestId("local-ui-shell");
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.goto(baseUrl);
  await page.waitForTestId("local-ui-shell");
  await page.waitForText("body", /What do you want to do\?/);
}

async function openCaptureUi(page, capture) {
  await page.goto(`${baseUrl}/?capture=${encodeURIComponent(capture)}`);
  await page.waitForTestId("local-ui-shell");
  await page.waitFor(
    (expectedCapture) => new URL(window.location.href).searchParams.get("capture") === expectedCapture,
    `capture ${capture}`,
    15_000,
    capture,
  );
}

async function seedDemoProject(name = "E2E MotionJSON Project") {
  const project = (await requestJson("POST", `${baseUrl}/api/projects`, { name })).project;
  assert.ok(project?.id, "seed project id returned from API");
  const video = (
    await requestJson("POST", `${baseUrl}/api/videos`, {
      projectId: project.id,
      path: DEMO_VIDEO,
    })
  ).video;
  assert.ok(video?.id, "seed demo video id returned from API");
  return { project, video };
}

async function waitForWorkflowPrimary(page, labelPattern) {
  try {
    await page.waitFor(
      (source, flags) => {
        const visible = (element) => {
          const box = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden" && !element.hidden;
        };
        const pattern = new RegExp(source, flags);
        return [...document.querySelectorAll('[data-testid="workflow-primary"]')].some(
          (button) => visible(button) && !button.disabled && pattern.test(button.textContent || ""),
        );
      },
      `workflow primary ${labelPattern}`,
      20_000,
      labelPattern.source,
      labelPattern.flags,
    );
  } catch (error) {
    const snapshot = await page.evaluate(() => ({
      primaryText: document.querySelector('[data-testid="workflow-primary"]')?.textContent?.trim() || "",
      primaryDisabled: document.querySelector('[data-testid="workflow-primary"]')?.disabled === true,
      activeJourneyPhase: document.querySelector("#journeyNav [data-journey-phase].is-active")?.dataset.journeyPhase || "",
      activeWorkflowStep: document.querySelector("[data-workflow-step][aria-current='step']")?.dataset.workflowStep || "",
      footerHint: document.querySelector("#workflowFooterHint")?.textContent?.trim() || "",
      footerReason: document.querySelector("#workflowFooterReason")?.textContent?.trim() || "",
      configStatus: document.querySelector("#configStatus")?.textContent?.trim() || "",
      runAlert: document.querySelector("#runPlanAlert")?.textContent?.trim().replace(/\s+/g, " ").slice(0, 800) || "",
    }));
    error.message = `${error.message}. Workflow snapshot: ${JSON.stringify(snapshot)}`;
    throw error;
  }
}

async function hasTestId(page, testId) {
  return page.evaluate((id) => Boolean(document.querySelector(`[data-testid="${id}"]`)), testId);
}

async function revealAdvancedTasks(page) {
  await page.clickVisible("details.advanced-task-panel > summary");
  await page.waitForVisible('[data-testid="goal-motion-foreground"]');
}

async function assertExportScreenOwnsViewport(page) {
  const state = await page.evaluate(() => {
    const visible = (element) => {
      if (!element) return false;
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden" && !element.hidden;
    };
    return {
      exportCardVisible: visible(document.querySelector("#studioExportCard")),
      librarySlotVisible: visible(document.querySelector("#reviewLibrarySectionSlot")),
      handoffUrlCount: document.querySelectorAll("[data-export-handoff-url]").length,
    };
  });
  assert.equal(state.exportCardVisible, true, `export screen should show the export/handoff card: ${JSON.stringify(state)}`);
  assert.equal(state.librarySlotVisible, false, `export screen should not be occupied by the asset library slot: ${JSON.stringify(state)}`);
  assert.ok(state.handoffUrlCount > 0, "export screen exposes handoff URLs");
}

async function workflowPrimaryText(page) {
  return page.evaluate(() => {
    const visible = (element) => {
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden" && !element.hidden;
    };
    const button = [...document.querySelectorAll('[data-testid="workflow-primary"]')].find((item) => visible(item));
    return button?.textContent?.trim() || "";
  });
}

async function workflowPrimaryMatches(page, labelPattern) {
  return page.evaluate(
    (source, flags) => {
      const visible = (element) => {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden" && !element.hidden;
      };
      const pattern = new RegExp(source, flags);
      return [...document.querySelectorAll('[data-testid="workflow-primary"]')].some(
        (item) => visible(item) && !item.disabled && pattern.test(item.textContent || ""),
      );
    },
    labelPattern.source,
    labelPattern.flags,
  );
}

async function clickVisibleWorkflowPrimary(page, labelPattern = null) {
  const box = await page.evaluate((source, flags) => {
    const visible = (element) => {
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden" && !element.hidden;
    };
    const pattern = source ? new RegExp(source, flags) : null;
    const button = [...document.querySelectorAll('[data-testid="workflow-primary"]')].find(
      (item) => visible(item) && !item.disabled && (!pattern || pattern.test(item.textContent || "")),
    );
    if (!button) throw new Error("No visible enabled workflow primary button");
    button.scrollIntoView({ block: "center", inline: "center" });
    const rect = button.getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  }, labelPattern?.source || "", labelPattern?.flags || "");
  await page.cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: box.x, y: box.y, button: "left", clickCount: 1 });
  await page.cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: box.x, y: box.y, button: "left", clickCount: 1 });
  await delay(80);
}

async function enterReviewThroughVisibleWorkflow(page) {
  await waitForWorkflowPrimary(page, /Continue to review|Validate reviewed objects|Validate export|Validate again/i);
  if (await workflowPrimaryMatches(page, /Continue to review/i)) {
    await clickVisibleWorkflowPrimary(page, /Continue to review/i);
  }
  await waitForWorkflowPrimary(page, /Validate reviewed objects|Validate export|Validate again/i);
  await page.waitFor(() => document.querySelectorAll("[data-track-row]").length > 0, "review tracks rendered");
}

async function validateReviewedObjectsThroughVisibleWorkflow(page, statusPattern) {
  await waitForWorkflowPrimary(page, /Validate reviewed objects|Validate export|Validate again/i);
  await clickVisibleWorkflowPrimary(page, /Validate reviewed objects|Validate export|Validate again/i);
  await page.waitForText('[data-testid="export-status"], #exportDecision, #exportStatusSummary, #exportStatus', statusPattern);
  await waitForWorkflowPrimary(page, /Continue to export|Export MotionJSON/i);
  if (await workflowPrimaryMatches(page, /Continue to export/i)) {
    await clickVisibleWorkflowPrimary(page, /Continue to export/i);
  }
  await waitForWorkflowPrimary(page, /Export MotionJSON/i);
}

async function exportReviewedObjectsThroughVisibleWorkflow(page, handoffLabel) {
  await waitForWorkflowPrimary(page, /Export MotionJSON/i);
  await clickVisibleWorkflowPrimary(page, /Export MotionJSON/i);
  await page.waitFor(() => document.querySelectorAll("[data-export-handoff-url]").length > 0, handoffLabel);
}

async function revealModelSetupOptions(page) {
  await page.waitForTestId("model-setup-panel");
  await page.evaluate(() => {
    const details = document.querySelector("#modelSetupDetail .model-setup-advanced");
    if (details) details.open = true;
  });
  const shouldShowOptions = await page.evaluate(() => {
    const button = document.querySelector('[data-model-setup-action="change-model"]');
    if (!button) return false;
    return /Show other options/i.test(button.textContent || button.getAttribute("aria-label") || "");
  });
  if (shouldShowOptions) {
    await page.click('[data-model-setup-action="change-model"]');
    await page.evaluate(() => {
      const details = document.querySelector("#modelSetupDetail .model-setup-advanced");
      if (details) details.open = true;
    });
  }
}

async function waitForModelSetupText(page, pattern) {
  try {
    await page.waitForText('[data-testid="model-setup-detail"]', pattern);
  } catch (error) {
    const snapshot = await page.evaluate(() => ({
      activeJourneyPhase: document.querySelector("#journeyNav [data-journey-phase].is-active")?.dataset.journeyPhase || "",
      activeWorkflowStep: document.querySelector("[data-workflow-step][aria-current='step']")?.dataset.workflowStep || "",
      detailText: document.querySelector('[data-testid="model-setup-detail"]')?.textContent?.trim().replace(/\s+/g, " ").slice(0, 800) || "",
      bodyText: document.body.textContent?.trim().replace(/\s+/g, " ").slice(0, 1200) || "",
    }));
    error.message = `${error.message}. Model setup snapshot: ${JSON.stringify(snapshot)}`;
    throw error;
  }
}

async function selectedProjectVideo(page) {
  const result = await page.evaluate(() => ({
    projectId: document.querySelector('[data-testid="project-select"]')?.value || "",
    videoId: document.querySelector('[data-testid="video-select"]')?.value || "",
  }));
  assert.ok(result.projectId, "selected project id is available");
  assert.ok(result.videoId, "selected video id is available");
  return result;
}

async function clickPrimaryUntilNewJob(page, projectId, beforeIds) {
  let lastButton = null;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    await page.waitFor(
      () => {
        const button = document.querySelector('[data-testid="workflow-primary"]');
        return Boolean(button && !button.disabled);
      },
      "workflow primary enabled",
      20_000,
    );
    lastButton = await page.evaluate(() => document.querySelector('[data-testid="workflow-primary"]')?.textContent?.trim() || "");
    await page.clickTestId("workflow-primary");
    const deadline = Date.now() + 3_000;
    while (Date.now() < deadline) {
      const created = (await listJobs(projectId)).find((job) => !beforeIds.has(job.id));
      if (created) return created;
      await delay(250);
    }
  }
  throw new Error(`No real extraction job appeared after workflow-primary clicks; last button: ${lastButton || "<none>"}`);
}

async function assertJobCanvasPreviewNonblank(page, jobId) {
  const tools = await requestJson("GET", `${baseUrl}/api/jobs/${encodeURIComponent(jobId)}/review-tools`);
  const canvas = (tools.tools || []).find((tool) => tool.toolId === "canvas_player");
  assert.equal(canvas?.status, "ready", `canvas player should be ready for ${jobId}`);
  await page.goto(`${baseUrl}${canvas.url}`);
  await page.waitFor(
    () => {
      const canvas = document.querySelector("canvas");
      return Boolean(canvas && canvas.width > 0 && canvas.height > 0);
    },
    "preview canvas mounted",
    20_000,
  );
  await page.waitFor(
    () => {
      const canvas = document.querySelector("canvas");
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return false;
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let index = 3; index < data.length; index += 4) {
        if (data[index] > 0) return true;
      }
      return false;
    },
    "preview canvas has visible pixels",
    20_000,
  );
}

async function assertSecretAbsent(page, secret) {
  const snapshot = await page.evaluate((value) => {
    const inputValues = [...document.querySelectorAll("input, textarea")]
      .map((input) => input.value || "")
      .filter(Boolean);
    const localValues = [];
    for (const store of [localStorage, sessionStorage]) {
      for (let index = 0; index < store.length; index += 1) {
        const key = store.key(index);
        localValues.push(`${key}:${store.getItem(key)}`);
      }
    }
    return {
      body: document.body.innerText.includes(value),
      inputs: inputValues.some((item) => item.includes(value)),
      storage: localValues.some((item) => item.includes(value)),
    };
  }, secret);
  assert.deepEqual(snapshot, { body: false, inputs: false, storage: false }, "hosted API key is redacted from browser-visible state");
  const providerSettings = await requestJson("GET", `${baseUrl}/api/provider-settings`);
  assert.equal(JSON.stringify(providerSettings).includes(secret), false, "hosted API key is redacted from provider settings response");
}

async function createMockJobFromBrowser(page, projectId, videoId) {
  const response = await page.evaluate(
    async (nextProjectId, nextVideoId) => {
      const result = await fetch("/api/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          projectId: nextProjectId,
          videoId: nextVideoId,
          maskProvider: "mock",
          maxFrames: 2,
          run: true,
        }),
      });
      const payload = await result.json();
      if (!result.ok) throw new Error(payload.error || `mock job failed: ${result.status}`);
      return payload;
    },
    projectId,
    videoId,
  );
  assert.ok(response.job?.id, "browser-created mock job has an id");
  return response;
}

async function installReadySam2ModelAndFakeJob(page) {
  await page.evaluate(() => {
    window.__motionJsonModelPresentJobPayloads = [];
    const originalFetch = window.fetch.bind(window);
    const nowIso = () => new Date().toISOString();
    let modelPresentJob = null;
    const fakeTrack = () => ({
      objectId: "object_0",
      label: "E2E SAM2 red ball",
      source: "sam2-local",
      providerName: "sam2-local",
      trackingProvider: "sam2-local",
      confidence: 0.94,
      frameCount: 3,
      visibleFrameCount: 3,
      exportStatus: "accepted",
      exportIncluded: true,
      exportable: true,
      trackClass: "moving_object",
      maskQuality: { qualityStatus: "good" },
      frames: [
        {
          frame: 0,
          sourceFrameIndex: 0,
          sampleIndex: 0,
          bbox: [78, 58, 88, 88],
          polygon: [
            [78, 58],
            [166, 58],
            [166, 146],
            [78, 146],
          ],
          visible: true,
          maskArea: 7744,
          outlineStatus: "mask_outline",
          outlineSource: "segmentation_contour",
        },
        {
          frame: 1,
          sourceFrameIndex: 1,
          sampleIndex: 1,
          bbox: [98, 63, 88, 88],
          polygon: [
            [98, 63],
            [186, 63],
            [186, 151],
            [98, 151],
          ],
          visible: true,
          maskArea: 7744,
          outlineStatus: "mask_outline",
          outlineSource: "segmentation_contour",
        },
        {
          frame: 2,
          sourceFrameIndex: 2,
          sampleIndex: 2,
          bbox: [121, 68, 88, 88],
          polygon: [
            [121, 68],
            [209, 68],
            [209, 156],
            [121, 156],
          ],
          visible: true,
          maskArea: 7744,
          outlineStatus: "mask_outline",
          outlineSource: "segmentation_contour",
        },
      ],
    });
    const fakeReview = () => ({
      format: "motionjson.review.v0.1",
      source: { frameCount: 3, width: 320, height: 180 },
      tracks: [fakeTrack()],
      objects: [
        {
          objectId: "object_0",
          id: "object_0",
          label: "E2E SAM2 red ball",
          rightsSummary: { status: "local_test_asset", notes: ["E2E browser-only SAM2 review fixture."] },
        },
      ],
      export: { includedObjectIds: ["object_0"], excludedObjectIds: [] },
      timeline: {
        format: "motionjson.review_timeline.v0.1",
        frameCount: 3,
        markers: [
          { id: "e2e-object-start", kind: "tracked_object", frameIndex: 0, objectId: "object_0", label: "E2E SAM2 red ball", status: "accepted" },
          { id: "e2e-object-end", kind: "tracked_object", frameIndex: 2, objectId: "object_0", label: "E2E SAM2 red ball", status: "accepted" },
        ],
      },
    });
    const fakeValidation = () => ({
      ok: true,
      checked: 1,
      issueCount: 0,
      issues: [],
      summary: "E2E SAM2 moving track validates for MotionJSON export.",
    });
    const fakeObjectLayerPack = () => ({
      objectCount: 1,
      snippets: {
        plainJs: "const scene = await fetch('/api/artifacts/e2e_sam2_scene/content').then((response) => response.json());",
        remotion: "import scene from './scene_graph.json';",
      },
    });
    const fakeExportAssets = () => [
      {
        id: "e2e_sam2_scene",
        kind: "validated_motionjson_scene",
        contentUrl: "/api/artifacts/e2e_sam2_scene/content",
        path: "scene_graph.json",
        metadata: { rel_path: "exports/e2e_sam2/scene_graph.json" },
      },
      {
        id: "e2e_sam2_pack",
        kind: "object_layer_pack",
        contentUrl: "/api/artifacts/e2e_sam2_pack/content",
        path: "object_layer_pack.json",
        metadata: { rel_path: "exports/e2e_sam2/object_layer_pack.json" },
      },
      {
        id: "e2e_sam2_remotion",
        kind: "remotion_plan",
        contentUrl: "/api/artifacts/e2e_sam2_remotion/content",
        path: "remotion_export_plan.json",
        metadata: { rel_path: "exports/e2e_sam2/remotion_export_plan.json" },
      },
      {
        id: "e2e_sam2_website",
        kind: "website_package",
        contentUrl: "/api/artifacts/e2e_sam2_website/content",
        path: "website_package.zip",
        metadata: { rel_path: "exports/e2e_sam2/website_package.zip" },
      },
      {
        id: "e2e_sam2_bundle",
        kind: "motionjson_export_zip",
        contentUrl: "/api/artifacts/e2e_sam2_bundle/content",
        path: "motionjson_export.zip",
        metadata: { rel_path: "exports/e2e_sam2/motionjson_export.zip" },
      },
    ];
    const fakeArtifacts = () => ({
      artifacts: [
        {
          id: "e2e_sam2_track_summary",
          kind: "track_summary",
          path: "track_summary.json",
          metadata: { provider: "sam2-local", trackCount: 1, rel_path: "review/track_summary.json" },
        },
      ],
      review: fakeReview(),
    });
    const fakeJob = (body = {}) => ({
      id: "e2e_sam2_ready_job",
      projectId: body.projectId,
      videoId: body.videoId,
      status: "succeeded",
      provider: "sam2-local",
      maskProvider: "sam2-local",
      createdAt: nowIso(),
      updatedAt: nowIso(),
      runConfig: body.runConfig,
      result: {
        objects: 1,
        frames: 3,
        tracks: [fakeTrack()],
        trackSummary: { tracks: [fakeTrack()] },
      },
    });
    const readyProvider = (provider) => {
      if (!provider || provider.id !== "sam2-local") return provider;
      return {
        ...provider,
        available: true,
        configured: true,
        runnable: true,
        status: "ready",
        reasons: [],
        readiness: {
          ...(provider.readiness || {}),
          configured: true,
          ready: true,
          runnable: true,
          status: "ready",
          message: "E2E SAM2 runtime ready.",
        },
        setupState: {
          ...(provider.setupState || {}),
          status: "ready",
          label: "Ready",
          message: "E2E SAM2 runtime ready.",
        },
        runtimeProof: {
          ...(provider.runtimeProof || {}),
          allowsRun: true,
          proofStatus: "verified",
          runtime: { deviceActual: "cpu", acceleratorKind: "cpu" },
        },
        runtimeVerification: {
          ...(provider.runtimeVerification || {}),
          verified: true,
          proofStatus: "verified",
          runtime: { deviceActual: "cpu", acceleratorKind: "cpu" },
        },
        settings: {
          ...(provider.settings || {}),
          sam2CheckpointPath: "/tmp/e2e-sam2-checkpoint.pt",
          sam2ModelConfigPath: "/tmp/e2e-sam2-config.yaml",
          sam2Device: "cpu",
        },
      };
    };
    const readyCapability = (provider) => {
      if (!provider || provider.name !== "sam2-local") return provider;
      return {
        ...provider,
        available: true,
        configured: true,
        runnable: true,
        status: "ready",
        reasons: [],
      };
    };
    const jsonResponse = (payload, init = {}) =>
      new Response(JSON.stringify(payload), {
        status: init.status || 200,
        headers: { "content-type": "application/json" },
      });

    window.fetch = async (...args) => {
      const request = args[0];
      const url = new URL(typeof request === "string" ? request : request.url, location.origin);
      const method = String(args[1]?.method || request?.method || "GET").toUpperCase();

      if (url.pathname === "/api/run-config/validate" && method === "POST") {
        const body = JSON.parse(args[1]?.body || "{}");
        return jsonResponse({ valid: true, errors: [], warnings: [], runConfig: body.runConfig });
      }

      if (url.pathname === "/api/model-setup/recommendation" && method === "GET") {
        return jsonResponse({
          format: "motionjson.model_setup_recommendation.v0.1",
          goal: url.searchParams.get("goal") || "trace_one_object",
          requiresModelSetup: true,
          selectedConnectionId: "sam2-local",
          selectedProviderId: "sam2-local",
          selectedCapabilityId: "sam2-local",
          title: "SAM2 prompt tracking",
          subtitle: "E2E SAM2 runtime ready.",
          status: "ready",
          primaryAction: { id: "continue", label: "Continue to run" },
          requiredInputs: [],
          optionalInputs: [],
          advancedInputs: [],
          runtimeBadges: [
            { id: "hardware", label: "CPU", status: "ok" },
            { id: "runtime", label: "Runtime ready", status: "ok" },
            { id: "model", label: "SAM2 checkpoint/config", status: "ok" },
            { id: "proof", label: "Proof verified", status: "ok" },
          ],
          whyThis: "E2E SAM2 runtime ready.",
          warnings: [],
          alternatives: [],
          runConfigMapping: { providerName: "sam2-local", discoveryMode: "manual_prompt" },
        });
      }

      if (url.pathname === "/api/jobs" && method === "POST") {
        const body = JSON.parse(args[1]?.body || "{}");
        window.__motionJsonModelPresentJobPayloads.push(body);
        modelPresentJob = fakeJob(body);
        return jsonResponse({
          job: modelPresentJob,
        });
      }

      if (url.pathname === "/api/jobs/e2e_sam2_ready_job") {
        return jsonResponse({ job: modelPresentJob || fakeJob() });
      }
      if (url.pathname === "/api/jobs/e2e_sam2_ready_job/events") {
        return jsonResponse({
          events: [
            { id: "e2e-started", kind: "job_started", message: "SAM2 tracking started", createdAt: nowIso() },
            { id: "e2e-succeeded", kind: "job_succeeded", message: "SAM2 masks and tracks ready", createdAt: nowIso() },
          ],
        });
      }
      if (url.pathname === "/api/jobs/e2e_sam2_ready_job/artifacts") return jsonResponse(fakeArtifacts());
      if (url.pathname === "/api/artifacts" && url.searchParams.get("jobId") === "e2e_sam2_ready_job") return jsonResponse(fakeArtifacts());
      if (url.pathname === "/api/jobs/e2e_sam2_ready_job/review-tools") return jsonResponse({ tools: [] });
      if (url.pathname === "/api/jobs/e2e_sam2_ready_job/corrections") {
        return jsonResponse({ jobId: "e2e_sam2_ready_job", history: [], trackEdits: {} });
      }
      if (url.pathname === "/api/jobs/e2e_sam2_ready_job/validate" && method === "POST") {
        return jsonResponse({
          validation: fakeValidation(),
          includedObjectIds: ["object_0"],
          excludedObjectIds: [],
          objectLayerPack: fakeObjectLayerPack(),
        });
      }
      if (url.pathname === "/api/jobs/e2e_sam2_ready_job/exports" && method === "POST") {
        return jsonResponse({
          export: {
            jobId: "e2e_sam2_ready_job",
            validation: fakeValidation(),
            includedObjectIds: ["object_0"],
            excludedObjectIds: [],
            assets: fakeExportAssets(),
            objectLayerPack: fakeObjectLayerPack(),
          },
          review: fakeReview(),
        });
      }

      const response = await originalFetch(...args);
      if (url.pathname === "/api/jobs" && method === "GET" && modelPresentJob) {
        const payload = await response.clone().json().catch(() => ({ jobs: [] }));
        const jobs = (payload.jobs || []).filter((job) => job?.id !== modelPresentJob.id);
        return jsonResponse({ ...payload, jobs: [modelPresentJob, ...jobs] });
      }
      if (url.pathname === "/api/progress" && method === "GET" && modelPresentJob) {
        const payload = await response.clone().json().catch(() => ({ progress: [] }));
        const progress = (payload.progress || []).filter((job) => job?.id !== modelPresentJob.id);
        return jsonResponse({ ...payload, progress: [modelPresentJob, ...progress] });
      }
      if (url.pathname === "/api/provider-settings") {
        const payload = await response.clone().json();
        return jsonResponse({ ...payload, providers: (payload.providers || []).map(readyProvider) });
      }
      if (url.pathname === "/api/capabilities") {
        const payload = await response.clone().json();
        return jsonResponse({ ...payload, providers: (payload.providers || []).map(readyCapability) });
      }
      return response;
    };
  });
}

async function installModelRunCapture(page) {
  await page.evaluate(() => {
    window.__motionJsonE2eModelRuns = [];
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const response = await originalFetch(...args);
      const url = String(args[0] || "");
      const method = String(args[1]?.method || "GET").toUpperCase();
      if (method === "POST" && /\/api\/model-runs(?:[?#].*)?$/.test(url)) {
        response
          .clone()
          .json()
          .then((payload) => {
            if (payload?.modelRun) window.__motionJsonE2eModelRuns.push(payload.modelRun);
          })
          .catch(() => {});
      }
      return response;
    };
  });
}

async function installModelRunFailure(page, message) {
  await page.evaluate((failureMessage) => {
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const url = String(args[0] || "");
      const method = String(args[1]?.method || "GET").toUpperCase();
      if (method === "POST" && /\/api\/model-runs(?:[?#].*)?$/.test(url)) {
        return new Response(JSON.stringify({ error: failureMessage }), {
          status: 500,
          headers: { "content-type": "application/json" },
        });
      }
      return originalFetch(...args);
    };
  }, message);
}

async function waitForCapturedModelRun(page) {
  await page.waitFor(() => Boolean(window.__motionJsonE2eModelRuns?.length), "captured model run");
  const runs = await page.evaluate(() => window.__motionJsonE2eModelRuns || []);
  return runs[runs.length - 1];
}

function findChrome() {
  const candidates = [
    process.env.CHROME_BIN,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ];
  return candidates.find((candidate) => candidate && existsSync(candidate)) || "";
}

function pythonCommand() {
  const requested = process.env.MOTIONJSON_PYTHON || process.env.PYTHON;
  const local = existsSync(join(ROOT, ".venv", "bin", "python")) ? join(ROOT, ".venv", "bin", "python") : "";
  const python = requested || local || "python3";
  if (process.platform === "darwin" && process.arch === "x64") {
    return { command: "arch", args: ["-arm64", python] };
  }
  return { command: python, args: [] };
}

function waitForLine(child, pattern, timeoutMs = 20_000) {
  return new Promise((resolvePromise, reject) => {
    let buffer = "";
    const timer = setTimeout(() => reject(new Error(`Timed out waiting for ${pattern}`)), timeoutMs);
    child.stdout.on("data", (chunk) => {
      buffer += String(chunk);
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.includes(pattern)) {
          clearTimeout(timer);
          resolvePromise(line);
        }
      }
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`Process exited before ${pattern}: ${code}`));
    });
  });
}

async function startUi(tmpRoot, { debugMock = true } = {}) {
  const python = pythonCommand();
  const args = [
    ...python.args,
    "-m",
    "motionjson.cli",
    "ui",
    "--no-open",
    ...(debugMock ? ["--debug-mock"] : []),
    "--host",
    "127.0.0.1",
    "--port",
    "0",
    "--db",
    join(tmpRoot, "backend.sqlite"),
    "--storage-root",
    join(tmpRoot, "storage"),
  ];
  const child = spawn(
    python.command,
    args,
    { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"] },
  );
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  const line = await waitForLine(child, "MotionJSON UI:");
  return { child, baseUrl: line.split("MotionJSON UI:", 2)[1].trim().replace(/\/$/, "") };
}

async function withTemporaryUi(options, run) {
  const oldBaseUrl = baseUrl;
  const tempRoot = await mkdtemp(join(tmpdir(), "motionjson-real-ui-e2e-"));
  const server = await startUi(tempRoot, options);
  try {
    baseUrl = server.baseUrl;
    await run();
  } finally {
    baseUrl = oldBaseUrl;
    await stopProcess(server.child);
    await removeTempRoot(tempRoot);
  }
}

function freePort() {
  return new Promise((resolvePromise, reject) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolvePromise(port));
    });
    server.on("error", reject);
  });
}

async function stopProcess(child) {
  if (!child || child.exitCode !== null || child.signalCode) return;
  const exited = new Promise((resolvePromise) => child.once("exit", resolvePromise));
  child.kill("SIGTERM");
  await Promise.race([exited, delay(2_000)]);
  if (child.exitCode === null && !child.signalCode) {
    const killed = new Promise((resolvePromise) => child.once("exit", resolvePromise));
    child.kill("SIGKILL");
    await Promise.race([killed, delay(1_000)]);
  }
}

async function removeTempRoot(path) {
  let lastError = null;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      await rm(path, { recursive: true, force: true });
      return;
    } catch (error) {
      lastError = error;
      await delay(150 * (attempt + 1));
    }
  }
  throw lastError;
}

async function startChrome(executablePath, tmpRoot, port) {
  const child = spawn(
    executablePath,
    [
      "--headless=new",
      "--disable-background-networking",
      "--disable-dev-shm-usage",
      "--disable-extensions",
      "--disable-gpu",
      "--disable-sync",
      "--no-first-run",
      "--remote-allow-origins=*",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${join(tmpRoot, "chrome-profile")}`,
      "about:blank",
    ],
    { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"] },
  );
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) return child;
    } catch {
      await delay(120);
    }
  }
  throw new Error("Chrome remote debugging endpoint did not start");
}

async function newTarget(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?about%3Ablank`, { method: "PUT" });
  if (!response.ok) throw new Error(`Could not create Chrome page: ${response.status}`);
  return response.json();
}

function connectCdp(webSocketDebuggerUrl) {
  const socket = new WebSocket(webSocketDebuggerUrl);
  let id = 0;
  const callbacks = new Map();
  const listeners = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && callbacks.has(message.id)) {
      const { resolve: resolvePromise, reject } = callbacks.get(message.id);
      callbacks.delete(message.id);
      if (message.error) reject(new Error(message.error.message || JSON.stringify(message.error)));
      else resolvePromise(message.result || {});
      return;
    }
    if (message.method && listeners.has(message.method)) {
      for (const listener of listeners.get(message.method)) listener(message.params || {});
    }
  });
  const opened = new Promise((resolvePromise, reject) => {
    socket.addEventListener("open", resolvePromise, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  return {
    async send(method, params = {}) {
      await opened;
      const messageId = ++id;
      const response = new Promise((resolvePromise, reject) => callbacks.set(messageId, { resolve: resolvePromise, reject }));
      socket.send(JSON.stringify({ id: messageId, method, params }));
      return response;
    },
    on(method, listener) {
      if (!listeners.has(method)) listeners.set(method, new Set());
      listeners.get(method).add(listener);
    },
    close() {
      socket.close();
    },
  };
}

async function withPage(run) {
  const target = await newTarget(cdpPort);
  const cdp = connectCdp(target.webSocketDebuggerUrl);
  const consoleErrors = [];
  const networkViolations = [];
  const requestUrls = [];
  const localOrigin = new URL(baseUrl).origin;
  cdp.on("Runtime.exceptionThrown", (params) => {
    const details = params.exceptionDetails || {};
    consoleErrors.push(details.exception?.description || details.text || "page exception");
  });
  cdp.on("Runtime.consoleAPICalled", (params) => {
    if (params.type !== "error") return;
    const args = (params.args || []).map((arg) => arg.value || arg.description || "").filter(Boolean);
    consoleErrors.push(args.join(" ") || "console.error");
  });
  cdp.on("Log.entryAdded", (params) => {
    const entry = params.entry || {};
    if (entry.level === "error") {
      const source = [entry.url, entry.networkRequestId].filter(Boolean).join(" ");
      consoleErrors.push([entry.text || "browser log error", source].filter(Boolean).join(" @ "));
    }
  });
  cdp.on("Network.requestWillBeSent", (params) => {
    const url = params.request?.url || "";
    if (!url) return;
    requestUrls.push(url);
    try {
      const parsed = new URL(url);
      if (/^https?:$/i.test(parsed.protocol) && parsed.origin !== localOrigin) {
        networkViolations.push(`external network request blocked by test policy: ${url}`);
      }
    } catch {
      // Relative paths are local page requests.
    }
  });
  cdp.on("Network.responseReceived", (params) => {
    const response = params.response || {};
    const url = response.url || "";
    const status = Number(response.status || 0);
    if (status >= 400 && /\/api\/jobs\/[^/]+\/preview-files\//.test(url)) {
      networkViolations.push(`preview file request failed: ${status} ${url}`);
    }
  });
  const page = new BrowserPage(cdp, consoleErrors, networkViolations, requestUrls);
  try {
    await cdp.send("Page.enable");
    await cdp.send("Network.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Log.enable").catch(() => {});
    await page.setViewport(1440, 900);
    await run(page);
  } finally {
    cdp.close();
    await fetch(`http://127.0.0.1:${cdpPort}/json/close/${target.id}`).catch(() => {});
  }
}

class BrowserPage {
  constructor(cdp, consoleErrors, networkViolations, requestUrls) {
    this.cdp = cdp;
    this.consoleErrors = consoleErrors;
    this.networkViolations = networkViolations;
    this.requestUrls = requestUrls;
  }

  async setViewport(width, height) {
    await this.cdp.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width <= 480,
    });
  }

  async goto(url) {
    await this.cdp.send("Page.navigate", { url });
    await this.waitFor(() => document.readyState === "complete", "page load");
  }

  async evaluate(fnOrSource, ...args) {
    const source =
      typeof fnOrSource === "function"
        ? `(${fnOrSource})(...${JSON.stringify(args)})`
        : String(fnOrSource);
    const result = await this.cdp.send("Runtime.evaluate", {
      awaitPromise: true,
      returnByValue: true,
      expression: source,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Browser evaluation failed");
    }
    return result.result?.value;
  }

  async waitFor(predicate, description, timeoutMs = 20_000, ...args) {
    const deadline = Date.now() + timeoutMs;
    let lastError = null;
    while (Date.now() < deadline) {
      try {
        if (await this.evaluate(predicate, ...args)) return;
      } catch (error) {
        lastError = error;
      }
      await delay(150);
    }
    throw new Error(`Timed out waiting for ${description}${lastError ? `: ${lastError.message}` : ""}`);
  }

  async waitForTestId(testId) {
    await this.waitFor((id) => Boolean(document.querySelector(`[data-testid="${id}"]`)), `data-testid=${testId}`, 15_000, testId);
  }

  async waitForVisible(selector) {
    await this.waitFor(
      (css) => {
        const element = document.querySelector(css);
        if (!element) return false;
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden" && !element.hidden;
      },
      `${selector} visible`,
      15_000,
      selector,
    );
  }

  async waitForText(selector, pattern) {
    await this.waitFor(
      (css, source, flags) => {
        const elements = [...document.querySelectorAll(css)];
        const text = elements.map((element) => element.textContent || "").join("\n");
        return new RegExp(source, flags).test(text);
      },
      `${selector} text ${pattern}`,
      20_000,
      selector,
      pattern.source,
      pattern.flags,
    );
  }

  async assertText(selector, pattern) {
    const ok = await this.evaluate(
      (css, source, flags) => {
        const text = [...document.querySelectorAll(css)].map((element) => element.textContent || "").join("\n");
        return new RegExp(source, flags).test(text);
      },
      selector,
      pattern.source,
      pattern.flags,
    );
    assert.equal(ok, true, `${selector} should match ${pattern}`);
  }

  async click(selector) {
    await this.evaluate((css) => {
      const element = document.querySelector(css);
      if (!element) throw new Error(`Missing selector ${css}`);
      element.scrollIntoView({ block: "center", inline: "center" });
      element.click();
      return true;
    }, selector);
    await delay(80);
  }

  async clickVisible(selector) {
    await this.waitForVisible(selector);
    await this.click(selector);
  }

  async clickTestId(testId) {
    await this.click(testIdSelector(testId));
  }

  async clickVisibleTestId(testId) {
    await this.clickVisible(testIdSelector(testId));
  }

  async clickElementCenter(selector) {
    const box = await this.evaluate((css) => {
      const element = document.querySelector(css);
      if (!element) throw new Error(`Missing selector ${css}`);
      element.scrollIntoView({ block: "center", inline: "center" });
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      if (rect.width <= 0 || rect.height <= 0 || style.display === "none" || style.visibility === "hidden" || element.hidden) {
        throw new Error(`Selector ${css} is not visible`);
      }
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    }, selector);
    await this.cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: box.x, y: box.y, button: "left", clickCount: 1 });
    await this.cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: box.x, y: box.y, button: "left", clickCount: 1 });
    await delay(80);
  }

  async setValue(selector, value) {
    await this.evaluate(
      (css, nextValue) => {
        const element = document.querySelector(css);
        if (!element) throw new Error(`Missing selector ${css}`);
        element.scrollIntoView({ block: "center", inline: "center" });
        element.value = nextValue;
        element.dispatchEvent(new Event("input", { bubbles: true }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      },
      selector,
      value,
    );
  }

  async assertNoConsoleErrors() {
    assert.deepEqual(this.consoleErrors.filter(Boolean), []);
    assert.deepEqual(this.networkViolations.filter(Boolean), []);
  }

  async assertNoRequests(pattern, description) {
    const matches = this.requestUrls.filter((url) => pattern.test(url));
    assert.deepEqual(matches, [], description);
  }
}

function testIdSelector(testId) {
  return `[data-testid="${String(testId).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"]`;
}

async function requestJson(method, url, payload = null) {
  const response = await fetch(url, {
    method,
    headers: { "content-type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(`${method} ${url} failed: ${response.status} ${text}`);
  return data;
}

async function listJobs(projectId = "") {
  const query = projectId ? `?projectId=${encodeURIComponent(projectId)}` : "";
  const body = await requestJson("GET", `${baseUrl}/api/jobs${query}`);
  return body.jobs || [];
}

async function waitForJob(predicate, description, { projectId = "", timeoutMs = 30_000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let latestJobs = [];
  while (Date.now() < deadline) {
    const jobs = await listJobs(projectId);
    latestJobs = jobs;
    const match = jobs.find(predicate);
    if (match) return match;
    await delay(250);
  }
  const summary = latestJobs.map((job) => `${job.id}:${job.status}`).join(", ") || "no jobs visible";
  throw new Error(`Timed out waiting for ${description}; latest jobs: ${summary}`);
}

async function waitForProviderSetting(providerId, predicate, description) {
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    const body = await requestJson("GET", `${baseUrl}/api/provider-settings`);
    const provider = (body.providers || []).find((item) => item.id === providerId);
    if (provider && predicate(provider)) return provider;
    await delay(200);
  }
  throw new Error(`Timed out waiting for ${description}`);
}

async function providerSettingMatches(providerId, predicate) {
  const body = await requestJson("GET", `${baseUrl}/api/provider-settings`);
  const provider = (body.providers || []).find((item) => item.id === providerId);
  return Boolean(provider && predicate(provider));
}

function delay(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}
