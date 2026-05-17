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
  const normalizedFrames = sequence.map((frame, index) => normalizeFrame(frame, index, baseUrl));
  const normalizedObject = {
    id: document.assetId,
    label: document.label,
    renderMode: document.renderMode || "raster_alpha_sequence",
    states: document.states || {},
    assets: {
      posterUrl: resolveAssetUrl(document.assets?.poster, baseUrl),
      spritesheet: normalizeSpritesheet(document.assets?.spritesheet, baseUrl),
      sequence: normalizedFrames,
      fallbackStaticPosterUrl: resolveAssetUrl(document.assets?.fallbackStaticPoster, baseUrl),
      fallbackVideoUrl: resolveAssetUrl(document.assets?.fallbackVideo, baseUrl),
      production: document.assets?.production || null
    }
  };
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
    assets: normalizedObject.assets,
    objects: [normalizedObject],
    layers: [{
      id: `${document.assetId}_raster_layer`,
      objectId: document.assetId,
      visible: true,
      opacity: 1,
      zIndex: 10,
      transform: { translate: [0, 0], scale: 1, rotation: 0 }
    }],
    raw: document
  };
}

function firstSceneObject(document) {
  if (!Array.isArray(document.objects) || document.objects.length === 0) {
    throw new Error("MotionJSON scene_graph.json must include at least one object");
  }
  return document.objects[0];
}

function sceneObjectFrames(object, layer, baseUrl) {
  const objectFrames = object.motion || object.frames || [];
  const sourceFrames = layer?.frames?.length ? layer.frames : objectFrames;
  return sourceFrames.map((frame, index) => {
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
}

function normalizeSceneObject(object, layer, baseUrl) {
  const frames = sceneObjectFrames(object, layer, baseUrl);
  const firstAsset = frames.find((frame) => frame.asset)?.asset;
  return {
    id: object.id,
    label: object.label,
    renderMode: object.renderMode || layer?.type || "raster_alpha_sequence",
    states: object.interactions || {},
    zIndex: numberOr(object.zIndex ?? layer?.z_index ?? layer?.zIndex, 10),
    assets: {
      posterUrl: resolveAssetUrl(firstAsset, baseUrl),
      spritesheet: normalizeSpritesheet(object.assets?.spritesheet, baseUrl),
      sequence: frames,
      fallbackStaticPosterUrl: resolveAssetUrl(firstAsset, baseUrl),
      fallbackVideoUrl: null,
      production: object.assets?.production || null
    }
  };
}

function normalizeSceneGraph(document, options) {
  const baseUrl = options.baseUrl || "";
  const selectedRawObject = options.objectId
    ? document.objects.find((candidate) => candidate.id === options.objectId)
    : firstSceneObject(document);
  if (!selectedRawObject) throw new Error(`MotionJSON object not found: ${options.objectId}`);
  const rawLayers = Array.isArray(document.layers) ? document.layers : [];
  const objects = document.objects.map((object) => {
    const layer = rawLayers.find((candidate) => candidate.object_id === object.id || candidate.objectId === object.id) || null;
    return normalizeSceneObject(object, layer, baseUrl);
  });
  const selected = objects.find((object) => object.id === selectedRawObject.id) || objects[0];
  const layers = (rawLayers.length ? rawLayers : objects.map((object) => ({ object_id: object.id, z_index: object.zIndex }))).map((layer, index) => {
    const objectId = layer.object_id || layer.objectId || objects[index]?.id;
    return {
      id: layer.id || `${objectId}_raster_layer`,
      objectId,
      visible: layer.visible !== false,
      opacity: numberOr(layer.opacity, 1),
      zIndex: numberOr(layer.z_index ?? layer.zIndex ?? objects.find((object) => object.id === objectId)?.zIndex, 10 + index),
      transform: {
        translate: Array.isArray(layer.transform?.translate)
          ? [numberOr(layer.transform.translate[0], 0), numberOr(layer.transform.translate[1], 0)]
          : [0, 0],
        scale: numberOr(layer.transform?.scale, 1),
        rotation: numberOr(layer.transform?.rotation, 0)
      }
    };
  });
  return {
    schema: SCENE_GRAPH_SCHEMA,
    sourceType: "scene_graph",
    assetId: selected.id,
    label: selected.label,
    renderMode: selected.renderMode,
    canvas: {
      width: numberOr(document.canvas?.width ?? document.source?.width, 1),
      height: numberOr(document.canvas?.height ?? document.source?.height, 1),
      fps: numberOr(document.canvas?.fps ?? document.source?.sampleFps, 12),
      frameCount: numberOr(document.canvas?.frame_count ?? document.source?.sampledFrameCount, selected.assets.sequence.length)
    },
    states: selected.states,
    assets: selected.assets,
    objects,
    layers,
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
