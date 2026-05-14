const WEB_MANIFEST_SCHEMA = "motionjson.web_asset_manifest.v0.1";
const SCENE_GRAPH_SCHEMA = "motionjson.scene_graph.v0.1";

function manifestDirectory(baseUrl) {
  if (!baseUrl) return "";
  const value = String(baseUrl);
  if (value.endsWith("/")) return value;
  try {
    return new URL(".", value).href;
  } catch {
    const slash = value.lastIndexOf("/");
    return slash >= 0 ? value.slice(0, slash + 1) : "";
  }
}

export function resolveAssetUrl(path, baseUrl = "") {
  if (path == null || path === "") return null;
  const value = String(path);
  if (/^(?:[a-z]+:)?\/\//i.test(value) || value.startsWith("data:") || value.startsWith("blob:") || value.startsWith("/")) {
    return value;
  }
  const base = manifestDirectory(baseUrl);
  if (!base) return value;
  try {
    return new URL(value, base).href;
  } catch {
    return `${base}${value}`;
  }
}

function numberOr(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeFrame(frame, index, baseUrl) {
  const sprite = frame.sprite || null;
  const width = numberOr(frame.width ?? frame.w ?? sprite?.w, 0);
  const height = numberOr(frame.height ?? frame.h ?? sprite?.h, 0);
  return {
    frame: numberOr(frame.frame ?? index + 1, index + 1),
    t: numberOr(frame.t, 0),
    visible: frame.visible !== false,
    asset: frame.asset ?? null,
    assetUrl: resolveAssetUrl(frame.asset, baseUrl),
    x: numberOr(frame.x, 0),
    y: numberOr(frame.y, 0),
    width,
    height,
    anchor: Array.isArray(frame.anchor) ? frame.anchor : [width / 2, height / 2],
    opacity: numberOr(frame.opacity, frame.visible === false ? 0 : 1),
    scale: numberOr(frame.scale, 1),
    rotation: numberOr(frame.rotation, 0),
    sprite
  };
}

function normalizeSpritesheet(spritesheet, baseUrl) {
  if (!spritesheet || !spritesheet.path) return null;
  return {
    ...spritesheet,
    url: resolveAssetUrl(spritesheet.path, baseUrl)
  };
}

function normalizeWebManifest(document, options) {
  const baseUrl = options.baseUrl || "";
  const sequence = document.assets?.sequence || [];
  return {
    schema: WEB_MANIFEST_SCHEMA,
    sourceType: "web_asset_manifest",
    assetId: document.assetId,
    label: document.label,
    renderMode: document.renderMode || "raster_alpha_sequence",
    canvas: {
      width: numberOr(document.canvas?.width, 1),
      height: numberOr(document.canvas?.height, 1),
      fps: numberOr(document.canvas?.fps, 12),
      frameCount: numberOr(document.canvas?.frameCount, sequence.length)
    },
    states: document.states || {},
    assets: {
      posterUrl: resolveAssetUrl(document.assets?.poster, baseUrl),
      spritesheet: normalizeSpritesheet(document.assets?.spritesheet, baseUrl),
      sequence: sequence.map((frame, index) => normalizeFrame(frame, index, baseUrl)),
      fallbackStaticPosterUrl: resolveAssetUrl(document.assets?.fallbackStaticPoster, baseUrl),
      fallbackVideoUrl: resolveAssetUrl(document.assets?.fallbackVideo, baseUrl),
      production: document.assets?.production || null
    },
    raw: document
  };
}

function firstSceneObject(document) {
  if (!Array.isArray(document.objects) || document.objects.length === 0) {
    throw new Error("MotionJSON scene_graph.json must include at least one object");
  }
  return document.objects[0];
}

function normalizeSceneGraph(document, options) {
  const baseUrl = options.baseUrl || "";
  const object = options.objectId
    ? document.objects.find((candidate) => candidate.id === options.objectId)
    : firstSceneObject(document);
  if (!object) throw new Error(`MotionJSON object not found: ${options.objectId}`);
  const layer = Array.isArray(document.layers)
    ? document.layers.find((candidate) => candidate.object_id === object.id) || document.layers[0]
    : null;
  const objectFrames = object.motion || object.frames || [];
  const sourceFrames = layer?.frames?.length ? layer.frames : objectFrames;
  const frames = sourceFrames.map((frame, index) => {
    const objectFrame = objectFrames[index] || {};
    return normalizeFrame(
      {
        ...objectFrame,
        ...frame,
        sprite: frame.sprite || objectFrame.sprite
      },
      index,
      baseUrl
    );
  });
  return {
    schema: SCENE_GRAPH_SCHEMA,
    sourceType: "scene_graph",
    assetId: object.id,
    label: object.label,
    renderMode: object.renderMode || layer?.type || "raster_alpha_sequence",
    canvas: {
      width: numberOr(document.canvas?.width ?? document.source?.width, 1),
      height: numberOr(document.canvas?.height ?? document.source?.height, 1),
      fps: numberOr(document.canvas?.fps ?? document.source?.sampleFps, 12),
      frameCount: numberOr(document.canvas?.frame_count ?? document.source?.sampledFrameCount, frames.length)
    },
    states: object.interactions || {},
    assets: {
      posterUrl: resolveAssetUrl(frames.find((frame) => frame.asset)?.asset, baseUrl),
      spritesheet: normalizeSpritesheet(object.assets?.spritesheet, baseUrl),
      sequence: frames,
      fallbackStaticPosterUrl: resolveAssetUrl(frames.find((frame) => frame.asset)?.asset, baseUrl),
      fallbackVideoUrl: null,
      production: object.assets?.production || null
    },
    raw: document
  };
}

export function normalizeMotionJSON(document, options = {}) {
  if (!document || typeof document !== "object") {
    throw new TypeError("MotionJSON runtime expects a manifest object");
  }
  if (document.schema === WEB_MANIFEST_SCHEMA || document.type === "web_motion_asset") {
    return normalizeWebManifest(document, options);
  }
  if (document.schema === SCENE_GRAPH_SCHEMA || Array.isArray(document.objects)) {
    return normalizeSceneGraph(document, options);
  }
  throw new Error(`Unsupported MotionJSON document schema: ${document.schema || "unknown"}`);
}

export function getRuntimeImportPath() {
  return "./index.js";
}
