---
historical: true
default_context: false
---

# Phase report: license-colab 01 - Apache license metadata

## Summary

Added explicit Apache-2.0 licensing for MotionJSON source code and package
metadata. Updated current-facing release docs so they no longer describe the
repository as unlicensed, while preserving the distinction between project
source-code rights and user-supplied/generated media rights.

## Starting worktree

The phase started from a dirty tree with untracked bundle files already
present: `LICENSE`, `README_UPDATE_NOTES.md`,
`apply_motionjson_license_colab_update.py`,
`docs/roadmap/phase-license-colab-notebooks-report.md`,
`notebooks/README.md`, `notebooks/colab_ui_local_demo.ipynb`,
`notebooks/colab_red_ball_export_preview.ipynb`, and
`notebooks/colab_provider_diagnostics.ipynb`. Only the files owned by this
phase were staged for the phase commit.

## Changed files

- `LICENSE`
- `README.md`
- `pyproject.toml`
- `package.json`
- `packages/motionjson-runtime/package.json`
- `packages/motionjson-sdk/package.json`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `docs/release_checklist.md`
- `docs/release_notes.md`
- `docs/repo_status.md`
- `docs/security_checklist.md`
- `docs/roadmap/final-audit.md`
- `docs/roadmap/phase-license-colab-01-report.md`
- `tests/test_phase09_release_readiness.py`
- `tests/test_phase10_release_hardening.py`

## Tests run

- `python3 - <<'PY' ...` license metadata parse for `pyproject.toml`,
  root `package.json`, and workspace package manifests
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m pytest -q tests/test_phase09_release_readiness.py tests/test_phase10_release_hardening.py`
- `npm test`
- `npm run build`
- `git diff --check`
- Read-only `diff-review-scout`; findings on `LICENSE` validation and report
  file listing were addressed, then targeted pytest and `git diff --check`
  were rerun.

## Known limitations

- This phase does not create a release tag.
- The Apache-2.0 project license does not grant rights to user-provided videos,
  model checkpoints, provider outputs, or generated assets whose rights depend
  on source-media metadata.

## Follow-up tasks

- Add Colab UI onboarding in the next phase.
