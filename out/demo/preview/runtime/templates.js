const TEMPLATE_PRESETS = Object.freeze({
  hero: Object.freeze({
    id: "hero",
    label: "Hero motion layer",
    className: "motionjson-template motionjson-template-hero",
    canvasClass: "motionjson-canvas motionjson-canvas-hero",
    background: "#fbfaf6",
    clickStateMs: 180,
    runtime: Object.freeze({ scrollState: true })
  }),
  ecommerce: Object.freeze({
    id: "ecommerce",
    label: "Ecommerce product layer",
    className: "motionjson-template motionjson-template-ecommerce",
    canvasClass: "motionjson-canvas motionjson-canvas-ecommerce",
    background: "#ffffff",
    clickStateMs: 140,
    runtime: Object.freeze({ scrollState: false })
  }),
  education: Object.freeze({
    id: "education",
    label: "Education explainer layer",
    className: "motionjson-template motionjson-template-education",
    canvasClass: "motionjson-canvas motionjson-canvas-education",
    background: "#f4f7fb",
    clickStateMs: 220,
    runtime: Object.freeze({ scrollState: true })
  })
});

function normalizeTemplateId(template) {
  if (!template) return null;
  if (typeof template === "string") return template.trim().toLowerCase();
  if (typeof template === "object" && template.id) return String(template.id).trim().toLowerCase();
  return null;
}

export function listMotionJSONTemplates() {
  return Object.values(TEMPLATE_PRESETS).map(({ runtime, ...template }) => ({ ...template }));
}

export function getMotionJSONTemplate(template) {
  const id = normalizeTemplateId(template);
  if (!id) return null;
  return TEMPLATE_PRESETS[id] || null;
}

export function resolveMotionJSONTemplate(template) {
  if (!template) return null;
  const preset = getMotionJSONTemplate(template);
  if (!preset && typeof template === "string") {
    throw new Error(`Unknown MotionJSON template: ${template}`);
  }
  if (typeof template === "object") {
    return {
      ...(preset || {}),
      ...template,
      id: normalizeTemplateId(template) || preset?.id,
      runtime: {
        ...(preset?.runtime || {}),
        ...(template.runtime || {})
      }
    };
  }
  return preset;
}

export function motionJSONTemplateOptions(template, options = {}) {
  const preset = resolveMotionJSONTemplate(template);
  if (!preset) return { ...options };
  return {
    ...(preset.runtime || {}),
    ...options,
    template: preset.id,
    templatePreset: preset,
    background: options.background ?? preset.background,
    canvasClass: options.canvasClass || preset.canvasClass,
    clickStateMs: options.clickStateMs ?? preset.clickStateMs
  };
}

export function decorateMotionJSONTemplate(element, template) {
  const preset = resolveMotionJSONTemplate(template);
  if (!preset || !element) return null;
  if (element.classList && preset.className) {
    for (const className of preset.className.split(/\s+/).filter(Boolean)) {
      element.classList.add(className);
    }
  }
  if (element.dataset) {
    element.dataset.motionjsonTemplateResolved = preset.id;
  }
  return preset;
}
