#!/usr/bin/env node
import { createReadStream, existsSync } from "node:fs";
import { mkdtemp, rm, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { extname, join, resolve } from "node:path";
import { spawn } from "node:child_process";
import process from "node:process";

const ROOT = process.cwd();
const DEFAULT_MANIFEST = "/out/demo/web_asset_manifest.json";

function parseArgs(argv) {
  const options = { check: false, manifest: DEFAULT_MANIFEST };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--check") options.check = true;
    else if (arg === "--manifest") options.manifest = argv[++index] || DEFAULT_MANIFEST;
    else if (arg === "--help" || arg === "-h") {
      console.log(`Usage: node scripts/smoke_embed_examples.mjs [--check] [--manifest /out/demo/web_asset_manifest.json]

Serves the repository locally, opens examples/plain_js_embed.html in headless
Chrome, and verifies that the demo manifest mounts with a nonblank Canvas2D
surface and no browser runtime errors.`);
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

function contentType(pathname) {
  const types = {
    ".css": "text/css; charset=utf-8",
    ".gif": "image/gif",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".mp4": "video/mp4",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
  };
  return types[extname(pathname).toLowerCase()] || "application/octet-stream";
}

function startStaticServer(port = 0) {
  const server = createServer(async (request, response) => {
    try {
      const url = new URL(request.url || "/", "http://127.0.0.1");
      const pathname = decodeURIComponent(url.pathname === "/" ? "/examples/plain_js_embed.html" : url.pathname);
      const filePath = resolve(ROOT, `.${pathname}`);
      if (!filePath.startsWith(ROOT)) {
        response.writeHead(403);
        response.end("Forbidden");
        return;
      }
      const info = await stat(filePath);
      if (!info.isFile()) {
        response.writeHead(404);
        response.end("Not found");
        return;
      }
      response.writeHead(200, {
        "content-type": contentType(filePath),
        "cache-control": "no-store",
      });
      createReadStream(filePath).pipe(response);
    } catch {
      response.writeHead(404);
      response.end("Not found");
    }
  });
  return new Promise((resolvePromise, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => resolvePromise(server));
  });
}

async function closeServer(server) {
  await new Promise((resolvePromise) => server.close(resolvePromise));
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

function connectCdp(webSocketDebuggerUrl, onEvent = null) {
  const socket = new WebSocket(webSocketDebuggerUrl);
  let id = 0;
  const callbacks = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id) {
      onEvent?.(message);
      return;
    }
    if (!callbacks.has(message.id)) return;
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

async function waitForEmbed(cdp) {
  const deadline = Date.now() + 12000;
  let last = null;
  while (Date.now() < deadline) {
    const result = await cdp.send("Runtime.evaluate", {
      returnByValue: true,
      expression: `(() => {
        const target = document.querySelector("#motion");
        const canvas = document.querySelector("#motion canvas");
        const status = document.querySelector("#status")?.textContent || "";
        if (!target || !canvas) return { status, mounted: target?.dataset.motionjsonMounted || "", canvas: false };
        const ctx = canvas.getContext("2d");
        const rect = canvas.getBoundingClientRect();
        const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
        const step = Math.max(4, Math.floor(data.length / 5000 / 4) * 4);
        let visiblePixels = 0;
        let variedPixels = 0;
        for (let index = 0; index < data.length; index += step) {
          const red = data[index];
          const green = data[index + 1];
          const blue = data[index + 2];
          const alpha = data[index + 3];
          if (alpha > 0) visiblePixels += 1;
          if (alpha > 0 && !(red === 251 && green === 250 && blue === 246)) variedPixels += 1;
        }
        return {
          status,
          mounted: target.dataset.motionjsonMounted || "",
          canvas: true,
          canvasWidth: canvas.width,
          canvasHeight: canvas.height,
          cssWidth: Math.round(rect.width),
          cssHeight: Math.round(rect.height),
          visiblePixels,
          variedPixels
        };
      })()`,
    });
    last = result.result.value || {};
    if (
      String(last.status || "").startsWith("Loaded ") &&
      last.mounted === "true" &&
      last.canvas &&
      last.canvasWidth > 0 &&
      last.canvasHeight > 0 &&
      last.visiblePixels > 0 &&
      last.variedPixels > 0
    ) {
      return last;
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 150));
  }
  throw new Error(`Timed out waiting for embed to render: ${JSON.stringify(last)}`);
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
  const manifestPath = resolve(ROOT, `.${options.manifest.startsWith("/") ? options.manifest : `/${options.manifest}`}`);
  if (options.check) {
    console.log(JSON.stringify({ chrome, canRun: Boolean(chrome), manifest: options.manifest, manifestExists: existsSync(manifestPath) }, null, 2));
    return;
  }
  if (!chrome) throw new Error("Chrome/Chromium is required. Set CHROME_BIN to a compatible binary.");
  if (!manifestPath.startsWith(ROOT) || !existsSync(manifestPath)) {
    throw new Error(`Demo manifest does not exist inside the repository: ${options.manifest}`);
  }

  const tmp = await mkdtemp(join(tmpdir(), "motionjson-embed-smoke-"));
  const chromePort = 9700 + Math.floor(Math.random() * 300);
  let server = null;
  let chromeProcess = null;
  let cdp = null;
  const browserErrors = [];
  try {
    server = await startStaticServer();
    const address = server.address();
    const baseUrl = `http://127.0.0.1:${address.port}`;
    chromeProcess = await startChrome(chrome, tmp, chromePort);
    const page = await newPage(chromePort, `${baseUrl}/examples/plain_js_embed.html?manifest=${encodeURIComponent(options.manifest)}`);
    cdp = connectCdp(page.webSocketDebuggerUrl, (event) => {
      if (event.method === "Runtime.exceptionThrown") {
        browserErrors.push(event.params?.exceptionDetails?.text || "Runtime exception");
      }
      if (event.method === "Log.entryAdded" && ["error", "warning"].includes(event.params?.entry?.level)) {
        browserErrors.push(event.params.entry.text || `Log ${event.params.entry.level}`);
      }
    });
    await cdp.send("Runtime.enable");
    await cdp.send("Log.enable");
    await cdp.send("Page.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 720,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await cdp.send("Page.navigate", { url: `${baseUrl}/examples/plain_js_embed.html?manifest=${encodeURIComponent(options.manifest)}` });
    const embed = await waitForEmbed(cdp);
    if (browserErrors.length) throw new Error(`Browser errors: ${browserErrors.join(" | ")}`);
    console.log(JSON.stringify({ status: "ok", url: `${baseUrl}/examples/plain_js_embed.html`, manifest: options.manifest, embed }, null, 2));
  } finally {
    cdp?.close();
    await stopProcess(chromeProcess);
    if (server) await closeServer(server);
    await rm(tmp, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }).catch(() => {});
  }
}

run().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
