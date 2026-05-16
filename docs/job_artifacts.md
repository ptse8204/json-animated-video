# Job Artifacts And Progress

Extraction now writes a local job artifact layer alongside the existing
MotionJSON outputs. The legacy files remain in the output directory:

- `scene_graph.json`
- `object_motion.json`
- `web_asset_manifest.json`
- `rights_manifest.json`
- `resource_profile.json`
- `objects/<object_id>/...`
- `frames/`, `masks/`, `preview/`

The job layer adds these auxiliary files:

- `run_config.json`: typed extraction config used for the run.
- `job.json`: local job state with status, timestamps, result, and failure.
- `events.jsonl`: append-only UI-consumable progress events.
- `logs.txt`: human-readable run log and traceback on failure.
- `metrics.json`: latency, provider performance, cost dashboard, and artifact
  summary.
- `artifacts.json`: manifest of relative artifact paths, kinds, sizes, content
  types, and object IDs.
- `provider_diagnostics.json`: capability diagnostics snapshot for the run.
- `failure.json`: readable failure diagnostics when the run fails or is
  canceled.
- `candidates.json`: Phase 4 object-candidate discovery summary.
- `tracks.json`: Phase 4 linked object-track summary with frame coverage,
  visibility, boxes, masks, assets, vectorization metadata, and Phase 6 track
  filter decisions.
- `fallback_diagnostics.json`: Phase 6 raster fallback reason codes,
  suggested fixes, affected tracks, and aggregate fallback counts.
- `discovery/`: Phase 5 generated candidate assets such as CPU motion
  foreground mask sequences.

These files are auxiliary; `motionjson validate out/demo` skips non-core job
and config JSON while still validating MotionJSON scene/object/resource files.

## Progress Events

Each line in `events.jsonl` is a JSON object with:

- `jobId`
- `timestamp`
- `type`
- `stage`
- `status`
- `message`
- `progress`
- `metadata`

`progress.overallRatio` is monotonic for UI progress bars. Per-stage work can
also include `stageRatio`, `current`, and `total`; `stageRatio` is monotonic
within each `(stage, objectId)` pair so multi-object runs can start a new
object at a lower stage-local ratio without moving overall progress backward.

Current extraction emits coarse stages for UI/API polling:

- `validating_config`
- `video_read`
- `keyframe_selection`
- `candidate_discovery`
- `initial_masks`
- `propagation`
- `track_linking`
- `vectorization`
- `export`

Phase 4 routes the legacy single-object flow through provider-stage adapters, so
`candidate_discovery`, `initial_masks`, `propagation`, `track_linking`, and
`vectorization` now report real provider-stage work even when the provider is a
deterministic no-model mock.

## Failure Diagnostics

Failures write `failure.json` and append the raw traceback to `logs.txt`.
`failure.json` includes a `reasonCode`, user-readable `message`,
`exceptionType`, and `tracebackRef`. Backend failures also register these files
as generated assets so support tooling and future UI views can retrieve them.

## Cancellation

Cancellation is cooperative. Pending backend jobs move directly to `canceled`.
Running backend jobs move to `cancel_requested`; workers check that state
between stages and sampled frames, then finish as `canceled`. Running local CLI
jobs also check for a `cancel.requested` marker between stages and sampled
frames, but long provider calls may not interrupt until the provider returns.

Backend CLI:

```bash
python -m motionjson.cli backend cancel-job JOB_ID --session-token-env MOTIONJSON_SESSION_TOKEN
```

API:

```text
POST /v1/jobs/{jobId}/cancel
GET  /v1/jobs/{jobId}/artifacts
```
