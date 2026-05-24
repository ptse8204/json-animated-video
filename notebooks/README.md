# MotionJSON Colab notebooks

These notebooks are designed for short, interactive MotionJSON demos in Google
Colab. Keep the paths separate:

- CPU/no-model demos: red-ball CLI, export preview, provider diagnostics, and
  local UI debug smoke.
- Provider-connect UI: hosted keys, explicit hosted opt-in, and real Local UI
  Model Connections.
- Heavy local SAM setup: optional SAM2/SAM3 cells inside the provider-connect
  notebook only.

Colab does not guarantee GPU availability, memory, runtime length, or VM
lifetime. Do not paste private videos, provider API keys, hosted credentials,
SAM checkpoints, or notebook outputs containing secrets into shared notebooks.
Use provider diagnostics to confirm that SAM2/SAM3 is runnable; a saved setting
or environment variable only means the provider is configured.

| Notebook | Open | Purpose | Safe first path |
| --- | --- | --- | --- |
| `colab_ui_local_demo.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_ui_local_demo.ipynb) | Launches the local MotionJSON UI inside a Colab runtime using Colab's notebook port proxy. | Contributor debug no-model UI with a generated red-ball video path to register. |
| `colab_ui_provider_connect_demo.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_ui_provider_connect_demo.ipynb) | Launches the Local UI with hosted SAM vendor dependencies, GPU checks, optional local SAM2/SAM3 setup cells, and provider profile setup. | Real Model Connections path for local SAM2, local SAM3, Replicate SAM2 video, Roboflow SAM3, Fal SAM3 image, or custom SAM endpoints. |
| `colab_red_ball_cli_demo.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_red_ball_cli_demo.ipynb) | Existing compact CLI demo that extracts, validates, and downloads red-ball output. | Threshold provider, CPU-only. |
| `colab_red_ball_export_preview.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_red_ball_export_preview.ipynb) | Runs extraction, validates output, creates a website ZIP, and previews the browser runtime through Colab. | Threshold provider plus static preview server. |
| `colab_provider_diagnostics.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_provider_diagnostics.ipynb) | Reports provider readiness and runs a no-model smoke extraction. | Diagnostics plus threshold smoke test. |

Colab is useful for learning and short demos. It is not a production hosting
surface for a long-running public MotionJSON UI. Hosted SAM2/SAM3 providers
can send frames, prompts, or derived image data to third-party services and
require explicit cost/privacy acknowledgement before smoke tests or runs.
