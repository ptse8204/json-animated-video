# SAM3 Local Discovery

SAM3 support is optional and capability-gated. The base MotionJSON install does
not install SAM3, download checkpoints, require CUDA, or make hosted calls. For
runtime setup details, use the official [facebookresearch/sam3](https://github.com/facebookresearch/sam3)
instructions as the source of truth.

Use SAM3 when you need scene-wide or semantic discovery:

- Find everything in the scene with SAM3 Tracker automatic mask generation on
  sampled keyframes, then SAM3 Tracker Video propagation for accepted masks.
- Trace by concept, for example `red ball` or `person in white`.
- Find objects like an exemplar/crop.

For lower-cost default object proposals, use `auto_object_proposals` with the
clean preset first.

## Requirements

SAM3 scene sweep is independent from SAM2. It does not require the `sam2`
package, a SAM2 checkpoint, or a SAM2 config. The scene-sweep runtime uses SAM3
Tracker automatic mask generation plus SAM3 Tracker Video support from the
independent `sam3-transformers` extra:

```bash
python3 -m pip install -e ".[sam3-transformers]"
```

The default model id is `facebook/sam3`. Set `SAM3_TRACKER_MODEL` or
`discovery.config.sam3TrackerModel` when you need a local model directory or a
different Hugging Face-compatible model id.

Real local SAM3 concept/exemplar execution expects:

- Python 3.12 or newer;
- PyTorch 2.7 or newer with CUDA available;
- the official SAM3 package installed separately;
- local model/checkpoint access configured through `SAM3_LOCAL_MODEL`.

Keep these paths distinct:

- `/content/sam3`, or any clone of `facebookresearch/sam3`, is the SAM3
  source/package directory. It lets Python import the official package, but it
  is not the model checkpoint.
- `facebook/sam3` is a Hugging Face repository id. It is useful when calling
  `hf_hub_download`, but it is not a local file path.
- `SAM3_LOCAL_MODEL` must point to a local checkpoint file, usually the
  downloaded `sam3.pt` in the Hugging Face cache, for example
  `/root/.cache/huggingface/hub/models--facebook--sam3/snapshots/<hash>/sam3.pt`.

Local `facebook/sam3` model use is gated by Meta approval. MotionJSON does not
provide a way to bypass that approval. If you already have an approved
`sam3.pt` file from a channel allowed by Meta, you can avoid Hugging Face token
setup by pointing `SAM3_LOCAL_MODEL` directly at that local file, for example a
Google Drive path mounted in Colab.

The official-package optional extra only prepares MotionJSON-side dependencies
for concept/exemplar workflows:

```bash
python3 -m pip install -e ".[sam3]"
```

Then install the official SAM3 package and resolve the checkpoint separately:

```bash
git clone https://github.com/facebookresearch/sam3.git /content/sam3
python3 -m pip install -e /content/sam3
python3 -m pip install huggingface_hub
python3 -c "from huggingface_hub import hf_hub_download; print(hf_hub_download(repo_id='facebook/sam3', filename='sam3.pt'))"
export SAM3_LOCAL_MODEL=/root/.cache/huggingface/hub/models--facebook--sam3/snapshots/<hash>/sam3.pt
python3 -m motionjson.cli backend diagnostics --json
```

Do not paste `facebook/sam3` or `/content/sam3` into `SAM3_LOCAL_MODEL`.
Paste the local `sam3.pt` file path printed by the resolver command.

To avoid Hugging Face token setup in Colab, put an approved checkpoint at a
stable path such as `/content/drive/MyDrive/motionjson-models/sam3.pt`, then
set:

```bash
export SAM3_LOCAL_MODEL=/content/drive/MyDrive/motionjson-models/sam3.pt
```

This avoids Hugging Face token setup, but it does not remove the requirement
for Meta-approved access to the local checkpoint. If you do not want local
gated-model setup at all, use Roboflow SAM3 or Fal SAM3 image from Model
Connections for concept/image workflows instead. Roboflow SAM3 is concept
segmentation, not a no-prompt scene-sweep provider.

Diagnostics should report missing package, unsupported Python, missing CUDA, or
missing model path explicitly. They must not claim SAM3 is runnable just because
the mock discovery modes are available.

In the Local UI, open **Model Connections -> SAM3 local**, save the local model
path and device, then run **Diagnose**. The checklist reports Python, torch,
CUDA, SAM3 package import, Hugging Face token status, and model-path readiness
without making hosted network calls. Local SAM3 runs in-process through
MotionJSON providers; no local API server workaround is used. Diagnostics
report scene-sweep readiness separately from concept/exemplar readiness, and
missing SAM2 is never a SAM3 scene-sweep blocker.

## Colab Checkpoint Path Flow

For Colab, the expected local setup order is:

1. Add `HF_TOKEN` to Colab userdata or enter it with `getpass`. Do not print the
   token or save notebook outputs containing it.
2. Optionally clone and install the source package:
   `git clone https://github.com/facebookresearch/sam3.git /content/sam3` and
   `python -m pip install -e /content/sam3`.
3. Resolve or download the checkpoint only after you opt in to the large gated
   download:

```python
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
checkpoint = Path(hf_hub_download(repo_id="facebook/sam3", filename="sam3.pt", token=token))
if not checkpoint.exists():
    raise RuntimeError(f"SAM3 checkpoint was not found: {checkpoint}")
os.environ["SAM3_LOCAL_MODEL"] = str(checkpoint)
print("Paste this into Model Connections -> SAM3 local -> model path:")
print(checkpoint)
```

The Colab notebook `notebooks/colab_ui_provider_connect_demo.ipynb` keeps this
download disabled by default with `RUN_DOWNLOAD_SAM3_CHECKPOINT = False`. It
also searches the Hugging Face cache, supports a Google Drive
`GOOGLE_DRIVE_SAM3_CHECKPOINT_PATH`, and lets you paste an existing approved
`sam3.pt` path before downloading anything.

## Troubleshooting

| Symptom | Meaning | Fix |
| --- | --- | --- |
| `SAM3_LOCAL_MODEL=facebook/sam3` | This is a Hugging Face repo id, not a local checkpoint path. | Use `hf_hub_download(repo_id="facebook/sam3", filename="sam3.pt")` and paste the returned local file path. |
| `SAM3_LOCAL_MODEL=/content/sam3` | This is the cloned source/package directory, not the checkpoint. | Install from `/content/sam3`, but set `SAM3_LOCAL_MODEL` to the downloaded `sam3.pt` file. |
| Missing `HF_TOKEN` | The gated Hugging Face file cannot be resolved. | Request/confirm access, then set `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` without printing it. |
| User does not want Hugging Face token setup | Official-package SAM3 concept/exemplar still needs an approved checkpoint, but scene sweep can use a SAM3 Tracker-compatible Transformers model path/id. | Use `SAM3_TRACKER_MODEL` for scene sweep, mount Google Drive or paste an approved `sam3.pt` for concept/exemplar, or use hosted concept/image workflows. |
| Access not approved | Hugging Face rejects the checkpoint download. | Open the model page while signed in, accept the access terms, then rerun the resolver. |
| Path does not exist | MotionJSON cannot find the local checkpoint file. | Rerun the resolver or paste the exact `sam3.pt` path printed by Hugging Face Hub. |
| CPU runtime | Official local SAM3 concept/exemplar expects CUDA; scene sweep also needs a usable torch/Transformers runtime and may be slow without GPU. | Use a GPU runtime for real SAM3 work, or use hosted concept/image workflows. |
| Python/CUDA incompatibility | The installed Colab runtime does not match official SAM3 requirements. | Use a Python 3.12 CUDA environment, or use hosted SAM3 for the first run. |
| Package import failure | The source package is not installed in the active runtime. | Install the official package separately, for example `python -m pip install -e /content/sam3`. |

## Config

SAM3 discovery modes are:

- `sam3_concept`
- `sam3_exemplar`
- `sam3_auto_masks`

Common config keys:

```json
{
  "mock": false,
  "sam3TrackerModel": "facebook/sam3",
  "sam3ModelPath": "/root/.cache/huggingface/hub/models--facebook--sam3/snapshots/<hash>/sam3.pt",
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
  --discovery-config '{"concept":"red ball","sam3ModelPath":"/root/.cache/huggingface/hub/models--facebook--sam3/snapshots/<hash>/sam3.pt"}' \
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

`sam3_auto_masks` is a true scene-sweep workflow. It does not send the broad
text concept `"object"` to SAM3 concept discovery. It samples keyframes, runs
SAM3 Tracker automatic mask generation on those frames, filters/dedupes masks,
then uses SAM3 Tracker Video to propagate accepted candidates:

```json
{
  "sceneSweep": true,
  "sam3TrackerModel": "facebook/sam3",
  "pointsPerBatch": 64,
  "qualityPreset": "maximum_recall",
  "maxKeyframes": 5,
  "maxCandidatesPerKeyframe": 64,
  "maxObjects": 24,
  "minMaskArea": 32,
  "maxMaskAreaRatio": 0.45,
  "dedupeIou": 0.78
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
