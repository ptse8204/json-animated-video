---
historical: true
default_context: false
---

# Phase Report: SAM3 Candidate Filtering

## Summary

This phase fixes the red-ball demo failure where SAM3 Scene Sweep reported:

`Discovery provider 'sam3_auto_masks' produced no candidates usable for extraction`

That was not a normal outcome for the product flow. SAM3 was returning candidate masks, but MotionJSON rejected every candidate before extraction. The main issue was stability filtering: the UI `Clean` scene-sweep preset sets `stabilityThreshold: 0.86`, while SAM3 Tracker mask-generation records do not always include explicit stability metadata. MotionJSON treated missing stability as a synthetic `0.75`, so valid candidates could be rejected as `unstable_mask`.

## Changed Files

- `src/motionjson/providers/discovery.py`
  - Applies `stabilityThreshold` only when the provider reports explicit stability metadata.
  - Keeps confidence/stability display values from reported score when stability is absent.
- `src/motionjson/pipeline.py`
  - Writes `candidates.json` before candidate-to-object conversion, so rejected candidates remain inspectable after failure.
  - Adds rejection reason counts to fallback diagnostics and failure text when every candidate is rejected.
- `src/motionjson/ui/static/app.js`, `src/motionjson/ui/static/config_builder.js`, `src/motionjson/ui/static/index.html`
  - Uses `Balanced` as the normal Trace All / Scene Sweep default instead of `Clean`.
- `tests/test_sam3_providers.py`, `tests/test_discovery_providers.py`, `scripts/test_ui_config_builder.mjs`
  - Covers missing-stability SAM3 candidates, all-rejected diagnostics, and the Trace All default.

## Tests Run

- `python3 -m py_compile src/motionjson/providers/discovery.py src/motionjson/pipeline.py`
- `python3 -m pytest -q tests/test_sam3_providers.py::test_sam3_auto_masks_does_not_reject_missing_stability_metadata tests/test_discovery_providers.py::test_multi_object_pipeline_writes_rejected_candidates_before_no_usable_error`
- `python3 -m pytest -q tests/test_sam3_providers.py tests/test_discovery_providers.py tests/test_sam3_discovery_subprocess.py tests/test_job_artifacts.py tests/test_job_lifecycle.py`
- `python3 -m pytest -q`
- `npm test`
- `npm run build`
- `npm run ui:layout -- --check --state workflow-provider --viewport desktop-1440`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

## Known Limitations

- CI still does not run real CUDA SAM3 inference.
- If SAM3 returns only true whole-frame/background masks, extraction may still fail, but the UI will now have `candidates.json` and rejection counts to explain why.
- Existing failed jobs retain old artifacts; rerun after restarting the backend.

## Follow-Up Tasks

- Retest the red-ball video in Colab after restarting the backend.
- If all candidates are still rejected, inspect the new rejection reason counts in diagnostics and `candidates.json`.
