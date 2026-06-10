---
historical: true
default_context: false
---

# Phase report: license-colab 03 - Colab companion notebooks

## Summary

Added companion Colab notebooks for export preview and provider diagnostics.
The export notebook runs the deterministic red-ball extraction, validates it,
creates a website handoff ZIP, and previews the generated browser runtime
through Colab's port proxy. The diagnostics notebook reports provider
readiness, defensively redacts credential-looking fields before display or
download, and runs a no-model threshold smoke extraction.

## Starting worktree

The phase started after commit `c8efe74` with the two companion notebooks and
some update-bundle helper files still untracked. This phase stages only the
companion notebooks, docs links/index updates, tests, and this report.

## Changed files

- `notebooks/colab_red_ball_export_preview.ipynb`
- `notebooks/colab_provider_diagnostics.ipynb`
- `notebooks/README.md`
- `README.md`
- `docs/run_free_instances.md`
- `docs/roadmap/phase-license-colab-03-report.md`
- `tests/test_phase10_free_hosted_demos.py`

## Tests run

- `python3 -m json.tool notebooks/colab_red_ball_export_preview.ipynb >/dev/null`
- `python3 -m json.tool notebooks/colab_provider_diagnostics.ipynb >/dev/null`
- `python3 -m pytest -q tests/test_phase10_free_hosted_demos.py tests/test_docs_links.py`
- `python3 -m motionjson.cli export --help`
- `python3 -m motionjson.cli backend diagnostics --json`
- Red-ball extraction/export command smoke in `/tmp`: generated demo video,
  ran threshold extraction, validated output, exported `website-zip`, and
  verified the ZIP is non-empty.
- `npm run build`
- `npm test`
- `npm run lint`
- `git diff --check`
- Read-only `diff-review-scout`; findings on diagnostics value redaction and
  broader public-tunnel test markers were addressed, then targeted validation
  was rerun.

Attempted but did not pass in this local environment:

- `npm run embed:smoke` failed twice because the local Chrome remote debugging
  endpoint did not start. Chrome exists at
  `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; the failure
  occurred before any MotionJSON runtime assertion.

## Known limitations

- These notebooks are short Colab demos, not production hosting or long-running
  services.
- Optional SAM2, detector, hosted segmentation, SAM3, OpenRouter, and other
  provider integrations remain environment-dependent and diagnostic-only unless
  users explicitly configure them.
- The provider diagnostics notebook redacts credential-looking keys
  defensively, but users should still review downloaded diagnostics before
  sharing them.

## Follow-up tasks

- Run the complete release checklist in a clean environment before tagging a
  release candidate.
