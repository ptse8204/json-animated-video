# System Requirements

MotionJSON's base install is intentionally CPU-friendly. Heavy model providers
are optional and should be enabled only after diagnostics show that the local
runtime, model files, and hosted-provider opt-ins match the workflow.

## Base Requirements

- Python `>=3.10`, matching `pyproject.toml`.
- Git for cloning the repository.
- 4 GB RAM minimum for tiny CPU/no-model demos; 8 GB RAM recommended.
- 10-30 GB free disk for the repository, virtual environment, cached frames,
  outputs, and optional checkpoints. Longer videos need more.
- FFmpeg for browser-safe previews and MP4/WebM video render/export paths.
  JSON, masks, cutouts, and website manifests can still be generated without
  FFmpeg.
- Node.js only for repository JavaScript checks and UI build scripts such as
  `npm test`, `npm run lint`, `npm run build`, and `npm run ui:layout`.

The Local UI first-run path should use short clips. Long clips multiply frame
cache size, model memory, review volume, and export time.

## Which Path Should I Choose?

| Path | Choose this when | Local requirements | Hosted/cost/privacy notes |
| --- | --- | --- | --- |
| CPU/no-model demo | You are trying MotionJSON for the first time or validating a machine. Use `Use demo video`, `Find moving things`, `Import masks`, or simple threshold CLI demos. | Python `>=3.10`, 4 GB RAM minimum for tiny demos, 8 GB recommended. No GPU, SAM, detectors, or API keys. | None. Keeps media local. |
| Local SAM2 | You want point/box-prompted object tracing and want frames to stay on your machine. In the UI choose `Cut out one object` and `Model Connections` -> `SAM2 local`. | 16 GB RAM minimum for small clips, 32 GB recommended. NVIDIA GPU with 8 GB VRAM can handle small experiments; 12-16+ GB VRAM is more comfortable. Requires SAM2 package, torch/CUDA, checkpoint path, and config path. CPU is expected to be slow. | None after setup. |
| Hosted SAM2 | You want SAM2-style tracing without a local GPU. In `Model Connections`, use `Replicate SAM2 video` or a custom SAM2-compatible endpoint. | No local GPU or model weights. Requires provider SDK/dependency only when the selected profile needs one. | Requires an API key, hosted-call opt-in, and cost/privacy acknowledgement before network tests or hosted runs. Frames and prompts may leave the machine. |
| Local SAM3 | You want concept/exemplar discovery locally and have a strong CUDA machine. In `Model Connections`, use `SAM3 local`. | 32 GB RAM recommended. Modern NVIDIA GPU with 16+ GB VRAM recommended unless your exact checkpoint/clip has been verified. Requires official SAM3 package, a real local `sam3.pt`, torch/CUDA, and compatible Python runtime. | None after setup. Model checkpoint access may require upstream approval. |
| Hosted SAM3 | You want text/concept segmentation without local SAM3 hardware. In `Model Connections`, use `Roboflow SAM3`, `Fal SAM3 image`, or a custom SAM3 endpoint. | No local GPU or checkpoint. | Requires an API key, hosted-call opt-in, and cost/privacy acknowledgement. Frames, prompts, or derived image data may be sent to the selected provider. |
| Motion foreground | You want a CPU moving-object pass on a short clip with a mostly stable camera. Use `Find moving things`. | Python `>=3.10`; no model weights, GPU, or hosted keys. Works best with clear motion and limited camera movement. | None. Keeps media local. |
| External masks | You already have masks from another tool. Use `Import masks`. | Python `>=3.10`; readable mask directory or manifest with matching frame/object IDs. | None unless the external tool used one. MotionJSON import stays local. |

## Optional Model Notes

MotionJSON keeps optional provider dependencies out of the base install. A
provider shown as configured is not necessarily runnable: diagnostics separate
`installed`, `configured`, and `runnable`, and hosted providers also require
explicit network/cost/privacy acknowledgement.

Official upstream requirements can be stricter than MotionJSON's base Python
requirement:

- The official SAM2 install guide recommends Linux with Python `>=3.10`,
  PyTorch `>=2.5.1`, matching torchvision, and CUDA toolkits matching the
  installed PyTorch build:
  <https://github.com/facebookresearch/sam2/blob/main/INSTALL.md>.
- The official SAM3 repository lists Python `3.12+`, PyTorch `2.7+`, and a
  CUDA-compatible GPU with CUDA `12.6+` for local SAM3:
  <https://github.com/facebookresearch/sam3>.
- Roboflow documents SAM3 hosted/serverless paths that require a Roboflow API
  key and accept URL or base64 image inputs:
  <https://docs.roboflow.com/deploy/supported-models/sam3>.
- Google Colab does not guarantee GPUs, runtime length, memory, or VM lifetime;
  limits and available hardware vary over time:
  <https://research.google.com/colaboratory/faq.html#resource-limits>.
- FFmpeg is the external tool MotionJSON uses for browser-safe previews and
  video render/export paths:
  <https://www.ffmpeg.org/documentation.html>.

If your local SAM3 setup needs Python 3.12 while MotionJSON is installed in a
Python 3.10/3.11 environment, use a separate SAM3 runtime or a hosted SAM3
provider until the exact local environment is verified.
