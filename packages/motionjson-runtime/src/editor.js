import { normalizeMotionJSON } from "./manifest.js";

const EDITOR_SCHEMA = "motionjson.timeline_editor_state.v0.1";

function numberOr(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function clamp(value, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return min;
  return Math.min(max, Math.max(min, number));
}

function clone(value) {
  return typeof structuredClone === "function"
    ? structuredClone(value)
    : JSON.parse(JSON.stringify(value));
}

function frameCountFor(scene) {
  return numberOr(scene.canvas?.frameCount ?? scene.canvas?.frame_count ?? scene.assets?.sequence?.length, 0);
}

function fpsFor(scene) {
  return numberOr(scene.canvas?.fps, 12);
}

function layerFrameBounds(scene) {
  return {
    startFrame: 1,
    endFrame: Math.max(1, frameCountFor(scene))
  };
}

function layerLabel(scene, objectId, index) {
  const object = scene.raw?.objects?.find?.((candidate) => candidate.id === objectId);
  return object?.label || scene.label || `Layer ${index + 1}`;
}

function makeLayer(scene, rawLayer, index) {
  const fallbackId = scene.assetId || rawLayer?.object_id || `object_${index}`;
  const rawObject = scene.raw?.objects?.find?.((candidate) => candidate.id === (rawLayer?.object_id || fallbackId));
  const id = rawLayer?.id || `${fallbackId}_layer`;
  const clip = layerFrameBounds(scene);
  return {
    id,
    objectId: rawLayer?.object_id || fallbackId,
    sourceAssetId: fallbackId,
    label: layerLabel(scene, rawLayer?.object_id || fallbackId, index),
    visible: rawLayer?.visible !== false,
    opacity: clamp(rawLayer?.opacity ?? 1, 0, 1),
    zIndex: Math.trunc(numberOr(rawLayer?.z_index ?? rawLayer?.zIndex ?? rawObject?.zIndex, 10 + index * 10)),
    clip: {
      startFrame: Math.trunc(numberOr(rawLayer?.clip?.startFrame, clip.startFrame)),
      endFrame: Math.trunc(numberOr(rawLayer?.clip?.endFrame, clip.endFrame))
    },
    transform: {
      translate: Array.isArray(rawLayer?.transform?.translate) ? [numberOr(rawLayer.transform.translate[0], 0), numberOr(rawLayer.transform.translate[1], 0)] : [0, 0],
      scale: numberOr(rawLayer?.transform?.scale, 1),
      rotation: numberOr(rawLayer?.transform?.rotation, 0)
    },
    reusedFromLayerId: null
  };
}

function normalizeEditorInput(document, options) {
  return document?.assets?.sequence ? document : normalizeMotionJSON(document, options);
}

export function initializeEditorState(document, options = {}) {
  const scene = normalizeEditorInput(document, options);
  const rawLayers = Array.isArray(scene.raw?.layers) && scene.raw.layers.length
    ? scene.raw.layers
    : [null];
  const layers = rawLayers.map((layer, index) => makeLayer(scene, layer, index));
  return {
    schema: EDITOR_SCHEMA,
    scene,
    fps: fpsFor(scene),
    frameCount: frameCountFor(scene),
    currentFrame: 1,
    playing: false,
    selectedLayerId: options.selectedLayerId || layers[0]?.id || null,
    background: {
      type: "checkerboard",
      color: "#f7f4ed",
      imageUrl: null
    },
    layers
  };
}

export function selectLayer(editorState, layerId) {
  return {
    ...editorState,
    selectedLayerId: editorState.layers.some((layer) => layer.id === layerId) ? layerId : editorState.selectedLayerId
  };
}

export function updateLayerTransform(editorState, layerId, transform = {}) {
  return {
    ...editorState,
    layers: editorState.layers.map((layer) => {
      if (layer.id !== layerId) return layer;
      const nextTranslate = Array.isArray(transform.translate)
        ? [numberOr(transform.translate[0], layer.transform.translate[0]), numberOr(transform.translate[1], layer.transform.translate[1])]
        : layer.transform.translate;
      return {
        ...layer,
        transform: {
          translate: nextTranslate,
          scale: numberOr(transform.scale, layer.transform.scale),
          rotation: numberOr(transform.rotation, layer.transform.rotation)
        }
      };
    })
  };
}

export function setLayerOpacity(editorState, layerId, opacity) {
  return {
    ...editorState,
    layers: editorState.layers.map((layer) => (
      layer.id === layerId ? { ...layer, opacity: clamp(opacity, 0, 1) } : layer
    ))
  };
}

export function setLayerVisibility(editorState, layerId, visible) {
  return {
    ...editorState,
    layers: editorState.layers.map((layer) => (
      layer.id === layerId ? { ...layer, visible: Boolean(visible) } : layer
    ))
  };
}

export function setLayerZIndex(editorState, layerId, zIndex) {
  return {
    ...editorState,
    layers: editorState.layers.map((layer) => (
      layer.id === layerId ? { ...layer, zIndex: Math.trunc(numberOr(zIndex, layer.zIndex)) } : layer
    ))
  };
}

export function setLayerClip(editorState, layerId, clip = {}) {
  return {
    ...editorState,
    layers: editorState.layers.map((layer) => {
      if (layer.id !== layerId) return layer;
      const frameCount = Math.max(1, editorState.frameCount);
      const startFrame = Math.min(frameCount, Math.max(1, Math.trunc(numberOr(clip.startFrame, layer.clip.startFrame))));
      const endFrame = Math.max(startFrame, Math.trunc(numberOr(clip.endFrame, layer.clip.endFrame)));
      return {
        ...layer,
        clip: {
          startFrame,
          endFrame: Math.min(frameCount, endFrame)
        }
      };
    })
  };
}

export function setCurrentFrame(editorState, frame) {
  const frameCount = Math.max(1, editorState.frameCount);
  return {
    ...editorState,
    currentFrame: Math.min(frameCount, Math.max(1, Math.trunc(numberOr(frame, editorState.currentFrame))))
  };
}

export function duplicateLayer(editorState, layerId, options = {}) {
  const source = editorState.layers.find((layer) => layer.id === layerId);
  if (!source) return editorState;
  const baseId = options.id || `${source.id}_reuse`;
  let id = baseId;
  let suffix = 2;
  while (editorState.layers.some((layer) => layer.id === id)) {
    id = `${baseId}_${suffix}`;
    suffix += 1;
  }
  const maxZ = editorState.layers.reduce((value, layer) => Math.max(value, layer.zIndex), source.zIndex);
  const next = {
    ...clone(source),
    id,
    label: options.label || `${source.label} reuse`,
    zIndex: Math.trunc(numberOr(options.zIndex, maxZ + 1)),
    transform: {
      translate: [
        source.transform.translate[0] + numberOr(options.offsetX, 32),
        source.transform.translate[1] + numberOr(options.offsetY, 24)
      ],
      scale: source.transform.scale,
      rotation: source.transform.rotation
    },
    sourceAssetId: source.sourceAssetId,
    reusedFromLayerId: source.id
  };
  return {
    ...editorState,
    selectedLayerId: id,
    layers: [...editorState.layers, next]
  };
}

export function setBackground(editorState, background = {}) {
  const type = ["checkerboard", "solid", "image"].includes(background.type) ? background.type : editorState.background.type;
  return {
    ...editorState,
    background: {
      ...editorState.background,
      ...background,
      type
    }
  };
}

export function frameInLayerClip(layer, frame) {
  const safeFrame = Math.trunc(numberOr(frame, 1));
  return safeFrame >= layer.clip.startFrame && safeFrame <= layer.clip.endFrame;
}

export function sortVisibleLayers(editorState, frame = editorState.currentFrame) {
  return editorState.layers
    .filter((layer) => layer.visible && layer.opacity > 0 && frameInLayerClip(layer, frame))
    .slice()
    .sort((a, b) => (a.zIndex - b.zIndex) || a.id.localeCompare(b.id));
}

export function serializeEditState(editorState) {
  return {
    schema: EDITOR_SCHEMA,
    canvas: {
      width: editorState.scene.canvas.width,
      height: editorState.scene.canvas.height,
      fps: editorState.fps,
      frameCount: editorState.frameCount
    },
    currentFrame: editorState.currentFrame,
    selectedLayerId: editorState.selectedLayerId,
    background: { ...editorState.background },
    layers: editorState.layers.map((layer) => ({
      id: layer.id,
      objectId: layer.objectId,
      sourceAssetId: layer.sourceAssetId,
      reusedFromLayerId: layer.reusedFromLayerId,
      label: layer.label,
      visible: layer.visible,
      opacity: layer.opacity,
      zIndex: layer.zIndex,
      clip: { ...layer.clip },
      transform: {
        translate: [...layer.transform.translate],
        scale: layer.transform.scale,
        rotation: layer.transform.rotation
      }
    }))
  };
}
