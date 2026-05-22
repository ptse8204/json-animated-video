#!/usr/bin/env node
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawn } from "node:child_process";
import process from "node:process";

const ROOT = process.cwd();
const VIEWPORTS = [
  { name: "mobile-390", width: 390, height: 844 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "tablet-1024", width: 1024, height: 768 },
  { name: "laptop-1366", width: 1366, height: 768 },
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1920", width: 1920, height: 1080 },
];
const REAL_STATES = ["real-empty-shell", "real-seeded-shell", "real-expanded-shell"];
const CAPTURE_STATES = [
  "nav-collapsed",
  "diagnostics-open",
  "workflow-goal",
  "workflow-project",
  "workflow-video",
  "workflow-provider",
  "workflow-prompts",
  "workflow-run",
  "workflow-review",
  "workflow-review-failure",
  "workflow-correct",
  "workflow-export",
  "workflow-dashboard",
  "first-run",
  "new-project",
  "extraction-wizard",
  "advanced-config",
  "provider-diagnostics",
  "provider-settings",
  "model-setup",
  "model-setup-local",
  "model-setup-hosted-warning",
  "model-setup-missing",
  "model-setup-invalid",
  "model-setup-success",
  "model-plan-preview",
  "model-plan-warning",
  "model-plan-confirmation",
  "model-plan-queued",
  "model-plan-running",
  "model-plan-succeeded",
  "job-review",
  "candidate-review",
  "correction-tools",
  "export-gate",
  "export-handoff",
  "export-success",
  "copyable-snippet",
];
const STATES = [...REAL_STATES, ...CAPTURE_STATES];

function parseArgs(argv) {
  const options = { check: false, screenshotDir: "", states: STATES, viewports: VIEWPORTS };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--check") options.check = true;
    else if (arg === "--screenshot-dir") options.screenshotDir = argv[++index] || "";
    else if (arg === "--state") options.states = (argv[++index] || "").split(",").filter(Boolean);
    else if (arg === "--viewport") {
      const names = new Set((argv[++index] || "").split(",").filter(Boolean));
      options.viewports = VIEWPORTS.filter((item) => names.has(item.name));
    } else if (arg === "--help" || arg === "-h") {
      console.log(`Usage: node scripts/check_local_ui_layout.mjs [--check] [--screenshot-dir DIR] [--state real-empty-shell,nav-collapsed,diagnostics-open,workflow-goal,workflow-review,workflow-review-failure,workflow-dashboard,first-run,model-setup,job-review,candidate-review,correction-tools,export-gate] [--viewport mobile-390,tablet-768,laptop-1366,desktop-1440]

Starts the mock/no-model Local UI, opens it in headless Chrome, and fails on
horizontal overflow, clipped controls, too-narrow cards, or unintended overlaps
across the commercial UI viewport matrix.`);
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return options;
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

function waitForLine(child, pattern, timeoutMs = 20000) {
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

async function startUi(tmp) {
  const python = pythonCommand();
  const child = spawn(
    python.command,
    [
      ...python.args,
      "-m",
      "motionjson.cli",
      "ui",
      "--no-open",
      "--mock",
      "--host",
      "127.0.0.1",
      "--port",
      "0",
      "--db",
      join(tmp, "backend.sqlite"),
      "--storage-root",
      join(tmp, "storage"),
    ],
    { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"] },
  );
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  const line = await waitForLine(child, "MotionJSON UI:");
  const baseUrl = line.split("MotionJSON UI:", 2)[1].trim().replace(/\/$/, "");
  return { child, baseUrl };
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

async function seedJobReview(baseUrl) {
  const project = (await requestJson("POST", `${baseUrl}/api/projects`, { name: "Layout Smoke Project" })).project;
  const video = (
    await requestJson("POST", `${baseUrl}/api/videos`, {
      projectId: project.id,
      path: resolve(ROOT, "examples/demo_red_ball.mp4"),
    })
  ).video;
  let job = (
    await requestJson("POST", `${baseUrl}/api/jobs`, {
      projectId: project.id,
      videoId: video.id,
      maskProvider: "mock",
      maxFrames: 2,
      sampleFps: 12,
      run: true,
    })
  ).job;
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    job = (await requestJson("GET", `${baseUrl}/api/jobs/${job.id}`)).job;
    if (["succeeded", "failed", "canceled"].includes(job.status)) return job;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 250));
  }
  throw new Error(`Timed out waiting for mock job; last status ${job.status}`);
}

async function startChrome(chromePath, tmp, port) {
  const child = spawn(
    chromePath,
    [
      "--headless=new",
      "--disable-background-networking",
      "--disable-dev-shm-usage",
      "--disable-extensions",
      "--disable-gpu",
      "--disable-sync",
      "--no-first-run",
      "--hide-scrollbars",
      "--remote-allow-origins=*",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${join(tmp, "chrome-profile")}`,
      "about:blank",
    ],
    { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"] },
  );
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) return child;
    } catch {
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 150));
    }
  }
  throw new Error("Chrome remote debugging endpoint did not start");
}

async function newPage(port, url) {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
  if (!response.ok) throw new Error(`Could not create Chrome page: ${response.status}`);
  return response.json();
}

function connectCdp(webSocketDebuggerUrl) {
  const socket = new WebSocket(webSocketDebuggerUrl);
  let id = 0;
  const callbacks = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !callbacks.has(message.id)) return;
    const { resolve: resolvePromise, reject } = callbacks.get(message.id);
    callbacks.delete(message.id);
    if (message.error) reject(new Error(message.error.message || JSON.stringify(message.error)));
    else resolvePromise(message.result);
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
    close() {
      socket.close();
    },
  };
}

async function waitForReady(cdp, capture) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try {
      const result = await cdp.send("Runtime.evaluate", {
        returnByValue: true,
        expression: `({
          href: location.href,
          ready: document.readyState,
          captureReady: document.documentElement.dataset.captureReady || ""
        })`,
      });
      const value = result.result.value || {};
      const navigated = capture ? String(value.href || "").includes("capture=") : !String(value.href || "").startsWith("about:");
      const ready = value.ready === "complete";
      const captureReady = capture ? value.captureReady === "true" : true;
      if (navigated && ready && captureReady) return;
    } catch {
      // A navigation can destroy the previous execution context; retry.
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 120));
  }
  throw new Error(`Timed out waiting for UI capture readiness: ${capture}`);
}

async function evaluateLayout(cdp) {
  const result = await cdp.send("Runtime.evaluate", {
    returnByValue: true,
    expression: `(() => {
      const failures = [];
      const importantSelectors = [
        ".app-shell", ".sidebar", ".workspace", ".right-rail", ".topbar",
        ".workspace-grid", ".viewer-panel", ".setup-panel", ".wizard-panel",
        ".config-panel", "#viewerStage", "#providerWarning", "#providerSettingsPanel", "#modelSetupPanel",
        "#candidateSummaryList", "#correctionGuidance", "#exportSummary"
      ];
      const rect = (selector) => {
        const element = document.querySelector(selector);
        if (!element) {
          failures.push("missing " + selector);
          return null;
        }
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return {
          selector,
          left: box.left,
          right: box.right,
          top: box.top,
          bottom: box.bottom,
          width: box.width,
          height: box.height,
          display: style.display,
          visibility: style.visibility,
        };
      };
      const boxes = Object.fromEntries(importantSelectors.map((selector) => [selector, rect(selector)]));
      const viewportWidth = document.documentElement.clientWidth;
      const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
      if (scrollWidth - viewportWidth > 2) failures.push("horizontal overflow: " + scrollWidth + " > " + viewportWidth);
      for (const selector of importantSelectors) {
        const box = boxes[selector];
        if (!box || box.display === "none" || box.visibility === "hidden") continue;
        if (box.width > viewportWidth + 2) failures.push(selector + " wider than viewport");
        if (box.right < -2 || box.left > viewportWidth + 2) failures.push(selector + " outside viewport");
      }
      const intersects = (a, b) => {
        if (!a || !b || a.display === "none" || b.display === "none") return false;
        const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        return x > 2 && y > 2;
      };
      const pairs = [
        [".sidebar", ".workspace"],
        [".workspace", ".right-rail"],
        [".sidebar", ".right-rail"],
      ];
      for (const [a, b] of pairs) {
        if (intersects(boxes[a], boxes[b])) failures.push(a + " overlaps " + b);
      }
      const isVisible = (element) => {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        const visibleByBrowser = typeof element.checkVisibility === "function" ? element.checkVisibility() : true;
        return visibleByBrowser && box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden";
      };
      const workspacePanels = [".viewer-panel", ".setup-panel", ".wizard-panel", ".config-panel"]
        .map((selector) => boxes[selector])
        .filter(Boolean)
        .filter((box) => box.display !== "none");
      for (let i = 0; i < workspacePanels.length; i += 1) {
        for (let j = i + 1; j < workspacePanels.length; j += 1) {
          if (intersects(workspacePanels[i], workspacePanels[j])) {
            failures.push(workspacePanels[i].selector + " overlaps " + workspacePanels[j].selector);
          }
        }
      }
      for (const element of document.querySelectorAll("button, .load-config-button")) {
        if (!isVisible(element)) continue;
        const label = (element.textContent || element.getAttribute("aria-label") || element.id || element.className || element.tagName)
          .trim()
          .replace(/\\s+/g, " ")
          .slice(0, 80);
        if (element.scrollWidth - element.clientWidth > 2) {
          failures.push("clipped control width: " + label);
        }
        if (element.scrollHeight - element.clientHeight > 2) {
          failures.push("clipped control height: " + label);
        }
      }
      const cardMinimumWidth = Math.min(240, Math.max(0, viewportWidth - 32));
      for (const element of document.querySelectorAll(".workspace .panel, .model-choice-card, .right-rail .compact-panel, .provider-settings-row, .candidate-row, .track-row, .right-rail .artifact-row, .first-run-row")) {
        if (!isVisible(element)) continue;
        const box = element.getBoundingClientRect();
        const minimumWidth = element.closest(".right-rail") ? 220 : cardMinimumWidth;
        if (box.width < minimumWidth) {
          const label = (element.getAttribute("aria-label") || element.querySelector("h2,h3,strong,summary")?.textContent || element.className || element.tagName)
            .trim()
            .replace(/\\s+/g, " ")
            .slice(0, 80);
          failures.push("too-narrow card: " + label + " " + Math.round(box.width) + "px");
        }
      }
      const focusTarget = [...document.querySelectorAll("button, input, select, summary, a[href]")]
        .find((element) => isVisible(element) && !element.disabled);
      if (focusTarget) {
        focusTarget.focus();
        const focusStyle = getComputedStyle(focusTarget);
        if (focusStyle.outlineStyle === "none" && focusStyle.boxShadow === "none") {
          failures.push("visible focus target has no visible focus style");
        }
        focusTarget.blur();
      }
      return { failures, viewportWidth, scrollWidth, boxes };
    })()`,
  });
  return result.result.value;
}

async function captureScreenshot(cdp, path, { captureBeyondViewport = false } = {}) {
  const result = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport });
  await writeFile(path, Buffer.from(result.data, "base64"));
}

async function closeTarget(cdp, targetId) {
  await Promise.race([
    cdp.send("Target.closeTarget", { targetId }),
    new Promise((resolvePromise) => setTimeout(resolvePromise, 1500)),
  ]).catch(() => {});
}

async function checkState({ port, baseUrl, viewport, state, screenshotDir, failures }) {
  const isRealState = REAL_STATES.includes(state);
  const capture = isRealState ? "" : state;
  const url = capture ? `${baseUrl}/?capture=${encodeURIComponent(capture)}` : baseUrl;
  const page = await newPage(port, url);
  const cdp = connectCdp(page.webSocketDebuggerUrl);
  try {
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
      source: `
        localStorage.removeItem("motionjson.localUi.sidebarCollapsed");
        localStorage.removeItem("motionjson.localUi.railCollapsed");
        localStorage.removeItem("motionjson.localUi.workflowStep");
        localStorage.removeItem("motionjson.localUi.workflowDashboard");
      `,
    });
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await cdp.send("Page.navigate", { url });
    await waitForReady(cdp, capture);
    if (state === "real-expanded-shell") {
      await cdp.send("Runtime.evaluate", {
        expression: `
          if (document.querySelector(".app-shell")?.classList.contains("is-rail-collapsed")) {
            document.querySelector("#detailsToggle")?.click();
          }
          const dashboard = document.querySelector("#workflowDashboardToggle");
          if (dashboard?.getAttribute("aria-pressed") !== "true") dashboard?.click();
          document.querySelectorAll("details").forEach((details) => { details.open = true; });
        `,
      });
    }
    if (state === "nav-collapsed") {
      await cdp.send("Runtime.evaluate", {
        expression: `
          if (!document.querySelector(".app-shell")?.classList.contains("is-sidebar-collapsed")) {
            document.querySelector("#sidebarToggle")?.click();
          }
        `,
      });
    }
    if (state === "diagnostics-open") {
      await cdp.send("Runtime.evaluate", {
        expression: `
          if (document.querySelector(".app-shell")?.classList.contains("is-rail-collapsed")) {
            document.querySelector("#detailsToggle")?.click();
          }
        `,
      });
    }
    const workflowStates = {
      "workflow-goal": "choose_goal",
      "workflow-project": "project_video",
      "workflow-video": "source_video",
      "workflow-provider": "provider_settings",
      "workflow-prompts": "prompt_preview",
      "workflow-run": "validate_run",
      "workflow-review": "review_candidates",
      "workflow-review-failure": "review_candidates",
      "workflow-correct": "correct_tracks",
      "workflow-export": "export",
    };
    const workflowStepOrder = [
      "choose_goal",
      "project_video",
      "source_video",
      "provider_settings",
      "prompt_preview",
      "validate_run",
      "review_candidates",
      "correct_tracks",
      "export",
    ];
    if (workflowStates[state]) {
      await cdp.send("Runtime.evaluate", {
        expression: `
          document.querySelector('[data-workflow-step="${workflowStates[state]}"]')?.click();
        `,
      });
    }
    if (state === "workflow-dashboard") {
      await cdp.send("Runtime.evaluate", {
        expression: `
          const toggle = document.querySelector("#workflowDashboardToggle");
          if (toggle?.getAttribute("aria-pressed") !== "true") toggle?.click();
        `,
      });
    }
    const layout = await evaluateLayout(cdp);
    const stateAssertions = await cdp.send("Runtime.evaluate", {
      returnByValue: true,
      expression: `(() => {
        const shell = document.querySelector(".app-shell");
        const rightRail = document.querySelector("#diagnosticsRail");
        const rightRailBox = rightRail?.getBoundingClientRect();
        const visible = (element) => {
          if (!element) return false;
          const box = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden";
        };
        return {
          sidebarCollapsed: shell?.classList.contains("is-sidebar-collapsed") || false,
          railCollapsed: shell?.classList.contains("is-rail-collapsed") || false,
          railVisible: visible(rightRail),
          sidebarExpanded: document.querySelector("#sidebarToggle")?.getAttribute("aria-expanded") || "",
          detailsExpanded: document.querySelector("#detailsToggle")?.getAttribute("aria-expanded") || "",
          rightRailWidth: Math.round(rightRailBox?.width || 0),
          providerWarningVisible: visible(document.querySelector("#providerWarning")),
          runPlanAlertVisible: visible(document.querySelector("#runPlanAlert")),
          workflowSummaryCount: document.querySelectorAll("#workflowStepSummary .step-summary-card").length,
          setupPanelTitle: document.querySelector("#setupPanelTitle")?.textContent?.trim() || "",
          wizardPanelTitle: document.querySelector("#wizardPanelTitle")?.textContent?.trim() || "",
          rawConfigOpen: document.querySelector("#rawConfigDisclosure")?.open === true,
          configSaveLoadOpen: document.querySelector(".compact-advanced-actions")?.open === true,
          startMockText: document.querySelector("#startMockRunButton")?.textContent?.trim() || "",
          videoFormVisible: visible(document.querySelector("#videoForm")),
          postRunGuideVisible: visible(document.querySelector("#postRunGuide")),
          postRunStageCount: document.querySelectorAll("#postRunGuideList .post-run-stage").length,
          runMonitorSummaryCount: document.querySelectorAll("#runMonitorSummary .status-summary-card").length,
          reviewStatusSummaryCount: document.querySelectorAll("#reviewStatusSummary .status-summary-card").length,
          correctionStatusSummaryCount: document.querySelectorAll("#correctionStatusSummary .status-summary-card").length,
          exportStatusSummaryCount: document.querySelectorAll("#exportStatusSummary .status-summary-card").length,
          runLogsOpen: document.querySelector("#runLogsDisclosure")?.open === true,
          fallbackDiagnosticsOpen: document.querySelector("#fallbackDiagnosticsDisclosure")?.open === true,
          fallbackDiagnosticBadCount: document.querySelectorAll("#fallbackDiagnostics .diagnostic-row.is-bad").length,
          exportArtifactsOpen: document.querySelector("#exportArtifactsDisclosure")?.open === true,
          workflowActiveStep: document.querySelector("[data-workflow-step][aria-current='step']")?.dataset.workflowStep || "",
          workflowDashboard: document.querySelector("#workflowDashboardToggle")?.getAttribute("aria-pressed") === "true",
          workflowPanels: [...document.querySelectorAll("[data-workflow-panel]")].map((element) => {
            const box = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            const steps = String(element.dataset.workflowPanel || "").split(/\\s+/).filter(Boolean);
            return {
              steps,
              hidden: element.hidden === true,
              ariaHidden: element.getAttribute("aria-hidden"),
              inert: element.inert === true,
              visible: box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden",
            };
          }),
          workflowFragments: [...document.querySelectorAll("[data-workflow-fragment]")].map((element) => {
            const box = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            const steps = String(element.dataset.workflowFragment || "").split(/\\s+/).filter(Boolean);
            return {
              steps,
              hidden: element.hidden === true,
              ariaHidden: element.getAttribute("aria-hidden"),
              inert: element.inert === true,
              visible: box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden",
            };
          }),
        };
      })()`,
    });
    const stateValue = stateAssertions.result.value || {};
    if (state === "nav-collapsed" && (!stateValue.sidebarCollapsed || stateValue.sidebarExpanded !== "false")) {
      failures.push(`${viewport.name}/${state}: sidebar did not collapse with aria-expanded=false`);
    }
    if (state === "diagnostics-open" && (stateValue.railCollapsed || !stateValue.railVisible || stateValue.detailsExpanded !== "true")) {
      failures.push(`${viewport.name}/${state}: diagnostics rail did not open accessibly`);
    }
    if (state === "real-empty-shell" && !stateValue.railCollapsed) {
      failures.push(`${viewport.name}/${state}: diagnostics rail should be reduced by default`);
    }
    if (state === "workflow-provider" && !stateValue.providerWarningVisible) {
      failures.push(`${viewport.name}/${state}: provider warning area should be visible in provider step`);
    }
    if (state === "workflow-run" && !stateValue.runPlanAlertVisible) {
      failures.push(`${viewport.name}/${state}: run-step provider/config alert should be visible`);
    }
    if (state === "workflow-project" && stateValue.setupPanelTitle !== "Create or open a project") {
      failures.push(`${viewport.name}/${state}: project step title did not simplify the setup card`);
    }
    if (state === "workflow-video" && (stateValue.setupPanelTitle !== "Add or select a video" || !stateValue.videoFormVisible)) {
      failures.push(`${viewport.name}/${state}: video step should expose the local video path form as the primary action`);
    }
    if (state === "workflow-provider" && stateValue.wizardPanelTitle !== "Choose extraction mode") {
      failures.push(`${viewport.name}/${state}: provider step title should focus on mode/provider choice`);
    }
    if (state === "workflow-prompts" && stateValue.wizardPanelTitle !== "Add prompt details") {
      failures.push(`${viewport.name}/${state}: prompt step title should focus on prompt details`);
    }
    if (state === "workflow-run" && (stateValue.rawConfigOpen || stateValue.configSaveLoadOpen || stateValue.startMockText !== "Start mock job")) {
      failures.push(`${viewport.name}/${state}: run step should keep raw config/save actions collapsed and promote the safe mock job`);
    }
    if (["workflow-review", "workflow-review-failure", "workflow-correct", "workflow-export"].includes(state)) {
      if (!stateValue.postRunGuideVisible || stateValue.postRunStageCount !== 5) {
        failures.push(`${viewport.name}/${state}: post-run guide should be visible with five guided stages`);
      }
    }
    if (state === "workflow-review" && (stateValue.runMonitorSummaryCount < 1 || stateValue.reviewStatusSummaryCount < 2 || stateValue.runLogsOpen)) {
      failures.push(`${viewport.name}/${state}: review step should show run/review summaries while keeping logs collapsed unless the run failed`);
    }
    if (state === "workflow-review-failure" && (stateValue.runMonitorSummaryCount < 1 || stateValue.reviewStatusSummaryCount < 2 || !stateValue.runLogsOpen || !stateValue.fallbackDiagnosticsOpen || stateValue.fallbackDiagnosticBadCount < 1)) {
      failures.push(`${viewport.name}/${state}: failed review state should surface logs and fallback diagnostics without extra discovery`);
    }
    if (state === "workflow-correct" && stateValue.correctionStatusSummaryCount < 1) {
      failures.push(`${viewport.name}/${state}: correction step should summarize correction readiness`);
    }
    if (state === "workflow-export" && (stateValue.exportStatusSummaryCount < 1 || stateValue.exportArtifactsOpen)) {
      failures.push(`${viewport.name}/${state}: export step should summarize export readiness while keeping artifact browser collapsed`);
    }
    const expectedWorkflowStep = workflowStates[state];
    if (expectedWorkflowStep) {
      if (stateValue.workflowActiveStep !== expectedWorkflowStep) {
        failures.push(`${viewport.name}/${state}: active workflow step ${stateValue.workflowActiveStep || "none"} did not match ${expectedWorkflowStep}`);
      }
      const activePanels = stateValue.workflowPanels.filter((panel) => panel.steps.includes(expectedWorkflowStep));
      const inactivePanels = stateValue.workflowPanels.filter((panel) => !panel.steps.includes(expectedWorkflowStep));
      const activeFragments = stateValue.workflowFragments.filter((fragment) => fragment.steps.includes(expectedWorkflowStep));
      const inactiveFragments = stateValue.workflowFragments.filter((fragment) => !fragment.steps.includes(expectedWorkflowStep));
      if (!activePanels.some((panel) => panel.visible && !panel.hidden && panel.ariaHidden === "false" && !panel.inert)) {
        failures.push(`${viewport.name}/${state}: no active workflow panel is visible and interactive`);
      }
      const expectedSummaryCount = Math.max(0, workflowStepOrder.indexOf(expectedWorkflowStep));
      if (stateValue.workflowSummaryCount !== expectedSummaryCount) {
        failures.push(`${viewport.name}/${state}: expected ${expectedSummaryCount} prior-step summary card(s), found ${stateValue.workflowSummaryCount}`);
      }
      const leakingInactive = inactivePanels.filter((panel) => panel.visible || !panel.hidden || panel.ariaHidden !== "true" || !panel.inert);
      if (leakingInactive.length) {
        failures.push(`${viewport.name}/${state}: ${leakingInactive.length} inactive workflow panel(s) remained visible or interactive`);
      }
      if (activeFragments.length && !activeFragments.some((fragment) => fragment.visible && !fragment.hidden && fragment.ariaHidden === "false" && !fragment.inert)) {
        failures.push(`${viewport.name}/${state}: no active workflow fragment is visible and interactive`);
      }
      const leakingInactiveFragments = inactiveFragments.filter((fragment) => fragment.visible || !fragment.hidden || fragment.ariaHidden !== "true" || !fragment.inert);
      if (leakingInactiveFragments.length) {
        failures.push(`${viewport.name}/${state}: ${leakingInactiveFragments.length} inactive workflow fragment(s) remained visible or interactive`);
      }
    }
    if (state === "workflow-dashboard") {
      if (!stateValue.workflowDashboard) {
        failures.push(`${viewport.name}/${state}: show-all workflow dashboard did not activate`);
      }
      const hiddenPanels = stateValue.workflowPanels.filter((panel) => panel.hidden || panel.ariaHidden === "true" || panel.inert);
      const hiddenFragments = stateValue.workflowFragments.filter((fragment) => fragment.hidden || fragment.ariaHidden === "true" || fragment.inert);
      const visiblePanels = stateValue.workflowPanels.filter((panel) => panel.visible);
      if (hiddenPanels.length) {
        failures.push(`${viewport.name}/${state}: ${hiddenPanels.length} workflow panel(s) stayed hidden in dashboard mode`);
      }
      if (hiddenFragments.length) {
        failures.push(`${viewport.name}/${state}: ${hiddenFragments.length} workflow fragment(s) stayed hidden in dashboard mode`);
      }
      if (visiblePanels.length < 8) {
        failures.push(`${viewport.name}/${state}: dashboard mode exposed too few workflow panels (${visiblePanels.length})`);
      }
    }
    if (screenshotDir) {
      await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}.png`));
      if (state === "advanced-config" && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), { captureBeyondViewport: true });
      }
      if (state.startsWith("model-setup") && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), { captureBeyondViewport: true });
      }
      if (state.startsWith("model-plan") && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), { captureBeyondViewport: true });
      }
      if (["job-review", "candidate-review", "correction-tools", "export-gate", "export-handoff", "export-success", "copyable-snippet"].includes(state) && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), { captureBeyondViewport: true });
      }
    }
    for (const failure of layout.failures) {
      failures.push(`${viewport.name}/${state}: ${failure}`);
    }
  } finally {
    await closeTarget(cdp, page.id);
    cdp.close();
  }
}

async function stopProcess(child) {
  if (!child || child.exitCode !== null) return;
  child.kill("SIGTERM");
  await new Promise((resolvePromise) => {
    const timer = setTimeout(() => {
      if (child.exitCode === null) child.kill("SIGKILL");
      resolvePromise();
    }, 1500);
    child.once("exit", () => {
      clearTimeout(timer);
      resolvePromise();
    });
  });
}

async function run() {
  const options = parseArgs(process.argv.slice(2));
  const chrome = findChrome();
  if (options.check) {
    console.log(JSON.stringify({ chrome, viewports: VIEWPORTS, states: STATES, canRun: Boolean(chrome) }, null, 2));
    return;
  }
  if (!chrome) throw new Error("Chrome/Chromium is required. Set CHROME_BIN to a compatible binary.");
  if (!options.viewports.length) throw new Error("No requested viewports matched.");
  if (!options.states.length) throw new Error("No states requested.");

  const tmp = await mkdtemp(join(tmpdir(), "motionjson-ui-layout-"));
  const port = 9300 + Math.floor(Math.random() * 400);
  let ui = null;
  let chromeProcess = null;
  const failures = [];
  try {
    ui = await startUi(tmp);
    chromeProcess = await startChrome(chrome, tmp, port);
    if (options.screenshotDir) await mkdir(options.screenshotDir, { recursive: true });

    const preSeedStates = options.states.filter((state) =>
      [
        "real-empty-shell",
        "first-run",
        "nav-collapsed",
        "diagnostics-open",
        "workflow-goal",
        "workflow-project",
        "workflow-video",
        "workflow-provider",
        "workflow-prompts",
        "workflow-run",
        "workflow-dashboard",
      ].includes(state),
    );
    const postSeedStates = options.states.filter((state) => !preSeedStates.includes(state));

    for (const viewport of options.viewports) {
      for (const state of preSeedStates) {
        await checkState({ port, baseUrl: ui.baseUrl, viewport, state, screenshotDir: options.screenshotDir, failures });
      }
    }

    if (postSeedStates.length) await seedJobReview(ui.baseUrl);

    for (const viewport of options.viewports) {
      for (const state of postSeedStates) {
        await checkState({ port, baseUrl: ui.baseUrl, viewport, state, screenshotDir: options.screenshotDir, failures });
      }
    }
  } finally {
    await stopProcess(chromeProcess);
    await stopProcess(ui?.child);
    await rm(tmp, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }).catch(() => {});
  }

  if (failures.length) {
    console.error(JSON.stringify({ status: "failed", failures }, null, 2));
    process.exit(1);
  }
  console.log(JSON.stringify({ status: "ok", viewports: options.viewports.map((item) => item.name), states: options.states }, null, 2));
}

run().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
