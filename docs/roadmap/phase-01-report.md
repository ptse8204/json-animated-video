# Phase 01 Report - Rewrite Public README

## Summary

Phase 01 replaced the root Codex planning packet README with a user-facing
README for first-time users. The new README leads with the CPU/no-model local UI
path, explains the product boundary, documents the red-ball CLI demo, keeps
provider diagnostics visible, and avoids claiming full video-to-vector
conversion or default heavyweight ML availability.

The old root planning packet was preserved at `docs/codex/planning_packet.md`.
The future roadmap remains in `docs/codex_future_plan.md`.

## Changed Files

- `README.md`: rewritten as a public landing page with quick start, red-ball
  demo, Docker/API path, free-instance status, provider options,
  troubleshooting, roadmap, Codex contribution notes, and license status.
- `docs/codex/planning_packet.md`: preserved copy of the previous root README
  planning packet.
- `docs/assets/README_ASSETS.md`: required README asset inventory and
  regeneration notes; all missing screenshots are marked pending instead of
  faked.
- `docs/repo_status.md`: updated the public README status row after the Phase
  01 rewrite.

No runtime, backend, frontend, provider, schema, or test behavior was changed.

## Subagent Notes

- `product_strategist`: recommended leading with reusable local motion layers,
  the no-model UI path, clear "not video to JSON/SVG/Lottie" boundaries, and no
  unverified hosted/free claims.
- `docs_devrel_engineer`: recommended the exact quick-start and red-ball
  commands, the optional browser preview command, relative docs links, provider
  caveats, and the `docs/assets/README_ASSETS.md` placeholder policy.

## Tests And Smoke Commands

- `python3 -m motionjson.cli --help` - passed.
- `python3 -m motionjson.cli ui --help` - passed.
- `python3 -m motionjson.cli backend diagnostics --json` - passed; optional
  heavy/network providers were reported as unavailable with reasons.
- `python3 -m motionjson.cli ui --no-open --mock --host 127.0.0.1 --port 0 --db /tmp/motionjson-phase01-ui.sqlite --storage-root /tmp/motionjson-phase01-ui-storage`
  - passed startup smoke; printed `MotionJSON UI:
  http://127.0.0.1:54737/`.
- `curl -fsS http://127.0.0.1:54737/api/health` - passed and returned
  `status: ok`, `localFirst: true`, and `mockMode: true`.
- `curl -fsS http://127.0.0.1:54737/api/capabilities` - passed and reported
  15 of 22 providers ready with expected optional missing providers. The
  temporary UI server was stopped after the smoke check.
- `docker compose config` - passed.
- Red-ball demo smoke against `/tmp`, to avoid overwriting existing untracked
  `out/demo_red_ball/`:

```bash
rm -rf /tmp/motionjson-phase01-demo_red_ball /tmp/motionjson-phase01-demo_red_ball.mp4
python3 examples/make_demo_video.py --out /tmp/motionjson-phase01-demo_red_ball.mp4
python3 -m motionjson.cli extract /tmp/motionjson-phase01-demo_red_ball.mp4 \
  --out /tmp/motionjson-phase01-demo_red_ball \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 12
python3 -m motionjson.cli validate /tmp/motionjson-phase01-demo_red_ball
```

Result: extraction wrote MotionJSON outputs and validation reported
`Validated 8 MotionJSON file(s); skipped 9 auxiliary JSON file(s).`

- `python3 -m pytest -q tests/test_ga_launch_docs.py tests/test_phase14_release_candidate.py` - passed, 9 tests.
- `npm run build` - passed.
- `npm test` - passed, 19 Node tests.
- `npm run lint` - passed.

## Screenshots And Demos Produced

No screenshot or GIF/MP4 assets were produced in Phase 01. The README avoids
broken or fake image links. `docs/assets/README_ASSETS.md` lists the required
assets and defers real capture automation to Phase 03.

## Review

Reviewer initially asked for evidence of the README's main mock UI startup path
and tighter wording around UI/backend workflow breadth. The UI startup,
health, and capabilities smoke checks were added to this report, the README
wording was narrowed to local UI/backend surfaces, and re-review found no
material findings.

## Known Limitations

- The README still has no embedded screenshots because real screenshot capture
  is a later phase.
- Devcontainer, Colab notebook, and Hugging Face Space paths are documented as
  planned rather than implemented.
- No license file exists in this repository snapshot, so the README states that
  reuse rights should not be assumed.
- Existing untracked `.motionjson/`, uppercase future-plan copy, and
  `out/demo_red_ball/` artifacts remain outside this phase commit scope.

## Follow-Up Tasks

- Phase 02: add copy-paste first-run scripts and free-instance docs.
- Phase 03: add real screenshot/demo capture automation and embed current
  assets in the README.
- Phase 04: make the docs index intent-based and add glossary/troubleshooting
  navigation.
- Phase 09: finalize generated artifact policy and CI/readiness checks.
