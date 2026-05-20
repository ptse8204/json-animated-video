# SAM3 Local Discovery

SAM3 support is optional and capability-gated. The base MotionJSON install does
not install SAM3, download checkpoints, require CUDA, or make hosted calls. For
runtime setup details, use the official [facebookresearch/sam3](https://github.com/facebookresearch/sam3)
instructions as the source of truth.

Use SAM3 when you need semantic discovery:

- Trace by concept, for example `red ball` or `person in white`.
- Find objects like an exemplar/crop.
- Run higher-recall semantic proposals before review.

For lower-cost default object proposals, use `auto_object_proposals` with the
clean preset first.

## Requirements

Real local SAM3 execution expects:

- Python 3.12 or newer;
- PyTorch 2.7 or newer with CUDA available;
- the official SAM3 package installed separately;
- local model/checkpoint access configured through `SAM3_LOCAL_MODEL`.

The optional package extra only prepares MotionJSON-side dependencies:

```bash
python3 -m pip install -e ".[sam3]"
```

Then install the official SAM3 package and model files according to the SAM3
project instructions, set `SAM3_LOCAL_MODEL`, and rerun diagnostics:

```bash
SAM3_LOCAL_MODEL=/path/to/sam3-model \
python3 -m motionjson.cli backend diagnostics --json
```

Diagnostics should report missing package, unsupported Python, missing CUDA, or
missing model path explicitly. They must not claim SAM3 is runnable just because
the mock discovery modes are available.

## Config

SAM3 discovery modes are:

- `sam3_concept`
- `sam3_exemplar`
- `sam3_auto_masks`

Common config keys:

```json
{
  "mock": false,
  "sam3ModelPath": "/path/to/sam3-model",
  "sam3Device": "cuda",
  "useVideoSession": true,
  "maxCandidatesPerKeyframe": 16,
  "maxObjects": 8,
  "minMaskArea": 32,
  "maxMaskAreaRatio": 0.9
}
```

Concept discovery:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/sam3_concept \
  --discovery-provider sam3_concept \
  --discovery-config '{"concept":"red ball","sam3ModelPath":"/path/to/sam3-model"}' \
  --mask-provider mock \
  --max-frames 24
```

Exemplar discovery accepts `exemplars` or a prompt `box`:

```json
{
  "exemplars": ["crop_001"],
  "box": [120, 80, 96, 72]
}
```

`sam3_auto_masks` uses a broad concept when no concept is supplied:

```json
{
  "concept": "object",
  "qualityPreset": "maximum_recall"
}
```

## Output

The local adapter writes the same API-first candidate shape used by other
discovery providers:

- `candidates.json`;
- candidate mask sequences;
- thumbnail and mask-preview artifacts;
- provider diagnostics and candidate metadata;
- review-gated track/export state.

When the SAM3 video predictor returns full mask sequences, MotionJSON records
`trackingProvider: "sam3-local"`. If only a prompt-frame mask is available,
MotionJSON writes a keyframe-seed mask sequence with a warning instead of
pretending video tracking succeeded.

## Tests

CI uses injected fake SAM3 processors and predictors. Real SAM3 smoke tests are
skipped unless both `MOTIONJSON_RUN_REAL_SAM3_TESTS=1` and `SAM3_LOCAL_MODEL`
are set.
