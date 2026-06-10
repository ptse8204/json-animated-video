# AGENTS.md - MotionJSON Codex Shim

Read `docs/codex/START_HERE.md` first.

Default Codex context is only:

- `docs/codex/START_HERE.md`
- `docs/codex/CURRENT_TASK.md`
- `docs/codex/SAFETY_INVARIANTS.md`
- `docs/codex/CURRENT_ARCHITECTURE.md`
- `docs/codex/CONTEXT_MANIFEST.yaml`

Obey `docs/codex/SAFETY_INVARIANTS.md`. Use
`docs/codex/CONTEXT_MANIFEST.yaml` to route task-specific docs, source paths,
and tests.

Do not load historical/archive docs by default. Source code and tests beat
stale docs.

Keep phase/task work small, validated, documented, and committed when the task
uses phase protocol.

No hidden hosted calls. No browser-side secrets. Do not expose raw API keys,
tokens, storage keys, local absolute paths, or `file://` URIs in public
responses, logs, screenshots, artifacts, validation errors, or reports.
