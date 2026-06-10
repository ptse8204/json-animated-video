---
historical: true
default_context: false
---

# Phase 10 Report: Free Hosted Demo Paths

Date: 2026-05-17

## Summary

Phase 10 added concrete low-install demo surfaces without introducing hosted
runtime dependencies, paid GPU assumptions, or hidden secrets. The README now
has an "Open in GitHub Codespaces" badge, links to the checked-in Colab CLI
notebook, and points to a Hugging Face Space handoff plan.

The Colab notebook is a CPU/no-model red-ball CLI walkthrough: clone the repo,
install the local package, run provider diagnostics, generate the deterministic
demo video, extract with the threshold provider, validate output, inspect key
MotionJSON files, and download a ZIP of the generated folder.

The Hugging Face Space plan is a static Docker Space handoff document for a
CPU Basic mock-mode demo. It documents the intended port, startup command,
diagnostics, tiny demo video, ephemeral storage assumptions, and no-secret/no
paid-GPU boundaries. Deployment docs now call out free hosted demo constraints
around persistence, privacy, provider credentials, and model downloads.

The working tree was not clean at phase start because
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md` and
`docs/Codex Prompt Instrcution.md` were preexisting untracked docs. They were
not staged for this phase.

## Changed Files

- `README.md`
  - Adds a Codespaces badge and links to the free-instance guide, Colab
    notebook, and Hugging Face Space handoff plan.
- `docs/run_free_instances.md`
  - Links the checked-in Colab notebook and Space plan from the existing
    Codespaces/Colab/Hugging Face guidance.
- `docs/deployment.md`
  - Adds free hosted demo constraints for CPU/mock-first demos, ephemeral
    storage, no paid GPU requirement, no hidden secrets, and opt-in providers.
- `notebooks/colab_red_ball_cli_demo.ipynb`
  - Adds the no-model Colab CLI demo.
- `spaces/huggingface/README.md`
  - Adds the CPU Basic mock-mode Space proof-of-concept plan.
- `tests/test_phase10_free_hosted_demos.py`
  - Adds structural tests for devcontainer, README/docs links, notebook
    contents, and Space no-secret/no-paid-GPU constraints.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider tests/test_phase10_free_hosted_demos.py tests/test_docs_links.py -q`
  - Result: 8 passed.
- `python3 -m json.tool .devcontainer/devcontainer.json`
  - Result: passed.
- `python3 -m json.tool notebooks/colab_red_ball_cli_demo.ipynb`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider -q`
  - Result: 261 passed.
- `npm test`
  - Result: 19 passed.
- `npm run lint`
  - Result: passed.
- `npm run build`
  - Result: passed.

## Screenshots And Demos Produced

No screenshots were produced. The new demo surface is the checked-in Colab
notebook, which generates the red-ball demo on demand instead of committing
additional generated outputs.

## Review

Read-only scout audits found the missing notebook, missing README Codespaces
badge, missing Space-specific handoff file, and missing targeted tests. The
implementation addresses those gaps while keeping hosted demos static and
CPU/mock-first. Final reviewer found no blocking issues, confirmed the
distinct report filename is acceptable because the older
`docs/roadmap/phase-10-report.md` should not be overwritten, and approved
commit after explicit staging.

## Known Limitations

- The Colab notebook is structurally validated but not executed in Colab during
  this phase.
- The Hugging Face Space artifact is a proof-of-concept plan, not a deployed
  public Space or committed Space-specific Dockerfile.
- External platform behavior, pricing, storage policies, and badge URLs can
  change; the docs point users back to platform guidance where relevant.
- Free-hosted UI demos still require careful persistence and privacy design
  before accepting private user videos.

## Follow-Up Tasks

- Execute the notebook in Colab before public release and record any Colab-only
  setup fixes.
- Convert the Hugging Face plan into a minimal Space branch or directory once
  the project is ready to own hosted demo operations.
- Add an automated notebook lint step to CI if more notebooks are added.

## 2026-05-18 Revalidation

The current commercial roadmap expects Phase 10 at
`docs/roadmap/phase-10-report.md`, so the free-hosted demo report now uses that
canonical path. The older correction-workflow Phase 10 report from a previous
roadmap was preserved as
`docs/roadmap/phase-10-correction-workflows-report.md`.
