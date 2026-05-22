# MotionJSON Apache-2.0 and Colab notebook update bundle

This bundle contains a commit-ready implementation for
`ptse8204/json-animated-video`:

- Apache License 2.0 root `LICENSE` file.
- Colab UI notebook: `notebooks/colab_ui_local_demo.ipynb`.
- Additional notebooks:
  - `notebooks/colab_red_ball_export_preview.ipynb`
  - `notebooks/colab_provider_diagnostics.ipynb`
- `notebooks/README.md` index.
- Roadmap phase report.
- An idempotent apply script that also updates README/docs and package metadata.

## Apply

From a local checkout of the repo:

```bash
python3 /path/to/motionjson_license_colab_update/apply_motionjson_license_colab_update.py --repo /path/to/json-animated-video
```

Then run validation:

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

Expected commit message:

```text
phase license-colab: add Apache license and UI notebooks
```
