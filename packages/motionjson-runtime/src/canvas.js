import { loadRuntimeAssets } from "./assets.js";
import { normalizeMotionJSON } from "./manifest.js";
import { composeFrameTransform, frameAt, stateTransforms } from "./timeline.js";

function fitContain(canvas, scene) {
  const rect = canvas.getBoundingClientRect();
  const cssWidth = Math.max(1, Math.floor(rect.width || scene.canvas.width));
  const cssHeight = Math.max(1, Math.floor(rect.height || scene.canvas.height));
  const scale = Math.min(cssWidth / scene.canvas.width, cssHeight / scene.canvas.height);
  return {
    cssWidth,
    cssHeight,
    scale,
    left: (cssWidth - scene.canvas.width * scale) / 2,
    top: (cssHeight - scene.canvas.height * scale) / 2
  };
}

function ensureCanvasSize(canvas, scene) {
  const dpr = globalThis.devicePixelRatio || 1;
  const fit = fitContain(canvas, scene);
  const width = Math.floor(fit.cssWidth * dpr);
  const height = Math.floor(fit.cssHeight * dpr);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  return { dpr, ...fit };
}

function spriteSize(frame, image) {
  return {
    width: frame.width || frame.sprite?.w || image?.width || 0,
    height: frame.height || frame.sprite?.h || image?.height || 0
  };
}

export function drawCanvasFrame(ctx, scene, loadedAssets, options = {}) {
  const canvas = ctx.canvas;
  const fit = ensureCanvasSize(canvas, scene);
  ctx.setTransform(fit.dpr, 0, 0, fit.dpr, 0, 0);
  ctx.clearRect(0, 0, fit.cssWidth, fit.cssHeight);
  if (options.background) {
    ctx.fillStyle = options.background;
    ctx.fillRect(0, 0, fit.cssWidth, fit.cssHeight);
  }
  ctx.save();
  ctx.translate(fit.left, fit.top);
  ctx.scale(fit.scale, fit.scale);
  if (options.showBounds) {
    ctx.strokeStyle = options.boundsColor || "rgba(0, 0, 0, .24)";
    ctx.strokeRect(0, 0, scene.canvas.width, scene.canvas.height);
  }

  const frame = options.frame || frameAt(scene, options.timeSeconds || 0, { loop: options.loop });
  const frameIndex = scene.assets.sequence.indexOf(frame);
  const image = loadedAssets.spritesheet || loadedAssets.frames[frameIndex];
  if (frame && image && frame.visible) {
    const transform = composeFrameTransform(frame, stateTransforms(scene, options.state, options));
    const { width, height } = spriteSize(frame, image);
    ctx.save();
    ctx.globalAlpha = transform.opacity;
    ctx.translate(frame.x + width / 2 + transform.translate[0], frame.y + height / 2 + transform.translate[1]);
    ctx.rotate(transform.rotation);
    ctx.scale(transform.scale, transform.scale);
    if (loadedAssets.spritesheet && frame.sprite) {
      ctx.drawImage(image, frame.sprite.x, frame.sprite.y, frame.sprite.w, frame.sprite.h, -width / 2, -height / 2, width, height);
    } else {
      ctx.drawImage(image, -width / 2, -height / 2, width, height);
    }
    if (transform.outline) {
      ctx.strokeStyle = options.outlineColor || "#2c8f7f";
      ctx.lineWidth = 3;
      ctx.strokeRect(-width / 2, -height / 2, width, height);
    }
    ctx.restore();
  }
  ctx.restore();
  return { frame, fit };
}

export function createCanvasRuntime(canvas, document, options = {}) {
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas2D context is not available");
  const scene = document.assets?.sequence ? document : normalizeMotionJSON(document, options);
  const runtime = {
    renderer: "canvas2d",
    canvas,
    scene,
    state: options.state || "idle",
    context: { ...options },
    playing: options.autoplay !== false,
    startedAt: 0,
    elapsedWhenPaused: 0,
    assets: { spritesheet: null, frames: [] },
    _raf: 0,
    async load() {
      runtime.assets = await loadRuntimeAssets(scene, options);
      runtime.startedAt = performance.now();
      return runtime;
    },
    setState(state) {
      runtime.state = state || "idle";
      runtime.render();
    },
    setEdit(edit) {
      runtime.context.edit = edit;
      runtime.render();
    },
    setScrollProgress(progress) {
      runtime.context.scrollProgress = Math.max(0, Math.min(1, Number(progress) || 0));
      runtime.render();
    },
    setPlaying(playing) {
      runtime.playing = Boolean(playing);
      if (runtime.playing) runtime.startedAt = performance.now() - runtime.elapsedWhenPaused * 1000;
    },
    timeSeconds(now = performance.now()) {
      if (!runtime.playing) return runtime.elapsedWhenPaused;
      runtime.elapsedWhenPaused = (now - runtime.startedAt) / 1000;
      return runtime.elapsedWhenPaused;
    },
    render(now = performance.now(), renderOptions = {}) {
      return drawCanvasFrame(ctx, scene, runtime.assets, {
        ...runtime.context,
        ...renderOptions,
        state: runtime.state,
        timeSeconds: runtime.timeSeconds(now)
      });
    },
    start() {
      const tick = (now) => {
        runtime.render(now);
        runtime._raf = requestAnimationFrame(tick);
      };
      runtime.stop();
      runtime._raf = requestAnimationFrame(tick);
      return runtime;
    },
    stop() {
      if (runtime._raf) cancelAnimationFrame(runtime._raf);
      runtime._raf = 0;
      return runtime;
    },
    destroy() {
      runtime.stop();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  };
  return runtime;
}
