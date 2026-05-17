# MotionJSON Docs

MotionJSON turns selected video objects into reusable motion layers controlled
by JSON while keeping photoreal objects as cached raster/alpha assets. Start
with the no-model path if you are new: it runs on CPU and does not require
SAM2, CUDA, detector weights, hosted services, or provider credentials.

## I Just Want To Try It Locally

1. [First run setup](first_run.md) explains the base install, diagnostics, the
   red-ball tutorial, PowerShell commands, and the local UI project flow.
2. [Run locally](run_local.md) gives copy-paste script and manual commands for
   the mock UI, red-ball CLI demo, backend API, Docker, and cleanup.
3. [Run on free or low-install instances](run_free_instances.md) covers
   Codespaces, Colab CLI demos, and the Hugging Face Space demo plan.
4. [Troubleshooting](troubleshooting.md) explains common setup, provider, bad
   mask, and raster-only failures.

Useful first commands:

```bash
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli ui --no-open --mock
python3 scripts/run_red_ball_demo.sh
```

## I Want To Extract An Object From A Video

Use this path when your goal is to create object tracks, masks, cutouts, and
MotionJSON output:

- [Examples](examples.md) shows the red-ball demo, UI screenshots, expected
  output folders, and browser preview links.
- [Local UI](local_ui.md) explains projects, videos, extraction presets, prompt
  tools, job review, corrections, and export.
- [Extraction run config](run_config.md) documents the typed config model behind
  CLI and UI runs.
- [Discovery providers](discovery_providers.md) explains when to use manual
  prompts, motion foreground, external masks, text detectors, class detectors,
  and automatic segment proposals.
- [Track filtering and fallback diagnostics](track_filtering.md) explains
  whole-frame mask rejection, raster fallback reason codes, and suggested fixes.
- [Job artifacts and progress](job_artifacts.md) lists the files and events a
  job writes.

## I Want To Build A Website Embed

Use this path when you already have a MotionJSON output folder and want to play
it on a page:

- [Runtime guide](runtime.md) shows plain JavaScript, Canvas2D, optional Pixi,
  React, timeline editing, website templates, and website ZIP export.
- [Final export](final_export.md) explains validated handoffs, export presets,
  and MP4/website-package outputs.
- [Schemas](schemas.md) explains scene graphs, object manifests, resource
  profiles, rights metadata, and production export metadata.
- [Rights and lineage](rights_and_lineage.md) explains source rights, generated
  asset lineage, and export warnings.
- [Privacy and data handling](privacy.md) explains local media and provider
  data boundaries.

Minimal local preview after running the red-ball demo:

```bash
python3 -m http.server 8080
```

Open:

```text
http://localhost:8080/examples/canvas_player.html?scene=/out/demo_red_ball/web_asset_manifest.json
```

## I Want To Develop Providers

Use this path when adding or debugging discovery, segmentation, tracking,
vectorization, or export providers:

- [Provider capabilities and diagnostics](provider_capabilities.md) documents
  provider names, status values, optional extras, CUDA/model/credential checks,
  and how failures should be surfaced.
- [Extraction provider pipeline](provider_pipeline.md) explains the
  `ObjectCandidateProvider`, `MaskProvider`, `VideoTracker`, `TrackLinker`,
  `Vectorizer`, and `Exporter` boundaries.
- [SAM2 segmentation providers](sam2_segmentation.md) documents optional local
  and hosted SAM2 paths, cache behavior, fallback routing, and tests.
- [AI provider architecture](ai_provider_architecture.md) explains provider
  interfaces and local-first boundaries for optional AI integrations.
- [Benchmark fixtures](benchmark_fixtures.md) and
  [Quality, testing, and benchmark plan](codex_motionjson_quality_benchmarks.md)
  show deterministic fixture coverage and quality gates.

Provider rule of thumb: missing optional packages, model weights, CUDA, FFmpeg,
or credentials should appear in diagnostics and logs. They should not break the
base CPU/mock install.

## I Want To Use Codex To Contribute

Use this path when continuing the phase-based roadmap:

- [Codex future plan](codex_future_plan.md) is the active public-onboarding
  phase plan.
- [Repository status](repo_status.md) records what is implemented, partial, or
  planned.
- [Phase commit checklist](phase_commit_checklist.md) summarizes phase hygiene.
- [Release notes](release_notes.md), [Migration and known limitations](migration_and_known_limitations.md),
  and [Final QA and release report](roadmap/final-qa-release-report.md) describe
  the current release-candidate boundary.
- [Roadmap](roadmap.md) and [Product requirements](product_requirements.md)
  preserve the broader product direction.

Phase reports live under `docs/roadmap/`. Each new phase should record changed
files, tests, screenshots or demos, known limitations, and follow-up tasks.

## Reference

- [Glossary](glossary.md)
- [Deployment guide](deployment.md)
- [Billing and pricing](billing_pricing.md)
- [Onboarding guide](onboarding.md)
- [Security checklist](security_checklist.md)
- [Developer API](developer_api.md)
- [Support operations](support.md)
- [Release notes](release_notes.md)
- [Migration and known limitations](migration_and_known_limitations.md)
- [Benchmark fixtures](benchmark_fixtures.md)
- [Final export](final_export.md)

## Validation

```bash
python3 -m pytest -q
npm test
npm run lint
git diff --check
```
