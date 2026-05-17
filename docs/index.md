# MotionJSON Public Docs

MotionJSON is AI object-layer editing for video and web graphics. It turns
selected video elements into reusable motion layers controlled by JSON while
keeping photoreal objects as cached raster/alpha assets. SVG and Lottie are
reserved for simple vector-like silhouettes, labels, annotations, icons, and
flat graphics.

## Start Here

- [GA launch guide](ga_launch.md)
- [First run setup](first_run.md)
- [Release notes](release_notes.md)
- [Migration and known limitations](migration_and_known_limitations.md)
- [Deployment guide](deployment.md)
- [Billing and pricing](billing_pricing.md)
- [Onboarding guide](onboarding.md)
- [Security checklist](security_checklist.md)
- [Developer API](developer_api.md)
- [Local UI](local_ui.md)
- [Extraction run config](run_config.md)
- [Job artifacts and progress](job_artifacts.md)
- [Extraction provider pipeline](provider_pipeline.md)
- [Discovery providers](discovery_providers.md)
- [Track filtering and fallback diagnostics](track_filtering.md)
- [Provider capabilities and diagnostics](provider_capabilities.md)
- [Runtime guide](runtime.md)
- [Privacy and data handling](privacy.md)

## Release Candidate

- [Release notes](release_notes.md)
- [Migration and known limitations](migration_and_known_limitations.md)
- [Quality, testing, and benchmark plan](codex_motionjson_quality_benchmarks.md)
- [Benchmark fixtures](benchmark_fixtures.md)
- [Final export](final_export.md)

## Product Boundary

AI and segmentation belong at ingest, correction, labeling, and optimization
time. Normal editing, preview, reuse, and website embeds use cached assets plus
JSON transforms; they do not rerun AI for drag, scale, rotate, opacity, z-index,
or background replacement edits.

## Validation

```bash
pytest -q
npm test
npm run lint
git diff --check
```
