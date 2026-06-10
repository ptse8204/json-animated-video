# Safety Invariants

These rules are stable across UI redesigns, roadmap changes, provider changes, and documentation refactors.

## Local And Hosted Boundaries

- MotionJSON is local-first by default.
- No hosted calls without explicit user opt-in.
- Hosted/network provider warnings must include cost and privacy language before a run starts.
- Hosted OpenAI/OpenRouter/model planners generate proposals only.
- OpenAI/OpenRouter are not segmentation, tracking, matting, or extraction providers.
- Segmentation/tracking must go through explicit CV providers.

## Secrets And Sensitive Data

- No browser-side secrets.
- Do not expose raw API keys, bearer tokens, storage keys, local absolute paths, or `file://` URIs in public responses, logs, screenshots, artifacts, validation errors, or reports.
- Keep provider credentials server-side and redacted.
- Environment-variable/provider-settings precedence must not leak raw values.

## Optional Dependencies

- CPU/mock/no-model workflows are required.
- Optional heavy ML dependencies must remain optional.
- Missing CUDA, SAM2, SAM3, detectors, FFmpeg, model weights, credentials, or optional packages must not break the base install.
- Provider failures must be visible, not swallowed.

## Model Plans And Extraction

- Model output must be validated before extraction.
- Model-generated run plans are proposals, not trusted extraction truth.
- Text prompts must be routed through detector/open-vocabulary candidate providers, not raw SAM2.
- SAM2/SAM3 capability, device, model, and hosted-readiness failures must be explicit.
- Automatic masks must be filtered so background, floor, wall, huge whole-frame, tiny, duplicate, and low-quality fragments do not become user-facing objects unless the user explicitly chooses all visible segments.

## Review And Export Truth

- Review/export gates must remain truthful.
- Exports should default to reviewed selected objects.
- Raster-only output must explain why vector/object tracks were unavailable.
- Partial success must show completed objects and failed object/frame/reason when available.
- A failed provider or rejected track must not be presented as a clean successful vector object.

## Claims And Rights

- Do not overclaim clean SVG/Lottie/vector conversion from photoreal video.
- Photoreal objects normally remain raster/alpha assets controlled by JSON transforms.
- Generated asset rights depend on source media, provider terms, user-entered rights metadata, and export metadata.
- Do not present user-supplied media, provider output, model checkpoints, or generated assets as repository-licensed unless their own rights metadata supports that claim.

## UI Redesign Boundary

- UI redesign may change layout completely.
- Cards, right rails, steppers, dashboards, panels, and current shell regions are not safety invariants.
- Any UI shape is acceptable only if it preserves local-first defaults, provider readiness, consent, visible failures, review truth, export readiness, and rights visibility.
