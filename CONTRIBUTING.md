# Contributing To MotionJSON

MotionJSON is developed as a local-first video object tracing project. Keep the
default path usable on CPU-only machines, keep heavyweight ML dependencies
optional, and surface provider failures in diagnostics instead of hiding them.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -e ".[dev]"
```

The JavaScript runtime and SDK are dependency-light workspace packages. They do
not need `npm install` for the current local tests.

## Validation

Run the smallest relevant set while developing, then run the release gate before
committing broad changes:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider -q
npm test
npm run lint
npm run build
npm --workspace @motionjson/runtime run test
npm --workspace @motionjson/sdk run test
git diff --check
```

Packaging and deployment smoke commands:

```bash
python3 -m build --sdist --wheel
npm pack --dry-run --workspace @motionjson/runtime
npm pack --dry-run --workspace @motionjson/sdk
docker build -t motionjson-ga .
docker compose config
```

## Phase Discipline

For roadmap work, read `AGENTS.md` as a shim, then start from
`docs/codex/START_HERE.md`, `docs/codex/CURRENT_TASK.md`, and
`docs/codex/CONTEXT_MANIFEST.yaml`. Use the manifest route for task-specific
docs and tests instead of loading old roadmap packets by default. Treat older
roadmaps such as `docs/codex_future_plan.md` as historical context unless a
maintainer explicitly selects that track. Work phase by phase, write the
required phase report, and commit at the end of each phase.

Do not remove or rewrite unrelated local changes. If the tree is dirty, record
what is unrelated in the phase report and stage only the files owned by the
phase.

## Generated Outputs

Generated local state belongs outside commits by default:

- `.motionjson/`
- `out/<new-run>/`
- `output/`
- `dist/`
- `build/`

`out/demo/` is intentionally tracked as the small committed web/runtime demo.
Add new generated outputs only when they are small, deterministic, documented,
and covered by tests or docs that need them.

## Provider And Security Boundaries

Do not make SAM2, detectors, CUDA, hosted endpoints, OpenRouter, or FFmpeg
mandatory for the base install. Public API, CLI, schema, and config changes
need docs and tests. Never commit provider keys, private videos, local database
files, or storage paths.

Hosted OpenAI/OpenRouter planning, hosted SAM-style providers, detector
services, and any other network-backed model path must remain server-side,
redacted, opt-in, and explicitly cost/privacy acknowledged before use. Model
planner output is a proposed run plan, not trusted extraction truth.

## License Boundary

MotionJSON source code is licensed under Apache-2.0. Keep the root `LICENSE`,
Python metadata, and npm package metadata aligned when preparing a release.
Do not present user-supplied videos, model checkpoints, provider outputs, or
generated assets as Apache-licensed unless their own rights metadata supports
that claim.
