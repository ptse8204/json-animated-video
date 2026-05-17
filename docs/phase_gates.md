# Phase Gates

The Master Agent must not proceed to the next phase until all gates pass.

## Required gate sequence

For each phase:

```text
1. Planning subagent
2. Master review of plan
3. Execution subagent
4. Master review of implementation
5. Review subagent
6. Fix any concerns
7. Tests and validation
8. Git commit
9. Report commit hash
```

## PASS conditions

The phase may close only when:

```text
Planning subagent: PASS / NO CONCERNS
Execution subagent: PASS / NO CONCERNS
Review subagent: PASS / NO CONCERNS
Tests/validation: PASS
Git commit: CREATED
```

## Stop conditions

The Master Agent must stop phase advancement if any result contains:

```text
FAIL
CONCERN
BLOCKER
QUESTION
UNCLEAR
NEEDS CHANGE
TODO REQUIRED BEFORE MERGE
TEST FAILURE
SECURITY RISK
SECRET LEAK
```

## Validation commands

Default:

```bash
pytest -q
git diff --check
```

If frontend code exists:

```bash
npm test
npm run lint
```

If extraction/rendering code changes:

```bash
python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 12
```

## Commit rule

Every phase must end with exactly one phase commit unless the Master Agent explicitly splits large work into reviewed subphase commits.

Commit message format:

```bash
git commit -m "phase N: <phase name>"
```

## Reviewer checklist

- Product framing remains object-layer editing, not universal SVG/Lottie conversion.
- Photoreal assets remain raster/alpha by default.
- AI providers are swappable.
- OpenRouter is not coupled to segmentation.
- No secrets are committed.
- Tests or validation commands exist.
- Resource-efficiency claims are measured, not exaggerated.
- Every export path preserves rights metadata placeholders.
