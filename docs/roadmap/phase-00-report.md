---
historical: true
default_context: false
---

# Phase 00 Report - Repo Archaeology and Truthful Status Baseline

## Summary

Phase 00 persisted the future public-onboarding plan in
`docs/codex_future_plan.md` and audited the current repository state without
changing product behavior.

The repository already contains an earlier implementation history through
Phase 14 plus a final QA report. That earlier work provides a substantial
local-first CLI/backend/UI foundation, but the current root `README.md` is
still a Codex planning packet rather than a public landing page. Phase 01
should therefore start with the README rewrite described in the future plan.

## Initial Working Tree

The working tree was not clean at Phase 00 start:

```text
?? .motionjson/
?? docs/MOTIONJSON_CODEX_FUTURE_PLAN.md
?? out/demo_red_ball/
```

During the first requested step, the future plan was copied to the canonical
path:

```text
?? docs/codex_future_plan.md
```

The runtime/output directories were not deleted or staged. The uppercase plan
file was left untouched because it was already present and untracked before
the canonical copy was created.

## Sources Read

- `AGENTS.md`
- `CODEX_MASTER_PROMPT.md`
- `codex_tasks.yaml`
- `README.md`
- `README_old.md`
- `pyproject.toml`
- `package.json`
- `Dockerfile`
- `docs/codex_motionjson_roadmap.md`
- `docs/index.md`
- existing reports in `docs/roadmap/`

## Current Architecture Snapshot

- Python package: `src/motionjson/`
- CLI entrypoint: `src/motionjson/cli.py`
- Backend CLI/API/jobs/storage: `src/motionjson/backend/`
- Provider interfaces and mocks: `src/motionjson/providers/`
- Legacy and CPU mask providers: `src/motionjson/masks.py`
- Pipeline and artifacts: `src/motionjson/pipeline.py`,
  `src/motionjson/job_artifacts.py`
- Track filtering and raster fallback diagnostics:
  `src/motionjson/track_filters.py`
- Validation schemas: `src/motionjson/schemas/`
- UI static shell: `src/motionjson/ui/static/`
- JS runtime and SDK: `packages/motionjson-runtime/`,
  `packages/motionjson-sdk/`
- Tests: `tests/` and package Node tests
- Examples: `examples/`
- Generated/demo outputs: `out/`

## Command Results

The exact requested Python commands fail in this shell because `python` is not
on PATH:

| Command | Result | Notes |
| --- | --- | --- |
| `python -m motionjson.cli --help` | Failed | `zsh:1: command not found: python` |
| `python -m motionjson.cli backend --help` | Failed | `zsh:1: command not found: python` |
| `python -m motionjson.cli ui --help` | Failed | `zsh:1: command not found: python` |
| `python -m pytest -q` | Failed | `zsh:1: command not found: python` |

Equivalent local commands with `python3` passed:

| Command | Result | Notes |
| --- | --- | --- |
| `python3 -m motionjson.cli --help` | Passed | Commands: `extract`, `validate`, `correct`, `export`, `benchmark`, `backend`, `ui`. |
| `python3 -m motionjson.cli extract --help` | Passed | Shows mask providers, discovery providers, SAM2 options, fallback mask provider, sampling, export, and rights flags. |
| `python3 -m motionjson.cli backend --help` | Passed | Shows diagnostics, init, auth/project/asset/job/API/library/beta/support/billing commands. |
| `python3 -m motionjson.cli ui --help` | Passed | Includes `--mock` for no-model UI smoke checks. |
| `python3 -m motionjson.cli backend diagnostics --json` | Passed | 15 of 22 providers ready; optional heavy/network providers report missing configuration or dependencies. |
| `python3 -m pytest -q` | Passed | 228 tests passed in 12.06s. |
| `npm run build` | Passed | Static UI shell check returned `status: ok`. |
| `npm test` | Passed | 19 Node tests passed. |
| `npm run lint` | Passed | Runtime, SDK, tests, and examples passed offline runtime constraints. |

Environment:

- Python: `Python 3.13.1` via `python3`
- Node: `v22.19.0`
- npm: `10.9.3`
- Branch: `main`
- Baseline HEAD: `dcc212f`

## Provider Diagnostics Snapshot

`python3 -m motionjson.cli backend diagnostics --json` reports:

- CPU/no-model ready: `threshold`, `motion`, `external`, `mock`,
  `manual_prompt`, `motion_foreground`, `external_masks`, `video-tracker`,
  `track-linker`, `contour-vectorizer`, JSON/export helpers, and ffmpeg video
  export.
- FFmpeg available at `/usr/local/bin/ffmpeg`.
- Torch is installed, CUDA is unavailable, and MPS is available.
- Missing or unconfigured optional providers: `sam2-local`, `sam2-hosted`,
  `openrouter`, `sam_auto_masks`, `text_detector`, and `class_detector`.
- Missing providers include explicit reasons and install/configuration hints.

## Docs And Claims Audit

| Path | Finding | Phase impact |
| --- | --- | --- |
| `README.md` | Still presents a "MotionJSON Codex Planning Packet" instead of a user-facing README. | Phase 01 should replace it and move planning text into Codex docs. |
| `README_old.md` | More useful public material, but it is long and includes many advanced capabilities. | Use as source material in Phase 01, verifying each claim. |
| `docs/index.md` | Existing docs index is a release-doc list, not an intent-based manual. | Phase 04 should reorganize docs by user path. |
| `docs/assets/` | No docs asset files were found. | Phase 01/03 must define and generate README assets. |
| `out/demo/**` | 181 generated demo files are tracked. | Future generated artifact policy should be clarified before broader screenshot/demo work. |
| `out/demo_red_ball/` | Untracked generated output exists. | Leave untouched unless a later phase explicitly stages a tiny demo or ignores it. |

## Changed Files

- `docs/codex_future_plan.md`: canonical copy of the full future phase plan
  supplied by the user.
- `docs/repo_status.md`: implemented, partial, and planned status table.
- `docs/roadmap/phase-00-report.md`: this Phase 00 report.

No runtime, backend, frontend, provider, schema, or test behavior was changed.

## Screenshots And Demos Produced

None. Phase 00 is an archaeology/status phase. Screenshot and GIF/MP4 asset
generation is deferred to Phase 03 after Phase 01 defines README asset needs.

## Review

Reviewer found no material command/test reporting gaps. The only scope note was
to commit only the three intended Phase 00 docs and leave unrelated runtime or
generated artifacts unstaged.

## Known Limitations

- The exact `python` commands fail because this shell only has `python3`.
- Heavy ML provider execution was not tested; diagnostics only verified that
  missing optional dependencies and configuration are reported clearly.
- No screenshot assets exist yet under `docs/assets/`.
- The working tree still contains untracked runtime/output artifacts outside
  this phase's intended commit scope.
- The prior Phase 0-14 roadmap and the new Phase 00-12 future plan use
  different numbering. Future work should follow `docs/codex_future_plan.md`
  for the public-onboarding roadmap.

## Follow-Up Tasks

- Phase 01: rewrite the public README for humans, move planning packet content
  out of the root README, and document README asset requirements.
- Phase 02: add first-run scripts and local/free run path docs.
- Phase 03: add real screenshot/demo capture automation.
- Phase 04: reorganize docs into a navigable manual.
- Phase 09: clarify generated output policy and CI coverage.
