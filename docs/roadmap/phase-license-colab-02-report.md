---
historical: true
default_context: false
---

# Phase report: license-colab 02 - Colab UI demo

## Summary

Added a Google Colab local UI onboarding path. The notebook clones MotionJSON,
installs the lightweight UI extra, creates the deterministic red-ball video,
runs provider diagnostics, starts `motionjson ui --no-open --mock`, and opens
the UI through Colab's notebook port proxy.

## Starting worktree

The phase started after commit `e99b9ac` with untracked Colab bundle files still
present from the initial worktree. This phase stages only the UI notebook,
notebook index, UI Colab docs links, tests, and this report. The companion
export preview and provider diagnostics notebooks remain for Phase 3.

## Changed files

- `notebooks/colab_ui_local_demo.ipynb`
- `notebooks/README.md`
- `README.md`
- `docs/index.md`
- `docs/run_free_instances.md`
- `docs/repo_status.md`
- `docs/roadmap/phase-license-colab-02-report.md`
- `tests/test_phase10_free_hosted_demos.py`

## Tests run

- `python3 -m json.tool notebooks/colab_ui_local_demo.ipynb >/dev/null`
- `python3 -m motionjson.cli backend diagnostics --json`
- `python3 -m pytest -q tests/test_phase10_free_hosted_demos.py`
- `python3 -m pytest -q tests/test_docs_links.py tests/test_phase10_release_hardening.py`
- `python3 -m motionjson.cli ui --help`
- `npm run build`
- `git diff --check`
- Read-only `diff-review-scout`; the finding that the notebook workspace ZIP
  could include the local SQLite database was addressed by replacing the ZIP
  download cell with a log-tail troubleshooting cell, then targeted tests were
  rerun.

## Known limitations

- The Colab UI notebook is framed as a short interactive demo, not public
  hosting for a long-running MotionJSON web service.
- The default path is mock/no-model. Real SAM2, detector, hosted segmentation,
  and model-planner providers remain optional and environment-dependent.
- Users still need to register the generated red-ball video path in the UI
  after the notebook starts the server.
- The notebook intentionally does not download the UI workspace database or
  storage root, because provider settings and generated artifacts may be
  sensitive after user interaction.

## Follow-up tasks

- Add companion Colab notebooks for export/browser preview and provider
  diagnostics in Phase 3.
