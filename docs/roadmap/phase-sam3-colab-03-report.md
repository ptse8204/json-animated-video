# Phase SAM3 Colab 03 Report: SAM3 Local Path Diagnostics

## Summary

Added shared SAM3 local model path diagnostics and wired them into the local
SAM3 backend, capability reports, CLI text diagnostics, and provider settings
diagnose responses. Common mistakes now return specific guidance:

- `facebook/sam3` is reported as a Hugging Face repo id, not a local path.
- `/content/sam3` is reported as the cloned source/package directory, not the
  checkpoint.
- directories containing `sam3.pt` suggest the checkpoint file instead of
  treating the directory as valid.
- missing or unset paths explain how to resolve/download and set
  `SAM3_LOCAL_MODEL`.

## Changed Files

- `src/motionjson/providers/sam3.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/provider_settings.py`
- `tests/test_sam3_providers.py`
- `tests/test_capabilities.py`
- `tests/test_provider_settings.py`
- `docs/roadmap/phase-sam3-colab-03-report.md`

## Tests Run

- `python3 -m pytest tests/test_sam3_providers.py tests/test_capabilities.py tests/test_provider_settings.py -q`
- `python3 -m py_compile src/motionjson/providers/sam3.py src/motionjson/capabilities.py src/motionjson/provider_settings.py`
- `python3 -m motionjson.cli backend diagnostics --text`
- `SAM3_LOCAL_MODEL=facebook/sam3 python3 -m motionjson.cli backend diagnostics --text`
- `SAM3_LOCAL_MODEL=/content/sam3 python3 -m motionjson.cli backend diagnostics --text | rg -n "sam3-local|source/package|sam3.pt|Hugging"`
- `git diff --check`

## Known Limitations

- Diagnostics do not contact Hugging Face or verify access approval. They only
  validate local path shape and existence.
- Provider settings diagnose redacts local filesystem paths in API responses,
  so directory-with-checkpoint suggestions show the action with redacted path
  text in that response.

## Follow-Up Tasks

- Add a dedicated notebook workflow regression test file.
- Add low-risk Model Connections helper text for the local SAM3 field.
