# Phase 0 Bootstrap Task

## Objective

Add durable Codex governance and a long-horizon roadmap.

## Files to create or verify

```text
AGENTS.md
.codex/config.toml
.codex/agents/motionjson_planner.toml
.codex/agents/motionjson_executor.toml
.codex/agents/motionjson_reviewer.toml
docs/roadmap.md
docs/phase_gates.md
docs/architecture_context.md
docs/ai_provider_architecture.md
docs/product_requirements.md
docs/commercial_context.md
```

## Phase 0 acceptance criteria

- Codex can discover `AGENTS.md` at the repo root.
- `.codex/agents` contains planner/executor/reviewer definitions.
- Planner is configured for `gpt-5.5` and `xhigh`.
- Executor and reviewer are configured for `gpt-5.5` and `high`.
- Roadmap includes phases 0 through 19.
- Phase gates require PASS / NO CONCERNS from planner/executor/reviewer.
- Git commit requirement is documented.
- Product framing avoids universal video-to-SVG/Lottie claims.
- OpenRouter is scoped to LLM/VLM routing, not pixel segmentation.
- Segmentation provider abstraction is documented.

## Validation commands

```bash
test -f AGENTS.md
test -f .codex/agents/motionjson_planner.toml
test -f .codex/agents/motionjson_executor.toml
test -f .codex/agents/motionjson_reviewer.toml
test -f docs/roadmap.md
test -f docs/phase_gates.md
test -f docs/ai_provider_architecture.md
git diff --check
```

If the repo already has tests:

```bash
pytest -q
```

If tests fail due to unrelated pre-existing conditions, document that and require reviewer approval before committing Phase 0.

## Required commit

```bash
git add AGENTS.md .codex docs
git commit -m "phase 0: add governance, roadmap, and Codex agent system"
```
