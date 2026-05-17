# MotionJSON Quality, Testing, and Benchmark Plan

## 1. Testing philosophy

The project must be testable without a GPU or large model downloads. Real ML providers should have smoke tests that can be skipped when unavailable, while the core pipeline, config, UI, exports, and diagnostics remain fully testable with mock/simple providers.

## 2. Test layers

### 2.1 Unit tests

Cover:

- config validation;
- provider registry;
- capability diagnostics;
- candidate filtering;
- fallback reason generation;
- track model operations;
- vectorization helpers;
- export validation;
- artifact path safety.

### 2.2 Pipeline tests

Use mock providers to verify stage ordering and outputs:

```text
config -> candidates -> masks -> tracks -> filter -> vectorize -> export
```

Test success and failures:

- no candidates;
- provider unavailable;
- huge/whole-frame mask;
- invalid prompt;
- tracking error;
- vectorization error;
- export error.

### 2.3 CLI tests

Cover:

- `extract --help` includes new config/mode options.
- Existing CLI examples still parse.
- `backend diagnostics --json` returns machine-readable status.
- `ui --help` exists after UI phase.
- Config file extraction works.

### 2.4 API tests

Cover:

- health endpoint;
- capabilities endpoint;
- project creation;
- video metadata endpoint with test fixture;
- run creation with mock provider;
- job polling/events;
- artifact retrieval;
- track edit endpoints;
- export endpoint.

### 2.5 Frontend tests

Cover:

- home screen renders;
- provider status chips render;
- wizard builds valid configs;
- prompt coordinate mapping is correct under zoom/scaling;
- mock job runs and results display;
- track visibility/export inclusion toggles;
- raster fallback message appears.

### 2.6 End-to-end tests

Use mock provider first, then optional real providers.

Minimum E2E:

1. Launch local UI.
2. Create/open sample project.
3. Choose mock/manual or mock/all-objects mode.
4. Run extraction.
5. Review one track.
6. Export MotionJSON.
7. Validate MotionJSON.

## 3. Fixture strategy

### 3.1 Synthetic video generator

Phase 12 implements a local fixture generator through
`python3 -m motionjson.cli benchmark`. It writes small MP4 files, ground-truth
masks, `fixture_manifest.json`, and `expected.json` for:

- red ball moving across static background;
- two moving colored circles;
- partial occlusion;
- tiny object masks;
- camera-pan simulation;
- whole-frame regression masks.

The current built-in fixture set is documented in
[`docs/benchmark_fixtures.md`](benchmark_fixtures.md): `red_ball`,
`multi_object`, `occlusion`, `small_object`, `camera_motion`, and
`whole_frame_regression`. This avoids licensing issues and makes expected
behavior controllable.

Future fixture candidates include object enter/exit, crossing identities, large
foreground objects, whole-frame color changes, and noisy backgrounds.

### 3.2 Golden output strategy

For mock/simple providers, golden outputs can be exact.

For real ML providers, use tolerant metrics:

- object count within tolerance;
- average area ratio within range;
- track continuity above threshold;
- no whole-frame mask unless expected;
- export validates.

## 4. Metrics

### Candidate metrics

- candidate count;
- accepted/rejected count;
- rejection reasons;
- average score;
- duplicate IoU distribution;
- min/max/mean area ratio.

### Track metrics

- number of tracks;
- frame coverage per track;
- dropped frames;
- area stability;
- centroid path length;
- duplicate track overlap;
- confidence mean/min;
- warnings count.

### Export metrics

- MotionJSON validation status;
- masks included count;
- contours included count;
- raster fallback reason;
- artifact count and sizes.

### Runtime metrics

- total runtime;
- time by stage;
- memory peak if available;
- device used;
- frames processed;
- FPS throughput.

## 5. Benchmark command

Command:

```bash
python3 -m motionjson.cli benchmark --fixtures synthetic --modes external --out out/benchmarks
```

Lightweight CI command:

```bash
python3 -m motionjson.cli benchmark --fixtures red_ball,whole_frame_regression --modes external --out out/benchmarks
```

Output:

```text
out/benchmarks/
  summary.json
  summary.md
  runs/
    red_ball_external_masks/
  fixtures/
    red_ball/
      video.mp4
      fixture_manifest.json
      expected.json
      masks/
```

`summary.json` is machine-readable
(`motionjson.evaluation_benchmark.v0.1`) and validates against the packaged
benchmark schema. `summary.md` is a human-readable table with accepted/rejected
track counts, duplicate-overlap metrics, fallback reasons, and runtime. The
benchmark uses CPU/no-model providers and records `aiUsage: none`.

## 6. Acceptance thresholds for release candidate

### Core

- Config, provider registry, and fallback tests pass.
- CLI help commands work.
- Mock pipeline exports valid MotionJSON.
- No-GPU UI smoke passes.

### Red-ball demo

- User can trace the ball through UI with manual point/box mode.
- Whole-frame mask failure is rejected or clearly diagnosed.
- Export includes at least one object track.

### Multi-object mock/simple demo

- UI can show at least two tracks.
- User can hide/delete/relabel one track.
- Export respects include/exclude choices.

### Diagnostics

- Missing SAM2 or CUDA produces a clear provider status.
- Provider unavailable does not crash UI startup.
- Raster fallback has a reason code.

## 7. Regression cases

- PowerShell multiline command examples use backticks or one-line forms.
- Prompt point coordinates stay in native video pixel space.
- A mask covering > default `max_mask_area_ratio` is flagged.
- Empty candidate list does not produce a misleading “success.”
- Missing optional dependency does not break base import.
- UI can start in mock mode without model downloads.

## 8. Manual QA checklist

Before release candidate, record expected result, actual result, evidence path
or command output, and pass/fail for each row:

| Check | Expected result | Evidence |
| --- | --- | --- |
| Fresh base install | CPU/no-model install imports `motionjson` without SAM2, CUDA, detectors, or FFmpeg. | Command transcript. |
| CLI help | `cli`, `extract`, `backend`, and `ui` help commands exit 0 and list current flags. | Command transcript. |
| Provider diagnostics | Missing optional providers show unavailable status, reason, and install hint. | `backend diagnostics --json` output. |
| Local UI launch | UI starts in mock mode, local health is ok, and first-run checklist is visible. | Browser screenshot or terminal URL. |
| Accessibility smoke | Skip link reaches workspace, focus ring is visible, active goal/tool state uses ARIA, and keyboard frame stepping works. | Browser notes with viewport. |
| Responsive panels | 390px, 920px, 1280px, and wide desktop avoid horizontal overflow and keep controls readable. | Screenshots or viewport notes. |
| Mock extraction | Red-ball sample runs with mock provider, shows progress/events/artifacts, and exposes at least one review track. | UI notes plus artifact IDs. |
| Review corrections | User can relabel, hide/show, delete, split/merge when available, and export inclusion is distinct from visibility. | UI notes or API transcript. |
| Cancellation | Pending local UI job cancels immediately; running jobs report cooperative cancellation request. | API transcript or job event log. |
| Export validation | Compact/debug export validates, writes scene, manifest, validation report, preview, and ZIP with relative paths. | Export artifact list. |
| Raster fallback | Whole-frame/raster-only result explains vector/object unavailability in UI and logs. | Fallback diagnostics artifact. |
| Privacy | API payloads do not expose storage keys, `file://` URIs, or absolute local paths. | API transcript. |
| Network | Static UI does not load remote resources; dynamic content links are restricted to local API content routes. | `npm run build` output. |
| Performance | Pointer/mask overlay redraw is coalesced, polling stops after terminal status, and large local responses use no-store headers. | Code/test notes. |
| Docs | Release notes, migration/known limitations, first-run setup, benchmark fixtures, and final export docs are linked from the docs index. | Docs review. |

## 9. Reviewer checklist

For every phase, reviewer should check:

- Are acceptance criteria satisfied?
- Are tests added or explicitly deferred with reason?
- Are heavy dependencies optional?
- Are errors user-readable?
- Is existing CLI behavior preserved?
- Is code modular enough for the next phase?
- Did the phase create a git commit?
