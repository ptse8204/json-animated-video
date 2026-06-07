# Phase 5 Report: Provider Runtime Proof Gating

## Summary

Phase 5 adds a public-safe runtime proof contract for providers that can trigger expensive, slow, GPU, or hosted model runs. Provider setup and smoke actions now generate a versioned `motionjson.runtime_proof.v0.1` envelope, provider settings and capability APIs expose it, and Local UI run-config validation/enqueue blocks proof-required workflows until proof allows the run.

The proof gate applies to SAM2 HF automatic masks, SAM3 Scene Sweep, and hosted SAM2/SAM3 providers. Mock, threshold, motion, external, and other no-model first-run paths remain runnable without proof. Hosted providers still require explicit local opt-in before network-capable runs, and no hosted smoke is attempted unless the user starts the hosted smoke action.

Read-only `diff-review-scout` findings were addressed before commit:

- Hosted runs now require per-run network/cost acknowledgement even when provider settings have saved hosted opt-in.
- Local runtime proof now stores and compares a public-safe runtime fingerprint so proof becomes stale when Python/torch/transformers/SAM/device availability changes.
- The phase report and before/after screenshot evidence are included in this commit.

## Changed Files

- `src/motionjson/provider_settings.py`: added runtime proof contract, proof generation, proof redaction, proof expiry, settings invalidation, local smoke persistence, hosted smoke persistence, and public provider proof state.
- `src/motionjson/capabilities.py`: surfaces runtime proof metadata and marks dependency-ready SAM2 HF/SAM3 Scene Sweep providers as not runnable until proof passes.
- `src/motionjson/provider_registry.py`: marks SAM2 HF workflows as runtime-proof-gated.
- `src/motionjson/ui/server.py`: exposes proof in model connector readiness, adds run-config proof warnings, blocks enqueue when proof is missing/stale/failed, and requires per-run hosted network/cost acknowledgement.
- `src/motionjson/backend/provider_setup_jobs.py`: returns runtime proof in setup job results.
- `src/motionjson/ui/static/app.js`: renders proof badges/status cards in Model setup and keeps local/free no-model affordances visible.
- `src/motionjson/cli.py`: restores the local UI launcher help wording.
- `scripts/test_ui_workflow_matrix.mjs`: updates workflow matrix assertions for proof-gated SAM3 Scene Sweep.
- `tests/fixtures/local_ui_workflow_matrix.v0.1.json`: adds proof-gated expected states for SAM2 HF, SAM3 Scene Sweep, and hosted providers.
- `tests/test_provider_settings.py`, `tests/test_local_ui_api.py`, `tests/test_capabilities.py`, `tests/test_provider_registry.py`: add runtime proof persistence, redaction, expiry, capability, validation, and enqueue-gating coverage.
- `docs/design/screenshots/phase-5-runtime-proof/`: browser layout evidence for Model setup before/after Phase 5.

## Validation

- `python3 -m pytest` -> 614 passed, 1 skipped.
- `python3 -m pytest tests/test_provider_settings.py tests/test_backend_jobs_worker.py tests/test_local_ui_api.py::test_local_ui_run_config_validation_and_enqueue_gate_runtime_proof -q` -> 71 passed after the final setup-job proof attachment patch.
- `python3 -m pytest tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_local_ui_workflow_matrix.py tests/test_capabilities.py tests/test_provider_registry.py -q` -> 149 passed after the runtime-fingerprint and hosted-ack fixes.
- `python3 -m pytest tests/test_provider_settings.py::test_runtime_proof_contract_persists_redacts_and_expires tests/test_local_ui_api.py::test_local_ui_blocks_hosted_sam2_without_per_run_ack_after_provider_opt_in tests/test_local_ui_api.py::test_local_ui_blocks_hosted_sam3_without_per_run_ack_after_provider_opt_in tests/test_local_ui_api.py::test_local_ui_run_config_validation_and_enqueue_gate_runtime_proof -q` -> 4 passed.
- `npm test` -> 23 passed.
- `npm run lint` -> passed.
- `npm run build` -> passed.
- `npm run test:e2e` -> 7 passed.
- CLI smoke:
  - `python3 -m motionjson.cli --help`
  - `python3 -m motionjson.cli extract --help`
  - `python3 -m motionjson.cli backend --help`
  - `python3 -m motionjson.cli ui --help`
- `npm run ui:layout -- --state model-setup --screenshot-dir docs/design/screenshots/phase-5-runtime-proof/before` from detached Phase 4 baseline -> passed for 390x844, 768x1024, 1024x768, 1366x768, 1440x900, 1920x1080.
- `npm run ui:layout -- --state model-setup --screenshot-dir docs/design/screenshots/phase-5-runtime-proof/after` from Phase 5 working tree -> passed for the same viewport set.
- `git diff --check` -> passed.

## Browser Evidence

Before screenshots were captured from detached baseline commit `cd4fcadcbb77da47e6337e4f142eebe0672cc36b` under `docs/design/screenshots/phase-5-runtime-proof/before/`.

After screenshots were captured from the Phase 5 working tree under `docs/design/screenshots/phase-5-runtime-proof/after/`.

The after pass preserves the Model setup layout across mobile, tablet, laptop, desktop, and wide desktop viewports. The new runtime proof status card is visible without horizontal overflow or clipped controls.

## Known Limitations

- Runtime proof expiry is currently a fixed 24-hour local policy.
- Runtime fingerprints are public-safe and intentionally coarse; they invalidate on Python, platform, requested device, torch, transformers, SAM2/SAM3, CUDA, or MPS changes, but do not include hostnames or local paths.
- Hosted providers can become runnable after settings and opt-in are complete without requiring a live network smoke; the proof status remains `settings_ready_no_network` until a hosted smoke is explicitly run.
- SAM2 local prompt tracking records optional smoke proof but remains proof-optional so legacy/no-model first-run flows are not blocked.

## Follow-Up Tasks

- Add a user-facing control for rerunning proof when a proof is stale or expired.
- Consider a configurable proof TTL once provider setup policies stabilize.
- Extend hosted smoke support beyond SAM3 when real hosted provider adapters are available.
