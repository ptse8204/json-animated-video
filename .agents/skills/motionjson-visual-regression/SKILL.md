---
name: motionjson-visual-regression
description: Use for MotionJSON screenshot capture, Playwright/browser smoke checks, layout-overlap checks, and docs asset regeneration for the Local UI.
---

# MotionJSON Visual Regression

Use this skill when validating Local UI layout, screenshots, README assets, or responsive behavior.

## Required Viewports

Check at least:

- 1366x768 laptop
- 1440x900 laptop/desktop
- 1920x1080 desktop
- 1024x768 narrow/tablet-like width

## What To Test

- No horizontal page overflow.
- Top bar, side navigation, main workspace, right inspector, and bottom timeline/job region do not collide.
- Dropdowns, dialogs, and details panels stay inside the viewport or intentionally overlay with a backdrop.
- Primary first-run actions remain visible.
- Focus rings are visible on keyboard navigation.
- Empty, loading, error, no-provider, and job-review states render without clipped text.

## Artifact Rules

- Store committed docs screenshots under `docs/assets/`.
- Store transient captures under `output/playwright/` or `.motionjson/tmp/`; do not commit transient browser traces unless explicitly needed.
- Screenshots must be real captures of the local UI or generated deterministic demos. Do not add fake screenshots.

## Validation Pattern

Prefer a lightweight script that can run without a full Node install beyond the repo's npm dependencies. If Playwright is not installed, document that and add a deterministic DOM/layout check with the browser automation available in the environment.

Phase reports must list:

- viewport sizes checked;
- commands run;
- screenshots generated or refreshed;
- remaining visual risks.
