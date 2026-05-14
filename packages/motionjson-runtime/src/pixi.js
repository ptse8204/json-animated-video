import { createCanvasRuntime } from "./canvas.js";
import { normalizeMotionJSON } from "./manifest.js";
import { composeFrameTransform, frameIndexAt, stateTransforms } from "./timeline.js";

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

  const objects = new Map((scene.objects || [{ id: scene.assetId, assets: scene.assets, states: scene.states }]).map((object) => [object.id, object]));
  const layers = Array.isArray(scene.layers) && scene.layers.length
    ? scene.layers.slice().sort((a, b) => (a.zIndex - b.zIndex) || String(a.id).localeCompare(String(b.id)))
    : [{ id: `${scene.assetId}_raster_layer`, objectId: scene.assetId, visible: true, opacity: 1, transform: { translate: [0, 0], scale: 1, rotation: 0 } }];
  const baseTextures = new Map();
  const sprites = new Map();
  for (const layer of layers) {
    const object = objects.get(layer.objectId);
    if (!object) continue;
    const firstFrame = object.assets.sequence[0];
    const baseTexture = object.assets.spritesheet?.url && PIXI.BaseTexture?.from
      ? PIXI.BaseTexture.from(object.assets.spritesheet.url)
      : null;
    baseTextures.set(object.id, baseTexture);
    const sprite = new PIXI.Sprite(makeTexture(PIXI, baseTexture, firstFrame));
    sprites.set(layer.id, sprite);
    app.stage.addChild(sprite);
  }
  const sprite = sprites.values().next().value;

  const runtime = {
    renderer: "pixi",
    scene,
    app,
    sprite,
    sprites,
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
      let renderedFrame = null;
      const timeSeconds = runtime.timeSeconds(now);
      const sortedLayers = layers.slice().sort((a, b) => (a.zIndex - b.zIndex) || String(a.id).localeCompare(String(b.id)));
      for (const layer of sortedLayers) {
        const sprite = sprites.get(layer.id);
        const object = objects.get(layer.objectId);
        if (!sprite || !object) continue;
        const sequence = object.assets.sequence || [];
        const frameIndex = frameIndexAt(timeSeconds, scene.canvas.fps, sequence.length, { loop: options.loop });
        const frame = sequence[frameIndex] || null;
        if (!frame) {
          sprite.visible = false;
          continue;
        }
        const baseTexture = baseTextures.get(object.id);
      if (baseTexture) {
        sprite.texture = makeTexture(PIXI, baseTexture, frame);
      } else if (frame.assetUrl && PIXI.Texture?.from) {
        sprite.texture = PIXI.Texture.from(frame.assetUrl);
      }
        const layerTransform = {
          translate: layer.transform?.translate || [0, 0],
          scale: layer.transform?.scale ?? 1,
          rotation: layer.transform?.rotation ?? 0,
          opacity: layer.opacity ?? 1
        };
      const transform = composeFrameTransform(frame, [
        ...stateTransforms({ ...scene, states: object.states || scene.states }, runtime.state, { ...runtime.context, ...renderOptions }),
        layerTransform
      ]);
      const { width, height } = spriteSize(frame, sprite);
      setPivot(sprite, width, height);
      sprite.visible = frame.visible && layer.visible !== false && layer.opacity > 0;
      sprite.x = frame.x + width / 2 + transform.translate[0];
      sprite.y = frame.y + height / 2 + transform.translate[1];
      sprite.alpha = transform.opacity;
      sprite.rotation = transform.rotation;
      sprite.scale?.set?.(transform.scale);
        renderedFrame = frame;
      }
      return renderedFrame;
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
