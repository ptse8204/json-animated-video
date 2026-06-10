# Conversation Context for Codex

> Historical reference. Do not use this as default Codex context. Start with
> `docs/codex/START_HERE.md`.

## What happened

A user attempted to run a multiline PowerShell command for MotionJSON extraction using Bash-style backslash line continuations. After correcting the command to PowerShell syntax, the command ran, but object identification failed: the output identified the whole video/frame as a raster instead of tracing the intended object.

The user then clarified the actual goal: they do not only want to trace a single manually prompted point. They want a workflow closer to:

> Trace every object in this video.

The user now wants a strong UI and better software architecture so they are not forced to copy/paste complex CLI commands or guess the right ML backend settings.

## Key technical conclusion

The current single-prompt SAM2 workflow is not enough for “trace every object.” A point prompt says “segment/track the object at this point,” not “discover all objects.”

The software needs a two-stage or multi-stage pipeline:

```text
object discovery
  -> initial masks/boxes/prompts
  -> video segmentation/tracking
  -> identity linking/filtering
  -> review/correction
  -> MotionJSON export
```

## Product consequence

The UI should not expose only raw CLI flags. It should ask what the user is trying to do and choose the right pipeline:

- Trace one selected object.
- Find objects from text labels.
- Propose all visible segments.
- Find moving objects.
- Use known-class detector tracking.
- Import masks/boxes.
- Review/correct an existing result.

## Why raster-only output matters

Raster-only output should never be a silent failure. It should be a diagnosed result with reason codes and suggested fixes. For example:

- prompt landed on background;
- only mask covered most of the frame;
- no candidates passed filters;
- provider unavailable;
- vectorization failed;
- user intentionally selected raster mode.

## User expectation for Codex execution

The user requested a master-agent/sub-agent workflow similar to planning/executing/reviewing. Codex should use specialized subagents for repository mapping, product design, backend CV architecture, UI engineering, QA/benchmarks, docs/devrel, packaging, and review.

Every roadmap phase must end with a git commit.
