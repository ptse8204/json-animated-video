# Scout Protocol

Scouts are optional, bounded, read-only reviewers. The master Codex agent owns planning, implementation, validation, review synthesis, commits, and final decisions.

## Default Scout Context

Do not give scouts full repo docs. A scout should receive only:

- current task summary;
- `docs/codex/SAFETY_INVARIANTS.md`;
- the relevant `docs/codex/CONTEXT_MANIFEST.yaml` route;
- changed diff;
- changed tests;
- validation output;
- short source snippets needed for the review.

## Restrictions

Scouts are read-only unless explicitly authorized by the user.

Scouts must not:

- edit files;
- install dependencies;
- mutate provider settings;
- call hosted services;
- commit;
- push;
- publish packages;
- spawn more agents.

Use at most one or two scouts when independent critique materially reduces risk.

## Output Format

Every scout response must use only:

```text
Scope inspected
Files/symbols reviewed
Findings
Evidence
Recommended action
Confidence level
```

Findings should be concrete, scoped, and grounded in file paths, diff hunks, screenshots, or command output.
