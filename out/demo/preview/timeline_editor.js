const runtimePath = location.pathname.includes("/preview/")
  ? "./runtime/index.js"
  : "../packages/motionjson-runtime/src/index.js";

const {
  composeFrameTransform,
  duplicateLayer,
  initializeEditorState,
  loadRuntimeAssets,
  normalizeMotionJSON,
  selectLayer,
  serializeEditState,
  setBackground,
  setCurrentFrame,
  setLayerOpacity,
  setLayerVisibility,
  setLayerZIndex,
  sortVisibleLayers,
  updateLayerTransform
} = await import(runtimePath);

const params = new URLSearchParams(location.search);
const defaultScene = location.pathname.includes("/preview/") ? "../scene_graph.json" : "/out/demo/scene_graph.json";
const sceneUrl = params.get("scene") || params.get("manifest") || defaultScene;

const els = {
  status: document.getElementById("status"),
  stageReadout: document.getElementById("stageReadout"),
  stage: document.getElementById("stage"),
  layerList: document.getElementById("layerList"),
  duplicateLayer: document.getElementById("duplicateLayer"),
  selectedName: document.getElementById("selectedName"),
  xRange: document.getElementById("xRange"),
  xNumber: document.getElementById("xNumber"),
  yRange: document.getElementById("yRange"),
  yNumber: document.getElementById("yNumber"),
  scaleRange: document.getElementById("scaleRange"),
  scaleNumber: document.getElementById("scaleNumber"),
  rotationRange: document.getElementById("rotationRange"),
  rotationNumber: document.getElementById("rotationNumber"),
  opacityRange: document.getElementById("opacityRange"),
  opacityNumber: document.getElementById("opacityNumber"),
  zIndex: document.getElementById("zIndex"),
  visibility: document.getElementById("visibility"),
  xOut: document.getElementById("xOut"),
  yOut: document.getElementById("yOut"),
  scaleOut: document.getElementById("scaleOut"),
  rotationOut: document.getElementById("rotationOut"),
  opacityOut: document.getElementById("opacityOut"),
  checkerboard: document.getElementById("checkerboard"),
  solidBackground: document.getElementById("solidBackground"),
  customColor: document.getElementById("customColor"),
  imageUpload: document.getElementById("imageUpload"),
  swatches: document.getElementById("swatches"),
  editJson: document.getElementById("editJson"),
  playPause: document.getElementById("playPause"),
  scrubber: document.getElementById("scrubber"),
  timeReadout: document.getElementById("timeReadout"),
  trackLabels: document.getElementById("trackLabels"),
  trackArea: document.getElementById("trackArea")
};

const ctx = els.stage.getContext("2d");
const swatchColors = ["#f7f4ed", "#101319", "#d9ecff", "#ffe0bd", "#d8f5df"];
const layerMetrics = new Map();

let scene;
let state;
let assets;
let fit = null;
let drag = null;
let backgroundImage = null;
let backgroundObjectUrl = null;
let raf = 0;
let playStart = 0;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value)));
}

function degreesToRadians(value) {
  return Number(value) * Math.PI / 180;
}

function radiansToDegrees(value) {
  return Number(value) * 180 / Math.PI;
}

function frameDuration() {
  return 1 / Math.max(1, state.fps);
}

function selectedLayer() {
  return state.layers.find((layer) => layer.id === state.selectedLayerId) || null;
}

function spriteSize(frame, image) {
  return {
    width: frame.width || frame.sprite?.w || image?.width || 0,
    height: frame.height || frame.sprite?.h || image?.height || 0
  };
}

function ensureCanvas() {
  const rect = els.stage.getBoundingClientRect();
  const cssWidth = Math.max(1, Math.floor(rect.width || scene.canvas.width));
  const cssHeight = Math.max(1, Math.floor(rect.height || scene.canvas.height));
  const dpr = globalThis.devicePixelRatio || 1;
  const width = Math.floor(cssWidth * dpr);
  const height = Math.floor(cssHeight * dpr);
  if (els.stage.width !== width || els.stage.height !== height) {
    els.stage.width = width;
    els.stage.height = height;
  }
  const scale = Math.min(cssWidth / scene.canvas.width, cssHeight / scene.canvas.height);
  return {
    cssWidth,
    cssHeight,
    dpr,
    scale,
    left: (cssWidth - scene.canvas.width * scale) / 2,
    top: (cssHeight - scene.canvas.height * scale) / 2
  };
}

function scenePointFromEvent(event) {
  const rect = els.stage.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left - fit.left) / fit.scale,
    y: (event.clientY - rect.top - fit.top) / fit.scale
  };
}

function rotatedPoint(cx, cy, x, y, rotation) {
  const cos = Math.cos(rotation);
  const sin = Math.sin(rotation);
  return {
    x: cx + x * cos - y * sin,
    y: cy + x * sin + y * cos
  };
}

function layerTransform(layer) {
  return {
    translate: [...layer.transform.translate],
    scale: layer.transform.scale,
    rotation: layer.transform.rotation,
    opacity: layer.opacity
  };
}

function currentFrameAsset() {
  const index = Math.max(0, Math.min(scene.assets.sequence.length - 1, state.currentFrame - 1));
  const frame = scene.assets.sequence[index] || scene.assets.sequence[0] || null;
  const image = assets.spritesheet || assets.frames[index] || null;
  return { frame, image, index };
}

function drawChecker(x, y, width, height, size) {
  ctx.fillStyle = "#f7f4ed";
  ctx.fillRect(x, y, width, height);
  ctx.fillStyle = "#d8d4cc";
  for (let row = 0; row < Math.ceil(height / size); row += 1) {
    for (let col = 0; col < Math.ceil(width / size); col += 1) {
      if ((row + col) % 2 === 0) {
        ctx.fillRect(x + col * size, y + row * size, size, size);
      }
    }
  }
}

function drawBackground() {
  ctx.fillStyle = "#14171d";
  ctx.fillRect(0, 0, fit.cssWidth, fit.cssHeight);
  const x = fit.left;
  const y = fit.top;
  const width = scene.canvas.width * fit.scale;
  const height = scene.canvas.height * fit.scale;
  if (state.background.type === "checkerboard") {
    drawChecker(x, y, width, height, 16);
    return;
  }
  ctx.fillStyle = state.background.color || "#f7f4ed";
  ctx.fillRect(x, y, width, height);
  if (state.background.type === "image" && backgroundImage) {
    const ratio = Math.max(width / backgroundImage.width, height / backgroundImage.height);
    const imageWidth = backgroundImage.width * ratio;
    const imageHeight = backgroundImage.height * ratio;
    ctx.drawImage(backgroundImage, x + (width - imageWidth) / 2, y + (height - imageHeight) / 2, imageWidth, imageHeight);
  }
}

function drawLayer(layer, frame, image, selected) {
  if (!frame || !image || frame.visible === false) return;
  const transform = composeFrameTransform(frame, [layerTransform(layer)]);
  const { width, height } = spriteSize(frame, image);
  if (!width || !height) return;
  const centerX = frame.x + width / 2 + transform.translate[0];
  const centerY = frame.y + height / 2 + transform.translate[1];

  ctx.save();
  ctx.globalAlpha = transform.opacity;
  ctx.translate(centerX, centerY);
  ctx.rotate(transform.rotation);
  ctx.scale(transform.scale, transform.scale);
  if (assets.spritesheet && frame.sprite) {
    ctx.drawImage(image, frame.sprite.x, frame.sprite.y, frame.sprite.w, frame.sprite.h, -width / 2, -height / 2, width, height);
  } else {
    ctx.drawImage(image, -width / 2, -height / 2, width, height);
  }
  ctx.restore();

  const scaledWidth = width * transform.scale;
  const scaledHeight = height * transform.scale;
  const scaleHandle = rotatedPoint(centerX, centerY, scaledWidth / 2, scaledHeight / 2, transform.rotation);
  const rotateHandle = rotatedPoint(centerX, centerY, 0, -scaledHeight / 2 - 30 / fit.scale, transform.rotation);
  const topCenter = rotatedPoint(centerX, centerY, 0, -scaledHeight / 2, transform.rotation);
  layerMetrics.set(layer.id, {
    centerX,
    centerY,
    width: scaledWidth,
    height: scaledHeight,
    rotation: transform.rotation,
    scaleHandle,
    rotateHandle
  });

  if (!selected) return;
  ctx.save();
  ctx.lineWidth = 1.5 / fit.scale;
  ctx.strokeStyle = "#6dc9b8";
  ctx.fillStyle = "#111319";
  ctx.translate(centerX, centerY);
  ctx.rotate(transform.rotation);
  ctx.strokeRect(-scaledWidth / 2, -scaledHeight / 2, scaledWidth, scaledHeight);
  ctx.restore();

  ctx.save();
  ctx.strokeStyle = "#6dc9b8";
  ctx.lineWidth = 1.25 / fit.scale;
  ctx.beginPath();
  ctx.moveTo(topCenter.x, topCenter.y);
  ctx.lineTo(rotateHandle.x, rotateHandle.y);
  ctx.stroke();
  for (const handle of [scaleHandle, rotateHandle]) {
    ctx.beginPath();
    ctx.fillStyle = handle === rotateHandle ? "#e2be64" : "#6dc9b8";
    ctx.arc(handle.x, handle.y, 7 / fit.scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#111319";
    ctx.stroke();
  }
  ctx.restore();
}

function renderStage() {
  if (!state || !assets) return;
  fit = ensureCanvas();
  ctx.setTransform(fit.dpr, 0, 0, fit.dpr, 0, 0);
  ctx.clearRect(0, 0, fit.cssWidth, fit.cssHeight);
  drawBackground();
  layerMetrics.clear();
  const { frame, image } = currentFrameAsset();
  ctx.save();
  ctx.translate(fit.left, fit.top);
  ctx.scale(fit.scale, fit.scale);
  ctx.strokeStyle = "rgba(255, 255, 255, .28)";
  ctx.lineWidth = 1 / fit.scale;
  ctx.strokeRect(0, 0, scene.canvas.width, scene.canvas.height);
  for (const layer of sortVisibleLayers(state, state.currentFrame)) {
    drawLayer(layer, frame, image, layer.id === state.selectedLayerId);
  }
  ctx.restore();
}

function setState(next) {
  state = next;
  syncUi();
  renderStage();
}

function renderLayers() {
  els.layerList.textContent = "";
  const ordered = state.layers.slice().sort((a, b) => b.zIndex - a.zIndex || a.id.localeCompare(b.id));
  for (const layer of ordered) {
    const row = document.createElement("div");
    row.className = `layer-row${layer.id === state.selectedLayerId ? " selected" : ""}${layer.visible ? "" : " hidden"}`;
    row.dataset.layerId = layer.id;

    const eye = document.createElement("button");
    eye.className = "eye";
    eye.textContent = layer.visible ? "On" : "Off";
    eye.title = "Toggle layer visibility";
    eye.addEventListener("click", (event) => {
      event.stopPropagation();
      setState(setLayerVisibility(state, layer.id, !layer.visible));
    });

    const body = document.createElement("div");
    const title = document.createElement("div");
    title.className = "layer-title";
    title.innerHTML = `<span></span><span>z ${layer.zIndex}</span>`;
    title.firstElementChild.textContent = layer.label;
    const meta = document.createElement("div");
    meta.className = "layer-meta";
    meta.textContent = `${Math.round(layer.opacity * 100)}% opacity | frames ${layer.clip.startFrame}-${layer.clip.endFrame}`;
    body.append(title, meta);
    row.append(eye, body);
    row.addEventListener("click", () => setState(selectLayer(state, layer.id)));
    els.layerList.append(row);
  }
}

function renderTimeline() {
  els.scrubber.max = String(Math.max(1, state.frameCount));
  els.scrubber.value = String(state.currentFrame);
  const totalSeconds = state.frameCount * frameDuration();
  const currentSeconds = (state.currentFrame - 1) * frameDuration();
  els.timeReadout.textContent = `${currentSeconds.toFixed(2)}s / ${totalSeconds.toFixed(2)}s`;
  els.stageReadout.textContent = `Frame ${state.currentFrame} / ${state.frameCount}`;

  els.trackLabels.textContent = "";
  els.trackArea.textContent = "";
  const frameWidth = Math.max(8, Math.floor((els.trackArea.clientWidth || 640) / Math.max(1, state.frameCount)));
  const trackWidth = Math.max(els.trackArea.clientWidth || 640, frameWidth * state.frameCount);
  els.trackArea.style.setProperty("--frame-width", `${frameWidth}px`);
  const ordered = state.layers.slice().sort((a, b) => b.zIndex - a.zIndex || a.id.localeCompare(b.id));

  for (const layer of ordered) {
    const label = document.createElement("div");
    label.className = "track-row";
    label.textContent = layer.label;
    els.trackLabels.append(label);

    const track = document.createElement("div");
    track.className = "track";
    track.style.width = `${trackWidth}px`;
    const clip = document.createElement("div");
    clip.className = "clip";
    clip.style.left = `${(layer.clip.startFrame - 1) * frameWidth}px`;
    clip.style.width = `${Math.max(frameWidth, (layer.clip.endFrame - layer.clip.startFrame + 1) * frameWidth)}px`;
    track.append(clip);
    track.addEventListener("click", (event) => {
      const rect = track.getBoundingClientRect();
      const frame = Math.floor((event.clientX - rect.left) / frameWidth) + 1;
      setState(selectLayer(setCurrentFrame(state, frame), layer.id));
    });
    els.trackArea.append(track);
  }

  const playhead = document.createElement("div");
  playhead.className = "playhead";
  playhead.style.left = `${(state.currentFrame - 1) * frameWidth}px`;
  playhead.style.height = `${Math.max(34, ordered.length * 34)}px`;
  els.trackArea.append(playhead);
}

function syncInspector() {
  const layer = selectedLayer();
  const disabled = !layer;
  for (const input of [
    els.xRange,
    els.xNumber,
    els.yRange,
    els.yNumber,
    els.scaleRange,
    els.scaleNumber,
    els.rotationRange,
    els.rotationNumber,
    els.opacityRange,
    els.opacityNumber,
    els.zIndex,
    els.visibility
  ]) {
    input.disabled = disabled;
  }
  if (!layer) {
    els.selectedName.textContent = "No layer";
    return;
  }
  const rotationDegrees = Math.round(radiansToDegrees(layer.transform.rotation));
  els.selectedName.textContent = layer.label;
  els.xRange.value = String(Math.round(layer.transform.translate[0]));
  els.xNumber.value = String(Math.round(layer.transform.translate[0]));
  els.yRange.value = String(Math.round(layer.transform.translate[1]));
  els.yNumber.value = String(Math.round(layer.transform.translate[1]));
  els.scaleRange.value = String(Math.round(layer.transform.scale * 100));
  els.scaleNumber.value = layer.transform.scale.toFixed(2);
  els.rotationRange.value = String(rotationDegrees);
  els.rotationNumber.value = String(rotationDegrees);
  els.opacityRange.value = String(Math.round(layer.opacity * 100));
  els.opacityNumber.value = String(Math.round(layer.opacity * 100));
  els.zIndex.value = String(layer.zIndex);
  els.visibility.value = String(layer.visible);
  els.xOut.textContent = `${Math.round(layer.transform.translate[0])} px`;
  els.yOut.textContent = `${Math.round(layer.transform.translate[1])} px`;
  els.scaleOut.textContent = layer.transform.scale.toFixed(2);
  els.rotationOut.textContent = `${rotationDegrees} deg`;
  els.opacityOut.textContent = `${Math.round(layer.opacity * 100)}%`;
}

function syncUi() {
  renderLayers();
  renderTimeline();
  syncInspector();
  els.playPause.textContent = state.playing ? "Pause" : "Play";
  els.editJson.textContent = JSON.stringify(serializeEditState(state), null, 2);
}

function updateSelectedTransform(patch) {
  const layer = selectedLayer();
  if (!layer) return;
  setState(updateLayerTransform(state, layer.id, {
    translate: patch.translate ?? layer.transform.translate,
    scale: patch.scale ?? layer.transform.scale,
    rotation: patch.rotation ?? layer.transform.rotation
  }));
}

function bindTransform(range, number, project) {
  const handler = (event) => {
    project(Number(event.currentTarget.value), event.currentTarget);
  };
  range.addEventListener("input", handler);
  number.addEventListener("input", handler);
}

function hitCircle(point, handle, radius) {
  return Math.hypot(point.x - handle.x, point.y - handle.y) <= radius;
}

function hitLayer(point, metrics) {
  const dx = point.x - metrics.centerX;
  const dy = point.y - metrics.centerY;
  const cos = Math.cos(-metrics.rotation);
  const sin = Math.sin(-metrics.rotation);
  const localX = dx * cos - dy * sin;
  const localY = dx * sin + dy * cos;
  return Math.abs(localX) <= metrics.width / 2 && Math.abs(localY) <= metrics.height / 2;
}

function pointerDown(event) {
  if (!fit) return;
  const point = scenePointFromEvent(event);
  const radius = 12 / fit.scale;
  let layer = selectedLayer();
  let metrics = layer ? layerMetrics.get(layer.id) : null;
  let mode = null;

  if (metrics && hitCircle(point, metrics.scaleHandle, radius)) mode = "scale";
  else if (metrics && hitCircle(point, metrics.rotateHandle, radius)) mode = "rotate";
  else if (metrics && hitLayer(point, metrics)) mode = "move";

  if (!mode) {
    const ordered = sortVisibleLayers(state, state.currentFrame).slice().reverse();
    for (const candidate of ordered) {
      const candidateMetrics = layerMetrics.get(candidate.id);
      if (candidateMetrics && hitLayer(point, candidateMetrics)) {
        setState(selectLayer(state, candidate.id));
        layer = candidate;
        metrics = candidateMetrics;
        mode = "move";
        break;
      }
    }
  }
  if (!mode || !layer || !metrics) return;
  event.preventDefault();
  els.stage.setPointerCapture(event.pointerId);
  drag = {
    mode,
    layerId: layer.id,
    startPoint: point,
    startTransform: {
      translate: [...layer.transform.translate],
      scale: layer.transform.scale,
      rotation: layer.transform.rotation
    },
    center: { x: metrics.centerX, y: metrics.centerY },
    startDistance: Math.max(1, Math.hypot(point.x - metrics.centerX, point.y - metrics.centerY)),
    startAngle: Math.atan2(point.y - metrics.centerY, point.x - metrics.centerX) - layer.transform.rotation
  };
}

function pointerMove(event) {
  if (!drag) return;
  const point = scenePointFromEvent(event);
  const layer = state.layers.find((candidate) => candidate.id === drag.layerId);
  if (!layer) return;
  let transform = layer.transform;
  if (drag.mode === "move") {
    transform = {
      ...transform,
      translate: [
        drag.startTransform.translate[0] + point.x - drag.startPoint.x,
        drag.startTransform.translate[1] + point.y - drag.startPoint.y
      ]
    };
  } else if (drag.mode === "scale") {
    const distance = Math.hypot(point.x - drag.center.x, point.y - drag.center.y);
    transform = {
      ...transform,
      scale: clamp(drag.startTransform.scale * distance / drag.startDistance, 0.2, 2.4)
    };
  } else if (drag.mode === "rotate") {
    transform = {
      ...transform,
      rotation: Math.atan2(point.y - drag.center.y, point.x - drag.center.x) - drag.startAngle
    };
  }
  state = updateLayerTransform(state, layer.id, transform);
  syncUi();
  renderStage();
}

function pointerUp(event) {
  if (drag) {
    els.stage.releasePointerCapture?.(event.pointerId);
  }
  drag = null;
}

function startPlayback() {
  state = { ...state, playing: true };
  playStart = performance.now() - (state.currentFrame - 1) * frameDuration() * 1000;
  const tick = (now) => {
    if (!state.playing) return;
    const elapsedFrames = Math.floor((now - playStart) / 1000 * state.fps);
    const nextFrame = elapsedFrames % Math.max(1, state.frameCount) + 1;
    state = setCurrentFrame(state, nextFrame);
    syncUi();
    renderStage();
    raf = requestAnimationFrame(tick);
  };
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(tick);
  syncUi();
}

function stopPlayback() {
  cancelAnimationFrame(raf);
  raf = 0;
  setState({ ...state, playing: false });
}

function bindEvents() {
  els.duplicateLayer.addEventListener("click", () => {
    const layer = selectedLayer();
    if (layer) setState(duplicateLayer(state, layer.id));
  });
  bindTransform(els.xRange, els.xNumber, (value) => {
    const layer = selectedLayer();
    if (layer) updateSelectedTransform({ translate: [value, layer.transform.translate[1]] });
  });
  bindTransform(els.yRange, els.yNumber, (value) => {
    const layer = selectedLayer();
    if (layer) updateSelectedTransform({ translate: [layer.transform.translate[0], value] });
  });
  bindTransform(els.scaleRange, els.scaleNumber, (value, input) => {
    const next = input === els.scaleRange ? value / 100 : value;
    updateSelectedTransform({ scale: clamp(next, 0.2, 2.4) });
  });
  bindTransform(els.rotationRange, els.rotationNumber, (value) => updateSelectedTransform({ rotation: degreesToRadians(value) }));
  bindTransform(els.opacityRange, els.opacityNumber, (value) => {
    const layer = selectedLayer();
    if (layer) setState(setLayerOpacity(state, layer.id, clamp(value / 100, 0, 1)));
  });
  els.zIndex.addEventListener("input", () => {
    const layer = selectedLayer();
    if (layer) setState(setLayerZIndex(state, layer.id, Number(els.zIndex.value)));
  });
  els.visibility.addEventListener("change", () => {
    const layer = selectedLayer();
    if (layer) setState(setLayerVisibility(state, layer.id, els.visibility.value === "true"));
  });
  els.scrubber.addEventListener("input", () => {
    if (state.playing) stopPlayback();
    setState(setCurrentFrame(state, Number(els.scrubber.value)));
  });
  els.playPause.addEventListener("click", () => {
    if (state.playing) stopPlayback();
    else startPlayback();
  });
  els.checkerboard.addEventListener("click", () => setState(setBackground(state, { type: "checkerboard" })));
  els.solidBackground.addEventListener("click", () => setState(setBackground(state, { type: "solid", color: els.customColor.value })));
  els.customColor.addEventListener("input", () => setState(setBackground(state, { type: "solid", color: els.customColor.value })));
  els.imageUpload.addEventListener("change", () => {
    const file = els.imageUpload.files?.[0];
    if (!file) return;
    if (backgroundObjectUrl) URL.revokeObjectURL(backgroundObjectUrl);
    const url = URL.createObjectURL(file);
    backgroundObjectUrl = url;
    const image = new Image();
    image.onload = () => {
      backgroundImage = image;
      setState(setBackground(state, { type: "image", imageUrl: url }));
    };
    image.src = url;
  });
  els.stage.addEventListener("pointerdown", pointerDown);
  els.stage.addEventListener("pointermove", pointerMove);
  els.stage.addEventListener("pointerup", pointerUp);
  els.stage.addEventListener("pointercancel", pointerUp);
  addEventListener("resize", () => {
    if (!state) return;
    renderStage();
    renderTimeline();
  });
}

function renderSwatches() {
  for (const color of swatchColors) {
    const button = document.createElement("button");
    button.className = "swatch";
    button.style.background = color;
    button.title = color;
    button.addEventListener("click", () => {
      els.customColor.value = color;
      setState(setBackground(state, { type: "solid", color }));
    });
    els.swatches.append(button);
  }
}

async function boot() {
  renderSwatches();
  bindEvents();
  const response = await fetch(sceneUrl);
  if (!response.ok) throw new Error(`Could not load ${sceneUrl}`);
  const documentJson = await response.json();
  scene = normalizeMotionJSON(documentJson, { baseUrl: sceneUrl });
  state = initializeEditorState(scene);
  assets = await loadRuntimeAssets(scene);
  els.status.textContent = `Loaded ${scene.label || scene.assetId} from ${sceneUrl}`;
  syncUi();
  renderStage();
}

boot().catch((error) => {
  els.status.textContent = error.message;
  els.status.style.color = "var(--danger)";
});

addEventListener("beforeunload", () => {
  if (backgroundObjectUrl) URL.revokeObjectURL(backgroundObjectUrl);
  cancelAnimationFrame(raf);
});
