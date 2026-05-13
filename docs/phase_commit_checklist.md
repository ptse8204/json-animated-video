# Phase Commit Checklist

Use this before every phase commit.

## 1. Scope check

```text
Is this phase limited to the intended roadmap scope?
Did it avoid implementing the next phase too early?
Did it avoid unrelated refactors?
```

## 2. Product check

```text
Does the wording preserve the product identity?
Does it avoid claiming universal SVG/Lottie conversion?
Does it treat JSON as an edit/runtime graph, not a replacement for video pixels?
```

## 3. Architecture check

```text
Are providers swappable?
Are LLM/VLM providers separate from segmentation providers?
Are mock providers available?
Are paid APIs optional?
Are secrets absent?
```

## 4. Test check

Run:

```bash
pytest -q
git diff --check
```

If frontend touched:

```bash
npm test
npm run lint
```

If extraction/rendering touched:

```bash
python examples/make_demo_video.py --out examples/demo_red_ball.mp4
python -m motionjson.cli extract examples/demo_red_ball.mp4 --out out/demo --mask-provider threshold --max-frames 12
```

## 5. Reviewer gate

Proceed only if reviewer returns:

```text
PASS / NO CONCERNS
```

## 6. Commit

```bash
git status
git add .
git commit -m "phase N: <phase name>"
git rev-parse --short HEAD
```
