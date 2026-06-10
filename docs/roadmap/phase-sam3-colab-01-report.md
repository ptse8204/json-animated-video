---
historical: true
default_context: false
---

# Phase SAM3 Colab 01 Report: Local SAM3 Checkpoint Path Notebook Flow

## Summary

Updated the Colab UI provider connection notebook so local SAM3 setup separates
the official source/package checkout from the checkpoint path required by
MotionJSON. The notebook now:

- explains that `/content/sam3` is the cloned SAM3 source/package directory, not
  the model checkpoint;
- explains that `facebook/sam3` is a Hugging Face repo id, not a local model
  path;
- keeps checkpoint download opt-in with `RUN_DOWNLOAD_SAM3_CHECKPOINT = False`;
- resolves cached or manually supplied `sam3.pt` paths and sets
  `SAM3_LOCAL_MODEL` only after validation;
- prints copy-paste Model Connections values without printing token values;
- runs local readiness checks before MotionJSON backend diagnostics.

## Changed Files

- `notebooks/colab_ui_provider_connect_demo.ipynb`
- `tests/test_phase10_free_hosted_demos.py`
- `docs/roadmap/phase-sam3-colab-01-report.md`

## Tests Run

- `python3 -m pytest tests/test_phase10_free_hosted_demos.py::test_colab_ui_provider_connect_notebook_uses_private_colab_proxy_and_vendor_profiles tests/test_sam3_providers.py -q`
- `python3 -m pytest tests/test_phase10_free_hosted_demos.py -q`
- `python3 -m pytest tests/test_sam3_providers.py -q`
- `git diff --check`

## Known Limitations

- The notebook does not download `facebook/sam3` by default. Users must opt in
  after Hugging Face access is approved.
- The notebook-level validator is duplicated locally for Colab usability.
  Shared backend diagnostics for suspicious SAM3 paths are handled in a later
  phase.
- No real SAM3 checkpoint download or GPU smoke test was run in this
  environment.

## Follow-Up Tasks

- Update SAM3 local docs and provider setup guide copy to match the notebook.
- Add shared diagnostics for common invalid values such as `facebook/sam3` and
  `/content/sam3`.
- Add a dedicated notebook workflow regression test suite.
