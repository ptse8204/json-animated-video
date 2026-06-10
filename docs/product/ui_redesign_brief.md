# UI Redesign Brief

This is the current product brief for Local UI redesign work. It is form-agnostic and intentionally does not preserve old layout shapes as requirements.

## Redesign Freedom

The UI may abandon cards, right rails, steppers, dashboards, and current panel layout.

Current screenshots, audits, and design-system notes are implementation evidence only. They are not constraints on a full redesign.

## Invariants

Safety invariants still apply. Read `docs/codex/SAFETY_INVARIANTS.md` before changing provider setup, model planning, hosted calls, review, export, rights, or diagnostics.

Required product behavior:

- source identity: users can tell which project/video/source they are using;
- goal clarity: users can tell what tracing goal they chose;
- provider readiness: users can tell whether the chosen provider/model can run;
- consent: hosted/network/cost/privacy boundaries require explicit user acknowledgement;
- run progress: users can tell what is running, queued, blocked, failed, or complete;
- failure recovery: users can see why a run failed and what to try next;
- review truth: users can inspect candidates/tracks and understand confidence, coverage, source provider, warnings, and correction state;
- export readiness: users can tell which objects are reviewed, selected, valid, and ready for each export;
- rights visibility: users can see source/generated rights warnings and metadata before handoff.

Raw JSON may remain available, but it should not dominate the nontechnical UI.

## Design Goal

The first screen should help a nontechnical user answer:

- What source am I working with?
- What am I trying to trace?
- Which provider or model will do the work?
- Will anything leave this machine?
- What is the next action?

The review/export experience should help the same user answer:

- What objects did MotionJSON find?
- Which objects are good enough to keep?
- What failed or needs correction?
- Which export is safe to create now?

## Implementation Guidance

- Prefer source/API state over duplicated UI state.
- Keep advanced controls available without making them the default path.
- Make mock/no-model mode explicit and testable.
- Preserve CLI compatibility unless a task explicitly migrates an interface with docs and tests.
- Use rendered browser evidence for layout changes.
