# Phase report: license and Colab notebook onboarding

## Purpose

Add explicit Apache-2.0 licensing and expand Colab onboarding from a CLI-only
path to a UI-first demo plus companion export-preview and provider diagnostics
notebooks.

## User value

- Users can understand redistribution/reuse rights from the root `LICENSE` and
  package metadata.
- Less technical users can launch the local MotionJSON UI from Colab and follow
  a guided red-ball demo path.
- Developers and support users can preview exported web runtime assets and
  collect provider diagnostics from a reproducible notebook.

## Files added

- `LICENSE`
- `notebooks/README.md`
- `notebooks/colab_ui_local_demo.ipynb`
- `notebooks/colab_red_ball_export_preview.ipynb`
- `notebooks/colab_provider_diagnostics.ipynb`

## Files updated by the apply script

- `README.md`
- `docs/run_free_instances.md`
- `pyproject.toml`
- `package.json`
- `packages/motionjson-runtime/package.json`
- `packages/motionjson-sdk/package.json`

## Validation

Recommended validation after applying:

```bash
python3 -m json.tool notebooks/colab_ui_local_demo.ipynb >/dev/null
python3 -m json.tool notebooks/colab_red_ball_export_preview.ipynb >/dev/null
python3 -m json.tool notebooks/colab_provider_diagnostics.ipynb >/dev/null
python3 -m pip install -e ".[ui]"
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli ui --help
npm test
npm run build
npm run lint
npm run ui:layout
npm run embed:smoke
```

## Known risks

- Colab's free tier is not appropriate for public long-running web UI hosting;
  the UI notebook labels this as a short interactive demo.
- Provider availability remains environment-dependent. The notebooks default to
  mock/threshold/no-model paths and keep optional ML providers diagnostic-only
  unless users configure them.

## Expected commit message

`phase license-colab: add Apache license and UI notebooks`
