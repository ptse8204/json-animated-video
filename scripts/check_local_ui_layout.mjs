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
      console.log(`Usage: node scripts/check_local_ui_layout.mjs [--check] [--screenshot-dir DIR] [--state real-empty-shell,first-run,model-setup,job-review,candidate-review,correction-tools,export-gate] [--viewport mobile-390,tablet-768,laptop-1366,desktop-1440]

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
        expression: `document.querySelectorAll("details").forEach((details) => { details.open = true; })`,
      });
    }
    const layout = await evaluateLayout(cdp);
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

    const preSeedStates = options.states.filter((state) => state === "real-empty-shell" || state === "first-run");
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
