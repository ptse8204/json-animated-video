import { createCanvasRuntime } from "./canvas.js";
import { normalizeMotionJSON } from "./manifest.js";
import { createPixiRuntime } from "./pixi.js";
import { decorateMotionJSONTemplate, motionJSONTemplateOptions } from "./templates.js";

function resolveTarget(target) {
  if (typeof target === "string") {
    const element = document.querySelector(target);
    if (!element) throw new Error(`MotionJSON target not found: ${target}`);
    return element;
  }
  return target;
}

function isCanvasElement(value) {
  return typeof HTMLCanvasElement !== "undefined" && value instanceof HTMLCanvasElement;
}

async function loadDocument(source) {
  if (typeof source !== "string") return { document: source, baseUrl: "" };
  const response = await fetch(source);
  if (!response.ok) throw new Error(`Could not fetch MotionJSON manifest: ${response.status}`);
  return { document: await response.json(), baseUrl: source };
}

export async function mountMotionJSON(target, source, options = {}) {
  const element = resolveTarget(target);
  const runtimeOptions = motionJSONTemplateOptions(options.template, options);
  const templatePreset = decorateMotionJSONTemplate(element, runtimeOptions.templatePreset || runtimeOptions.template);
  const { document: motionDocument, baseUrl } = await loadDocument(source);
  const scene = normalizeMotionJSON(motionDocument, { ...runtimeOptions, baseUrl: runtimeOptions.baseUrl || baseUrl });
  const usePixi = runtimeOptions.renderer === "pixi";
  const createdCanvas = !usePixi && !isCanvasElement(element);
  const canvas = usePixi
    ? null
    : isCanvasElement(element)
      ? element
      : document.createElement("canvas");
  if (canvas && createdCanvas) {
    canvas.className = runtimeOptions.canvasClass || "motionjson-canvas";
    element.appendChild(canvas);
  }

  const runtime = usePixi
    ? await createPixiRuntime(element, scene, runtimeOptions)
    : createCanvasRuntime(canvas, scene, runtimeOptions);
  if (runtime.load) await runtime.load();
  const surface = canvas || runtime.app?.view || runtime.canvas || element;

  const onEnter = () => runtime.setState("hover");
  const onLeave = () => runtime.setState("idle");
  const onClick = (event) => {
    runtime.setState("click");
    runtimeOptions.onClick?.({ event, scene, action: scene.states.click?.action, template: templatePreset });
    setTimeout(() => runtime.setState("idle"), runtimeOptions.clickStateMs || 180);
  };
  const onScroll = () => {
    const maxScroll = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    runtime.setScrollProgress?.(Math.min(1, scrollY / maxScroll));
  };

  surface.addEventListener("mouseenter", onEnter);
  surface.addEventListener("mouseleave", onLeave);
  surface.addEventListener("click", onClick);
  if (runtimeOptions.scrollState !== false) addEventListener("scroll", onScroll, { passive: true });
  runtime.start?.();

  return {
    runtime,
    scene,
    template: templatePreset,
    canvas: surface,
    surface,
    destroy() {
      surface.removeEventListener("mouseenter", onEnter);
      surface.removeEventListener("mouseleave", onLeave);
      surface.removeEventListener("click", onClick);
      if (runtimeOptions.scrollState !== false) removeEventListener("scroll", onScroll);
      runtime.destroy?.();
      if (createdCanvas) canvas.remove();
    }
  };
}

export function autoMountMotionJSON(root = document, options = {}) {
  const mounts = [];
  const elements = root.querySelectorAll("[data-motionjson-src], [data-motionjson-manifest]");
  for (const element of elements) {
    if (element.dataset.motionjsonMounted === "true") continue;
    const source = element.dataset.motionjsonSrc || element.dataset.motionjsonManifest;
    if (!source) continue;
    element.dataset.motionjsonMounted = "true";
    mounts.push(mountMotionJSON(element, source, {
      ...options,
      renderer: element.dataset.motionjsonRenderer || options.renderer,
      template: element.dataset.motionjsonTemplate || options.template,
      background: element.dataset.motionjsonBackground || options.background,
      showBounds: element.dataset.motionjsonBounds === "true" || options.showBounds
    }));
  }
  return Promise.all(mounts);
}
