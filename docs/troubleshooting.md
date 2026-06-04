# Troubleshooting

Use this page when MotionJSON does not launch, a provider is unavailable, masks
look wrong, or an export falls back to raster-only output. Start by collecting
diagnostics:

```bash
python3 -m motionjson.cli backend diagnostics --text
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli validate out/demo_red_ball
```

The local UI shows the same capability status in the First Run and Capabilities
panels. When a run has already started, use **Job Center** / **Run monitor**
first: it shows the selected job, active jobs, failed/canceled state, latest
event, provider/model, logs, retry guidance, and whether review/export is
blocked.

## Python Command Not Found

On macOS and Linux, use `python3` if `python` is not installed:

```bash
python3 -m motionjson.cli --help
```

On Windows PowerShell, use `py -3` for virtualenv creation, then `python` after
activation:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m motionjson.cli --help
```

## FFmpeg Is Missing

FFmpeg is optional for the base install. MotionJSON JSON output, masks,
cutouts, website manifests, and browser runtime previews can still work without
it. MP4, WebM, and some final video export paths need FFmpeg.

Check diagnostics first:

```bash
python3 -m motionjson.cli backend diagnostics --json
```

If FFmpeg is unavailable, use JSON/runtime exports or install FFmpeg through
your operating system package manager before rendering video outputs.

## CUDA Is Missing Or CPU-Only

CUDA is not required for the no-model path. `mock`, `threshold`, `motion`, and
`external` providers are intended to run on CPU. Optional heavy providers may
report `available_cpu_only`, `missing_dependency`, or `not_configured`.

Use a CPU-safe workflow:

```bash
python3 -m motionjson.cli ui --no-open
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo_red_ball \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --max-frames 12
```

## SAM2 Is Missing

SAM2 is optional and is not installed by the default package. A missing SAM2
dependency, checkpoint, or config should appear in diagnostics instead of
failing the base install.

No-model alternatives:

- use `threshold` for simple color demos;
- use `motion` or `motion_foreground` for simple moving objects;
- use `external` or `external_masks` when masks already exist;
- use `mock` for UI and smoke checks.

If you need local SAM2, install the optional extra and configure model paths:

```bash
python3 -m pip install -e ".[sam2]"
export SAM2_LOCAL_CHECKPOINT=/path/to/checkpoint.pt
export SAM2_LOCAL_CONFIG=/path/to/config.yaml
python3 -m motionjson.cli backend diagnostics --json
```

SAM2 tracks a prompted object. It does not discover every semantic object by
itself.

## SAM3 Is Missing Or Not Runnable

SAM3 is optional and is not installed by the default package. A saved
`SAM3_LOCAL_MODEL` path, hosted key, or provider setting only means setup data
exists. Diagnostics must still show the provider as runnable before the UI can
start a real SAM3 job.

No-model alternatives:

- use `Find moving things` for CPU motion foreground;
- use `Import masks` when another tool already created masks;
- use `Cut out one object` with SAM2 when point/box tracing is enough;
- use debug mock mode only for contributor smoke checks.

For SAM3 Scene Sweep, use Model setup first. The tracker model is
`sam3TrackerModel=facebook/sam3` by default, or a local Hugging Face
`from_pretrained` directory. A single `sam3.pt` checkpoint file is not valid
for this Transformers path.

For Advanced official-package SAM3 concept/exemplar workflows, verify the
official package, compatible Python/CUDA runtime, torch/CUDA availability, and
a real local `sam3.pt` file:

```bash
python3 -m pip install -e ".[sam3]"
export SAM3_LOCAL_MODEL=/path/to/sam3.pt
python3 -m motionjson.cli backend diagnostics --json
```

For hosted SAM3, configure `Roboflow SAM3`, `Fal SAM3 image`, or a custom SAM3
endpoint in Model setup, then acknowledge hosted cost/privacy before running a
smoke test or extraction. Hosted scene sweep should be enabled only for hosted
profiles that explicitly advertise automatic mask generation.

## Text Or Class Detectors Are Missing

Text prompts and class presets need detector candidates before segmentation.
Missing detector packages or model weights should be shown as diagnostics.
Use `discovery.config.mock=true` or the local UI mock presets when you only
need to test candidate review/export behavior.

Optional installs:

```bash
python3 -m pip install -e ".[detectors]"
python3 -m pip install -e ".[yolo]"
```

Then configure the relevant detector model path and rerun diagnostics. If you
only need a local smoke path, use manual prompts, motion foreground, external
masks, or mock mode instead.

If a provider is `configured` but `runnable: false`, setup was found but the
current local workflow still cannot execute it. Hosted segmentation is the
common case: credentials can be present while network use still requires an
explicit opt-in or injected client.

## Bad Masks Or Whole-Frame Masks

A point prompt or automatic proposal can select background, floor, wall, or the
whole frame. MotionJSON should flag these cases before export.

Inspect:

```bash
cat out/demo_red_ball/tracks.json
cat out/demo_red_ball/fallback_diagnostics.json
```

Look for reason codes such as:

- `masks_too_large_whole_frame`
- `no_masks_accepted`
- `mask_area_below_minimum`
- `track_too_short`
- `duplicate_track`

Useful fixes:

- use a tighter box or a more precise prompt point;
- reduce automatic proposal count;
- import explicit external masks;
- delete or hide bad tracks in the local UI before export;
- lower the scope to one object first, then add more objects after review.

See [Track filtering and fallback diagnostics](track_filtering.md).

## Run Stalls During Asset Preparation

After vectorization, MotionJSON writes local masks, cutouts, and sprite assets.
If asset preparation stops making backend progress beyond the watchdog window,
the Local UI converts the run from `running` to a typed terminal outcome. Runs
with no completed object manifests still fail. Runs with completed object
manifests are reconciled as partial success so those objects remain reviewable.

Common reason codes:

- `asset_preparation_frame_timeout`: a frame-start event did not receive its
  matching finish event before the timeout. The failure should identify the
  object and frame when known.
- `worker_heartbeat_stale`: no heartbeat/progress arrived and no in-flight
  frame is known.
- `asset_preparation_stalled`: compatibility umbrella reason. New debug-report
  consumers should prefer `reasonCode` and treat this as
  `compatibilityReasonCode` when present.

Example frame-timeout message:

```text
Raster asset preparation timed out on frame 13/48 for sam3_grid_024. No frame-finished event arrived.
```

Example heartbeat-stale message:

```text
Worker heartbeat stopped during asset preparation after frame 1/48 for sam3_grid_024. No export artifacts were produced.
```

Use **Review/Export** first when the report shows `partialSuccess: true` or an
`asset_preparation_partial_success` event. The run kept completed object
manifests and recorded the failed object/frame as an
`asset_preparation_object_failed` event. Use **Retry asset prep** to rerun from
the current setup only after checking the partial objects. Use **Retry from
Model setup** if provider/cache/runtime state may have changed. Logs should
remain available. If earlier objects finished before the failure, their object
manifests should remain reviewable rather than reporting `objects: 0` and
`artifacts: 0`.

Optional watchdog overrides:

```bash
export MOTIONJSON_ASSET_PREP_FRAME_TIMEOUT_SECONDS=240
export MOTIONJSON_WORKER_HEARTBEAT_STALE_SECONDS=240
```

Do not use larger timeouts as the first fix. First inspect the per-frame
asset-prep events, failed object id, crop dimensions, and file sizes.

## Auto-Mask Object Is Too Large To Materialize

Scene Sweep and automatic-mask runs may find background-like candidates. If an
object would exceed the cutout materialization budget, MotionJSON should keep
masks and diagnostics but skip cutout/spritesheet writing for that object.

Look for reason code:

```text
asset_materialization_budget_exceeded
```

Default budget:

```bash
MOTIONJSON_MAX_OBJECT_CUTOUT_PIXELS=64000000
```

Better fixes are usually to reduce candidate count, use Clean/Balanced instead
of maximum recall, add tighter discovery filters, or trace one object first.
Raise the budget only when the machine has enough memory for the expected crop
sizes.

## Object Discovery Finds Too Few Candidates

Start with the default Clean preset. It is intentionally conservative: few
keyframes, capped candidates, stricter filtering, and selected-candidate
tracking. If the desired object is missing from the API candidate gallery,
retry with Maximum Recall. Maximum Recall uses more keyframes, more candidates,
and looser filters, so expect slower runs and more review work.

SAM2 can help with automatic keyframe proposals when `sam2-local` diagnostics
show the package, checkpoint, config, and device are available. SAM3 is the
optional path for concept prompts, exemplars, and higher-recall semantic
discovery. Missing SAM2/SAM3 should be shown in capabilities instead of hidden
behind a generic "no candidates" message.

## Object Discovery Finds Too Many Candidates

Stay in Clean or Balanced when possible. Use the candidate browser filters for
selected, stable, moving, non-background, non-duplicate, and minimum frame
coverage. Track selected candidates only unless you are deliberately auditing a
noisy discovery pass.

Trace Everything is expert/experimental. It requires explicit cost/noise
acknowledgement, remains capped, writes rejected candidates, and blocks export
until review. Use it when you need an audit pass, not as the default workflow.

## Raster-Only Output

Photoreal objects are expected to stay raster/alpha layers controlled by JSON.
That is normal. Raster-only fallback is different: it means vector/object tracks
were unavailable, rejected, or intentionally bypassed.

When this happens, read:

- `fallback_diagnostics.json`
- `tracks.json`
- `provider_diagnostics.json`
- the local UI job review panel

Common causes:

- no object candidates were found;
- masks were too large or too small;
- the selected provider was unavailable;
- vectorization failed;
- the run was configured for raster fallback.

Do not assume a raster-only result is successful object extraction until the
diagnostics explain why object tracks were unavailable.

## Review Or Export Is Blocked

Use the `Review & export` step and read the primary action:

- `Track selected`: candidates exist, but object tracks have not been created.
- `Mark reviewed`: tracks exist, but no kept track is marked for export.
- `Export reviewed objects`: reviewed export validation passed.
- Diagnostics/log action: the selected job failed or was canceled, so review
  output is not ready.

The export cards also show one disabled reason per format. Common blockers are
no completed run, active/failed/canceled job, no tracks, unmaterialized
corrections, no included reviewed track, or export validation failure.

## The UI Cannot Read A Video Path

The local UI backend can only register files that are readable by the process
running `motionjson ui`. If the UI is inside a container or Codespace, use a
path that exists inside that environment.

Try the bundled demo first:

```bash
python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4
python3 -m motionjson.cli ui --no-open
```

Then register `examples/demo_red_ball.mp4` in the UI.

## Where To Look Next

- [First run setup](first_run.md)
- [Run locally](run_local.md)
- [Provider capabilities and diagnostics](provider_capabilities.md)
- [Discovery providers](discovery_providers.md)
- [Track filtering and fallback diagnostics](track_filtering.md)
- [Migration and known limitations](migration_and_known_limitations.md)
