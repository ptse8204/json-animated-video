# Migration and Known Limitations

## Migration notes

- Keep existing CLI scripts on `python3 -m motionjson.cli ...` on macOS/Linux,
  or `python -m motionjson.cli ...` after activating a Windows virtual
  environment. Phase 14 does not remove or rename existing commands.
- Use `python3 -m motionjson.cli ui --mock` for first-run local UI smoke checks
  on CPU-only macOS/Linux machines.
- Use `python3 -m motionjson.cli backend diagnostics --json` before installing
  optional ML extras. Missing SAM2, CUDA, detectors, FFmpeg, or model weights
  should be treated as capability status, not as base-install failures.
- For repeatable release checks, use the synthetic benchmark command documented
  in `docs/benchmark_fixtures.md` instead of large external videos.
- Existing MotionJSON output can be imported into the local UI for review; local
  import rejects symlinked paths and keeps private storage paths out of API
  responses.
- Reusable motion layers can be saved through the local Asset Library only from
  explicit generated/export artifact kinds. Creator-approved packs require
  approved creator and commercial-use rights metadata on every included layer.

## Known limitations

- Job cancellation is cooperative. Pending jobs cancel immediately; running jobs
  finish as canceled only after the worker reaches a cancellation check.
- SAM2 remains a promptable mask/tracking provider. Text prompts require a
  detector or open-vocabulary candidate provider before segmentation.
- Hosted or heavyweight ML providers are optional. The default install supports
  no-model smoke tests and deterministic providers, but it does not download
  SAM2 weights or detector checkpoints automatically.
- Browser-level UI smoke coverage is still mostly manual. Static shell checks,
  JS helper tests, and local API E2E tests cover the release gate without GPU or
  a real browser session.
- Video and artifact content endpoints are local-only and use no-store headers,
  but large media responses are still served from local storage by the bundled
  dependency-light server rather than a production streaming server.
- Automatic mask proposals can still include weak candidates. The product
  workflow filters whole-frame/background fragments and explains raster fallback
  reasons, but users should review tracks before export.
- Final video rendering still depends on FFmpeg availability. Validated
  MotionJSON export and website/runtime artifacts work without FFmpeg.
- The Asset Library is local metadata and local stored assets. It is not a
  public marketplace, payment system, or hosted creator distribution flow.

## Upgrade checklist

1. Run the release gate commands from `docs/release_notes.md`.
2. Launch the UI in mock mode and complete the red-ball smoke workflow.
3. Review provider capabilities before enabling optional ML providers.
4. Validate exports before publishing or embedding generated artifacts.
5. Read fallback diagnostics whenever output is raster-only or has no accepted
   object tracks.
