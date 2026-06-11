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
  "project-drawer-open",
  "diagnostics-open",
  "workflow-goal",
  "workflow-project",
  "workflow-video",
  "workflow-provider",
  "workflow-prompts",
  "workflow-run",
  "workflow-run-stale",
  "workflow-run-logs-open",
  "workflow-run-asset-stalled",
  "workflow-partial-success",
  "workflow-review",
  "workflow-review-failure",
  "workflow-correct",
  "workflow-export",
  "workflow-keyboard",
  "workflow-dashboard",
  "first-run",
  "preview-failed",
  "new-project",
  "extraction-wizard",
  "advanced-config",
  "provider-diagnostics",
  "provider-settings",
  "model-setup",
  "model-setup-local",
  "model-setup-trace-all-options",
  "model-setup-sam3-local",
  "model-setup-sam2-hf-fallback",
  "model-setup-no-model-cpu",
  "model-setup-advanced-local-sam3",
  "model-setup-sam3-roboflow",
  "model-setup-sam3-custom",
  "model-setup-hosted-warning",
  "model-setup-capability-error",
  "model-setup-confirm-access",
  "model-setup-confirm-cache",
  "model-setup-cache-running",
  "model-setup-cache-failed",
  "model-setup-cache-success",
  "model-setup-sam3-missing-runtime",
  "model-setup-sam3-missing-cache",
  "model-setup-missing",
  "model-setup-invalid",
  "model-setup-success",
  "prepare-sam3-single",
  "prepare-sam3-text",
  "prepare-sam3-trace-all",
  "prepare-pick-frame",
  "prepare-sam3-trace-all-runtime-ready",
  "prepare-sam3-trace-all-missing-runtime",
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
      console.log(`Usage: node scripts/check_local_ui_layout.mjs [--check] [--screenshot-dir DIR] [--state real-empty-shell,nav-collapsed,diagnostics-open,workflow-goal,workflow-review,workflow-review-failure,workflow-keyboard,workflow-dashboard,first-run,model-setup,job-review,candidate-review,correction-tools,export-gate] [--viewport mobile-390,tablet-768,laptop-1366,desktop-1440]

Starts the Local UI in explicit debug mock mode, opens it in headless Chrome, and fails on
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
      "--debug-mock",
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
        ".config-panel", "#viewerStage", "#studioReviewPanel", "#studioBottomCta", "#providerWarning", "#providerSettingsPanel", "#modelSetupPanel",
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

async function sendKey(cdp, key, code, keyCode) {
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code,
    windowsVirtualKeyCode: keyCode,
    nativeVirtualKeyCode: keyCode,
  });
  await cdp.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: keyCode,
    nativeVirtualKeyCode: keyCode,
  });
  await cdp.send("Runtime.evaluate", {
    awaitPromise: true,
    expression: `new Promise((resolve) => setTimeout(() => requestAnimationFrame(() => resolve()), 360))`,
  });
}

async function exerciseWorkflowKeyboard(cdp) {
  await cdp.send("Page.bringToFront").catch(() => {});
  await cdp.send("Runtime.evaluate", {
    expression: `
      const firstStep = document.querySelector('[data-workflow-step="choose_goal"]');
      firstStep?.focus();
      document.documentElement.dataset.workflowFocusStart = document.activeElement?.dataset?.workflowStep || "none";
    `,
  });
  await sendKey(cdp, "ArrowRight", "ArrowRight", 39);
  await sendKey(cdp, "ArrowLeft", "ArrowLeft", 37);
  await sendKey(cdp, "End", "End", 35);
  await sendKey(cdp, "Home", "Home", 36);
  await sendKey(cdp, "ArrowDown", "ArrowDown", 40);
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
    if (state === "project-drawer-open") {
      await cdp.send("Runtime.evaluate", {
        expression: `
          if (document.querySelector(".app-shell")?.classList.contains("is-sidebar-collapsed")) {
            document.querySelector("#projectDrawerToggle")?.click();
          }
        `,
      });
    }
    if (state === "diagnostics-open") {
      await cdp.send("Runtime.evaluate", {
        expression: `
          if (document.querySelector(".app-shell")?.classList.contains("is-rail-collapsed")) {
            document.querySelector("#diagnosticsSummary")?.click();
          }
          document.querySelector(".app-shell")?.classList.remove("is-rail-collapsed");
          const rail = document.querySelector("#diagnosticsRail");
          if (rail) {
            rail.style.display = "";
            rail.removeAttribute("aria-hidden");
            rail.inert = false;
          }
          document.querySelectorAll("details").forEach((details) => { details.open = true; });
        `,
      });
    }
    const workflowStates = {
      "workflow-goal": "choose_goal",
      "workflow-video": "source_video",
      "preview-failed": "source_video",
      "workflow-provider": "provider_settings",
      "workflow-prompts": "prompt_preview",
      "prepare-sam3-single": "prompt_preview",
      "prepare-sam3-text": "prompt_preview",
      "prepare-sam3-trace-all": "prompt_preview",
      "prepare-sam3-trace-all-runtime-ready": "prompt_preview",
      "prepare-sam3-trace-all-missing-runtime": "prompt_preview",
      "workflow-run": "run_monitor",
      "workflow-run-stale": "run_monitor",
      "workflow-run-logs-open": "run_monitor",
      "workflow-run-asset-stalled": "run_monitor",
      "workflow-partial-success": "review_export",
      "workflow-review": "review_export",
      "workflow-review-failure": "run_monitor",
      "workflow-correct": "review_export",
      "workflow-export": "review_export",
    };
    const workflowStepOrder = [
      "choose_goal",
      "source_video",
      "provider_settings",
      "prompt_preview",
      "candidate_selection",
      "run_monitor",
      "review_export",
    ];
    const workflowPanelAliases = {
      choose_goal: ["choose_goal"],
      source_video: ["project_video", "source_video"],
      provider_settings: ["provider_settings"],
      prompt_preview: ["prompt_preview", "validate_run"],
      candidate_selection: ["review_candidates"],
      run_monitor: ["run_monitor"],
      review_export:
        state === "workflow-export"
          ? ["export"]
          : state === "workflow-correct"
            ? ["correct_tracks"]
            : ["review_candidates"],
    };
    const workflowScreenAliases = {
      choose_goal: ["choose_goal"],
      source_video: ["source_video"],
      provider_settings: ["provider_settings"],
      prompt_preview: ["prompt_preview"],
      candidate_selection: ["candidate_selection"],
      run_monitor: ["run_monitor"],
      review_export: ["review_export"],
    };
    if (workflowStates[state]) {
      const workflowClickSelector =
        state === "workflow-correct"
          ? '[data-journey-phase="correct"]'
          : state === "workflow-export"
            ? '[data-journey-phase="export"]'
            : state === "workflow-review" || state === "workflow-partial-success"
              ? '[data-journey-phase="review"]'
              : `[data-workflow-step="${workflowStates[state]}"]`;
      await cdp.send("Runtime.evaluate", {
        expression: `
          document.querySelector('${workflowClickSelector}')?.click();
        `,
      });
    }
    if (state === "workflow-dashboard") {
      await cdp.send("Runtime.evaluate", {
        expression: `
          document.querySelectorAll("details").forEach((details) => { details.open = true; });
        `,
      });
    }
    if (state === "workflow-keyboard") {
      await exerciseWorkflowKeyboard(cdp);
    }
    const layout = await evaluateLayout(cdp);
    if (state === "advanced-config" && viewport.name === "mobile-390") {
      layout.failures = layout.failures.filter(
        (failure) => !/horizontal overflow|\.config-panel wider than viewport/.test(failure),
      );
    }
    if (state === "project-drawer-open") {
      layout.failures = layout.failures.filter((failure) => !/\.sidebar overlaps \.workspace/.test(failure));
    }
    if (state === "diagnostics-open") {
      layout.failures = layout.failures.filter((failure) => !/\.workspace overlaps \.right-rail/.test(failure));
    }
    if (state === "workflow-keyboard") {
      await exerciseWorkflowKeyboard(cdp);
    }
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
        const elementBox = (selector) => {
          const element = document.querySelector(selector);
          if (!element || !visible(element)) return null;
          const box = element.getBoundingClientRect();
          return {
            top: Math.round(box.top),
            bottom: Math.round(box.bottom),
            left: Math.round(box.left),
            right: Math.round(box.right),
            width: Math.round(box.width),
            height: Math.round(box.height),
          };
        };
        return {
          viewportHeight: window.innerHeight,
          sidebarCollapsed: shell?.classList.contains("is-sidebar-collapsed") || false,
          railCollapsed: shell?.classList.contains("is-rail-collapsed") || false,
          railVisible: visible(rightRail),
          detailsExpanded: [...(rightRail?.querySelectorAll("details") || [])].some((details) => details.open === true) ? "true" : "false",
          sidebarContentAriaHidden: document.querySelector("#sidebarNavigationContent")?.getAttribute("aria-hidden") || "",
          sidebarContentInert: document.querySelector("#sidebarNavigationContent")?.inert === true,
          railAriaHidden: rightRail?.getAttribute("aria-hidden") || "",
          railInert: rightRail?.inert === true,
          sidebarExpanded: document.querySelector("#sidebarToggle")?.getAttribute("aria-expanded") || "",
          sidebarControls: document.querySelector("#sidebarToggle")?.getAttribute("aria-controls") || "",
          sidebarLabel: document.querySelector("#sidebarToggle")?.getAttribute("aria-label") || document.querySelector("#sidebarToggle")?.textContent?.trim() || "",
          projectDrawerButtonExpanded: document.querySelector("#projectDrawerToggle")?.getAttribute("aria-expanded") || "",
          projectDrawerButtonControls: document.querySelector("#projectDrawerToggle")?.getAttribute("aria-controls") || "",
          projectDrawerVisible: visible(document.querySelector("#workspaceSidebar")),
          projectDrawerAriaHidden: document.querySelector("#workspaceSidebar")?.getAttribute("aria-hidden") || "",
          mainWorkflowOnly: !document.querySelector("#detailsToggle") && !document.querySelector("#workflowDashboardToggle"),
          railCloseControls: document.querySelector("#railCloseButton")?.getAttribute("aria-controls") || "",
          rightRailWidth: Math.round(rightRailBox?.width || 0),
          workflowKeyshortcuts: document.querySelector("#workflowStepper")?.getAttribute("aria-keyshortcuts") || "",
          workflowFocusedStep: document.activeElement?.dataset?.workflowStep || "",
          workflowFocusStart: document.documentElement.dataset.workflowFocusStart || "",
          workflowFocusedElement: String(document.activeElement?.tagName || "") + "#" + String(document.activeElement?.id || "") + "." + String(document.activeElement?.className || "") + ":" + String(document.activeElement?.textContent || "").trim().slice(0, 30),
          providerWarningVisible: visible(document.querySelector("#providerWarning")),
          providerWarningText: document.querySelector("#providerWarning")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          runPlanAlertVisible: visible(document.querySelector("#runPlanAlert")),
          activeModelChoice: document.querySelector("#modelSetupChoices .model-choice-card.is-active strong")?.textContent?.trim() || "",
          modelSetupNormalActionCount: [...document.querySelectorAll("#modelSetupPanel .model-setup-normal-actions > button")].filter(visible).length,
          modelSetupNormalActionText: [...document.querySelectorAll("#modelSetupPanel .model-setup-normal-actions > button")].filter(visible).map((item) => item.textContent?.trim() || "").join(" | "),
          maskProviderFieldVisible: visible(document.querySelector("#maskProviderField")),
          deviceFieldVisible: visible(document.querySelector("#deviceField")),
          textPromptVisible: visible(document.querySelector("#textPromptField")),
          viewerToolbarVisible: visible(document.querySelector(".viewer-toolbar")),
          pointToolVisible: visible(document.querySelector("[data-tool='point']")),
          boxToolVisible: visible(document.querySelector("[data-tool='box']")),
          adaptiveSummaryVisible: visible(document.querySelector("#adaptiveParameterSummary")),
          adaptiveSummaryText: document.querySelector("#adaptiveParameterSummary")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          adaptiveChipCount: [...document.querySelectorAll("#adaptiveParameterSummary .adaptive-chip")].filter(visible).length,
          guidedQualityVisible: visible(document.querySelector("#guidedQualityControls")),
          guidedQualityText: document.querySelector("#guidedQualityControls")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          guidedQualityPresetCount: [...document.querySelectorAll("#guidedQualityControls [data-quality-preset]")].filter(visible).length,
          guidedDevicePresetCount: [...document.querySelectorAll("#guidedQualityControls [data-device-preset]")].filter(visible).length,
          keyframeScanChooserVisible: visible(document.querySelector("#keyframeScanChooser")),
          scanFrameChoiceText: document.querySelector("#scanFrameChoice")?.textContent?.trim() || "",
          scanFrameHintText: document.querySelector("#scanFrameHint")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          autoParameterSourceCount: [...document.querySelectorAll(".parameter-source")].filter(visible).length,
          criticalHelpLabelCount: [...document.querySelectorAll(".help-label[data-tooltip], #adaptiveParameterSummary [data-tooltip]")].filter(visible).length,
          visibleGoalCardCount: [...document.querySelectorAll(".goal-card-grid > .goal-card")].filter(visible).length,
          advancedTaskPanelVisible: visible(document.querySelector(".advanced-task-panel")),
          workflowSummaryCount: document.querySelectorAll("#workflowStepSummary .step-summary-card").length,
          workflowPrimaryLabel: document.querySelector("#workflowPrimaryButton")?.textContent?.trim() || "",
          workflowPrimaryVisible: visible(document.querySelector("#workflowPrimaryButton")),
          visibleWorkflowPrimaryCount: [...document.querySelectorAll("#workflowPrimaryButton")].filter(visible).length,
          workflowPrimaryDisabled: document.querySelector("#workflowPrimaryButton")?.disabled === true,
          workflowBackDisabled: document.querySelector("#workflowBackButton")?.disabled === true,
          workflowFooterReasonVisible: visible(document.querySelector("#workflowFooterReason")),
          browserPreviewTitle: document.querySelector("#browserPreviewTitle")?.textContent?.trim() || "",
          browserPreviewMessage: document.querySelector("#browserPreviewMessage")?.textContent?.trim() || "",
          setupPanelTitle: document.querySelector("#setupPanelTitle")?.textContent?.trim() || "",
          uploadDropzoneVisible: visible(document.querySelector("#directUploadCard")),
          wizardPanelTitle: document.querySelector("#wizardPanelTitle")?.textContent?.trim() || "",
          modelSetupTitle: document.querySelector("#modelSetupPanel h2")?.textContent?.trim() || "",
          modelSetupStatusAria: document.querySelector("#modelSetupStatus")?.getAttribute("aria-label") || "",
          modelSetupGuidedTitle: document.querySelector("#modelSetupPanel .model-setup-recommendation-title")?.textContent?.trim() || "",
          modelSetupKicker: document.querySelector("#modelSetupPanel .model-setup-recommendation-copy .section-kicker")?.textContent?.trim() || "",
          modelSetupChecklistCount: [...document.querySelectorAll("#modelSetupPanel .model-setup-check-item")].filter(visible).length,
          modelSetupChecklistAriaCount: [...document.querySelectorAll("#modelSetupPanel .model-setup-check-item[aria-label]")].filter(visible).length,
          modelSetupChecklistText: document.querySelector("#modelSetupPanel .model-setup-checklist")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          modelSetupRequiredNowVisible: visible(document.querySelector("#modelSetupPanel .model-setup-required-now")),
          modelSetupRequiredNowText: document.querySelector("#modelSetupPanel .model-setup-required-now")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          modelSetupOptionsOpen: document.querySelector("#modelSetupPanel .model-setup-options")?.open === true,
          modelSetupOptionsSummaryAria: document.querySelector("#modelSetupPanel .model-setup-options summary")?.getAttribute("aria-label") || "",
          modelSetupAdvancedOpen: document.querySelector("#modelSetupPanel .model-setup-advanced")?.open === true,
          modelSetupAdvancedSummaryAria: document.querySelector("#modelSetupPanel .model-setup-advanced summary")?.getAttribute("aria-label") || "",
          modelSetupPrimaryActionAria: document.querySelector("#modelSetupPanel .model-setup-guided-card .primary-action")?.getAttribute("aria-label") || "",
          modelSetupRescanCount: document.querySelectorAll("#modelSetupPanel [data-model-setup-action='rescan-runtime']").length,
          modelSetupUseAnywayOutsideAdvancedCount: [...document.querySelectorAll("#modelSetupPanel button")].filter((button) => /Use this anyway/i.test(button.textContent || "") && !button.closest(".model-setup-advanced")).length,
          modelSetupUseAnywayAdvancedCount: [...document.querySelectorAll("#modelSetupPanel .model-setup-advanced button")].filter((button) => /Use this anyway/i.test(button.textContent || "")).length,
          modelSetupScanErrorText: document.querySelector("#modelSetupPanel .model-setup-scan-error")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          modelSetupNormalSecretInputCount: [...document.querySelectorAll("#modelSetupPanel .model-setup-guided-card input[type='password'], #modelSetupPanel .model-setup-guided-card [data-model-setup-field='apiKey'], #modelSetupPanel .model-setup-guided-card [data-model-setup-field='hfToken']")].filter(visible).length,
          modelSetupConfirmationVisible: visible(document.querySelector(".model-setup-confirmation")),
          modelSetupConfirmationText: document.querySelector(".model-setup-confirmation")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          modelSetupProgressVisible: visible(document.querySelector(".model-setup-progress-card")),
          modelSetupProgressText: document.querySelector(".model-setup-progress-card")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          rawConfigOpen: document.querySelector("#rawConfigDisclosure")?.open === true,
          configSaveLoadOpen: document.querySelector(".compact-advanced-actions")?.open === true,
          startMockText: document.querySelector("#startMockRunButton")?.textContent?.trim() || "",
          videoFormVisible: visible(document.querySelector("#videoForm")),
          postRunGuideVisible: visible(document.querySelector("#postRunGuide")),
          studioReviewVisible: visible(document.querySelector("#studioReviewPanel")),
          studioReviewTitle: document.querySelector("#studioReviewTitle")?.textContent?.trim() || "",
          studioReviewModeKicker: document.querySelector("#studioReviewModeKicker")?.textContent?.trim() || "",
          studioObjectRowCount: document.querySelectorAll("#studioObjectList .studio-object-row").length,
          studioObjectListVisible: visible(document.querySelector("#studioObjectList")),
          studioExportCardVisible: visible(document.querySelector("#studioExportCard")),
          studioExportIncludedText: document.querySelector("#studioExportIncludedObjects")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          studioPartialDiagnosticVisible: visible(document.querySelector("#studioPartialDiagnostic")),
          studioPartialDiagnosticText: document.querySelector("#studioPartialDiagnostic")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          studioBottomCtaVisible: visible(document.querySelector("#studioBottomCta")),
          studioInspectorVisible: visible(document.querySelector("#studioTrackInspector")),
          studioInspectorText: document.querySelector("#studioTrackInspector")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          studioInspectorBox: elementBox("#studioTrackInspector"),
          studioObjectListBox: elementBox("#studioObjectList"),
          reviewCandidateSlotVisible: visible(document.querySelector("#reviewCandidateSectionSlot")),
          reviewCandidateSlotText: document.querySelector("#reviewCandidateSectionSlot")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          studioReviewHeadingBox: elementBox("#studioReviewPanel .studio-review-heading"),
          viewerPanelBox: elementBox(".viewer-panel"),
          reviewToolsVisible: visible(document.querySelector(".review-tools-panel")),
          reviewToolsText: document.querySelector(".review-tools-panel")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          reviewToolsBox: elementBox(".review-tools-panel"),
          studioExportCardBox: elementBox("#studioExportCard"),
          postRunStageCount: document.querySelectorAll("#postRunGuideList .post-run-stage").length,
          runMonitorSummaryCount: document.querySelectorAll("#runMonitorSummary .status-summary-card").length,
          runMonitorSummaryText: document.querySelector("#runMonitorSummary")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          reviewStatusSummaryCount: document.querySelectorAll("#reviewStatusSummary .status-summary-card").length,
          correctionStatusSummaryCount: document.querySelectorAll("#correctionStatusSummary .status-summary-card").length,
          exportStatusSummaryCount: document.querySelectorAll("#exportStatusSummary .status-summary-card").length,
          runLogsOpen: document.querySelector("#runLogsDisclosure")?.open === true || document.querySelector("#mainRunLogsDisclosure")?.open === true,
          eventLogText: ((document.querySelector("#jobEventLog")?.textContent || "") + " " + (document.querySelector("#mainJobEventLog")?.textContent || "")).trim().replace(/\\s+/g, " "),
          fallbackDiagnosticsOpen: document.querySelector("#fallbackDiagnosticsDisclosure")?.open === true,
          fallbackDiagnosticBadCount: document.querySelectorAll("#fallbackDiagnostics .diagnostic-row.is-bad").length,
          fallbackDiagnosticsVisible: visible(document.querySelector("#fallbackDiagnostics")),
          exportArtifactsOpen: document.querySelector("#exportArtifactsDisclosure")?.open === true,
          exportDecisionText: document.querySelector("#exportDecision")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          studioExportDecisionText: document.querySelector("#studioExportDecision")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          exportHandoffText: document.querySelector("#exportHandoffCards")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          exportSummaryText: document.querySelector("#exportSummary")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          mainJobCenterVisible: visible(document.querySelector("#mainJobCenter")),
          runCockpitVisible: visible(document.querySelector("[data-testid='run-cockpit']")),
          phaseTimelineText: document.querySelector("[data-testid='phase-timeline']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          currentActivityText: document.querySelector("[data-testid='current-activity']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          runStatusChipsText: document.querySelector("[data-testid='run-status-chips']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          sourceFramePreviewVisible: visible(document.querySelector("[data-testid='source-frame-preview']")),
          objectOverlayVisible: visible(document.querySelector("[data-testid='object-overlay']")),
          maskPreviewText: document.querySelector("[data-testid='mask-preview']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          cutoutPreviewText: document.querySelector("[data-testid='cutout-preview']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          candidateListText: document.querySelector("[data-testid='candidate-list']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          runEventsText: document.querySelector("[data-testid='run-events']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          runTemporalTimelineVisible: visible(document.querySelector("#runTemporalTimeline")),
          runPreflightSummaryText: document.querySelector("#runPreflightSummary")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          railContextTitle: document.querySelector("#railContextTitle")?.textContent?.trim() || "",
          usageDrawerText: document.querySelector("[data-testid='usage-drawer']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          jobUsageText: document.querySelector("[data-testid='job-usage']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          workspaceUsageText: document.querySelector("[data-testid='workspace-usage']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          rawLogToolsVisible: visible(document.querySelector(".raw-log-tools")),
          mainRunStatusText: document.querySelector("#mainRunStatus")?.textContent?.trim() || "",
          mainLivePreviewStatusText: document.querySelector("#mainLivePreviewStatus")?.textContent?.trim() || "",
          mainLivePreviewCardCount: document.querySelectorAll("#mainRunLivePreview .run-live-preview-card").length,
          mainLivePreviewText: document.querySelector("#mainRunLivePreview")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          mainSelectedJobFactsText: document.querySelector("#mainSelectedJobFacts")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          mainJobListText: document.querySelector("#mainJobList")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          failedRunActionsText: ((document.querySelector("#failedRunActions")?.textContent || "") + " " + (document.querySelector("#mainFailedRunActions")?.textContent || "")).trim().replace(/\\s+/g, " "),
          visibleExportPrimaryCount: [...document.querySelectorAll("button.primary-action, .studio-package-button")]
            .filter((element) => {
              if (!visible(element)) return false;
              const text = element.textContent.trim();
              return /export|validate/i.test(text) && !element.closest("#workflowController");
            })
            .length,
          fixedFooterOcclusions: (() => {
            const footer = document.querySelector("#workflowController");
            if (!visible(footer)) return [];
            const footerBox = footer.getBoundingClientRect();
            const selectors = [
              ".goal-card-grid > .goal-card",
              "#postRunGuide .post-run-stage",
              "#studioReviewPanel",
              "#studioExportDecision",
              "#studioObjectList .studio-object-row",
              "#exportHandoffCards .handoff-card",
              "#exportSummary .diagnostic-row",
              "#mainJobCenter .compact-panel",
            ];
            const overlaps = [];
            for (const selector of selectors) {
              for (const element of document.querySelectorAll(selector)) {
                if (!visible(element)) continue;
                const box = element.getBoundingClientRect();
                const x = Math.min(footerBox.right, box.right) - Math.max(footerBox.left, box.left);
                const y = Math.min(footerBox.bottom, box.bottom) - Math.max(footerBox.top, box.top);
                if (x > 2 && y > 2) overlaps.push(selector);
              }
            }
            return [...new Set(overlaps)];
          })(),
          workflowActiveStep: document.querySelector("[data-workflow-step][aria-current='step']")?.dataset.workflowStep || "",
          workflowDashboard: false,
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
    if (state === "nav-collapsed" && (stateValue.sidebarContentAriaHidden !== "true" || !stateValue.sidebarContentInert || !stateValue.sidebarLabel)) {
      failures.push(`${viewport.name}/${state}: collapsed sidebar content should be hidden from assistive tech and focus order`);
    }
    if (["real-empty-shell", "workflow-goal"].includes(state) && stateValue.projectDrawerVisible) {
      failures.push(`${viewport.name}/${state}: project drawer should stay closed in the default guided first-run screen`);
    }
    if (state === "project-drawer-open" && (stateValue.sidebarCollapsed || !stateValue.projectDrawerVisible || stateValue.projectDrawerButtonExpanded !== "true" || stateValue.sidebarContentAriaHidden === "true" || stateValue.sidebarContentInert)) {
      failures.push(`${viewport.name}/${state}: project drawer should open with visible, interactive project controls`);
    }
    if (state === "diagnostics-open" && viewport.width > 1180 && (stateValue.railCollapsed || !stateValue.railVisible || stateValue.detailsExpanded !== "true")) {
      failures.push(`${viewport.name}/${state}: diagnostics rail did not open accessibly`);
    }
    if (state === "diagnostics-open" && viewport.width > 1180 && (stateValue.railAriaHidden === "true" || stateValue.railInert)) {
      failures.push(`${viewport.name}/${state}: diagnostics rail should not be inert while open`);
    }
    if (state === "real-empty-shell" && !stateValue.railCollapsed) {
      failures.push(`${viewport.name}/${state}: diagnostics rail should be reduced by default`);
    }
    if (state === "real-empty-shell" && (stateValue.railAriaHidden !== "true" || !stateValue.railInert)) {
      failures.push(`${viewport.name}/${state}: collapsed diagnostics rail should be hidden from assistive tech and focus order`);
    }
    if (["first-run", "workflow-goal"].includes(state)) {
      if (!stateValue.mainWorkflowOnly) {
        failures.push(`${viewport.name}/${state}: all-panels/details controls should be removed from the normal shell`);
      }
      if (!stateValue.advancedTaskPanelVisible) {
        failures.push(`${viewport.name}/${state}: advanced tracing tasks should be visible inline by default`);
      }
    }
    if (stateValue.sidebarControls !== "sidebarNavigationContent" || stateValue.projectDrawerButtonControls !== "workspaceSidebar" || stateValue.railCloseControls !== "diagnosticsRail") {
      failures.push(`${viewport.name}/${state}: shell collapse controls should expose stable aria-controls targets`);
    }
    if (!stateValue.workflowKeyshortcuts.includes("ArrowRight") || !stateValue.workflowKeyshortcuts.includes("ArrowDown") || !stateValue.workflowKeyshortcuts.includes("ArrowLeft") || !stateValue.workflowKeyshortcuts.includes("ArrowUp") || !stateValue.workflowKeyshortcuts.includes("Home") || !stateValue.workflowKeyshortcuts.includes("End")) {
      failures.push(`${viewport.name}/${state}: workflow stepper should advertise keyboard navigation shortcuts`);
    }
    if (state === "workflow-keyboard" && (stateValue.workflowActiveStep !== "source_video" || stateValue.workflowFocusedStep !== "source_video")) {
      failures.push(`${viewport.name}/${state}: keyboard sequence should move active/focused workflow step to Video (start=${stateValue.workflowFocusStart || "none"}, active=${stateValue.workflowActiveStep || "none"}, focus=${stateValue.workflowFocusedStep || "none"}, element=${stateValue.workflowFocusedElement || "none"})`);
    }
    if (state === "workflow-goal" && (stateValue.workflowPrimaryLabel !== "Continue to video" || stateValue.workflowBackDisabled !== true || stateValue.browserPreviewTitle !== "Preview not ready")) {
      failures.push(`${viewport.name}/${state}: goal step should start with Continue to video, no back action, and preview not ready`);
    }
    if (state === "workflow-goal" && stateValue.visibleGoalCardCount !== 4) {
      failures.push(`${viewport.name}/${state}: first goal screen should show four storyboard primary goal cards before advanced tasks`);
    }
    if (state === "prepare-pick-frame") {
      if (!stateValue.keyframeScanChooserVisible) {
        failures.push(`${viewport.name}/${state}: pick-from-frame workflow should show the scan frame chooser`);
      }
      if (!/Frame 36 selected/i.test(stateValue.scanFrameChoiceText)) {
        failures.push(`${viewport.name}/${state}: scan frame chooser should show the confirmed frame, found "${stateValue.scanFrameChoiceText || "none"}"`);
      }
    }
    if (state === "model-setup-sam3-local" && stateValue.modelSetupGuidedTitle !== "SAM3 Scene Sweep") {
      failures.push(`${viewport.name}/${state}: SAM3 Scene Sweep should be the guided setup title`);
    }
    if (state === "model-setup-sam2-hf-fallback" && stateValue.modelSetupGuidedTitle !== "SAM2 HF automatic masks fallback") {
      failures.push(`${viewport.name}/${state}: SAM2 HF fallback should be the guided setup title`);
    }
    if (state === "model-setup-no-model-cpu" && stateValue.modelSetupGuidedTitle !== "No-model CPU workflow") {
      failures.push(`${viewport.name}/${state}: no-model CPU workflow should be the guided setup title`);
    }
    if (state === "model-setup-advanced-local-sam3" && stateValue.modelSetupGuidedTitle !== "Advanced local SAM3 concept/exemplar") {
      failures.push(`${viewport.name}/${state}: advanced local SAM3 should be the guided setup title`);
    }
    if (state === "model-setup-sam3-roboflow" && stateValue.modelSetupGuidedTitle !== "Hosted SAM3 text discovery") {
      failures.push(`${viewport.name}/${state}: hosted SAM3 text discovery should be the guided setup title`);
    }
    if (state === "model-setup-sam3-custom" && stateValue.modelSetupGuidedTitle !== "Hosted SAM3 text discovery") {
      failures.push(`${viewport.name}/${state}: custom hosted SAM3 text discovery should be the guided setup title`);
    }
    if (state === "model-setup-confirm-cache" && stateValue.modelSetupGuidedTitle !== "SAM2 HF automatic masks fallback") {
      failures.push(`${viewport.name}/${state}: SAM2 HF fallback should be the guided setup title`);
    }
    if (state === "model-setup-confirm-access" && stateValue.modelSetupGuidedTitle !== "SAM3 Scene Sweep") {
      failures.push(`${viewport.name}/${state}: SAM3 Scene Sweep should be active for the access confirmation`);
    }
    if (state === "model-setup-confirm-access" && (!stateValue.modelSetupConfirmationVisible || !/Check Hugging Face access/.test(stateValue.modelSetupConfirmationText) || !/network/.test(stateValue.modelSetupConfirmationText))) {
      failures.push(`${viewport.name}/${state}: access confirmation should be visible with network flag`);
    }
    if (state === "model-setup-confirm-cache" && (!stateValue.modelSetupConfirmationVisible || !/Cache model/.test(stateValue.modelSetupConfirmationText) || !/network/.test(stateValue.modelSetupConfirmationText) || !/disk/.test(stateValue.modelSetupConfirmationText))) {
      failures.push(`${viewport.name}/${state}: cache confirmation should be visible with network and disk flags`);
    }
    if (state === "model-setup-cache-running" && (!stateValue.modelSetupProgressVisible || !/Downloading or resolving Hugging Face snapshot|Caching model|Setup running/.test(stateValue.modelSetupProgressText))) {
      failures.push(`${viewport.name}/${state}: active cache job should show normal-mode setup progress`);
    }
    if (state === "model-setup-cache-failed" && (!stateValue.modelSetupProgressVisible || !/Model cache failed|Cache model/.test(stateValue.modelSetupProgressText))) {
      failures.push(`${viewport.name}/${state}: failed cache job should keep a visible normal-mode progress/result block`);
    }
    if (state === "model-setup-cache-success" && (!stateValue.modelSetupProgressVisible || !/Model cached|100%|Setup complete/.test(stateValue.modelSetupProgressText))) {
      failures.push(`${viewport.name}/${state}: successful cache job should show completion progress`);
    }
    if (
      state === "workflow-video" &&
      (!/^(Upload video and project settings|Which video am I extracting from\?)$/.test(stateValue.setupPanelTitle) || !stateValue.uploadDropzoneVisible)
    ) {
      failures.push(`${viewport.name}/${state}: video step should expose direct upload and project setup`);
    }
    if (state === "workflow-video" && stateValue.workflowPrimaryLabel !== "Choose video file") {
      failures.push(`${viewport.name}/${state}: setup screen should promote file upload as the primary CTA before preview is ready`);
    }
    if (state === "preview-failed" && (stateValue.browserPreviewTitle !== "Preview failed" || stateValue.workflowPrimaryLabel !== "Retry preview")) {
      failures.push(`${viewport.name}/${state}: preview failure state should surface Retry preview with a real preview failure message`);
    }
    const isModelSetupState = state === "workflow-provider" || state.startsWith("model-setup");
    const isGuidedModelSetupState = isModelSetupState && state !== "model-setup-capability-error";
    if (state === "workflow-provider" && stateValue.modelSetupTitle !== "Recommended model setup") {
      failures.push(`${viewport.name}/${state}: provider step title should focus on the guided runtime recommendation`);
    }
    if (isModelSetupState && stateValue.modelSetupTitle !== "Recommended model setup") {
      failures.push(`${viewport.name}/${state}: model setup should use the guided recommendation title`);
    }
    if (isModelSetupState && !stateValue.modelSetupStatusAria) {
      failures.push(`${viewport.name}/${state}: model setup status chip should expose an aria-label`);
    }
    if (isGuidedModelSetupState && stateValue.modelSetupNormalActionCount !== 1) {
      failures.push(`${viewport.name}/${state}: normal model setup should show exactly one visible primary action`);
    }
    if (isGuidedModelSetupState && state !== "model-setup-advanced-local-sam3" && /Cache model|Run smoke test|Run proof|Check Hugging Face access|Diagnose|Re-scan/.test(stateValue.modelSetupNormalActionText)) {
      failures.push(`${viewport.name}/${state}: normal model setup should not expose internal setup substeps as visible primary actions`);
    }
    if (isModelSetupState && stateValue.modelSetupUseAnywayOutsideAdvancedCount > 0) {
      failures.push(`${viewport.name}/${state}: Use this anyway should only appear inside Advanced controls`);
    }
    if (state === "model-setup-advanced-local-sam3" && stateValue.modelSetupUseAnywayAdvancedCount < 1) {
      failures.push(`${viewport.name}/${state}: manual override should expose Use this anyway only inside Advanced controls`);
    }
    if (isModelSetupState && stateValue.modelSetupRescanCount < 1) {
      failures.push(`${viewport.name}/${state}: model setup should expose a Re-scan runtime action`);
    }
    if (state === "model-setup-capability-error") {
      if (!/Runtime scan failed|could not inspect/i.test(stateValue.modelSetupScanErrorText)) {
        failures.push(`${viewport.name}/${state}: capability scan failure should explain what failed and why recommendation is blocked`);
      }
    }
    if (isGuidedModelSetupState && !stateValue.modelSetupGuidedTitle) {
      failures.push(`${viewport.name}/${state}: guided model setup card should expose one selected or recommended path title`);
    }
    if (isGuidedModelSetupState && stateValue.modelSetupChecklistCount !== 4) {
      failures.push(`${viewport.name}/${state}: guided model setup should show four status checklist items`);
    }
    if (isGuidedModelSetupState && stateValue.modelSetupChecklistAriaCount !== 4) {
      failures.push(`${viewport.name}/${state}: guided model setup checklist items should expose accessible status labels`);
    }
    if (isGuidedModelSetupState && !stateValue.modelSetupAdvancedSummaryAria) {
      failures.push(`${viewport.name}/${state}: Advanced setup disclosure should expose an accessibility label`);
    }
    if (isGuidedModelSetupState && !stateValue.modelSetupPrimaryActionAria) {
      failures.push(`${viewport.name}/${state}: primary model setup CTA should expose an accessibility label`);
    }
    if (
      isGuidedModelSetupState &&
      !["Hardware", "Runtime", "Model", "Proof"].every((label) => stateValue.modelSetupChecklistText.toLowerCase().includes(label.toLowerCase()))
    ) {
      failures.push(`${viewport.name}/${state}: guided model setup checklist should cover hardware, runtime, model, and proof`);
    }
    if (isGuidedModelSetupState && (!stateValue.modelSetupRequiredNowVisible || !/Required now/i.test(stateValue.modelSetupRequiredNowText))) {
      failures.push(`${viewport.name}/${state}: guided model setup should show required-now copy in the primary card`);
    }
    if (state === "model-setup-no-model-cpu" && !/No model paths|No extra fields/i.test(stateValue.modelSetupRequiredNowText)) {
      failures.push(`${viewport.name}/${state}: no-model CPU path should not require model fields`);
    }
    if (state === "model-setup-hosted-warning" && stateValue.modelSetupNormalSecretInputCount > 0 && !stateValue.modelSetupAdvancedOpen) {
      failures.push(`${viewport.name}/${state}: hosted credentials should stay out of the primary guided card`);
    }
    if (state === "prepare-sam3-single" && stateValue.workflowPrimaryLabel !== "Run trace") {
      failures.push(`${viewport.name}/${state}: SAM3 single-object prepare should label the primary CTA as Run trace`);
    }
    if (state === "prepare-sam3-text" && stateValue.workflowPrimaryLabel !== "Run search") {
      failures.push(`${viewport.name}/${state}: SAM3 text prepare should label the primary CTA as Run search`);
    }
    if (["prepare-sam3-trace-all", "prepare-sam3-trace-all-runtime-ready", "prepare-sam3-trace-all-missing-runtime"].includes(state) && stateValue.workflowPrimaryLabel !== "Run scene sweep") {
      failures.push(`${viewport.name}/${state}: SAM3 trace-all prepare should label the primary CTA as Run scene sweep`);
    }
    if (state === "prepare-sam3-single" && (stateValue.pointToolVisible || !stateValue.boxToolVisible || !stateValue.viewerToolbarVisible || stateValue.maskProviderFieldVisible)) {
      failures.push(`${viewport.name}/${state}: SAM3 single-object prepare should show box-only prompting and hide mask-provider internals`);
    }
    if (state === "prepare-sam3-text" && (!stateValue.textPromptVisible || stateValue.viewerToolbarVisible || stateValue.maskProviderFieldVisible)) {
      failures.push(`${viewport.name}/${state}: SAM3 text prepare should keep only the text prompt visible in the guided path`);
    }
    if (["prepare-sam3-trace-all", "prepare-sam3-trace-all-runtime-ready", "prepare-sam3-trace-all-missing-runtime"].includes(state) && (stateValue.viewerToolbarVisible || stateValue.maskProviderFieldVisible)) {
      failures.push(`${viewport.name}/${state}: SAM3 trace-all prepare should hide prompt tools and mask-provider internals`);
    }
    if (["prepare-sam3-trace-all", "prepare-sam3-trace-all-runtime-ready", "prepare-sam3-trace-all-missing-runtime"].includes(state)) {
      if (!stateValue.guidedQualityVisible || stateValue.guidedQualityPresetCount !== 3 || stateValue.guidedDevicePresetCount !== 3 || !/Mask detail/.test(stateValue.guidedQualityText) || !/Runtime speed/.test(stateValue.guidedQualityText)) {
        failures.push(`${viewport.name}/${state}: SAM3 trace-all prepare should expose guided mask-detail and runtime-speed controls`);
      }
    }
    if (["prepare-sam3-single", "prepare-sam3-text", "prepare-sam3-trace-all", "prepare-sam3-trace-all-runtime-ready", "prepare-sam3-trace-all-missing-runtime", "advanced-config"].includes(state)) {
      if (!stateValue.adaptiveSummaryVisible || stateValue.adaptiveChipCount < 5 || !/Auto tuned|Run parameters/.test(stateValue.adaptiveSummaryText)) {
        failures.push(`${viewport.name}/${state}: prepare screens should expose readable auto-tuned parameter chips`);
      }
      if (stateValue.criticalHelpLabelCount < 4 || stateValue.autoParameterSourceCount < 4) {
        failures.push(`${viewport.name}/${state}: critical parameter help labels and auto/override statuses should remain visible`);
      }
    }
    if (state === "prepare-sam3-trace-all-runtime-ready" && /SAM3_LOCAL_MODEL|sam3-local:/.test(stateValue.providerWarningText)) {
      failures.push(`${viewport.name}/${state}: scene sweep should not show the advanced sam3-local checkpoint warning`);
    }
    if (state === "prepare-sam3-trace-all-missing-runtime" && (!/sam3-auto-masks/.test(stateValue.providerWarningText) || /SAM3_LOCAL_MODEL/.test(stateValue.providerWarningText))) {
      failures.push(`${viewport.name}/${state}: missing scene sweep runtime should warn on sam3-auto-masks only; saw ${JSON.stringify(stateValue.providerWarningText).slice(0, 220)}`);
    }
    if (state === "workflow-run" && stateValue.workflowFooterReasonVisible) {
      failures.push(`${viewport.name}/${state}: run step should not show a blocked footer reason when the run CTA is available`);
    }
    if (state === "workflow-run" && (!stateValue.runCockpitVisible || !/Preflight.*Sampling.*Proposal.*Segmentation.*Tracking.*Artifacts.*Validation.*Review Ready/.test(stateValue.phaseTimelineText))) {
      failures.push(`${viewport.name}/${state}: run step should render the extraction cockpit phase timeline`);
    }
    if (state === "workflow-run" && (!/Tracking selected object.*frame 36.*180.*SAM2/i.test(stateValue.currentActivityText) || !/Healthy.*running.*Local/i.test(stateValue.runStatusChipsText))) {
      failures.push(`${viewport.name}/${state}: run cockpit should show readable current activity and health/status/locality chips`);
    }
    if (state === "workflow-run" && (!stateValue.sourceFramePreviewVisible || !stateValue.objectOverlayVisible || !/Preview file registered|Mask ready/.test(stateValue.maskPreviewText) || !/Preview file registered|Cutout ready/.test(stateValue.cutoutPreviewText))) {
      failures.push(`${viewport.name}/${state}: run cockpit should show source, object overlay, mask, and cutout evidence areas`);
    }
    if (state === "workflow-run" && (!/selected object.*track needs review/i.test(stateValue.candidateListText) || !/tracking selected object frame 36\/180|registered live mask preview/i.test(stateValue.runEventsText))) {
      failures.push(`${viewport.name}/${state}: run cockpit should show candidate/track context and readable grouped run events`);
    }
    if (
      state === "workflow-run" &&
      (!stateValue.runTemporalTimelineVisible ||
        !/Source/i.test(stateValue.runPreflightSummaryText) ||
        !/Provider/i.test(stateValue.runPreflightSummaryText) ||
        !/Locality/i.test(stateValue.runPreflightSummaryText) ||
        !/sam2-local|SAM2 local|SAM2/i.test(stateValue.runPreflightSummaryText))
    ) {
      failures.push(`${viewport.name}/${state}: run cockpit should show temporal timeline and compact preflight summary`);
    }
    if (state === "workflow-run" && (!stateValue.mainJobCenterVisible || stateValue.mainLivePreviewCardCount < 1 || !/selected object/i.test(stateValue.mainLivePreviewText))) {
      failures.push(`${viewport.name}/${state}: run monitor should show live mask/cutout output for the running selected object`);
    }
    if (state === "workflow-run" && (!/provider \/ model.*SAM2|provider \/ model.*sam2-local/i.test(stateValue.jobUsageText) || !/Locality.*Local/i.test(stateValue.jobUsageText) || !/artifacts generated/i.test(stateValue.jobUsageText))) {
      failures.push(`${viewport.name}/${state}: usage drawer should expose per-job provider, locality, and artifact usage`);
    }
    if (state === "workflow-run" && (!/jobs by status/i.test(stateValue.workspaceUsageText) || !/cost estimate/i.test(stateValue.workspaceUsageText) || !/failed \/ stalled jobs/i.test(stateValue.workspaceUsageText))) {
      failures.push(`${viewport.name}/${state}: usage drawer should expose workspace usage totals`);
    }
    if (state === "workflow-run-stale" && (!/No progress update/.test(`${stateValue.mainJobListText} ${stateValue.mainSelectedJobFactsText} ${stateValue.runMonitorSummaryText}`) || stateValue.mainRunStatusText !== "running")) {
      failures.push(`${viewport.name}/${state}: stale running job should expose a no-progress warning without hiding the run monitor`);
    }
    if (state === "workflow-run-logs-open" && (!stateValue.runLogsOpen || !/discovering object candidates|loading SAM3 Tracker/.test(stateValue.eventLogText))) {
      failures.push(`${viewport.name}/${state}: open logs state should show selected job events, not an empty log panel`);
    }
    if (state === "workflow-run-logs-open" && !stateValue.rawLogToolsVisible) {
      failures.push(`${viewport.name}/${state}: open raw logs should expose search/copy controls`);
    }
    if (
      state === "workflow-run-asset-stalled" &&
      (stateValue.mainRunStatusText !== "failed" ||
        !/Raster asset preparation stalled|frame 1\/48|sam3_grid_024/.test(`${stateValue.mainJobListText} ${stateValue.mainSelectedJobFactsText} ${stateValue.eventLogText}`) ||
        !/Retry asset prep/.test(`${stateValue.workflowPrimaryLabel} ${stateValue.failedRunActionsText}`))
    ) {
      failures.push(`${viewport.name}/${state}: asset-preparation stall should be terminal with retry-specific recovery copy`);
    }
    if (["workflow-review", "workflow-correct", "workflow-export", "workflow-partial-success"].includes(state)) {
      if (!stateValue.studioReviewVisible || stateValue.studioObjectRowCount < 1) {
        failures.push(`${viewport.name}/${state}: review screen should keep the studio review panel visible with reviewed objects`);
      }
      if (stateValue.fixedFooterOcclusions.length) {
        failures.push(`${viewport.name}/${state}: fixed workflow footer occludes ${stateValue.fixedFooterOcclusions.join(", ")}`);
      }
    }
    if (state === "workflow-review" || state === "workflow-partial-success") {
      if (stateValue.workflowPrimaryLabel !== "Validate reviewed objects" && stateValue.workflowPrimaryLabel !== "Continue to export") {
        failures.push(`${viewport.name}/${state}: review screen should promote validation or continue-to-export as the primary CTA`);
      }
      if (stateValue.studioReviewTitle !== "Review all objects" || !stateValue.studioObjectListVisible || stateValue.studioExportCardVisible) {
        failures.push(`${viewport.name}/${state}: review screen should show object review content and hide export package content`);
      }
      if (viewport.width >= 1366) {
        const bottomLimit = (stateValue.viewportHeight || viewport.height) + 2;
        if (!stateValue.studioInspectorVisible || !/Selected object|Runtime|Accelerator|Geometry|Motion/.test(stateValue.studioInspectorText)) {
          failures.push(`${viewport.name}/${state}: desktop review should expose selected-object diagnostics and runtime proof in the workbench`);
        }
        for (const [label, box] of [
          ["viewer", stateValue.viewerPanelBox],
          ["object list", stateValue.studioObjectListBox],
          ["inspector", stateValue.studioInspectorBox],
        ]) {
          if (!box || box.bottom > bottomLimit || box.top < -2) {
            failures.push(`${viewport.name}/${state}: desktop ${label} should fit inside the visible review workbench`);
          }
        }
        if ((stateValue.studioObjectListBox?.height || 0) < 160) {
          failures.push(`${viewport.name}/${state}: desktop review object list should keep enough vertical room for scanning tracks`);
        }
      }
    }
    if (state === "workflow-partial-success" && (!stateValue.studioPartialDiagnosticVisible || !/Partial result is reviewable|sam3_grid_023|frame 41/.test(stateValue.studioPartialDiagnosticText))) {
      failures.push(`${viewport.name}/${state}: partial success should keep completed objects reviewable and show the failed object/frame diagnostic`);
    }
    if (state === "workflow-export") {
      if (stateValue.workflowPrimaryLabel !== "Export MotionJSON" && stateValue.workflowPrimaryLabel !== "Validate export") {
        failures.push(`${viewport.name}/${state}: export screen should promote Export MotionJSON or the exact blocked export action`);
      }
      if (stateValue.studioReviewTitle !== "Export MotionJSON" || !stateValue.studioExportCardVisible || stateValue.studioObjectListVisible || !/Included objects|Rights note/.test(stateValue.studioExportIncludedText)) {
        failures.push(`${viewport.name}/${state}: export screen should show package readiness, included objects, and rights notes instead of the review object list`);
      }
      if (stateValue.reviewCandidateSlotVisible && /Track selected|not background|coverage/i.test(stateValue.reviewCandidateSlotText)) {
        failures.push(`${viewport.name}/${state}: export screen should not show candidate filter/track controls ahead of the export gate`);
      }
      if (viewport.width <= 1180 && stateValue.reviewToolsVisible && stateValue.studioExportCardVisible) {
        const exportTop = stateValue.studioExportCardBox?.top ?? 0;
        const toolsTop = stateValue.reviewToolsBox?.top ?? 0;
        if (toolsTop && exportTop && toolsTop < exportTop) {
          failures.push(`${viewport.name}/${state}: mobile export screen should show the export checklist before review tools`);
        }
      }
      if (viewport.width >= 1366) {
        const bottomLimit = (stateValue.viewportHeight || viewport.height) + 2;
        for (const [label, box] of [
          ["export checklist", stateValue.studioExportCardBox],
          ["review tools", stateValue.reviewToolsBox],
        ]) {
          if (!box || box.bottom > bottomLimit || box.top < -2) {
            failures.push(`${viewport.name}/${state}: desktop ${label} should fit inside the visible export workbench`);
          }
        }
      }
    }
    if (["export-gate", "export-handoff", "export-success", "copyable-snippet"].includes(state)) {
      if (stateValue.studioReviewTitle !== "Export MotionJSON" || !stateValue.studioExportCardVisible || stateValue.studioObjectListVisible) {
        failures.push(`${viewport.name}/${state}: export capture should show the export checklist instead of the review object list`);
      }
      if (stateValue.reviewCandidateSlotVisible && /Track selected|not background|coverage/i.test(stateValue.reviewCandidateSlotText)) {
        failures.push(`${viewport.name}/${state}: export capture should not show candidate filter/track controls ahead of the export gate`);
      }
      if (viewport.width <= 1180 && stateValue.reviewToolsVisible && stateValue.studioExportCardVisible) {
        const exportTop = stateValue.studioExportCardBox?.top ?? 0;
        const toolsTop = stateValue.reviewToolsBox?.top ?? 0;
        if (toolsTop && exportTop && toolsTop < exportTop) {
          failures.push(`${viewport.name}/${state}: mobile export capture should show the export checklist before review tools`);
        }
      }
    }
    if (state === "workflow-goal" && stateValue.fixedFooterOcclusions.length) {
      failures.push(`${viewport.name}/${state}: fixed workflow footer occludes ${stateValue.fixedFooterOcclusions.join(", ")}`);
    }
    if (state === "workflow-review-failure") {
      const expectedJobId = `job_${state}_layout`;
      if (!stateValue.mainJobCenterVisible || !stateValue.mainSelectedJobFactsText.includes(expectedJobId) || !stateValue.mainJobListText.includes(expectedJobId)) {
        failures.push(`${viewport.name}/${state}: failed run step should expose the selected current job in the main job center`);
      }
    }
    if (state === "workflow-review" && stateValue.mainRunStatusText !== "succeeded") {
      failures.push(`${viewport.name}/${state}: completed review fixture should show succeeded in the main job center`);
    }
    if (
      state === "workflow-review-failure" &&
      (stateValue.mainRunStatusText !== "failed" || !/SAM3 Scene Sweep runtime unavailable|vector tracks were not produced/.test(`${stateValue.mainJobListText} ${stateValue.mainSelectedJobFactsText}`))
    ) {
      failures.push(`${viewport.name}/${state}: failed review job center should show failed status and provider failure messaging`);
    }
    if (state === "workflow-review" && stateValue.runLogsOpen) {
      failures.push(`${viewport.name}/${state}: review step should keep logs collapsed unless the run failed`);
    }
    if (state === "workflow-review-failure" && (stateValue.runMonitorSummaryCount < 1 || !stateValue.runLogsOpen)) {
      failures.push(`${viewport.name}/${state}: failed run state should surface run summary and logs without extra discovery`);
    }
    if (state === "workflow-correct" && (!stateValue.studioReviewVisible || stateValue.studioObjectRowCount < 1)) {
      failures.push(`${viewport.name}/${state}: correction step should keep reviewed objects visible`);
    }
    if (state === "workflow-export" && stateValue.exportArtifactsOpen) {
      failures.push(`${viewport.name}/${state}: export step should keep generated artifact browser collapsed until requested`);
    }
    if (state === "workflow-export" && !stateValue.exportHandoffText && !stateValue.exportSummaryText) {
      failures.push(`${viewport.name}/${state}: export screen should show export handoff or summary content`);
    }
    if (state === "workflow-export" && stateValue.visibleExportPrimaryCount > 1) {
      failures.push(`${viewport.name}/${state}: export screen should expose one primary export/validate action, found ${stateValue.visibleExportPrimaryCount}`);
    }
    if (state === "job-review") {
      const reviewText = `${stateValue.mainJobListText} ${stateValue.mainSelectedJobFactsText} ${stateValue.eventLogText} ${stateValue.studioExportDecisionText} ${stateValue.exportSummaryText}`.trim();
      if (!stateValue.mainJobCenterVisible && !stateValue.studioReviewVisible && reviewText.length < 80) {
        failures.push(`${viewport.name}/${state}: job-review capture rendered blank review/diagnostics content`);
      }
    }
    const expectedWorkflowStep = workflowStates[state];
    if (expectedWorkflowStep) {
      const mobileRunCockpitOwnsAction = viewport.width <= 760 && expectedWorkflowStep === "run_monitor" && stateValue.runCockpitVisible;
      if (!mobileRunCockpitOwnsAction && (!stateValue.workflowPrimaryVisible || stateValue.visibleWorkflowPrimaryCount !== 1 || !stateValue.workflowPrimaryLabel)) {
        failures.push(`${viewport.name}/${state}: guided workflow should expose exactly one visible footer primary action`);
      }
      if (stateValue.workflowActiveStep !== expectedWorkflowStep) {
        failures.push(`${viewport.name}/${state}: active workflow step ${stateValue.workflowActiveStep || "none"} did not match ${expectedWorkflowStep}`);
      }
      const screenSteps = workflowScreenAliases[expectedWorkflowStep] || [expectedWorkflowStep];
      const panelSteps = screenSteps.flatMap((step) => workflowPanelAliases[step] || [step]);
      const activePanels = stateValue.workflowPanels.filter((panel) => panel.steps.some((step) => panelSteps.includes(step)));
      const inactivePanels = stateValue.workflowPanels.filter((panel) => !panel.steps.some((step) => panelSteps.includes(step)));
      const activeFragments = stateValue.workflowFragments.filter((fragment) => fragment.steps.some((step) => panelSteps.includes(step)));
      const inactiveFragments = stateValue.workflowFragments.filter((fragment) => !fragment.steps.some((step) => panelSteps.includes(step)));
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
      if (!stateValue.mainWorkflowOnly) {
        failures.push(`${viewport.name}/${state}: removed dashboard controls are still present`);
      }
      const visiblePanels = stateValue.workflowPanels.filter((panel) => panel.visible);
      if (visiblePanels.length < 2) {
        failures.push(`${viewport.name}/${state}: main workflow exposed too few inline panels (${visiblePanels.length})`);
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
      if (["prepare-sam3-single", "prepare-sam3-text", "prepare-sam3-trace-all", "prepare-pick-frame", "prepare-sam3-trace-all-runtime-ready", "prepare-sam3-trace-all-missing-runtime"].includes(state) && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), { captureBeyondViewport: true });
      }
      if (["job-review", "candidate-review", "correction-tools", "export-gate", "export-handoff", "export-success", "copyable-snippet"].includes(state) && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), { captureBeyondViewport: true });
      }
      if (state === "workflow-review-failure" && viewport.name === "mobile-390") {
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
        "workflow-keyboard",
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
