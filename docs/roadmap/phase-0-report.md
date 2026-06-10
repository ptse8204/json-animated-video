---
historical: true
default_context: false
---

# Phase 0 Report - Repository Discovery and Guardrails

## Summary

Phase 0 established the Codex roadmap guardrails and mapped the current MotionJSON repository without changing product code. The canonical Phase 0 scope is `docs/codex_motionjson_roadmap.md` and `codex_tasks.yaml`; older planning notes such as `docs/phase_0_bootstrap.md` are historical context and should not override the current roadmap loop.

The working tree was not clean at the start of Phase 0. Pre-existing changes included modified `AGENTS.md`, modified `README.md`, many modified generated `out/demo/*` artifacts, and untracked planning files including `CODEX_MASTER_PROMPT.md`, `codex_tasks.yaml`, and `docs/codex_motionjson_*.md`. Phase 0 deliberately avoids staging generated demo artifacts or product code.

## Subagent Findings

- `repo_archaeologist`: mapped package layout, CLI commands, extraction pipeline, SAM2 paths, dependency surfaces, and existing test commands.
- `product_strategist`: confirmed Phase 0 is discovery/guardrails only and recommended the user-facing wording "Propose all visible segments" to avoid overpromising semantic objects.
- `qa_benchmark_engineer`: identified existing CPU/no-model coverage, smoke commands, and missing future diagnostics/benchmark/UI checks.
- `reviewer`: flagged dirty-baseline risk, conflicting older Phase 0 docs, SAM2 mapping risk, and the need to keep generated outputs out of the commit.

## Current Architecture Map

- Packaging: setuptools `src` layout in `pyproject.toml`; console script is `motionjson = motionjson.cli:main`.
- Python package: `src/motionjson`.
- CLI entrypoint: `src/motionjson/cli.py`.
- Extraction core: `src/motionjson/pipeline.py`.
- Mask provider interface and CPU/demo providers: `src/motionjson/masks.py`.
- Optional provider abstractions and SAM2-compatible providers: `src/motionjson/providers/`.
- Local backend: `src/motionjson/backend/`, with SQLite storage, jobs, local stdlib HTTP API, and worker commands.
- Exporters: `src/motionjson/exporters/`.
- Schemas: `src/motionjson/schemas/`.
- JavaScript workspace: root `package.json` with `packages/motionjson-runtime` and `packages/motionjson-sdk`.
- Examples and browser previews: `examples/`.
- Existing generated/demo output: `out/`.

## Current CLI Map

`python3 -m motionjson.cli --help` reports these top-level commands:

- `extract`: extract one selected object layer from a short video.
- `validate`: validate a MotionJSON file or output directory.
- `correct`: apply deterministic local mask corrections to an existing extraction.
- `export`: export final MP4, transparent object WebM, website ZIP, Remotion plan, or all formats.
- `backend`: run local backend commands.

`extract` currently supports mask providers `external`, `threshold`, `motion`, `sam2`, `sam2-local`, and `sam2-hosted`. The default is `threshold`. Multi-object extraction exists only through repeatable deterministic external mask inputs, for example `--object-mask-dir object_id=/path/to/masks` with optional `--object-label object_id=Label`.

`backend` already includes local commands for database initialization, auth/session flows, uploads, job queueing, worker execution, API serving, API keys, asset/library workflows, beta/support flows, and local billing metadata. It does not yet include a provider capability diagnostics command.

## Extraction Flow

Current single-object extraction calls `run_pipeline()`, which wraps `run_multi_object_pipeline()` with one `ObjectExtractionSpec`.

The pipeline:

1. Samples frames from the input video with OpenCV.
2. Writes sampled debug frames.
3. Prepares the configured mask provider.
4. Gets one mask per sampled frame, optionally through a batch provider method.
5. Converts the largest accepted mask contour into per-frame metadata.
6. Writes masks, cropped alpha cutouts, spritesheets, object manifests, object motion JSON, scene graph JSON, web asset manifest, rights manifest, resource profile, preview HTML/runtime files, and optional benchmark output.

Current output is cached raster/alpha object layers by design. This is different from the future "bad raster-only fallback" state that must include reason codes and suggested fixes.

## SAM2 And Fallback Map

- `--mask-provider sam2` uses the legacy `SAM2Provider` stub in `src/motionjson/masks.py`. It fails clearly unless a client is injected.
- `--mask-provider sam2-local` uses `LocalSAM2SegmentationProvider` in `src/motionjson/providers/sam2.py`. SAM2 and torch remain optional and are imported lazily only when this provider is configured and executed.
- `--mask-provider sam2-hosted` uses `HostedSAM2SegmentationProvider` in `src/motionjson/providers/sam2.py`. Hosted use requires endpoint/auth configuration and explicit network opt-in.
- `--fallback-mask-provider threshold|motion` can wrap SAM2-compatible segmentation providers through `FallbackSegmentationProvider`.
- Current raster routing is quality-based. `recommended_output()` keeps photoreal objects as `raster_alpha_sequence` unless strict vector suitability thresholds pass.
- Missing later-phase pieces: provider capability registry, machine-readable diagnostics, whole-frame mask rejection, stable `ObjectTrack` model, and explicit raster fallback reason codes.

## Tests And Smoke Commands

Required commands from `codex_tasks.yaml`:

- `python -m motionjson.cli --help` - failed in this shell because `python` is not on PATH.
- `python -m motionjson.cli extract --help` - failed in this shell because `python` is not on PATH.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help` - passed.

Additional Phase 0 verification:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli validate --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli correct --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli export --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed, 114 tests.
- `npm test` - passed, 18 Node tests.
- `npm run lint` - passed.
- `git diff --check` - passed.
- `npm run build` - unavailable; root `package.json` has no `build` script.

## Changed Files

- `AGENTS.md`: repository guardrails are updated for the MotionJSON local-first tracing roadmap; Phase 0 also corrected the workflow name to "Propose all visible segments."
- `CODEX_MASTER_PROMPT.md`: Codex master roadmap prompt added as an authoritative planning artifact.
- `codex_tasks.yaml`: machine-readable phase plan added.
- `docs/codex_motionjson_context.md`: source context for the roadmap.
- `docs/codex_motionjson_prd.md`: product requirements.
- `docs/codex_motionjson_roadmap.md`: phased execution roadmap.
- `docs/codex_motionjson_architecture.md`: target architecture.
- `docs/codex_motionjson_ui_spec.md`: target UI specification.
- `docs/codex_motionjson_ml_pipeline_spec.md`: multi-object ML pipeline specification.
- `docs/codex_motionjson_quality_benchmarks.md`: testing and benchmark plan.
- `docs/roadmap/phase-0-report.md`: this report.

## Known Limitations

- The working tree still has unrelated pre-existing changes in `README.md`, backup prompt files, and generated `out/demo/*` artifacts. They were not included in the Phase 0 commit.
- There is no UI command yet; it is intentionally deferred to Phase 7.
- There is no provider diagnostics command yet; it is deferred to Phase 2.
- There is no explicit raster fallback reason model yet; it is deferred to Phase 6.
- There is no benchmark subcommand yet despite benchmark planning docs; benchmark command work is deferred to Phase 12.
- Heavy SAM2/model behavior was not exercised in Phase 0; current tests cover injected fake providers and no-model paths.

## Follow-Up Tasks

- Phase 1: add typed extraction run configuration shared by CLI and future UI.
- Phase 2: add provider capability registry and diagnostics, including clear CUDA/SAM2/model availability.
- Phase 3: add job lifecycle and structured artifact model.
- Phase 4: refactor extraction into provider pipeline interfaces and add deterministic mock providers.
- Phase 6: add object track filtering and diagnosed raster fallback reason codes.
- Phase 7 onward: add local API/UI shell, guided workflows, review/correction UI, export validation, fixtures, packaging, and release readiness.
