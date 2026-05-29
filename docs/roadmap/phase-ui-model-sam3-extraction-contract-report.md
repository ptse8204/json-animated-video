# Phase Report: SAM3 Scene Sweep Extraction Contract

## Summary

This phase fixes the actual-video SAM3 Scene Sweep extraction regression introduced by the isolated subprocess provider. The new subprocess wrapper did not expose the required `ObjectCandidateProvider.name` field, so `run_multi_object_pipeline()` failed with:

`'SubprocessSAM3AutoMasksDiscoveryProvider' object has no attribute 'name'`

The provider now satisfies the discovery provider protocol with `name="sam3_auto_masks"` while keeping `provider_name="sam3-local"`. The shared pipeline also checks provider contract shape before discovery starts, so future wrappers fail with a clear `ProviderConfigError` instead of a raw attribute error.

## Changed Files

- `src/motionjson/backend/sam3_discovery_subprocess.py`
  - Added the discovery `name` field required by the shared object-candidate provider contract.
  - Added test hooks for fake Python executable, worker module, and child environment.
- `src/motionjson/pipeline.py`
  - Added a defensive candidate-provider name check.
  - Reused the validated provider name for candidate events, candidate artifacts, and review gates.
- `src/motionjson/ui/static/app.js`
  - Added failed/canceled job progress copy so terminal failures do not read as `100% complete`.
- `tests/test_sam3_discovery_subprocess.py`
  - Added protocol and full fake-subprocess pipeline coverage without loading SAM3 or CUDA.
- `tests/test_provider_settings.py`, `tests/test_discovery_providers.py`, `scripts/test_ui_config_builder.mjs`
  - Added regression coverage for cached runtime provider shape, defensive provider errors, and failed-job progress text.

## Tests Run

- `python3 -m pytest -q tests/test_sam3_discovery_subprocess.py tests/test_provider_settings.py::test_worker_cached_runtime_providers_require_verified_runtime_without_public_config_leak tests/test_discovery_providers.py::test_multi_object_pipeline_reports_missing_discovery_provider_name`
- `python3 -m pytest -q tests/test_sam3_discovery_subprocess.py tests/test_provider_settings.py tests/test_discovery_providers.py tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py`
- `python3 -m pytest -q`
- `npm test`
- `npm run build`
- `npm run ui:layout -- --check --state workflow-review-failure --viewport desktop-1440`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`

## Known Limitations

- The regression test uses a fake isolated worker and does not prove real CUDA SAM3 weights load in CI.
- Any already-running Colab backend process still has the old code until the server is restarted.
- Any already-failed extraction job should be canceled or ignored and rerun after restart.

## Follow-Up Tasks

- Continue testing real Colab L4 SAM3 Scene Sweep runs after restart.
- If real SAM3 loading still stalls, inspect the isolated worker timeout/error event rather than the old `.name` contract failure.
