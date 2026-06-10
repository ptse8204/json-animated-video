---
historical: true
default_context: false
---

# Phase UI-MODEL-05B Report - First-Class SAM3 Guided Flow

## Summary

UI-MODEL-05B turns SAM3 into a first-class Local UI engine instead of a hidden
discovery side path and reduces the guided flow to goal, video, connect model,
prepare, and review/export decisions.

The phase adds `sam3-local` and `sam3-hosted` to the typed run-config contract,
adds `provider.sam3` for saved engine settings, updates the backend worker so
SAM3 UI jobs are valid local runs, and rewires the guided UI so users no longer
choose a low-level mask provider in the normal SAM path.

In the guided UI:

- `Trace one object` can run through SAM2 or SAM3, with SAM3 using a box-first
  exemplar flow.
- `Trace all objects` defaults to SAM3 auto masks and falls back to local SAM2
  automatic proposals when needed.
- `Find by description` defaults to SAM3 concept discovery.
- Model-free workflows skip SAM setup decisions.

The working tree was clean at phase start.

## Changed Files

- `src/motionjson/config.py`
- `src/motionjson/backend/models.py`
- `src/motionjson/backend/worker.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/config_builder.js`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_config.py`
- `tests/test_backend_jobs_worker.py`
- `tests/test_phase8_ui_config_builder.py`
- `tests/test_provider_settings.py`
- `tests/test_local_ui_api.py`
- `docs/local_ui.md`
- `docs/design/screenshots/phase-ui-model-05b/*`
- `docs/roadmap/phase-ui-model-05b-report.md`

## Browser Evidence

Before screenshots were captured into:

```text
docs/design/screenshots/phase-ui-model-05b/before
```

Before states covered:

- `first-run`
- `workflow-video`
- `model-setup-local`
- `model-setup-hosted-warning`
- `workflow-prompts`
- `workflow-review`

After screenshots were captured into:

```text
docs/design/screenshots/phase-ui-model-05b/after
```

After states covered:

- `first-run`
- `workflow-video`
- `model-setup-sam3-local`
- `model-setup-sam3-roboflow`
- `model-setup-sam3-custom`
- `prepare-sam3-single`
- `prepare-sam3-text`
- `prepare-sam3-trace-all`
- `workflow-review`

Required viewports covered:

- `390x844`
- `768x1024`
- `1024x768`
- `1366x768`
- `1440x900`
- `1920x1080`

Representative comparisons:

- Before `before/desktop-1440-model-setup-local.png`: the guided setup still
  centered on SAM2 and the connect step exposed mixed model choices without
  goal-aware filtering.
- After `after/desktop-1440-model-setup-sam3-roboflow.png`: the connect step
  shows only goal-compatible SAM3 choices and the inline setup surface for the
  selected engine.
- After `after/desktop-1440-prepare-sam3-single.png`: SAM3 single-object
  prepare is box-first and hides point/brush controls.
- After `after/desktop-1440-prepare-sam3-text.png`: the text prompt form leads
  the prepare step while the preview becomes secondary.

## Implementation Notes

- Added first-class `sam3-local` and `sam3-hosted` provider names to the typed
  run-config and introduced `provider.sam3` with local model and hosted runtime
  fields.
- Updated backend provider policy so local UI jobs may use SAM2 and SAM3 engine
  names directly instead of rejecting them as non-deterministic aliases.
- Updated the worker to:
  - merge `provider.sam3` into discovery runtime config;
  - accept `sam3_concept`, `sam3_exemplar`, and `sam3_auto_masks` as real UI
    jobs;
  - construct local SAM2 runs directly again for prompted single-object flows.
- Added goal/capability metadata to provider and hosted-profile definitions so
  the guided connect step can filter model choices by workflow.
- Kept legacy `text_detector`, `class_detector`, `sam_auto_masks`, and raw
  provider controls available through the broader Advanced/dashboard path, but
  removed the visible mask-provider decision from the normal guided flow.
- Reordered SAM3 text and trace-all prepare states so the decision surface leads
  and the video preview no longer dominates mobile or desktop by default.
- Stopped showing positive “providers are ready” alerts on every form change;
  setup messaging now appears only when there is an actual blocker, warning, or
  explicit action result.

## Tests Run

```bash
npm run build
```

Passed.

```bash
npm test
```

Passed: 21 Node tests.

```bash
npm run lint
```

Passed.

```bash
python3 -m pytest tests/test_config.py tests/test_backend_jobs_worker.py tests/test_phase8_ui_config_builder.py tests/test_provider_settings.py tests/test_local_ui_api.py -q
```

Passed: 105 passed.

```bash
python3 -m pytest
```

Passed: 454 passed, 1 skipped.

```bash
node scripts/check_local_ui_layout.mjs --state first-run,workflow-video,model-setup-local,model-setup-hosted-warning,workflow-prompts,workflow-review --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-ui-model-05b/before
```

Passed. The existing Python multiprocessing `resource_tracker` semaphore warning
 still appears during worker shutdown.

```bash
node scripts/check_local_ui_layout.mjs --state first-run,workflow-video,model-setup-sam3-local,model-setup-sam3-roboflow,model-setup-sam3-custom,prepare-sam3-single,prepare-sam3-text,prepare-sam3-trace-all,workflow-review --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-ui-model-05b/after
```

Passed, with the same shutdown warning.

```bash
git diff --check
```

Passed.

## Known Limitations

- The fixed hosted SAM3 profiles still keep their current capability limits:
  Roboflow is not offered for single-object exemplar tracing, and Fal stays
  text-led only in the guided path.
- The custom hosted SAM3 path is treated as exemplar/tracking-capable because
  the user is explicitly selecting the generic MotionJSON SAM3-compatible
  contract. If the remote endpoint does not honor that contract, setup/test or
  run-time failures are surfaced after action time.
- The internal workflow state machine still uses the older finer-grained steps;
  the simplified 5-step model is the visible layer on top.

## Follow-Up Tasks

- Add a browser smoke that clicks through a real first-run SAM3 local flow and a
  hosted Roboflow text flow instead of relying only on capture states.
- Add a dedicated compact connect-step layout for mobile so local-path and API
  key forms read even more clearly at narrow widths.
- Consider promoting the remaining Advanced-only legacy discovery modes into a
  separate “Compatibility tools” surface instead of leaving them in the same
  dashboard.
