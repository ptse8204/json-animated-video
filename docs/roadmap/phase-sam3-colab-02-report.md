---
historical: true
default_context: false
---

# Phase SAM3 Colab 02 Report: SAM3 Local Checkpoint Path Docs

## Summary

Updated SAM3 local documentation and provider setup guidance to match the
Colab workflow. The docs now state that `/content/sam3` is the source/package
checkout, `facebook/sam3` is a Hugging Face repo id, and `SAM3_LOCAL_MODEL`
must be the resolved local `sam3.pt` checkpoint file path.

Provider settings now point SAM3 local users to `docs/sam3_local.md`, label the
required field as a checkpoint file path, and show a practical resolver command
using `hf_hub_download` without embedding or printing tokens.

## Changed Files

- `docs/sam3_local.md`
- `docs/provider_capabilities.md`
- `docs/local_ui.md`
- `docs/security/api_keys.md`
- `src/motionjson/provider_settings.py`
- `tests/test_provider_settings.py`
- `tests/test_docs_links.py`
- `docs/roadmap/phase-sam3-colab-02-report.md`

## Tests Run

- `python3 -m pytest tests/test_provider_settings.py::test_sam3_local_setup_guide_distinguishes_source_repo_from_checkpoint_path tests/test_docs_links.py::test_od08_sam3_local_adapter_docs_are_truthful -q`
- `python3 -m pytest tests/test_sam3_providers.py -q`
- `python3 -m pytest tests/test_provider_settings.py tests/test_docs_links.py -q`
- `git diff --check`

## Known Limitations

- The setup guide documents the expected Hugging Face Hub resolver but does not
  run a real download in tests.
- Backend diagnostics still need more specific invalid-path wording for
  `facebook/sam3`, `/content/sam3`, and directories containing `sam3.pt`.

## Follow-Up Tasks

- Add shared SAM3 path validation and diagnostics messages.
- Add dedicated notebook workflow regression tests beyond the existing Colab
  demo guard.
