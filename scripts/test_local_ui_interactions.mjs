#!/usr/bin/env node
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
const E2E_TIMEOUT_MS = 150_000;

let tmp = "";
let ui = null;
let chrome = null;
let cdpPort = 0;

function delay(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
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
  if (process.platform === "darwin" && process.arch === "x64") return { command: "arch", args: ["-arm64", python] };
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
    child.once("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`Process exited before ${pattern}: ${code}`));
    });
  });
}

async function startUi(tmpRoot) {
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
      join(tmpRoot, "backend.sqlite"),
      "--storage-root",
      join(tmpRoot, "storage"),
    ],
    { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"] },
  );
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  const line = await waitForLine(child, "MotionJSON UI:");
  return { child, baseUrl: line.split("MotionJSON UI:", 2)[1].trim().replace(/\/$/, "") };
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

async function newTarget(port, url = "about:blank") {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
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

class BrowserPage {
  constructor(cdp, baseUrl) {
    this.cdp = cdp;
    this.baseUrl = baseUrl;
    this.consoleErrors = [];
    this.networkViolations = [];
    this.requestUrls = [];
    const localOrigin = new URL(baseUrl).origin;
    cdp.on("Runtime.exceptionThrown", (params) => {
      const details = params.exceptionDetails || {};
      this.consoleErrors.push(details.exception?.description || details.text || "page exception");
    });
    cdp.on("Runtime.consoleAPICalled", (params) => {
      if (params.type !== "error") return;
      const args = (params.args || []).map((arg) => arg.value || arg.description || "").filter(Boolean);
      this.consoleErrors.push(args.join(" ") || "console.error");
    });
    cdp.on("Log.entryAdded", (params) => {
      const entry = params.entry || {};
      if (entry.level === "error") this.consoleErrors.push(entry.text || "browser log error");
    });
    cdp.on("Network.requestWillBeSent", (params) => {
      const url = params.request?.url || "";
      if (!url) return;
      this.requestUrls.push(url);
      try {
        const parsed = new URL(url);
        if (/^https?:$/i.test(parsed.protocol) && parsed.origin !== localOrigin) {
          this.networkViolations.push(`external network request: ${url}`);
        }
      } catch {
        // Relative URLs are local.
      }
    });
  }

  async evaluate(fnOrSource, ...args) {
    const expression = typeof fnOrSource === "function" ? `(${fnOrSource})(...${JSON.stringify(args)})` : String(fnOrSource);
    const result = await this.cdp.send("Runtime.evaluate", {
      awaitPromise: true,
      returnByValue: true,
      expression,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Browser evaluation failed");
    }
    return result.result?.value;
  }

  async setViewport(width, height) {
    await this.cdp.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });
  }

  async goto(url) {
    await this.cdp.send("Page.navigate", { url });
    await this.waitFor(() => document.readyState === "complete", "page load", 20_000);
  }

  async openFresh() {
    await this.goto(this.baseUrl);
    await this.waitForTestId("local-ui-shell");
    await this.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await this.goto(this.baseUrl);
    await this.waitForTestId("local-ui-shell");
    await this.waitForText("body", /What do you want to do\?/i);
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

  async waitForText(selector, pattern, timeoutMs = 20_000) {
    await this.waitFor(
      (css, source, flags) => {
        const text = [...document.querySelectorAll(css)].map((element) => element.textContent || "").join("\n");
        return new RegExp(source, flags).test(text);
      },
      `${selector} text ${pattern}`,
      timeoutMs,
      selector,
      pattern.source,
      pattern.flags,
    );
  }

  async click(selector) {
    await this.evaluate((css) => {
      const element = document.querySelector(css);
      if (!element) throw new Error(`Missing selector ${css}`);
      if (element.disabled) throw new Error(`Disabled selector ${css}`);
      element.scrollIntoView({ block: "center", inline: "center" });
      element.focus?.();
      element.click();
      return true;
    }, selector);
    await delay(120);
  }

  async clickTestId(testId) {
    await this.click(`[data-testid="${String(testId).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"]`);
  }

  async waitForActivePhase(phase, timeoutMs = 20_000) {
    await this.waitFor(
      (expected) => document.querySelector("#journeyNav [data-journey-phase].is-active")?.dataset.journeyPhase === expected,
      `active journey phase ${phase}`,
      timeoutMs,
      phase,
    );
  }

  async activePhase() {
    return this.evaluate(() => document.querySelector("#journeyNav [data-journey-phase].is-active")?.dataset.journeyPhase || "");
  }

  async primaryLabel() {
    return this.evaluate(() => document.querySelector('[data-testid="workflow-primary"]')?.textContent?.trim() || "");
  }

  async auditVisibleControls(stageName) {
    const offenders = await this.evaluate(() => {
      const visible = (element) => {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden" && !element.hidden;
      };
      const contractAttrs = [
        "id",
        "data-testid",
        "data-workflow-step",
        "data-journey-phase",
        "data-ui-action",
        "data-action",
        "data-tool",
        "data-point-kind",
        "data-preset",
        "data-quality-preset",
        "data-device-preset",
        "data-model-setup-action",
        "data-export-handoff-action",
        "data-track-export",
        "data-track-merge",
        "data-track-visibility",
        "data-track-visible",
        "data-studio-track-visible",
        "data-studio-track-export",
        "data-timeline-frame",
        "data-candidate-row",
        "data-track-id",
        "data-object-id",
        "data-job-id",
        "data-video-id",
      ];
      return [...document.querySelectorAll("button, a[href], summary")]
        .filter((element) => visible(element) && !element.disabled)
        .map((element) => {
          const label = (element.getAttribute("aria-label") || element.textContent || element.title || "").trim().replace(/\s+/g, " ");
          const hasContract =
            element.tagName === "SUMMARY" ||
            (element.tagName === "A" && element.hasAttribute("href")) ||
            contractAttrs.some((attr) => element.hasAttribute(attr));
          return {
            tag: element.tagName.toLowerCase(),
            id: element.id || "",
            label,
            hasContract,
          };
        })
        .filter((item) => !item.label || !item.hasContract);
    });
    assert.deepEqual(offenders, [], `${stageName} visible controls must have labels and handler contract markers`);
  }

  async assertNoErrors() {
    assert.deepEqual(this.consoleErrors.filter(Boolean), []);
    assert.deepEqual(this.networkViolations.filter(Boolean), []);
  }
}

async function waitForJob(baseUrl, projectId, predicate, description) {
  const deadline = Date.now() + 35_000;
  let latest = [];
  while (Date.now() < deadline) {
    const query = projectId ? `?projectId=${encodeURIComponent(projectId)}` : "";
    latest = (await requestJson("GET", `${baseUrl}/api/jobs${query}`)).jobs || [];
    const match = latest.find(predicate);
    if (match) return match;
    await delay(300);
  }
  throw new Error(`Timed out waiting for ${description}; latest jobs: ${latest.map((job) => `${job.id}:${job.status}`).join(", ") || "none"}`);
}

async function runInteractionContract() {
  assert.ok(existsSync(DEMO_VIDEO), "demo video fixture exists");
  const chromePath = findChrome();
  assert.ok(chromePath, "Chrome/Chromium is required for UI interaction contract tests");
  tmp = await mkdtemp(join(tmpdir(), "motionjson-ui-interactions-"));
  ui = await startUi(tmp);
  cdpPort = await freePort();
  chrome = await startChrome(chromePath, tmp, cdpPort);

  const target = await newTarget(cdpPort);
  const cdp = connectCdp(target.webSocketDebuggerUrl);
  const page = new BrowserPage(cdp, ui.baseUrl);
  try {
    await cdp.send("Page.enable");
    await cdp.send("Network.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Log.enable").catch(() => {});
    await page.setViewport(1440, 900);

    await page.openFresh();
    await page.auditVisibleControls("goal");
    await page.clickTestId("goal-trace-one-object");
    await page.clickTestId("workflow-primary");
    await page.waitForActivePhase("source");
    await page.auditVisibleControls("source");
    await page.clickTestId("use-demo-video");
    await page.waitFor(() => Boolean(document.querySelector('[data-testid="video-select"]')?.value), "demo source selected");
    await page.clickTestId("workflow-primary");
    await page.waitFor(
      () => ["model", "target"].includes(document.querySelector("#journeyNav [data-journey-phase].is-active")?.dataset.journeyPhase || ""),
      "cut-out goal reaches model or target",
    );
    const cutOutPhase = await page.activePhase();
    assert.ok(["model", "target"].includes(cutOutPhase), `cut-out flow reached ${cutOutPhase}`);
    await page.auditVisibleControls(`cut-out-${cutOutPhase}`);

    await page.openFresh();
    await page.clickTestId("goal-motion-foreground");
    await page.clickTestId("workflow-primary");
    await page.waitForActivePhase("source");
    await page.clickTestId("use-demo-video");
    await page.waitFor(() => Boolean(document.querySelector('[data-testid="video-select"]')?.value), "motion source selected");
    await page.clickTestId("workflow-primary");
    await page.waitForActivePhase("target");
    assert.equal(await page.primaryLabel(), "Continue to preflight");
    await page.auditVisibleControls("target");
    await page.clickTestId("workflow-primary");
    await page.waitForActivePhase("preflight");
    await page.waitFor(() => {
      const element = document.querySelector("#stagePreflight");
      const box = element?.getBoundingClientRect();
      return Boolean(box && box.width > 0 && box.height > 0 && !element.hidden);
    }, "preflight stage visible");
    await page.auditVisibleControls("preflight");
    await page.clickTestId("workflow-primary");
    await page.waitForActivePhase("run", 25_000);
    await page.auditVisibleControls("run");

    const selected = await page.evaluate(() => ({
      projectId: document.querySelector('[data-testid="project-select"]')?.value || "",
      videoId: document.querySelector('[data-testid="video-select"]')?.value || "",
    }));
    assert.ok(selected.projectId, "project selected after guided demo flow");
    assert.ok(selected.videoId, "video selected after guided demo flow");
    const finished = await waitForJob(ui.baseUrl, selected.projectId, (job) => ["succeeded", "failed", "canceled"].includes(String(job.status)), "guided mock job to finish");
    assert.equal(finished.status, "succeeded", `guided mock job should succeed, got ${finished.status}`);
    await page.click("#refreshButton");
    await page.waitForText("body", new RegExp(finished.id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    await page.click(`[data-job-id="${finished.id}"]`);
    await page.waitForText('[data-testid="workflow-primary"]', /Continue to review|Select objects|Review partial objects/i);
    if (/Continue to review|Review partial objects/i.test(await page.primaryLabel())) {
      await page.clickTestId("workflow-primary");
    } else {
      await page.click('#journeyNav [data-journey-phase="review"]');
    }
    await page.waitForActivePhase("review");
    await page.waitFor(() => document.querySelectorAll("[data-track-row], #studioObjectList .studio-object-row").length > 0, "review tracks rendered");
    await page.auditVisibleControls("review");

    await page.click('#journeyNav [data-journey-phase="correct"]');
    await page.waitForActivePhase("correct");
    await page.auditVisibleControls("correct");
    await page.evaluate(() => {
      const input = document.querySelector('[data-testid="correction-label-input"]');
      if (input) {
        input.value = "Interaction red ball";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    await page.clickTestId("relabel-track");
    await page.waitForText("#correctionPersistenceMessage, #correctionHistory, #trackList, #studioObjectList", /saved|Interaction red ball|Correction/i);

    await page.evaluate(() => {
      const toggle = document.querySelector("[data-track-export]");
      if (toggle && !toggle.checked) toggle.click();
    });
    await page.click('#journeyNav [data-journey-phase="export"]');
    await page.waitForActivePhase("export");
    await page.auditVisibleControls("export");
    await page.click("#studioValidateExportButton");
    await page.waitForText("#studioExportStatus, #studioExportDecision, #exportStatusSummary", /ready|valid|export|review/i);
    const exportEnabled = await page.evaluate(() => document.querySelector("#studioExportMotionJsonButton")?.disabled === false);
    assert.equal(exportEnabled, true, "Export MotionJSON button becomes enabled after validation");
    await page.click("#studioExportMotionJsonButton");
    await page.waitForActivePhase("reuse", 25_000);
    await page.waitForText("#studioExportReuseGuide", /Layer reuse checks|Runtime snippet|Copyable handoff/i);
    await page.auditVisibleControls("reuse");
    await page.clickTestId("workflow-primary");
    await page.waitForText("#runPlanAlert, #providerWarning, #studioExportReuseGuide", /copied|Copyable|Layer reuse/i);

    await page.click("#helpButton");
    await page.waitFor(
      () => document.querySelector("#diagnosticsRail")?.getAttribute("aria-hidden") !== "true",
      "help opens diagnostics rail",
    );
    await page.click("#settingsButton");
    await page.waitFor(
      () => document.querySelector("#workspaceSidebar")?.getAttribute("aria-hidden") !== "true",
      "settings opens project drawer",
    );
    await page.assertNoErrors();
  } finally {
    cdp.close();
    await fetch(`http://127.0.0.1:${cdpPort}/json/close/${target.id}`).catch(() => {});
  }
}

let failure = null;
try {
  await Promise.race([
    runInteractionContract(),
    delay(E2E_TIMEOUT_MS).then(() => {
      throw new Error(`Timed out after ${E2E_TIMEOUT_MS}ms`);
    }),
  ]);
  console.log(JSON.stringify({ status: "ok", baseUrl: ui?.baseUrl || "", viewport: "desktop-1440" }, null, 2));
} catch (error) {
  failure = error;
  console.error(error.stack || error.message);
} finally {
  await stopProcess(chrome);
  await stopProcess(ui?.child);
  if (tmp) await rm(tmp, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }).catch(() => {});
}
process.exit(failure ? 1 : 0);
