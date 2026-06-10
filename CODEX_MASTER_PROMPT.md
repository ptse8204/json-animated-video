# Codex Master Prompt - MotionJSON

Use the compact Codex harness instead of loading historical roadmap packets.

Read first:

- `docs/codex/START_HERE.md`
- `docs/codex/CURRENT_TASK.md`
- `docs/codex/CONTEXT_MANIFEST.yaml`

Then read `docs/codex/SAFETY_INVARIANTS.md` and
`docs/codex/CURRENT_ARCHITECTURE.md` as directed by `START_HERE.md`.

Choose one manifest subsystem route for the task. Do not broaden context with
archive files, completed phase reports, old future plans, or old design packets
unless the user explicitly asks for historical analysis.

For the current task, complete `DOC-HARNESS-00`, run the required validation,
write `docs/roadmap/phase-doc-harness-00-report.md`, and commit:

```bash
git commit -m "phase doc-harness-00: reduce codex documentation context"
```
