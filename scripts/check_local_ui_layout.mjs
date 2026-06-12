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
const requestedScreenshotTimeoutMs = Number(process.env.MOTIONJSON_UI_SCREENSHOT_TIMEOUT_MS || 15000);
const DEFAULT_SCREENSHOT_TIMEOUT_MS =
  Number.isFinite(requestedScreenshotTimeoutMs) && requestedScreenshotTimeoutMs > 0 ? requestedScreenshotTimeoutMs : 15000;
const requestedCdpTimeoutMs = Number(process.env.MOTIONJSON_UI_CDP_TIMEOUT_MS || 20000);
const DEFAULT_CDP_TIMEOUT_MS = Number.isFinite(requestedCdpTimeoutMs) && requestedCdpTimeoutMs > 0 ? requestedCdpTimeoutMs : 20000;
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
  const options = {
    check: false,
    screenshotDir: "",
    screenshotTimeoutMs: DEFAULT_SCREENSHOT_TIMEOUT_MS,
    states: STATES,
    viewports: VIEWPORTS,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--check") options.check = true;
    else if (arg === "--screenshot-dir") options.screenshotDir = argv[++index] || "";
    else if (arg === "--screenshot-timeout-ms") {
      options.screenshotTimeoutMs = Number(argv[++index] || "");
      if (!Number.isFinite(options.screenshotTimeoutMs) || options.screenshotTimeoutMs <= 0) {
        throw new Error("--screenshot-timeout-ms must be a positive number");
      }
    } else if (arg === "--state") options.states = (argv[++index] || "").split(",").filter(Boolean);
    else if (arg === "--viewport") {
      const names = new Set((argv[++index] || "").split(",").filter(Boolean));
      options.viewports = VIEWPORTS.filter((item) => names.has(item.name));
    } else if (arg === "--help" || arg === "-h") {
      console.log(`Usage: node scripts/check_local_ui_layout.mjs [--check] [--screenshot-dir DIR] [--screenshot-timeout-ms 15000] [--state real-empty-shell,nav-collapsed,diagnostics-open,workflow-goal,workflow-review,workflow-review-failure,workflow-keyboard,workflow-dashboard,first-run,model-setup,job-review,candidate-review,correction-tools,export-gate] [--viewport mobile-390,tablet-768,laptop-1366,desktop-1440]

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
    async send(method, params = {}, { timeoutMs = DEFAULT_CDP_TIMEOUT_MS } = {}) {
      await opened;
      const messageId = ++id;
      let timer = null;
      const response = new Promise((resolvePromise, reject) => {
        timer = setTimeout(() => {
          callbacks.delete(messageId);
          reject(new Error(`Timed out after ${timeoutMs}ms waiting for CDP ${method}`));
        }, timeoutMs);
        callbacks.set(messageId, {
          resolve: (value) => {
            clearTimeout(timer);
            resolvePromise(value);
          },
          reject: (error) => {
            clearTimeout(timer);
            reject(error);
          },
        });
      });
      socket.send(JSON.stringify({ id: messageId, method, params }));
      return response;
    },
    close() {
      socket.close();
    },
  };
}

async function waitForReady(cdp, capture, { timeoutMs = 15000 } = {}) {
  const startedAt = Date.now();
  const deadline = Date.now() + timeoutMs;
  let lastState = null;
  let lastError = "";
  let reloadAttempted = false;
  while (Date.now() < deadline) {
    try {
      const result = await cdp.send("Runtime.evaluate", {
        returnByValue: true,
        expression: `({
          href: location.href,
          ready: document.readyState,
          capture: document.documentElement.dataset.capture || "",
          captureReady: document.documentElement.dataset.captureReady || "",
          captureError: document.documentElement.dataset.captureError || "",
          bodyText: document.body?.innerText?.slice(0, 160) || ""
        })`,
      });
      const value = result.result.value || {};
      lastState = value;
      const navigated = capture ? String(value.href || "").includes("capture=") : !String(value.href || "").startsWith("about:");
      const ready = value.ready === "complete";
      const captureReady = capture ? value.captureReady === "true" : true;
      if (navigated && ready && captureReady) return;
      if (
        capture &&
        navigated &&
        !reloadAttempted &&
        !value.capture &&
        (value.ready === "interactive" || value.ready === "loading") &&
        Date.now() - startedAt > 2500
      ) {
        reloadAttempted = true;
        await cdp.send("Page.stopLoading").catch(() => {});
        await cdp.send("Page.reload", { ignoreCache: true }).catch(() => {});
      }
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
      // A navigation can destroy the previous execution context; retry.
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 120));
  }
  const detail = lastState
    ? `last=${JSON.stringify(lastState)}`
    : lastError
      ? `lastError=${lastError}`
      : "no page state observed";
  throw new Error(`Timed out waiting for UI capture readiness: ${capture} (${detail})`);
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
        .find((element) => !element.matches(".skip-link") && isVisible(element) && !element.disabled);
      if (focusTarget) {
        focusTarget.focus();
        const focusStyle = getComputedStyle(focusTarget);
        if (focusStyle.outlineStyle === "none" && focusStyle.boxShadow === "none") {
          const focusLabel = (
            focusTarget.getAttribute("aria-label") ||
            focusTarget.textContent ||
            focusTarget.getAttribute("id") ||
            focusTarget.tagName
          ).trim().replace(/\s+/g, " ").slice(0, 80);
          failures.push("visible focus target has no visible focus style: " + (focusLabel || focusTarget.tagName));
        }
        focusTarget.blur();
      }
      return { failures, viewportWidth, scrollWidth, boxes };
    })()`,
  });
  return result.result.value;
}

async function withTimeout(promise, timeoutMs, message) {
  let timer = null;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(message)), timeoutMs);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    clearTimeout(timer);
    promise.catch(() => {});
  }
}

async function captureScreenshot(cdp, path, { captureBeyondViewport = false, label = path, timeoutMs = DEFAULT_SCREENSHOT_TIMEOUT_MS } = {}) {
  await cdp.send("Page.bringToFront").catch(() => {});
  await cdp
    .send("Runtime.evaluate", {
      awaitPromise: true,
      expression: `new Promise((resolve) => requestAnimationFrame(() => resolve()))`,
    })
    .catch(() => {});
  const result = await withTimeout(
    cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport, fromSurface: true }, { timeoutMs }),
    timeoutMs,
    `Timed out after ${timeoutMs}ms capturing screenshot for ${label}`,
  );
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

async function checkState({ port, baseUrl, viewport, state, screenshotDir, screenshotTimeoutMs, failures }) {
  const isRealState = REAL_STATES.includes(state);
  const capture = isRealState ? "" : state;
  const url = capture ? `${baseUrl}/?capture=${encodeURIComponent(capture)}` : baseUrl;
  const page = await newPage(port, "about:blank");
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
    await waitForReady(cdp, capture, { timeoutMs: Math.max(15000, screenshotTimeoutMs) });
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
          const shell = document.querySelector(".app-shell");
          const visible = (element) => {
            if (!element) return false;
            const box = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden";
          };
          const boxFor = (selector) => {
            const element = document.querySelector(selector);
            if (!element || !visible(element)) return null;
            const box = element.getBoundingClientRect();
            return {
              left: Math.round(box.left),
              right: Math.round(box.right),
              width: Math.round(box.width),
            };
          };
          const journeyToggle = document.querySelector("#journeyNavToggle");
          window.__motionjsonCollapseProbe = null;
          if (window.innerWidth > 900) {
            const projectToggle = document.querySelector("#projectDrawerToggle");
            const sidebarToggle = document.querySelector("#sidebarToggle");
            if (projectToggle && shell?.classList.contains("is-sidebar-collapsed")) projectToggle.click();
            if (sidebarToggle && !shell?.classList.contains("is-sidebar-collapsed")) sidebarToggle.click();
            window.__motionjsonCollapseProbe = {
              sidebarCollapsed: shell?.classList.contains("is-sidebar-collapsed") || false,
              sidebarExpanded: sidebarToggle?.getAttribute("aria-expanded") || "",
              sidebarAriaHidden: document.querySelector("#workspaceSidebar")?.getAttribute("aria-hidden") || "",
              journeyBoxAfterProjectClose: boxFor("#journeyNav"),
              workspaceBoxAfterProjectClose: boxFor("#workspaceMain"),
              horizontalOverflowAfterProjectClose: document.documentElement.scrollWidth > window.innerWidth,
            };
          }
          if (window.innerWidth > 900 && visible(journeyToggle) && !shell?.classList.contains("is-journey-collapsed")) {
            journeyToggle.click();
          } else if (!shell?.classList.contains("is-sidebar-collapsed")) {
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
      "workflow-preflight": "prompt_preview",
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
            : state === "workflow-preflight"
              ? '[data-journey-phase="preflight"]'
            : state === "workflow-review" || state === "workflow-partial-success"
              ? '[data-journey-phase="review"]'
              : `[data-workflow-step="${workflowStates[state]}"]`;
      await cdp.send("Runtime.evaluate", {
        expression: `
          document.querySelector('${workflowClickSelector}')?.click();
        `,
      });
      await cdp.send("Runtime.evaluate", {
        awaitPromise: true,
        expression: `new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))`,
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
        const elementMetrics = (element) => {
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
        const elementBox = (selector) => {
          const element = document.querySelector(selector);
          if (!element || !visible(element)) return null;
          return elementMetrics(element);
        };
        return {
          viewportHeight: window.innerHeight,
          viewportWidth: window.innerWidth,
          sidebarCollapsed: shell?.classList.contains("is-sidebar-collapsed") || false,
          journeyCollapsed: shell?.classList.contains("is-journey-collapsed") || false,
          railCollapsed: shell?.classList.contains("is-rail-collapsed") || false,
          railVisible: visible(rightRail),
          horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
          detailsExpanded: [...(rightRail?.querySelectorAll("details") || [])].some((details) => details.open === true) ? "true" : "false",
          sidebarContentAriaHidden: document.querySelector("#sidebarNavigationContent")?.getAttribute("aria-hidden") || "",
          sidebarContentInert: document.querySelector("#sidebarNavigationContent")?.inert === true,
          railAriaHidden: rightRail?.getAttribute("aria-hidden") || "",
          railInert: rightRail?.inert === true,
          sidebarExpanded: document.querySelector("#sidebarToggle")?.getAttribute("aria-expanded") || "",
          sidebarControls: document.querySelector("#sidebarToggle")?.getAttribute("aria-controls") || "",
          sidebarLabel: document.querySelector("#sidebarToggle")?.getAttribute("aria-label") || document.querySelector("#sidebarToggle")?.textContent?.trim() || "",
          journeyToggleExpanded: document.querySelector("#journeyNavToggle")?.getAttribute("aria-expanded") || "",
          journeyToggleLabel: document.querySelector("#journeyNavToggle")?.textContent?.trim() || "",
          journeyToggleVisible: visible(document.querySelector("#journeyNavToggle")),
          collapseProbe: window.__motionjsonCollapseProbe || null,
          journeyNavBox: elementBox("#journeyNav"),
          journeyPhaseOrder: [...document.querySelectorAll("#journeyNav [data-journey-phase]")].map((button) => button.dataset.journeyPhase || ""),
          activeJourneyButtonBox: elementBox("#journeyNav [data-journey-phase].is-active"),
          journeyNavScrollLeft: document.querySelector("#journeyNav")?.scrollLeft || 0,
          journeyNavScrollWidth: document.querySelector("#journeyNav")?.scrollWidth || 0,
          journeyNavClientWidth: document.querySelector("#journeyNav")?.clientWidth || 0,
          activeJourneyOffsetLeft: document.querySelector("#journeyNav [data-journey-phase].is-active")?.closest("li")?.offsetLeft || 0,
          activeJourneyPhase: document.querySelector("#journeyNav [data-journey-phase].is-active")?.dataset.journeyPhase || "",
          journeyPhaseCount: document.querySelectorAll("#journeyNav [data-journey-phase]").length,
          workspaceBox: elementBox("#workspaceMain"),
          workspaceGridBox: elementBox(".workspace-grid"),
          shellGridColumns: shell ? getComputedStyle(shell).gridTemplateColumns : "",
          projectDrawerButtonExpanded: document.querySelector("#projectDrawerToggle")?.getAttribute("aria-expanded") || "",
          projectDrawerButtonControls: document.querySelector("#projectDrawerToggle")?.getAttribute("aria-controls") || "",
          projectDrawerBox: elementBox("#workspaceSidebar"),
          projectDrawerVisible: visible(document.querySelector("#workspaceSidebar")),
          projectDrawerAriaHidden: document.querySelector("#workspaceSidebar")?.getAttribute("aria-hidden") || "",
          mainWorkflowOnly: !document.querySelector("#detailsToggle") && !document.querySelector("#workflowDashboardToggle"),
          railCloseControls: document.querySelector("#railCloseButton")?.getAttribute("aria-controls") || "",
          railCloseVisible: visible(document.querySelector("#railCloseButton")),
          rightRailWidth: Math.round(rightRailBox?.width || 0),
          workflowKeyshortcuts: document.querySelector("#workflowStepper")?.getAttribute("aria-keyshortcuts") || "",
          legacyWorkflowStepperVisible: visible(document.querySelector("#workflowStepper")),
          legacyProgressMirrorVisible: visible(document.querySelector("#studioProgressStepper")),
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
          targetSourceRequiredVisible: visible(document.querySelector("#targetSourceRequired")),
          targetSourceRequiredText: document.querySelector("#targetSourceRequired")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          targetSourceRequiredStepCount: [...document.querySelectorAll("#targetSourceRequired .source-required-steps li")].filter(visible).length,
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
          browserPreviewBox: elementBox("#browserPreviewCard"),
          setupPanelTitle: document.querySelector("#setupPanelTitle")?.textContent?.trim() || "",
          uploadDropzoneVisible: visible(document.querySelector("#directUploadCard")),
          uploadDropzoneBox: elementBox("#directUploadCard"),
          guidedProjectSummaryBox: elementBox("#guidedProjectSummary"),
          topbarActionClipping: (() => {
            const actions = document.querySelector(".topbar-actions");
            if (!actions || !visible(actions)) return false;
            const actionBox = actions.getBoundingClientRect();
            return [...actions.children].filter(visible).some((child) => {
              const box = child.getBoundingClientRect();
              return (
                box.left < actionBox.left - 1 ||
                box.right > actionBox.right + 1
              );
            });
          })(),
          wizardPanelTitle: document.querySelector("#wizardPanelTitle")?.textContent?.trim() || "",
          wizardPanelVisible: visible(document.querySelector(".wizard-panel")),
          configPanelTitle: document.querySelector("#configPanelTitle")?.textContent?.trim() || "",
          configPanelVisible: visible(document.querySelector(".config-panel")),
          modelSetupTitle: document.querySelector("#modelSetupPanel h2")?.textContent?.trim() || "",
          modelSetupStatusText: document.querySelector("#modelSetupStatus")?.textContent?.trim() || "",
          modelSetupStatusAria: document.querySelector("#modelSetupStatus")?.getAttribute("aria-label") || "",
          modelSetupGuidedTitle: document.querySelector("#modelSetupPanel .model-setup-recommendation-title")?.textContent?.trim() || "",
          modelSetupSourceRequiredVisible: visible(document.querySelector("#modelSetupPanel .source-required-stage")),
          modelSetupSourceRequiredText: document.querySelector("#modelSetupPanel .source-required-stage")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          modelSetupSourceRequiredStepCount: [...document.querySelectorAll("#modelSetupPanel .source-required-steps li")].filter(visible).length,
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
          modelSetupPrimaryActionAria: document.querySelector("#modelSetupPanel .model-setup-normal-actions > button")?.getAttribute("aria-label") || "",
          modelSetupRescanCount: document.querySelectorAll("#modelSetupPanel [data-model-setup-action='rescan-runtime']").length,
          modelSetupUseAnywayOutsideAdvancedCount: [...document.querySelectorAll("#modelSetupPanel button")].filter((button) => /Use this anyway/i.test(button.textContent || "") && !button.closest(".model-setup-advanced")).length,
          modelSetupUseAnywayAdvancedCount: [...document.querySelectorAll("#modelSetupPanel .model-setup-advanced button")].filter((button) => /Use this anyway/i.test(button.textContent || "")).length,
          modelSetupScanErrorText: document.querySelector("#modelSetupPanel .model-setup-scan-error")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          modelSetupNormalSecretInputCount: [...document.querySelectorAll("#modelSetupPanel .model-setup-guided-card input[type='password'], #modelSetupPanel .model-setup-guided-card [data-model-setup-field='apiKey'], #modelSetupPanel .model-setup-guided-card [data-model-setup-field='hfToken']")].filter(visible).length,
          modelSetupConfirmationVisible: visible(document.querySelector(".model-setup-confirmation")),
          modelSetupConfirmationText: document.querySelector(".model-setup-confirmation")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          modelSetupProgressVisible: visible(document.querySelector(".model-setup-progress-card")),
          modelSetupProgressText: document.querySelector(".model-setup-progress-card")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          runPlanSummaryVisible: visible(document.querySelector("#runPlanSummary")),
          runPlanListBox: elementBox("#runPlanSummary .run-plan-list"),
          runPlanStepBoxes: [...document.querySelectorAll("#runPlanSummary .run-plan-step")].filter(visible).map(elementMetrics),
          rawConfigOpen: document.querySelector("#rawConfigDisclosure")?.open === true,
          configSaveLoadOpen: document.querySelector(".compact-advanced-actions")?.open === true,
          startMockText: document.querySelector("#startMockRunButton")?.textContent?.trim() || "",
          videoFormVisible: visible(document.querySelector("#videoForm")),
          postRunGuideVisible: visible(document.querySelector("#postRunGuide")),
          studioReviewVisible: visible(document.querySelector("#studioReviewPanel")),
          studioReviewTitle: document.querySelector("#studioReviewTitle")?.textContent?.trim() || "",
          studioReviewModeKicker: document.querySelector("#studioReviewModeKicker")?.textContent?.trim() || "",
          studioObjectRowCount: document.querySelectorAll("#studioObjectList .studio-object-row").length,
          studioObjectRowOverflowCount: [...document.querySelectorAll("#studioObjectList .studio-object-row")]
            .filter((element) => visible(element) && element.scrollHeight - element.clientHeight > 2)
            .length,
          studioObjectRowClippedByListCount: (() => {
            const list = document.querySelector("#studioObjectList");
            if (!list || !visible(list)) return 0;
            const listBox = list.getBoundingClientRect();
            return [...list.querySelectorAll(".studio-object-row")]
              .filter((element) => {
                if (!visible(element)) return false;
                const box = element.getBoundingClientRect();
                return box.top < listBox.bottom - 2 && box.bottom > listBox.bottom + 2;
              })
              .length;
          })(),
          studioObjectListVisible: visible(document.querySelector("#studioObjectList")),
          studioExportCardVisible: visible(document.querySelector("#studioExportCard")),
          studioExportIncludedText: document.querySelector("#studioExportIncludedObjects")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          studioExportReuseGuideVisible: visible(document.querySelector("#studioExportReuseGuide")),
          studioExportReuseGuideText: document.querySelector("#studioExportReuseGuide")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          studioExportReuseActionCount: [...document.querySelectorAll("#studioExportReuseGuide [data-export-handoff-action]")]
            .filter((element) => visible(element))
            .length,
          studioExportReuseRowOverflowCount: [...document.querySelectorAll("#studioExportReuseGuide .studio-export-reuse-row")]
            .filter((element) => visible(element) && (element.scrollHeight - element.clientHeight > 2 || element.scrollWidth - element.clientWidth > 2))
            .length,
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
          wizardPanelBox: elementBox(".wizard-panel"),
          reviewToolsVisible: visible(document.querySelector(".review-tools-panel")),
          reviewToolsText: document.querySelector(".review-tools-panel")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          reviewToolsBox: elementBox(".review-tools-panel"),
          studioExportCardBox: elementBox("#studioExportCard"),
          postRunStageCount: document.querySelectorAll("#postRunGuideList .post-run-stage").length,
          runMonitorSummaryCount: document.querySelectorAll("#runMonitorSummary .status-summary-card").length,
          runMonitorSummaryText: document.querySelector("#runMonitorSummary")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          reviewStatusSummaryCount: document.querySelectorAll("#reviewStatusSummary .status-summary-card").length,
          correctionStatusSummaryCount: document.querySelectorAll("#correctionStatusSummary .status-summary-card").length,
          correctionTrackVisible: visible(document.querySelector("#correctionTrackSelect")),
          correctionLabelVisible: visible(document.querySelector("#correctionLabelInput")),
          correctionRelabelVisible: visible(document.querySelector("#relabelTrackButton")),
          correctionRangeVisible: visible(document.querySelector("#correctionFrameStart")) && visible(document.querySelector("#correctionFrameEnd")),
          correctionActionsVisible: visible(document.querySelector(".correction-actions")),
          correctionActionsText: document.querySelector(".correction-actions")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          correctionActionsBox: elementBox(".correction-actions"),
          correctionActionButtonClippedCount: (() => {
            const actions = document.querySelector(".correction-actions");
            if (!actions || !visible(actions)) return 0;
            const footer = document.querySelector("[data-testid='command-footer']");
            const footerTop = visible(footer) ? footer.getBoundingClientRect().top : window.innerHeight;
            const actionBox = actions.getBoundingClientRect();
            return [...actions.querySelectorAll("button")].filter((button) => {
              if (!visible(button)) return false;
              const box = button.getBoundingClientRect();
              return box.bottom > footerTop - 1 || box.left < actionBox.left - 1 || box.right > actionBox.right + 1 || box.top < actionBox.top - 1 || box.bottom > actionBox.bottom + 1;
            }).length;
          })(),
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
          candidateNestedButtonCount: document.querySelectorAll("[data-testid='candidate-list'] button button").length,
          runEventsText: document.querySelector("[data-testid='run-events']")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          runEventsSectionBox: elementBox(".run-events-section"),
          runEventsListBox: elementBox("[data-testid='run-events']"),
          runEventRowCount: [...document.querySelectorAll("[data-testid='run-events'] .run-event-row")].filter(visible).length,
          runEventFullyVisibleRowCount: (() => {
            const list = document.querySelector("[data-testid='run-events']");
            if (!list || !visible(list)) return 0;
            const listBox = list.getBoundingClientRect();
            const footer = document.querySelector("[data-testid='command-footer']");
            const footerTop = visible(footer) ? footer.getBoundingClientRect().top : window.innerHeight;
            const visibleBottom = Math.min(listBox.bottom, footerTop);
            return [...list.querySelectorAll(".run-event-row")].filter((row) => {
              if (!visible(row)) return false;
              const box = row.getBoundingClientRect();
              return box.top >= listBox.top - 1 && box.bottom <= visibleBottom + 1;
            }).length;
          })(),
          runEventRowOverflowCount: [...document.querySelectorAll("[data-testid='run-events'] .run-event-row")]
            .filter((row) => visible(row) && (row.scrollHeight - row.clientHeight > 2 || row.scrollWidth - row.clientWidth > 2))
            .length,
          runEventListClientHeight: document.querySelector("[data-testid='run-events']")?.clientHeight || 0,
          runTemporalTimelineVisible: visible(document.querySelector("#runTemporalTimeline")),
          runTemporalTimelineBox: elementBox("#runTemporalTimeline"),
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
          runRecoveryVisible: visible(document.querySelector("#runRecoveryStrip")),
          runRecoveryText: document.querySelector("#runRecoveryStrip")?.textContent?.trim().replace(/\\s+/g, " ") || "",
          runRecoveryCopyBox: elementBox("#runRecoveryStrip > div:first-child"),
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
              "#studioExportReuseGuide .studio-export-reuse-row",
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
          commandFooterBox: elementBox("[data-testid='command-footer']"),
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
    if (state === "nav-collapsed" && stateValue.viewportWidth > 900) {
      if (!stateValue.journeyCollapsed || stateValue.journeyToggleExpanded !== "false") {
        failures.push(`${viewport.name}/${state}: journey menu did not collapse with aria-expanded=false`);
      }
      if (stateValue.journeyToggleLabel !== "Expand") {
        failures.push(`${viewport.name}/${state}: collapsed journey menu should expose an Expand control`);
      }
      if (!stateValue.journeyNavBox || stateValue.journeyNavBox.width > 80) {
        failures.push(`${viewport.name}/${state}: collapsed journey menu should be a compact rail`);
      }
      if (!stateValue.workspaceBox || stateValue.workspaceBox.left < (stateValue.journeyNavBox?.right || 0)) {
        failures.push(`${viewport.name}/${state}: workspace should start after the collapsed journey rail`);
      }
      if (stateValue.horizontalOverflow) {
        failures.push(`${viewport.name}/${state}: collapsed journey menu should not create horizontal overflow`);
      }
      const closeProbe = stateValue.collapseProbe || {};
      const closeJourneyBox = closeProbe.journeyBoxAfterProjectClose || null;
      const closeWorkspaceBox = closeProbe.workspaceBoxAfterProjectClose || null;
      if (!closeProbe.sidebarCollapsed || closeProbe.sidebarExpanded !== "false" || closeProbe.sidebarAriaHidden !== "true") {
        failures.push(`${viewport.name}/${state}: project menu close should restore the collapsed drawer accessibility state before journey collapse`);
      }
      if (!closeJourneyBox || closeJourneyBox.width < 220 || closeJourneyBox.width > 300) {
        failures.push(`${viewport.name}/${state}: closing the project menu should restore the full journey rail before compacting it`);
      }
      if (!closeWorkspaceBox || closeWorkspaceBox.left < (closeJourneyBox?.right || 0) - 1) {
        failures.push(`${viewport.name}/${state}: closing the project menu should keep workspace aligned after the restored journey rail`);
      }
      if (closeProbe.horizontalOverflowAfterProjectClose) {
        failures.push(`${viewport.name}/${state}: closing the project menu should not create horizontal overflow`);
      }
    }
    if (state === "workflow-goal" && stateValue.viewportWidth > 900 && stateValue.viewportWidth <= 1100) {
      if (!stateValue.journeyCollapsed || stateValue.journeyToggleExpanded !== "false" || stateValue.journeyToggleLabel !== "Expand") {
        failures.push(`${viewport.name}/${state}: narrow desktop journey menu should auto-collapse with a truthful Expand control`);
      }
      if (!stateValue.journeyNavBox || stateValue.journeyNavBox.width > 80) {
        failures.push(`${viewport.name}/${state}: narrow desktop journey menu should use the compact rail width`);
      }
    }
    if (["workflow-review", "workflow-correct", "workflow-export", "workflow-partial-success", "candidate-review", "correction-tools", "export-gate", "export-handoff", "export-success", "copyable-snippet"].includes(state) && stateValue.viewportWidth > 900) {
      if (!stateValue.journeyNavBox || !stateValue.workspaceBox || stateValue.workspaceBox.left < stateValue.journeyNavBox.right - 1) {
        failures.push(`${viewport.name}/${state}: result workbench should start after the visible journey rail`);
      }
      if (stateValue.studioObjectRowOverflowCount > 0) {
        failures.push(`${viewport.name}/${state}: reviewed object rows should not clip or overlap their status content`);
      }
    }
    if (["real-empty-shell", "workflow-goal"].includes(state) && stateValue.projectDrawerVisible) {
      failures.push(`${viewport.name}/${state}: project drawer should stay closed in the default guided first-run screen`);
    }
    if (state === "project-drawer-open" && (stateValue.sidebarCollapsed || !stateValue.projectDrawerVisible || stateValue.projectDrawerButtonExpanded !== "true" || stateValue.sidebarContentAriaHidden === "true" || stateValue.sidebarContentInert)) {
      failures.push(`${viewport.name}/${state}: project drawer should open with visible, interactive project controls`);
    }
    if (
      state === "project-drawer-open" &&
      viewport.width > 900 &&
      (!stateValue.projectDrawerBox || !stateValue.workspaceBox || stateValue.workspaceBox.left < stateValue.projectDrawerBox.right - 1)
    ) {
      failures.push(`${viewport.name}/${state}: project drawer should reserve its visible width instead of clipping the command bar`);
    }
    if (state === "diagnostics-open" && viewport.width > 1180 && (stateValue.railCollapsed || !stateValue.railVisible || stateValue.detailsExpanded !== "true")) {
      failures.push(`${viewport.name}/${state}: diagnostics rail did not open accessibly`);
    }
    if (state === "diagnostics-open" && stateValue.railVisible && !stateValue.railCloseVisible) {
      failures.push(`${viewport.name}/${state}: diagnostics drawer should expose a visible close button`);
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
    if (stateValue.legacyWorkflowStepperVisible || stateValue.legacyProgressMirrorVisible) {
      failures.push(`${viewport.name}/${state}: legacy workflow progress controls must stay hidden behind the journey nav`);
    }
    if (!stateValue.workflowKeyshortcuts.includes("ArrowRight") || !stateValue.workflowKeyshortcuts.includes("ArrowDown") || !stateValue.workflowKeyshortcuts.includes("ArrowLeft") || !stateValue.workflowKeyshortcuts.includes("ArrowUp") || !stateValue.workflowKeyshortcuts.includes("Home") || !stateValue.workflowKeyshortcuts.includes("End")) {
      failures.push(`${viewport.name}/${state}: hidden compatibility workflow control should retain keyboard navigation shortcuts`);
    }
    if (state === "workflow-keyboard" && (stateValue.workflowActiveStep !== "source_video" || stateValue.workflowFocusedStep !== "source_video")) {
      failures.push(`${viewport.name}/${state}: keyboard sequence should move active/focused workflow step to Source (start=${stateValue.workflowFocusStart || "none"}, active=${stateValue.workflowActiveStep || "none"}, focus=${stateValue.workflowFocusedStep || "none"}, element=${stateValue.workflowFocusedElement || "none"})`);
    }
    if (state === "workflow-goal" && (stateValue.workflowPrimaryLabel !== "Continue to source" || stateValue.workflowBackDisabled !== true || stateValue.browserPreviewTitle !== "Preview not ready")) {
      failures.push(`${viewport.name}/${state}: goal step should start with Continue to source, no back action, and preview not ready`);
    }
    if (state === "workflow-goal" && stateValue.visibleGoalCardCount !== 4) {
      failures.push(`${viewport.name}/${state}: first goal screen should show four storyboard primary goal cards before advanced tasks`);
    }
    if (stateValue.journeyPhaseCount !== 10) {
      failures.push(`${viewport.name}/${state}: journey should expose ten workflow phases including Reuse`);
    }
    const expectedJourneyOrder = "goal,source,target,model,preflight,run,review,correct,export,reuse";
    if (stateValue.journeyPhaseOrder.join(",") !== expectedJourneyOrder) {
      failures.push(`${viewport.name}/${state}: journey order should be ${expectedJourneyOrder}`);
    }
    if (stateValue.viewportWidth <= 720 && stateValue.topbarActionClipping) {
      failures.push(`${viewport.name}/${state}: mobile command bar should not clip status, help, or settings controls`);
    }
    if (state === "workflow-video" && stateValue.viewportWidth <= 720) {
      if (!stateValue.uploadDropzoneVisible || !stateValue.uploadDropzoneBox) {
        failures.push(`${viewport.name}/${state}: mobile source step should show the source upload control`);
      } else {
        const footerTop = stateValue.footerBox?.top ?? stateValue.viewportHeight;
        if (stateValue.uploadDropzoneBox.top >= footerTop - 24) {
          failures.push(`${viewport.name}/${state}: mobile source upload control should start above the fixed footer`);
        }
        if (stateValue.guidedProjectSummaryBox && stateValue.uploadDropzoneBox.top > stateValue.guidedProjectSummaryBox.top) {
          failures.push(`${viewport.name}/${state}: mobile source upload control should appear before project metadata`);
        }
      }
    }
    if (
      state === "workflow-video" &&
      stateValue.viewportWidth > 720 &&
      stateValue.guidedProjectSummaryBox &&
      stateValue.uploadDropzoneBox &&
      stateValue.uploadDropzoneBox.top > stateValue.guidedProjectSummaryBox.top
    ) {
      failures.push(`${viewport.name}/${state}: source upload control should lead project metadata in the normal workflow`);
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
    if (state === "workflow-video" && stateValue.browserPreviewTitle === "Preview not ready" && (stateValue.browserPreviewBox?.height || 0) > 120) {
      failures.push(`${viewport.name}/${state}: empty source preview should stay compact before a video is selected`);
    }
    if (state === "preview-failed" && (stateValue.browserPreviewTitle !== "Preview failed" || stateValue.workflowPrimaryLabel !== "Retry preview")) {
      failures.push(`${viewport.name}/${state}: preview failure state should surface Retry preview with a real preview failure message`);
    }
    const isSourceBlockedProvider = state === "workflow-provider" && stateValue.browserPreviewTitle === "Preview not ready";
    const isModelSetupState = state === "workflow-provider" || state.startsWith("model-setup");
    const isGuidedModelSetupState = isModelSetupState && state !== "model-setup-capability-error" && !isSourceBlockedProvider;
    if (state === "workflow-provider" && stateValue.modelSetupTitle !== "Recommended model setup") {
      failures.push(`${viewport.name}/${state}: provider step title should focus on the guided runtime recommendation`);
    }
    if (state === "workflow-provider" && stateValue.browserPreviewTitle === "Preview not ready" && stateValue.workflowPrimaryLabel !== "Add source video") {
      failures.push(`${viewport.name}/${state}: model step without a source video should route back to source setup`);
    }
    if (state === "workflow-provider" && stateValue.browserPreviewTitle === "Preview not ready") {
      if (stateValue.modelSetupStatusText !== "Needs source" || !stateValue.modelSetupSourceRequiredVisible) {
        failures.push(`${viewport.name}/${state}: model step without a source video should show a source-required model setup state`);
      }
      if (stateValue.modelSetupSourceRequiredStepCount < 3 || !/Choose a local file|demo video/i.test(stateValue.modelSetupSourceRequiredText) || !/local-first provider path/i.test(stateValue.modelSetupSourceRequiredText)) {
        failures.push(`${viewport.name}/${state}: model source-required state should explain the source, preview, and provider recommendation sequence`);
      }
      if (stateValue.modelSetupGuidedTitle) {
        failures.push(`${viewport.name}/${state}: model step without a source video should not expose a ready provider recommendation`);
      }
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
    if (isModelSetupState && !isSourceBlockedProvider && stateValue.modelSetupRescanCount < 1) {
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
    if (state === "workflow-prompts" && stateValue.browserPreviewTitle === "Preview not ready" && stateValue.workflowPrimaryLabel !== "Add source video") {
      failures.push(`${viewport.name}/${state}: target step without a source video should route back to source setup`);
    }
    if (state === "workflow-prompts" && stateValue.browserPreviewTitle === "Preview not ready") {
      if (!stateValue.targetSourceRequiredVisible || !/Add a source video/i.test(stateValue.targetSourceRequiredText)) {
        failures.push(`${viewport.name}/${state}: target step without a source video should show one source-required work surface`);
      }
      if (stateValue.targetSourceRequiredStepCount < 3 || !/browser-safe preview/i.test(stateValue.targetSourceRequiredText) || !/Target tools/i.test(stateValue.targetSourceRequiredText)) {
        failures.push(`${viewport.name}/${state}: target source-required state should explain the source, frame, and target-tool sequence`);
      }
      if (stateValue.viewerToolbarVisible || stateValue.pointToolVisible || stateValue.wizardPanelVisible || stateValue.configPanelVisible) {
        failures.push(`${viewport.name}/${state}: target step without a source video should hide prompt, wizard, and preflight controls`);
      }
    }
    if (state === "workflow-preflight") {
      if (stateValue.activeJourneyPhase !== "preflight") {
        failures.push(`${viewport.name}/${state}: preflight capture should activate the Preflight journey phase`);
      }
      if (!stateValue.configPanelVisible || stateValue.configPanelTitle !== "What will happen if I press Run?") {
        failures.push(`${viewport.name}/${state}: preflight should show the truthful run summary panel`);
      }
      if (
        viewport.width >= 1200 &&
        stateValue.runPlanListBox &&
        stateValue.runPlanStepBoxes?.length > 1 &&
        stateValue.runPlanStepBoxes.some((box) => box.width < stateValue.runPlanListBox.width - 12)
      ) {
        failures.push(`${viewport.name}/${state}: preflight summary should read as one confirmation list, not a multi-column card grid`);
      }
      if (stateValue.wizardPanelVisible || stateValue.viewerToolbarVisible) {
        failures.push(`${viewport.name}/${state}: preflight should not keep target prompt editing as the primary visible surface`);
      }
      if (stateValue.targetSourceRequiredVisible || stateValue.workflowPrimaryLabel === "Add source video") {
        failures.push(`${viewport.name}/${state}: preflight fixture should use a prepared source instead of the source-required gate`);
      }
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
    if (
      ["prepare-sam3-single", "prepare-sam3-text", "prepare-sam3-trace-all", "prepare-pick-frame", "prepare-sam3-trace-all-runtime-ready", "prepare-sam3-trace-all-missing-runtime"].includes(state) &&
      viewport.width >= 1200 &&
      stateValue.viewerPanelBox &&
      stateValue.wizardPanelBox &&
      stateValue.wizardPanelBox.left > stateValue.viewerPanelBox.left + 8 &&
      stateValue.wizardPanelBox.top < stateValue.viewerPanelBox.bottom - 8
    ) {
      failures.push(`${viewport.name}/${state}: target controls should stack inline below the source frame, not in a right-side setup rail`);
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
    if (state === "workflow-run" && stateValue.candidateNestedButtonCount > 0) {
      failures.push(`${viewport.name}/${state}: candidate/track rows should not contain nested interactive buttons`);
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
    if (state === "workflow-run" && viewport.width >= 1200) {
      const footerTop = stateValue.commandFooterBox?.top || stateValue.viewportHeight;
      if (!stateValue.runEventsSectionBox || stateValue.runEventsSectionBox.top >= footerTop - 24) {
        failures.push(`${viewport.name}/${state}: run events should be visible above the command footer in the first viewport`);
      }
      if (!stateValue.runEventsListBox || stateValue.runEventsListBox.top >= footerTop - 24) {
        failures.push(`${viewport.name}/${state}: run event rows should be readable above the command footer in the first viewport`);
      }
      const requiredRunEventRows = Math.min(3, stateValue.runEventRowCount || 3);
      if (
        stateValue.runEventFullyVisibleRowCount < requiredRunEventRows ||
        stateValue.runEventListClientHeight < requiredRunEventRows * 18
      ) {
        failures.push(`${viewport.name}/${state}: run event ledger should expose at least three full readable rows on desktop`);
      }
      if (stateValue.runEventRowOverflowCount > 0) {
        failures.push(`${viewport.name}/${state}: run event rows should not clip their own text or status chips`);
      }
      if (!stateValue.runTemporalTimelineBox || stateValue.runTemporalTimelineBox.top >= footerTop - 24) {
        failures.push(`${viewport.name}/${state}: run timeline should be visible above the command footer in the first viewport`);
      }
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
    if (
      state === "workflow-run-stale" &&
      (!stateValue.runRecoveryVisible ||
        !/Open logs/.test(stateValue.runRecoveryText) ||
        !/Copy debug report/.test(stateValue.runRecoveryText) ||
        !/Cancel run/.test(stateValue.runRecoveryText))
    ) {
      failures.push(`${viewport.name}/${state}: stale running job should expose first-viewport recovery actions`);
    }
    if (["workflow-run-stale", "workflow-run-asset-stalled"].includes(state) && stateValue.runRecoveryVisible && (stateValue.runRecoveryCopyBox?.width || 0) < 180) {
      failures.push(`${viewport.name}/${state}: run recovery copy should not collapse into unreadable vertical text`);
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
    if (
      state === "workflow-run-asset-stalled" &&
      (!stateValue.runRecoveryVisible ||
        !/Open logs/.test(stateValue.runRecoveryText) ||
        !/Copy debug report/.test(stateValue.runRecoveryText) ||
        !/Retry asset prep/.test(stateValue.runRecoveryText) ||
        !/Retry from Model setup/.test(stateValue.runRecoveryText))
    ) {
      failures.push(`${viewport.name}/${state}: terminal stalled run should expose first-viewport recovery actions`);
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
      if (stateValue.studioObjectRowClippedByListCount > 0) {
        failures.push(`${viewport.name}/${state}: review object list should not rest with a partially clipped candidate row`);
      }
      if (viewport.width >= 1366) {
        const bottomLimit = (stateValue.viewportHeight || viewport.height) + 2;
        if (!stateValue.studioInspectorVisible || !/Selected object|Runtime|Accelerator|Geometry|Motion/.test(stateValue.studioInspectorText)) {
          failures.push(`${viewport.name}/${state}: desktop review should expose selected-object diagnostics and runtime proof in the workbench`);
        }
        if (
          stateValue.studioInspectorBox &&
          stateValue.studioObjectListBox &&
          (stateValue.studioInspectorBox.left > stateValue.studioObjectListBox.left + 8 ||
            stateValue.studioInspectorBox.width < stateValue.studioObjectListBox.width - 12)
        ) {
          failures.push(`${viewport.name}/${state}: desktop selected-object diagnostics should be inline with the review list, not a right-side rail`);
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
      if (stateValue.activeJourneyPhase !== "export") {
        failures.push(`${viewport.name}/${state}: export validation screen should keep Export active before handoff reuse`);
      }
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
        if (
          stateValue.reviewToolsVisible &&
          stateValue.reviewToolsBox &&
          stateValue.studioExportCardBox &&
          (stateValue.reviewToolsBox.top <= stateValue.studioExportCardBox.top ||
            stateValue.reviewToolsBox.left > stateValue.studioExportCardBox.left + 8 ||
            stateValue.reviewToolsBox.width < stateValue.studioExportCardBox.width - 12)
        ) {
          failures.push(`${viewport.name}/${state}: desktop layer reuse checks should be inline below the export checklist, not a right-side rail`);
        }
        for (const [label, box] of [
          ["export checklist", stateValue.studioExportCardBox],
        ]) {
          if (!box || box.bottom > bottomLimit || box.top < -2) {
            failures.push(`${viewport.name}/${state}: desktop ${label} should fit inside the visible export workbench`);
          }
        }
      }
    }
    if (["export-gate", "export-handoff", "export-success", "copyable-snippet"].includes(state)) {
      const reuseHandoffState = ["export-success", "copyable-snippet"].includes(state);
      if (["export-success", "copyable-snippet"].includes(state) && stateValue.activeJourneyPhase !== "reuse") {
        failures.push(`${viewport.name}/${state}: exported handoff screen should activate the Reuse journey phase`);
      }
      if (reuseHandoffState && stateValue.workflowPrimaryLabel !== "Copy reuse steps") {
        failures.push(`${viewport.name}/${state}: reuse handoff screen should promote copying reusable object-layer steps`);
      }
      if (reuseHandoffState) {
        if (!stateValue.studioExportReuseGuideVisible) {
          failures.push(`${viewport.name}/${state}: reuse handoff screen should show inline object-layer handoff checks in the main workbench`);
        }
        const missingReuseTerms = ["Layer reuse checks", "Runtime snippet", "Copyable handoff steps", "MotionJSON scene", "Developer handoff"]
          .filter((term) => !stateValue.studioExportReuseGuideText.includes(term));
        if (missingReuseTerms.length) {
          failures.push(`${viewport.name}/${state}: reuse handoff screen is missing inline handoff terms: ${missingReuseTerms.join(", ")}`);
        }
        if (stateValue.studioExportReuseActionCount < 4) {
          failures.push(`${viewport.name}/${state}: reuse handoff screen should expose actionable open/copy handoff rows`);
        }
        if (stateValue.studioExportReuseRowOverflowCount) {
          failures.push(`${viewport.name}/${state}: reuse handoff rows should not clip or overflow their text/actions`);
        }
      } else if (stateValue.studioExportReuseGuideVisible) {
        failures.push(`${viewport.name}/${state}: pre-export checklist should not show reusable handoff actions before export succeeds`);
      }
      const expectedStudioTitle = reuseHandoffState ? "Reuse object layer" : "Export MotionJSON";
      if (stateValue.studioReviewTitle !== expectedStudioTitle || !stateValue.studioExportCardVisible || stateValue.studioObjectListVisible) {
        failures.push(`${viewport.name}/${state}: export capture should show the ${reuseHandoffState ? "reuse handoff" : "export checklist"} instead of the review object list`);
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
      if (viewport.width >= 1366 && stateValue.reviewToolsVisible && stateValue.studioExportCardVisible) {
        if (
          stateValue.reviewToolsBox &&
          stateValue.studioExportCardBox &&
          (stateValue.reviewToolsBox.top <= stateValue.studioExportCardBox.top ||
            stateValue.reviewToolsBox.left > stateValue.studioExportCardBox.left + 8 ||
            stateValue.reviewToolsBox.width < stateValue.studioExportCardBox.width - 12)
        ) {
          failures.push(`${viewport.name}/${state}: desktop export capture should keep reuse checks inline below the checklist, not in a side rail`);
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
    if (
      state === "workflow-correct" &&
      viewport.width > 900 &&
      (!stateValue.correctionTrackVisible || !stateValue.correctionLabelVisible || !stateValue.correctionRelabelVisible || !stateValue.correctionRangeVisible)
    ) {
      failures.push(`${viewport.name}/${state}: correction step should show relabel and frame range controls without clipping on desktop`);
    }
    if (state === "workflow-correct" && viewport.width > 900) {
      const footerTop = stateValue.commandFooterBox?.top || stateValue.viewportHeight;
      const gridBottom = stateValue.workspaceGridBox?.bottom || footerTop;
      const actionBottom = stateValue.correctionActionsBox?.bottom || 0;
      if (
        !stateValue.correctionActionsVisible ||
        !/Merge selected.*Split track.*Add from prompts.*Repair with prompts/i.test(stateValue.correctionActionsText) ||
        stateValue.correctionActionButtonClippedCount > 0 ||
        actionBottom > Math.min(footerTop, gridBottom) - 8
      ) {
        failures.push(`${viewport.name}/${state}: correction action buttons should be fully visible above the footer and inside the workbench`);
      }
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
      if (viewport.width <= 900 && stateValue.journeyNavBox && stateValue.activeJourneyButtonBox) {
        const activeJourneyVisible =
          stateValue.activeJourneyButtonBox.left >= stateValue.journeyNavBox.left - 2 &&
          stateValue.activeJourneyButtonBox.right <= Math.min(stateValue.viewportWidth, stateValue.journeyNavBox.right) + 2;
        if (!activeJourneyVisible) {
          failures.push(`${viewport.name}/${state}: active journey step should be fully visible in the mobile journey strip (scrollLeft=${stateValue.journeyNavScrollLeft}, scrollWidth=${stateValue.journeyNavScrollWidth}, clientWidth=${stateValue.journeyNavClientWidth}, activeOffset=${stateValue.activeJourneyOffsetLeft})`);
        }
      }
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
      const preflightUsesConfigPanelOnly = state === "workflow-preflight";
      if (!preflightUsesConfigPanelOnly && activeFragments.length && !activeFragments.some((fragment) => fragment.visible && !fragment.hidden && fragment.ariaHidden === "false" && !fragment.inert)) {
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
      if (visiblePanels.length !== 1) {
        failures.push(`${viewport.name}/${state}: normal workflow should keep one primary stage visible, not a dashboard of ${visiblePanels.length} panels`);
      }
    }
    if (screenshotDir) {
      const baseScreenshotOptions = {
        label: `${viewport.name}/${state}`,
        timeoutMs: screenshotTimeoutMs,
      };
      await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}.png`), baseScreenshotOptions);
      if (state === "advanced-config" && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), {
          ...baseScreenshotOptions,
          captureBeyondViewport: true,
          label: `${viewport.name}/${state} full`,
        });
      }
      if (state.startsWith("model-setup") && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), {
          ...baseScreenshotOptions,
          captureBeyondViewport: true,
          label: `${viewport.name}/${state} full`,
        });
      }
      if (state.startsWith("model-plan") && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), {
          ...baseScreenshotOptions,
          captureBeyondViewport: true,
          label: `${viewport.name}/${state} full`,
        });
      }
      if (["prepare-sam3-single", "prepare-sam3-text", "prepare-sam3-trace-all", "prepare-pick-frame", "prepare-sam3-trace-all-runtime-ready", "prepare-sam3-trace-all-missing-runtime"].includes(state) && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), {
          ...baseScreenshotOptions,
          captureBeyondViewport: true,
          label: `${viewport.name}/${state} full`,
        });
      }
      if (["job-review", "candidate-review", "correction-tools", "export-gate", "export-handoff", "export-success", "copyable-snippet"].includes(state) && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), {
          ...baseScreenshotOptions,
          captureBeyondViewport: true,
          label: `${viewport.name}/${state} full`,
        });
      }
      if (state === "workflow-review-failure" && viewport.name === "mobile-390") {
        await captureScreenshot(cdp, join(screenshotDir, `${viewport.name}-${state}-full.png`), {
          ...baseScreenshotOptions,
          captureBeyondViewport: true,
          label: `${viewport.name}/${state} full`,
        });
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
        await checkState({
          port,
          baseUrl: ui.baseUrl,
          viewport,
          state,
          screenshotDir: options.screenshotDir,
          screenshotTimeoutMs: options.screenshotTimeoutMs,
          failures,
        });
      }
    }

    if (postSeedStates.length) await seedJobReview(ui.baseUrl);

    for (const viewport of options.viewports) {
      for (const state of postSeedStates) {
        await checkState({
          port,
          baseUrl: ui.baseUrl,
          viewport,
          state,
          screenshotDir: options.screenshotDir,
          screenshotTimeoutMs: options.screenshotTimeoutMs,
          failures,
        });
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
