# Phase Flow Rebuild 6 Report: Documentation, Notebooks, And Requirements

## Summary

Updated the user-facing onboarding docs so they match the rebuilt Local UI flow
and current provider contract. The docs now use the exact visible UI names:
`Start`, `Video`, `Model`, `Prepare & run`, **Job Center** / **Run monitor**,
and `Review & export`. Review guidance now describes `Candidates` ->
`Track selected` -> `Tracks` -> `Corrections` -> `Export` and names the
primary actions `Track selected`, `Mark reviewed`, and
`Export reviewed objects`.

Added a central system requirements page with a "Which path should I choose?"
table covering CPU/no-model demo, local SAM2, hosted SAM2, local SAM3, hosted
SAM3, motion foreground, and external masks. The requirements keep
MotionJSON's base Python `>=3.10` separate from optional upstream SAM2/SAM3
runtime requirements and use conservative RAM/VRAM guidance.

Updated Colab notebook markdown and the notebook index so users can distinguish
CPU/no-model demos, Local UI provider-connect workflows, hosted-key paths, and
heavy local SAM setup. The notebooks now warn against private videos, API keys,
SAM checkpoints, or secret-containing outputs in shared notebooks, and they
state that Colab GPU/RAM/runtime resources are not guaranteed.

## Changed Files

- `README.md`
- `docs/system_requirements.md`
- `docs/index.md`
- `docs/first_run.md`
- `docs/local_ui.md`
- `docs/run_local.md`
- `docs/run_free_instances.md`
- `docs/troubleshooting.md`
- `docs/provider_capabilities.md`
- `docs/security/api_keys.md`
- `docs/repo_status.md`
- `notebooks/README.md`
- `notebooks/colab_provider_diagnostics.ipynb`
- `notebooks/colab_red_ball_cli_demo.ipynb`
- `notebooks/colab_red_ball_export_preview.ipynb`
- `notebooks/colab_ui_local_demo.ipynb`
- `notebooks/colab_ui_provider_connect_demo.ipynb`
- `docs/roadmap/phase-flow-rebuild-6-report.md`

## Verification Sources

- SAM2 official install guide:
  <https://github.com/facebookresearch/sam2/blob/main/INSTALL.md>
- SAM3 official repository install requirements:
  <https://github.com/facebookresearch/sam3>
- Roboflow SAM3 hosted API docs:
  <https://docs.roboflow.com/deploy/supported-models/sam3>
- Google Colab FAQ and resource limits:
  <https://research.google.com/colaboratory/faq.html#resource-limits>
- FFmpeg documentation:
  <https://www.ffmpeg.org/documentation.html>

## Tests Run

- `python3 - <<'PY' ... validate notebooks JSON/source/empty outputs ... PY`
  - Passed for all checked-in notebooks.
- `python3 -m pytest -p no:cacheprovider tests/test_docs_links.py tests/test_phase09_release_readiness.py -q`
  - Passed: 14 tests.
- `python3 -m pytest -q tests/test_phase10_free_hosted_demos.py tests/test_colab_notebooks.py`
  - Passed: 19 tests.
- `npm run build`
  - Passed.
- `npm test`
  - Passed: 21 Node tests.
- `npm run ui:layout -- --state workflow-review,workflow-review-failure,export-handoff --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
  - Passed.
- `npm run ui:layout -- --state workflow-goal,workflow-video,workflow-provider,workflow-run --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
  - Passed.
- `git diff --check`
  - Passed.

## Browser Evidence

No docs assets or UI layout files were changed in this phase, so no new
screenshots were committed. The required Local UI layout smoke was still run
against the documented setup, run, review, failure, and export handoff states
across the supported viewport matrix.

The full default `npm run ui:layout` command was started first, but the Chrome
CDP harness sat idle for more than four minutes with no result. That process
and its spawned UI/Chrome children were cleaned up. Focused phase-relevant
layout matrices then completed successfully. This appears to be a harness
runtime limitation for the exhaustive default state set, not a docs change
failure.

## Known Limitations

- The requirements are intentionally conservative. Real SAM2/SAM3 memory needs
  vary by checkpoint, clip length, resolution, prompt count, and provider
  implementation.
- Local SAM3 may require a separate Python 3.12/CUDA environment even though
  the MotionJSON base install remains Python `>=3.10`.
- The Colab notebooks remain structural/source validated in this phase; they
  were not executed end to end in Colab.
- Hosted provider docs explain the opt-in and privacy/cost boundary, but no
  hosted smoke tests were run because this phase must not call hosted
  providers without human-supplied credentials and review.

## Follow-Up Tasks

- Add a bounded timeout or progress logging to `scripts/check_local_ui_layout.mjs`
  so the full default matrix cannot hang silently.
- Refresh committed docs screenshots only after Phase 7 release validation
  decides whether new visual assets are needed.
- Keep `docs/system_requirements.md` synchronized with upstream SAM2/SAM3
  install guidance as those repositories evolve.
