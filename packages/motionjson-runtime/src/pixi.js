import { createCanvasRuntime } from "./canvas.js";
import { normalizeMotionJSON } from "./manifest.js";
import { composeFrameTransform, frameAt, stateTransforms } from "./timeline.js";

function pixiFromOptions(options) {
  return options.PIXI || globalThis.PIXI || null;
}

function isCanvasElement(value) {
  return typeof HTMLCanvasElement !== "undefined" && value instanceof HTMLCanvasElement;
}

function makeTexture(PIXI, base, frame) {
  if (!frame?.sprite || !PIXI.Rectangle || !PIXI.Texture) {
    return PIXI.Texture?.from ? PIXI.Texture.from(frame?.assetUrl || base) : base;
  }
  const rectangle = new PIXI.Rectangle(frame.sprite.x, frame.sprite.y, frame.sprite.w, frame.sprite.h);
  return new PIXI.Texture(base, rectangle);
}

function spriteSize(frame, sprite) {
  return {
    width: frame.width || frame.sprite?.w || sprite?.width || 0,
    height: frame.height || frame.sprite?.h || sprite?.height || 0
  };
}

function setPivot(sprite, width, height) {
  if (sprite.pivot?.set) {
    sprite.pivot.set(width / 2, height / 2);
    return;
  }
  if (sprite.anchor?.set) {
    sprite.anchor.set(0.5);
  }
}

export async function createPixiRuntime(target, motionDocument, options = {}) {
  const PIXI = pixiFromOptions(options);
  if (!PIXI) {
    const canvas = isCanvasElement(target) ? target : globalThis.document?.createElement("canvas");
    if (!canvas) throw new Error("Pixi runtime fallback requires a canvas-capable target");
    const ownsCanvas = Boolean(target.appendChild && canvas !== target);
    if (ownsCanvas) target.appendChild(canvas);
    const fallback = createCanvasRuntime(canvas, motionDocument, options);
    fallback.renderer = "canvas2d";
    fallback.fallbackReason = "PIXI was not provided";
    const destroyCanvasRuntime = fallback.destroy.bind(fallback);
    fallback.destroy = () => {
      destroyCanvasRuntime();
      if (ownsCanvas) canvas.remove?.();
    };
    return fallback;
  }

  const scene = motionDocument.assets?.sequence ? motionDocument : normalizeMotionJSON(motionDocument, options);
  const app = new PIXI.Application({
    width: scene.canvas.width,
    height: scene.canvas.height,
    backgroundAlpha: 0,
    antialias: true,
    ...(options.appOptions || {})
  });
  if (target.appendChild && app.view) target.appendChild(app.view);

  const firstFrame = frameAt(scene, 0) || scene.assets.sequence[0];
  const baseTexture = scene.assets.spritesheet?.url && PIXI.BaseTexture?.from
    ? PIXI.BaseTexture.from(scene.assets.spritesheet.url)
    : null;
  const sprite = new PIXI.Sprite(makeTexture(PIXI, baseTexture, firstFrame));
  app.stage.addChild(sprite);

  const runtime = {
    renderer: "pixi",
    scene,
    app,
    sprite,
    state: options.state || "idle",
    context: { ...options },
    playing: options.autoplay !== false,
    startedAt: performance.now(),
    elapsedWhenPaused: 0,
    _tick: null,
    setState(state) {
      runtime.state = state || "idle";
      runtime.render();
    },
    setPlaying(playing) {
      runtime.playing = Boolean(playing);
      if (runtime.playing) runtime.startedAt = performance.now() - runtime.elapsedWhenPaused * 1000;
    },
    setEdit(edit) {
      runtime.context.edit = edit;
      runtime.render();
    },
    setScrollProgress(progress) {
      runtime.context.scrollProgress = Math.max(0, Math.min(1, Number(progress) || 0));
      runtime.render();
    },
    timeSeconds(now = performance.now()) {
      if (!runtime.playing) return runtime.elapsedWhenPaused;
      runtime.elapsedWhenPaused = (now - runtime.startedAt) / 1000;
      return runtime.elapsedWhenPaused;
    },
    render(now = performance.now(), renderOptions = {}) {
      const frame = frameAt(scene, runtime.timeSeconds(now), { loop: options.loop });
      if (!frame) return null;
      if (baseTexture) {
        sprite.texture = makeTexture(PIXI, baseTexture, frame);
      } else if (frame.assetUrl && PIXI.Texture?.from) {
        sprite.texture = PIXI.Texture.from(frame.assetUrl);
      }
      const transform = composeFrameTransform(frame, stateTransforms(scene, runtime.state, { ...runtime.context, ...renderOptions }));
      const { width, height } = spriteSize(frame, sprite);
      setPivot(sprite, width, height);
      sprite.visible = frame.visible;
      sprite.x = frame.x + width / 2 + transform.translate[0];
      sprite.y = frame.y + height / 2 + transform.translate[1];
      sprite.alpha = transform.opacity;
      sprite.rotation = transform.rotation;
      sprite.scale?.set?.(transform.scale);
      return frame;
    },
    start() {
      runtime._tick = () => runtime.render(performance.now());
      app.ticker?.add?.(runtime._tick);
      runtime.render();
      return runtime;
    },
    stop() {
      if (runtime._tick) app.ticker?.remove?.(runtime._tick);
      return runtime;
    },
    destroy() {
      runtime.stop();
      app.destroy?.(true);
    }
  };
  return runtime;
}
