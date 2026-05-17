export function frameIndexAt(timeSeconds, fps, frameCount, options = {}) {
  if (!frameCount) return 0;
  const safeFps = Number.isFinite(Number(fps)) && Number(fps) > 0 ? Number(fps) : 12;
  const raw = Math.max(0, Math.floor(Math.max(0, timeSeconds) * safeFps));
  if (options.loop === false) return Math.min(frameCount - 1, raw);
  return raw % frameCount;
}

export function frameAt(scene, timeSeconds, options = {}) {
  const frames = scene.assets.sequence;
  return frames[frameIndexAt(timeSeconds, scene.canvas.fps, frames.length, options)] || null;
}

export function transformFromState(state, context = {}) {
  if (!state || typeof state !== "object") {
    return { translate: [0, 0], scale: 1, rotation: 0, opacity: 1, outline: false };
  }
  const progress = Number.isFinite(context.scrollProgress) ? context.scrollProgress : 1;
  const translate = Array.isArray(state.translate)
    ? [Number(state.translate[0] || 0) * progress || 0, Number(state.translate[1] || 0) * progress || 0]
    : [0, 0];
  return {
    translate,
    scale: Number.isFinite(Number(state.scale)) ? Number(state.scale) : 1,
    rotation: Number.isFinite(Number(state.rotation)) ? Number(state.rotation) * progress : 0,
    opacity: Number.isFinite(Number(state.opacity)) ? Number(state.opacity) : 1,
    outline: Boolean(state.outline)
  };
}

export function composeFrameTransform(frame, transforms = []) {
  const output = {
    x: frame?.x || 0,
    y: frame?.y || 0,
    scale: frame?.scale ?? 1,
    rotation: frame?.rotation ?? 0,
    opacity: frame?.opacity ?? 1,
    translate: [0, 0],
    outline: false
  };
  for (const transform of transforms) {
    if (!transform) continue;
    if (Array.isArray(transform.translate)) {
      output.translate[0] += Number(transform.translate[0] || 0);
      output.translate[1] += Number(transform.translate[1] || 0);
    }
    if (Number.isFinite(Number(transform.scale))) output.scale *= Number(transform.scale);
    if (Number.isFinite(Number(transform.rotation))) output.rotation += Number(transform.rotation);
    if (Number.isFinite(Number(transform.opacity))) output.opacity *= Number(transform.opacity);
    output.outline ||= Boolean(transform.outline);
  }
  return output;
}

export function stateTransforms(scene, activeState, context = {}) {
  const states = scene.states || {};
  const transforms = [transformFromState(states.idle, context)];
  if (activeState === "hover") transforms.push(transformFromState(states.hover, context));
  if (activeState === "click") transforms.push(transformFromState(states.click, context));
  if (Number.isFinite(context.scrollProgress)) transforms.push(transformFromState(states.scroll, context));
  if (context.edit) transforms.push(transformFromState(context.edit, context));
  return transforms;
}
