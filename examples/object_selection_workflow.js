(function () {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const defaultBase = window.location.pathname.includes('/preview/') ? '..' : '/out/demo';
  const manifestUrl = params.get('manifest') || params.get('asset') || `${defaultBase}/web_asset_manifest.json`;
  const sceneUrl = params.get('scene') || `${defaultBase}/scene_graph.json`;
  const reviewUrl = params.get('review') || '';
  const exportUrl = params.get('export') || '';
  const jobId = params.get('jobId') || '';

  const $ = (id) => document.getElementById(id);
  const els = {
    statusDot: $('statusDot'),
    headerStatus: $('headerStatus'),
    videoUpload: $('videoUpload'),
    sourceVideo: $('sourceVideo'),
    selectionOverlay: $('selectionOverlay'),
    videoFrame: $('videoFrame'),
    videoEmpty: $('videoEmpty'),
    scrub: $('scrub'),
    currentTimeOut: $('currentTimeOut'),
    durationScrubOut: $('durationScrubOut'),
    durationOut: $('durationOut'),
    frameOut: $('frameOut'),
    videoSizeOut: $('videoSizeOut'),
    promptFrameOut: $('promptFrameOut'),
    pointMode: $('pointMode'),
    boxMode: $('boxMode'),
    selectionSummary: $('selectionSummary'),
    selectionX: $('selectionX'),
    selectionY: $('selectionY'),
    selectionW: $('selectionW'),
    selectionH: $('selectionH'),
    providerSelect: $('providerSelect'),
    labelInput: $('labelInput'),
    simulateJob: $('simulateJob'),
    clearSelection: $('clearSelection'),
    statusList: $('statusList'),
    jobBadge: $('jobBadge'),
    cliCommand: $('cliCommand'),
    exportMotionJson: $('exportMotionJson'),
    exportStatusLine: $('exportStatusLine'),
    correctionMode: $('correctionMode'),
    correctionFrame: $('correctionFrame'),
    correctionRadius: $('correctionRadius'),
    correctionPropagate: $('correctionPropagate'),
    correctionPropagationMode: $('correctionPropagationMode'),
    correctionPropagateWindow: $('correctionPropagateWindow'),
    correctionSmooth: $('correctionSmooth'),
    addCorrection: $('addCorrection'),
    clearCorrections: $('clearCorrections'),
    correctionSummary: $('correctionSummary'),
    correctionCommand: $('correctionCommand'),
    correctionJson: $('correctionJson'),
    playPause: $('playPause'),
    capturePromptFrame: $('capturePromptFrame'),
    fitBadge: $('fitBadge'),
    assetCanvas: $('assetCanvas'),
    assetEmpty: $('assetEmpty'),
    assetStatus: $('assetStatus'),
    assetSource: $('assetSource'),
    assetFrame: $('assetFrame'),
    assetFrameOut: $('assetFrameOut'),
    xControl: $('xControl'),
    yControl: $('yControl'),
    scaleControl: $('scaleControl'),
    rotationControl: $('rotationControl'),
    opacityControl: $('opacityControl'),
    xOut: $('xOut'),
    yOut: $('yOut'),
    scaleOut: $('scaleOut'),
    rotationOut: $('rotationOut'),
    opacityOut: $('opacityOut'),
    transformJson: $('transformJson'),
    graphSummary: $('graphSummary'),
    graphMetrics: $('graphMetrics'),
    sceneGraphPre: $('sceneGraphPre'),
    manifestPre: $('manifestPre')
  };

  const jobSteps = ['queued', 'prompt ready', 'extracting', 'caching', 'ready'];
  const appState = {
    objectUrl: null,
    videoName: 'uploaded-video.mp4',
    selectionMode: 'point',
    selection: null,
    dragStart: null,
    dragPreview: null,
    promptFrame: 0,
    jobTimers: [],
    jobIndex: 0,
    manifest: null,
    sceneGraph: null,
    assetLayer: null,
    assetImages: [],
    spriteSheet: null,
    animationRequest: 0,
    assetPlaying: true,
    corrections: [],
    review: null,
    exportResult: null
  };

  function prettyJson(value) {
    return JSON.stringify(value, null, 2);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function round(value) {
    return Math.round(value);
  }

  function seconds(value) {
    return Number.isFinite(value) ? value.toFixed(2) : '0.00';
  }

  function shellQuote(value) {
    const text = String(value || '');
    if (/^[A-Za-z0-9_./:=,-]+$/.test(text)) return text;
    return `'${text.replace(/'/g, "'\\''")}'`;
  }

  function sceneBase(url) {
    const parts = url.split('/');
    parts.pop();
    return parts.join('/') || '.';
  }

  function loadImage(src) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = src;
    });
  }

  function currentVideoFrame() {
    const fps = appState.sceneGraph?.canvas?.fps || appState.manifest?.canvas?.fps || 30;
    return Math.max(0, Math.round((els.sourceVideo.currentTime || 0) * fps));
  }

  function displayedVideoRect() {
    const host = els.videoFrame.getBoundingClientRect();
    const video = els.sourceVideo;
    const videoWidth = video.videoWidth || 16;
    const videoHeight = video.videoHeight || 9;
    const scale = Math.min(host.width / videoWidth, host.height / videoHeight);
    const width = videoWidth * scale;
    const height = videoHeight * scale;
    return {
      left: (host.width - width) / 2,
      top: (host.height - height) / 2,
      width,
      height,
      scale,
      videoWidth,
      videoHeight,
      hostWidth: host.width,
      hostHeight: host.height
    };
  }

  function pointerToVideoPoint(event) {
    const host = els.videoFrame.getBoundingClientRect();
    const fit = displayedVideoRect();
    const px = event.clientX - host.left;
    const py = event.clientY - host.top;
    if (px < fit.left || py < fit.top || px > fit.left + fit.width || py > fit.top + fit.height) {
      return null;
    }
    return {
      x: round(clamp((px - fit.left) / fit.scale, 0, fit.videoWidth)),
      y: round(clamp((py - fit.top) / fit.scale, 0, fit.videoHeight))
    };
  }

  function setHeaderStatus(text, mode) {
    els.headerStatus.textContent = text;
    els.statusDot.style.background = mode === 'ready' ? 'var(--accent)' : mode === 'error' ? 'var(--danger)' : 'var(--warn)';
    els.statusDot.style.boxShadow = mode === 'ready'
      ? '0 0 0 3px rgba(109, 201, 184, .13)'
      : mode === 'error'
        ? '0 0 0 3px rgba(216, 111, 98, .13)'
        : '0 0 0 3px rgba(240, 179, 90, .13)';
  }

  function renderStatusSteps() {
    els.statusList.innerHTML = jobSteps.map((step, index) => {
      const state = index < appState.jobIndex ? 'done' : index === appState.jobIndex ? 'active' : '';
      const mark = index < appState.jobIndex ? 'cached' : index === appState.jobIndex ? 'running' : 'waiting';
      return `<div class="status-step ${state}"><span>${step}</span><strong>${mark}</strong></div>`;
    }).join('');
    els.jobBadge.textContent = jobSteps[Math.min(appState.jobIndex, jobSteps.length - 1)];
  }

  function activeSelection() {
    return appState.dragPreview || appState.selection;
  }

  function updateSelectionReadout() {
    const selection = appState.selection;
    if (!selection) {
      els.selectionSummary.textContent = 'no prompt';
      els.selectionX.textContent = '-';
      els.selectionY.textContent = '-';
      els.selectionW.textContent = '-';
      els.selectionH.textContent = '-';
      els.promptFrameOut.textContent = 'none';
      els.correctionFrame.value = String(Math.max(1, appState.promptFrame || 1));
      return;
    }

    els.promptFrameOut.textContent = String(selection.promptFrame);
    els.correctionFrame.value = String(Math.max(1, selection.promptFrame || 1));
    if (selection.type === 'point') {
      els.selectionSummary.textContent = `point ${selection.x},${selection.y}`;
      els.selectionX.textContent = selection.x;
      els.selectionY.textContent = selection.y;
      els.selectionW.textContent = '-';
      els.selectionH.textContent = '-';
    } else {
      els.selectionSummary.textContent = `box ${selection.x},${selection.y},${selection.w},${selection.h}`;
      els.selectionX.textContent = selection.x;
      els.selectionY.textContent = selection.y;
      els.selectionW.textContent = selection.w;
      els.selectionH.textContent = selection.h;
    }
  }

  function buildCliCommand() {
    const provider = els.providerSelect.value;
    const label = els.labelInput.value.trim() || 'selected_object';
    const outName = label.toLowerCase().replace(/[^a-z0-9_-]+/g, '_') || 'selected_object';
    const parts = [
      'python3',
      '-m',
      'motionjson.cli',
      'extract',
      shellQuote(appState.videoName),
      '--out',
      shellQuote(`out/${outName}`),
      '--mask-provider',
      provider,
      '--label',
      shellQuote(label),
      '--sample-fps',
      '12',
      '--max-frames',
      '80'
    ];

    if (appState.selection?.type === 'point') {
      parts.push('--prompt-point', `${appState.selection.x},${appState.selection.y}`);
      parts.push('--sam2-prompt-frame', String(appState.selection.promptFrame));
    }
    if (appState.selection?.type === 'box') {
      parts.push('--prompt-box', `${appState.selection.x},${appState.selection.y},${appState.selection.w},${appState.selection.h}`);
      parts.push('--sam2-prompt-frame', String(appState.selection.promptFrame));
    }
    if (provider === 'external') {
      parts.push('--mask-dir', shellQuote('masks/'));
    }
    if (provider === 'threshold') {
      parts.push('--lower-hsv', '0,80,80', '--upper-hsv', '12,255,255');
    }

    const note = exportUrl
      ? [
          `# Reviewing Local UI job ${jobId || '(current run)'}.`,
          '# Use Export MotionJSON below to write the actual reviewed result.',
          '# This command is a reproducible CLI equivalent for a new extraction run.',
          parts.join(' ')
        ]
      : [
          '# Standalone example mode; not connected to a Local UI job API.',
          '# Normal preview edits below use cached assets plus JSON transforms only.',
          parts.join(' ')
        ];
    els.cliCommand.textContent = note.join('\n');
  }

  function correctionRequest() {
    const frame = Math.max(1, Number(els.correctionFrame.value) || 1);
    const windowSize = Math.max(0, Number(els.correctionPropagateWindow.value) || 0);
    const propagationModes = ['same_coordinates', 'centroid_delta'];
    const propagationMode = propagationModes.includes(els.correctionPropagationMode.value)
      ? els.correctionPropagationMode.value
      : 'same_coordinates';
    const propagation = {
      enabled: Boolean(els.correctionPropagate.checked),
      mode: propagationMode
    };
    if (propagation.enabled && windowSize) {
      propagation.frameRange = [Math.max(1, frame - windowSize), frame + windowSize];
    }
    return {
      schema: 'motionjson.correction_request.v0.1',
      objectId: 'object_0',
      operations: appState.corrections,
      propagation,
      temporalSmoothing: {
        enabled: Boolean(els.correctionSmooth.checked),
        radius: 1,
        threshold: 0.5
      },
      aiUsage: 'none'
    };
  }

  function buildCorrectionCommand() {
    const label = els.labelInput.value.trim() || 'selected_object';
    const outName = label.toLowerCase().replace(/[^a-z0-9_-]+/g, '_') || 'selected_object';
    const parts = [
      'python3',
      '-m',
      'motionjson.cli',
      'correct',
      shellQuote(`out/${outName}`),
      '--out',
      shellQuote(`out/${outName}_corrected`),
      '--request',
      'correction_request.json'
    ];
    els.correctionCommand.textContent = [
      '# Local deterministic correction only; no provider, network, or model-router call.',
      '# Normal drag/scale/rotate preview continues to use cached assets + JSON transforms.',
      els.correctionPropagate.checked ? `# Propagation: ${els.correctionPropagationMode.value || 'same_coordinates'}, window ${Math.max(0, Number(els.correctionPropagateWindow.value) || 0)}` : '# Propagation: off',
      parts.join(' ')
    ].join('\n');
    els.correctionJson.textContent = prettyJson(correctionRequest());
    els.correctionSummary.textContent = `${appState.corrections.length} ops`;
  }

  function addCorrectionFromSelection() {
    const selection = appState.selection;
    if (!selection) {
      setHeaderStatus('Choose a point or box before adding a correction.', 'error');
      return;
    }
    const frame = Math.max(1, Number(els.correctionFrame.value) || selection.promptFrame || 1);
    const radius = Math.max(1, Number(els.correctionRadius.value) || 12);
    const type = els.correctionMode.value;
    let operation;
    if (type === 'box' || selection.type === 'box') {
      const box = selection.type === 'box'
        ? selection
        : { x: selection.x - radius, y: selection.y - radius, w: radius * 2, h: radius * 2 };
      operation = { type: 'box', frame, x: box.x, y: box.y, w: box.w, h: box.h, mode: 'constrain' };
    } else if (type === 'brush') {
      operation = { type: 'brush', frame, points: [[selection.x, selection.y]], radius, mode: 'add' };
    } else if (type === 'remove_point') {
      operation = { type: 'remove_point', frame, x: selection.x, y: selection.y, radius };
    } else {
      operation = { type: 'add_point', frame, x: selection.x, y: selection.y, radius };
    }
    if (els.correctionPropagate.checked) operation.propagate = true;
    appState.corrections.push(operation);
    buildCorrectionCommand();
    setHeaderStatus('Correction request updated. Run the generated local command to regenerate cached assets.', 'warn');
  }

  function drawSelectionOverlay() {
    const canvas = els.selectionOverlay;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const cssW = Math.max(1, Math.floor(rect.width));
    const cssH = Math.max(1, Math.floor(rect.height));
    if (canvas.width !== Math.floor(cssW * dpr) || canvas.height !== Math.floor(cssH * dpr)) {
      canvas.width = Math.floor(cssW * dpr);
      canvas.height = Math.floor(cssH * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    if (!els.sourceVideo.videoWidth) return;
    const fit = displayedVideoRect();
    ctx.strokeStyle = 'rgba(109, 201, 184, .38)';
    ctx.lineWidth = 1;
    ctx.strokeRect(fit.left, fit.top, fit.width, fit.height);

    const selection = activeSelection();
    if (!selection) return;
    ctx.save();
    ctx.translate(fit.left, fit.top);
    ctx.scale(fit.scale, fit.scale);
    ctx.lineWidth = Math.max(1.5 / fit.scale, 1);
    ctx.strokeStyle = '#6dc9b8';
    ctx.fillStyle = 'rgba(109, 201, 184, .16)';

    if (selection.type === 'point') {
      const size = Math.max(10 / fit.scale, 5);
      ctx.beginPath();
      ctx.moveTo(selection.x - size, selection.y);
      ctx.lineTo(selection.x + size, selection.y);
      ctx.moveTo(selection.x, selection.y - size);
      ctx.lineTo(selection.x, selection.y + size);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(selection.x, selection.y, Math.max(4 / fit.scale, 2), 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.fillRect(selection.x, selection.y, selection.w, selection.h);
      ctx.strokeRect(selection.x, selection.y, selection.w, selection.h);
    }
    ctx.restore();
  }

  function normalizeBox(start, end) {
    const x = Math.min(start.x, end.x);
    const y = Math.min(start.y, end.y);
    const w = Math.abs(end.x - start.x);
    const h = Math.abs(end.y - start.y);
    return {
      type: 'box',
      x,
      y,
      w,
      h,
      promptFrame: appState.promptFrame
    };
  }

  function selectPoint(point) {
    appState.promptFrame = currentVideoFrame();
    appState.selection = {
      type: 'point',
      x: point.x,
      y: point.y,
      promptFrame: appState.promptFrame
    };
    updateSelectionReadout();
    buildCliCommand();
    buildCorrectionCommand();
    drawSelectionOverlay();
  }

  function setMode(mode) {
    appState.selectionMode = mode;
    els.pointMode.classList.toggle('active', mode === 'point');
    els.boxMode.classList.toggle('active', mode === 'box');
    drawSelectionOverlay();
  }

  function updateVideoMetrics() {
    const video = els.sourceVideo;
    const duration = Number.isFinite(video.duration) ? video.duration : 0;
    els.durationOut.textContent = `${seconds(duration)}s`;
    els.durationScrubOut.textContent = seconds(duration);
    els.currentTimeOut.textContent = seconds(video.currentTime || 0);
    els.frameOut.textContent = String(currentVideoFrame());
    els.videoSizeOut.textContent = video.videoWidth ? `${video.videoWidth}x${video.videoHeight}` : 'n/a';
    els.scrub.max = String(duration || 0);
    if (document.activeElement !== els.scrub) {
      els.scrub.value = String(video.currentTime || 0);
    }
    const fit = displayedVideoRect();
    els.fitBadge.textContent = `${round(fit.width)}x${round(fit.height)} contain`;
  }

  function handleUpload(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    if (appState.objectUrl) URL.revokeObjectURL(appState.objectUrl);
    appState.objectUrl = URL.createObjectURL(file);
    appState.videoName = file.name || 'uploaded-video.mp4';
    els.sourceVideo.src = appState.objectUrl;
    els.sourceVideo.load();
    els.videoEmpty.style.display = 'none';
    setHeaderStatus(`Loaded ${appState.videoName}. Prompt selection is local to this page.`, 'warn');
    buildCliCommand();
    buildCorrectionCommand();
  }

  function simulateJob() {
    appState.jobTimers.forEach((timer) => window.clearTimeout(timer));
    appState.jobTimers = [];
    appState.jobIndex = 0;
    renderStatusSteps();
    const hasPrompt = Boolean(appState.selection);
    setHeaderStatus(hasPrompt ? 'Simulating extraction job from stored prompt.' : 'Simulating queued job without a prompt.', 'warn');
    jobSteps.forEach((step, index) => {
      const timer = window.setTimeout(() => {
        appState.jobIndex = index;
        renderStatusSteps();
        if (step === 'ready') {
          appState.jobIndex = jobSteps.length - 1;
          renderStatusSteps();
          setHeaderStatus('Cached raster/alpha layer is ready for JSON transform preview.', 'ready');
        }
      }, index * 520);
      appState.jobTimers.push(timer);
    });
  }

  function transformState() {
    const edit = {
      translate: [Number(els.xControl.value), Number(els.yControl.value)],
      scale: Number(els.scaleControl.value) / 100,
      rotation: Number(els.rotationControl.value) * Math.PI / 180,
      opacity: Number(els.opacityControl.value) / 100
    };
    els.xOut.textContent = `${edit.translate[0]}px`;
    els.yOut.textContent = `${edit.translate[1]}px`;
    els.scaleOut.textContent = edit.scale.toFixed(2);
    els.rotationOut.textContent = `${els.rotationControl.value}deg`;
    els.opacityOut.textContent = `${els.opacityControl.value}%`;
    els.transformJson.textContent = prettyJson({
      layerEdit: edit,
      previewPolicy: 'cached assets + JSON transforms; no AI rerun for drag, scale, rotate, or opacity'
    });
    return edit;
  }

  function layerFromManifest(manifest) {
    return {
      id: manifest.assetId || 'object_0',
      fps: manifest.canvas?.fps || 12,
      canvas: {
        width: manifest.canvas?.width || 320,
        height: manifest.canvas?.height || 180
      },
      spritesheet: manifest.assets?.spritesheet || null,
      frames: manifest.assets?.sequence || []
    };
  }

  function layerFromScene(scene) {
    if (scene.layers && scene.layers[0]) {
      return {
        id: scene.layers[0].id,
        fps: scene.layers[0].fps || scene.canvas?.fps || 12,
        canvas: {
          width: scene.canvas?.width || 320,
          height: scene.canvas?.height || 180
        },
        spritesheet: scene.objects?.[0]?.assets?.spritesheet || null,
        frames: scene.layers[0].frames || []
      };
    }
    const object = scene.objects?.[0] || {};
    return {
      id: object.id || 'object_0',
      fps: scene.canvas?.fps || 12,
      canvas: {
        width: scene.canvas?.width || 320,
        height: scene.canvas?.height || 180
      },
      spritesheet: object.assets?.spritesheet || null,
      frames: object.motion || object.frames || []
    };
  }

  async function loadJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${url} returned ${response.status}`);
    return response.json();
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload || {})
    });
    const text = await response.text();
    let body = {};
    if (text) {
      try {
        body = JSON.parse(text);
      } catch (error) {
        body = { error: text.slice(0, 200) };
      }
    }
    if (!response.ok) throw new Error(body.error || body.detail || `${url} returned ${response.status}`);
    return body;
  }

  async function loadReviewState() {
    if (!reviewUrl) return;
    try {
      const payload = await loadJson(reviewUrl);
      appState.review = payload.review || payload;
      const tracks = Array.isArray(appState.review.tracks) ? appState.review.tracks.length : 0;
      const objects = Array.isArray(appState.review.objects) ? appState.review.objects.length : 0;
      const reviewCount = tracks || objects;
      els.exportStatusLine.textContent = `Connected to Local UI job ${jobId || ''}. ${reviewCount} reviewed object${reviewCount === 1 ? '' : 's'} available for export.`;
      els.exportMotionJson.disabled = false;
    } catch (error) {
      els.exportStatusLine.textContent = `Review API unavailable: ${error.message}`;
      els.exportMotionJson.disabled = !exportUrl;
    }
  }

  async function exportMotionJson() {
    if (!exportUrl) {
      els.exportStatusLine.textContent = 'This standalone example is not connected to a Local UI export endpoint.';
      return;
    }
    els.exportMotionJson.disabled = true;
    els.exportStatusLine.textContent = 'Exporting reviewed MotionJSON artifacts...';
    try {
      const result = await postJson(exportUrl, {
        preset: 'compact',
        includeMasks: false,
        includeContours: false,
        includePreview: true
      });
      appState.exportResult = result.export || result;
      const assets = Array.isArray(result.artifacts) ? result.artifacts : Array.isArray(appState.exportResult.assets) ? appState.exportResult.assets : [];
      const sceneAsset = assets.find((asset) => ['validated_motionjson_scene', 'scene_graph'].includes(asset.kind));
      const packageAsset = assets.find((asset) => ['website_package', 'motionjson_export_zip'].includes(asset.kind));
      els.exportStatusLine.innerHTML = [
        'Export complete.',
        sceneAsset?.contentUrl ? `<a href="${sceneAsset.contentUrl}" target="_blank" rel="noopener noreferrer">Open scene_graph.json</a>` : '',
        packageAsset?.contentUrl ? `<a href="${packageAsset.contentUrl}" target="_blank" rel="noopener noreferrer">Open package</a>` : ''
      ].filter(Boolean).join(' ');
      if (window.parent && window.parent !== window) {
        window.parent.postMessage(
          {
            type: 'motionjson:export-complete',
            jobId,
            export: appState.exportResult,
            artifactCount: assets.length
          },
          window.location.origin
        );
      }
      setHeaderStatus('Actual MotionJSON export finished for this Local UI run.', 'ready');
    } catch (error) {
      els.exportStatusLine.textContent = `Export failed: ${error.message}`;
      setHeaderStatus('MotionJSON export failed.', 'error');
    } finally {
      els.exportMotionJson.disabled = false;
    }
  }

  async function loadAssetDocuments() {
    els.assetSource.textContent = manifestUrl;
    const [manifestResult, sceneResult] = await Promise.allSettled([
      loadJson(manifestUrl),
      loadJson(sceneUrl)
    ]);

    if (manifestResult.status === 'fulfilled') {
      appState.manifest = manifestResult.value;
      els.manifestPre.textContent = prettyJson(appState.manifest);
    } else {
      els.manifestPre.textContent = manifestResult.reason.message;
    }

    if (sceneResult.status === 'fulfilled') {
      appState.sceneGraph = sceneResult.value;
      els.sceneGraphPre.textContent = prettyJson(appState.sceneGraph);
    } else {
      els.sceneGraphPre.textContent = sceneResult.reason.message;
    }

    if (!appState.manifest && !appState.sceneGraph) {
      throw new Error('Could not load scene_graph.json or web_asset_manifest.json');
    }

    const layer = appState.manifest ? layerFromManifest(appState.manifest) : layerFromScene(appState.sceneGraph);
    appState.assetLayer = layer;
    const base = appState.manifest ? sceneBase(manifestUrl) : sceneBase(sceneUrl);
    appState.spriteSheet = layer.spritesheet?.path ? await loadImage(`${base}/${layer.spritesheet.path}`) : null;
    appState.assetImages = appState.spriteSheet
      ? []
      : await Promise.all(layer.frames.map((frame) => frame.asset ? loadImage(`${base}/${frame.asset}`) : null));

    els.assetFrame.max = String(Math.max(0, layer.frames.length - 1));
    els.assetEmpty.style.display = layer.frames.length ? 'none' : 'grid';
    els.assetStatus.textContent = layer.frames.length ? `${layer.frames.length} cached frames` : 'no cached frames';
    renderGraphSummary();
  }

  function renderGraphSummary() {
    const scene = appState.sceneGraph;
    const manifest = appState.manifest;
    const canvas = manifest?.canvas || scene?.canvas || {};
    const objects = scene?.objects?.length || (manifest ? 1 : 0);
    const frames = manifest?.assets?.sequence?.length || scene?.canvas?.frame_count || appState.assetLayer?.frames?.length || 0;
    els.graphSummary.textContent = `${objects} object, ${frames} frames`;
    els.graphMetrics.innerHTML = [
      ['Objects', objects],
      ['Frames', frames],
      ['Canvas', canvas.width && canvas.height ? `${canvas.width}x${canvas.height}` : 'n/a'],
      ['Mode', manifest?.renderMode || scene?.rendering?.defaultRenderMode || 'raster_alpha_sequence']
    ].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join('');
  }

  function frameSprite(frame) {
    return frame.sprite || null;
  }

  function frameSize(frame, img, sprite) {
    return {
      width: frame.width || frame.w || sprite?.w || img?.width || 1,
      height: frame.height || frame.h || sprite?.h || img?.height || 1
    };
  }

  function drawAssetPreview(now) {
    const canvas = els.assetCanvas;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const cssW = Math.max(1, Math.floor(rect.width));
    const cssH = Math.max(1, Math.floor(rect.height));
    if (canvas.width !== Math.floor(cssW * dpr) || canvas.height !== Math.floor(cssH * dpr)) {
      canvas.width = Math.floor(cssW * dpr);
      canvas.height = Math.floor(cssH * dpr);
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);
    ctx.fillStyle = '#111216';
    ctx.fillRect(0, 0, cssW, cssH);

    const layer = appState.assetLayer;
    if (!layer || !layer.frames.length) return;

    const autoIndex = appState.assetPlaying
      ? Math.floor((now / 1000) * (layer.fps || 12)) % layer.frames.length
      : Number(els.assetFrame.value);
    const index = clamp(autoIndex, 0, layer.frames.length - 1);
    if (document.activeElement !== els.assetFrame) {
      els.assetFrame.value = String(index);
    }
    els.assetFrameOut.textContent = String(layer.frames[index]?.frame || index);

    const frame = layer.frames[index];
    const img = appState.spriteSheet || appState.assetImages[index];
    if (!frame || !img || frame.visible === false) return;

    const canvasWidth = layer.canvas.width || appState.manifest?.canvas?.width || 320;
    const canvasHeight = layer.canvas.height || appState.manifest?.canvas?.height || 180;
    const fit = Math.min(cssW / canvasWidth, cssH / canvasHeight) * .92;
    const left = (cssW - canvasWidth * fit) / 2;
    const top = (cssH - canvasHeight * fit) / 2;
    const edit = transformState();
    const sprite = frameSprite(frame);
    const size = frameSize(frame, img, sprite);

    ctx.save();
    ctx.translate(left, top);
    ctx.scale(fit, fit);
    ctx.strokeStyle = 'rgba(244, 241, 234, .14)';
    ctx.strokeRect(0, 0, canvasWidth, canvasHeight);
    ctx.globalAlpha = (frame.opacity == null ? 1 : frame.opacity) * edit.opacity;
    ctx.translate((frame.x || 0) + size.width / 2 + edit.translate[0], (frame.y || 0) + size.height / 2 + edit.translate[1]);
    ctx.rotate((frame.rotation || 0) + edit.rotation);
    ctx.scale((frame.scale || 1) * edit.scale, (frame.scale || 1) * edit.scale);
    if (sprite && appState.spriteSheet) {
      ctx.drawImage(img, sprite.x, sprite.y, sprite.w, sprite.h, -size.width / 2, -size.height / 2, size.width, size.height);
    } else {
      ctx.drawImage(img, -size.width / 2, -size.height / 2, size.width, size.height);
    }
    ctx.strokeStyle = '#6dc9b8';
    ctx.lineWidth = 2 / fit;
    ctx.strokeRect(-size.width / 2, -size.height / 2, size.width, size.height);
    ctx.restore();
  }

  function animationTick(now) {
    updateVideoMetrics();
    drawSelectionOverlay();
    drawAssetPreview(now);
    appState.animationRequest = window.requestAnimationFrame(animationTick);
  }

  function bindEvents() {
    els.videoUpload.addEventListener('change', handleUpload);
    els.sourceVideo.addEventListener('loadedmetadata', () => {
      updateVideoMetrics();
      drawSelectionOverlay();
    });
    els.sourceVideo.addEventListener('timeupdate', updateVideoMetrics);
    els.scrub.addEventListener('input', () => {
      els.sourceVideo.currentTime = Number(els.scrub.value);
      updateVideoMetrics();
    });
    els.playPause.addEventListener('click', () => {
      if (!els.sourceVideo.src) return;
      if (els.sourceVideo.paused) {
        els.sourceVideo.play();
        els.playPause.textContent = 'Pause';
      } else {
        els.sourceVideo.pause();
        els.playPause.textContent = 'Play';
      }
    });
    els.capturePromptFrame.addEventListener('click', () => {
      appState.promptFrame = currentVideoFrame();
      if (appState.selection) appState.selection.promptFrame = appState.promptFrame;
      updateSelectionReadout();
      buildCliCommand();
      buildCorrectionCommand();
    });
    els.pointMode.addEventListener('click', () => setMode('point'));
    els.boxMode.addEventListener('click', () => setMode('box'));
    els.providerSelect.addEventListener('change', buildCliCommand);
    els.exportMotionJson.addEventListener('click', exportMotionJson);
    els.labelInput.addEventListener('input', () => {
      buildCliCommand();
      buildCorrectionCommand();
    });
    els.simulateJob.addEventListener('click', simulateJob);
    els.addCorrection.addEventListener('click', addCorrectionFromSelection);
    els.clearCorrections.addEventListener('click', () => {
      appState.corrections = [];
      buildCorrectionCommand();
    });
    [els.correctionMode, els.correctionFrame, els.correctionRadius, els.correctionPropagate, els.correctionPropagationMode, els.correctionPropagateWindow, els.correctionSmooth].forEach((input) => {
      input.addEventListener('input', buildCorrectionCommand);
      input.addEventListener('change', buildCorrectionCommand);
    });
    els.clearSelection.addEventListener('click', () => {
      appState.selection = null;
      appState.dragPreview = null;
      updateSelectionReadout();
      buildCliCommand();
      buildCorrectionCommand();
      drawSelectionOverlay();
    });
    els.assetFrame.addEventListener('input', () => {
      appState.assetPlaying = false;
      els.assetFrameOut.textContent = els.assetFrame.value;
    });
    [els.xControl, els.yControl, els.scaleControl, els.rotationControl, els.opacityControl].forEach((input) => {
      input.addEventListener('input', transformState);
    });

    els.selectionOverlay.addEventListener('pointerdown', (event) => {
      const point = pointerToVideoPoint(event);
      if (!point || !els.sourceVideo.videoWidth) return;
      appState.promptFrame = currentVideoFrame();
      if (appState.selectionMode === 'point') {
        selectPoint(point);
        return;
      }
      appState.dragStart = point;
      appState.dragPreview = normalizeBox(point, point);
      els.selectionOverlay.setPointerCapture(event.pointerId);
      drawSelectionOverlay();
    });
    els.selectionOverlay.addEventListener('pointermove', (event) => {
      if (!appState.dragStart) return;
      const point = pointerToVideoPoint(event);
      if (!point) return;
      appState.dragPreview = normalizeBox(appState.dragStart, point);
      drawSelectionOverlay();
    });
    els.selectionOverlay.addEventListener('pointerup', (event) => {
      if (!appState.dragStart) return;
      const point = pointerToVideoPoint(event) || appState.dragStart;
      const box = normalizeBox(appState.dragStart, point);
      if (box.w >= 2 && box.h >= 2) {
        appState.selection = box;
      }
      appState.dragStart = null;
      appState.dragPreview = null;
      try {
        els.selectionOverlay.releasePointerCapture(event.pointerId);
      } catch (error) {
        /* Pointer capture may already be released by the browser. */
      }
      updateSelectionReadout();
      buildCliCommand();
      buildCorrectionCommand();
      drawSelectionOverlay();
    });
    window.addEventListener('resize', drawSelectionOverlay);
  }

  async function init() {
    renderStatusSteps();
    updateSelectionReadout();
    buildCliCommand();
    buildCorrectionCommand();
    transformState();
    bindEvents();
    try {
      await loadAssetDocuments();
      await loadReviewState();
      setHeaderStatus(`Loaded cached assets from ${manifestUrl}`, 'ready');
    } catch (error) {
      els.assetStatus.textContent = 'asset load failed';
      els.assetEmpty.style.display = 'grid';
      els.sceneGraphPre.textContent = error.stack || error.message;
      setHeaderStatus('Demo assets not loaded. Generate out/demo or pass query params.', 'error');
    }
    appState.animationRequest = window.requestAnimationFrame(animationTick);
  }

  window.addEventListener('beforeunload', () => {
    if (appState.objectUrl) URL.revokeObjectURL(appState.objectUrl);
    window.cancelAnimationFrame(appState.animationRequest);
  });

  init();
}());
