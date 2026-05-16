# Track Filtering And Raster Fallback Diagnostics

Phase 6 adds deterministic track analysis before the UI review workflow. The
core MotionJSON scene schema stays unchanged; filter details live in auxiliary
artifacts and in the existing provider-performance/quality diagnostics.

## Outputs

Successful extraction writes:

- `tracks.json`: includes each track's `exportStatus`, warnings, frame coverage
  metrics, filter decisions, and merge suggestions.
- `fallback_diagnostics.json`: includes raster fallback reason codes,
  user-facing messages, suggested fixes, severity, and affected track/provider
  metadata.

Both files are auxiliary and are skipped by `motionjson validate` unless they
declare a core MotionJSON schema.

## Reason Codes

- `no_candidates`: discovery returned no object candidates.
- `no_masks_accepted`: no masks passed the track filters.
- `masks_too_large_whole_frame`: masks cover too much of the frame and likely
  represent background or the whole video.
- `vectorization_failed`: a mask could not produce useful vector geometry.
- `provider_unavailable`: a selected provider was unavailable.
- `tracking_failed`: tracking failed before a usable track was produced.
- `user_chose_raster_mode`: the run was configured to stay raster.
- `duplicate_track`: two tracks overlap enough that one should be merged or
  suppressed.
- `mask_area_below_minimum`: accepted mask area is below the configured minimum.
- `track_too_short`: the object is visible in too few frames.
- `confidence_below_filter`: provider confidence is below the configured
  threshold.

## Current Filters

The default filter is conservative:

- keep stable IDs and labels for all tracks;
- flag or reject whole-frame masks;
- flag likely background-sized masks;
- reject tracks with no accepted masks;
- reject duplicate tracks by mean bounding-box IoU;
- keep rejected tracks in diagnostics so users can inspect why they failed.

Phase 6 does not delete core output objects. It makes bad tracks explicit and
reviewable while preserving CLI compatibility.

## Examples

Run the focused tests:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k 'track or fallback or filter' -q
```

Inspect fallback diagnostics:

```bash
python3 -m motionjson.cli validate out/demo
cat out/demo/fallback_diagnostics.json
```
