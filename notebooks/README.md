# MotionJSON Colab notebooks

These notebooks are designed for short, interactive MotionJSON demos in Google
Colab. Keep the first run CPU/no-model unless you intentionally configure
optional providers.

| Notebook | Open | Purpose | Safe first path |
| --- | --- | --- | --- |
| `colab_ui_local_demo.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_ui_local_demo.ipynb) | Launches the local MotionJSON UI inside a Colab runtime using Colab's notebook port proxy. | Mock/no-model local UI with a generated red-ball video path to register. |
| `colab_ui_provider_connect_demo.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_ui_provider_connect_demo.ipynb) | Launches the Local UI with hosted SAM vendor dependencies and provider profile setup. | UI stays in mock mode until a user explicitly enables hosted provider calls. |
| `colab_red_ball_cli_demo.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_red_ball_cli_demo.ipynb) | Existing compact CLI demo that extracts, validates, and downloads red-ball output. | Threshold provider, CPU-only. |
| `colab_red_ball_export_preview.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_red_ball_export_preview.ipynb) | Runs extraction, validates output, creates a website ZIP, and previews the browser runtime through Colab. | Threshold provider plus static preview server. |
| `colab_provider_diagnostics.ipynb` | [![Open in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/colab_provider_diagnostics.ipynb) | Reports provider readiness and runs a no-model smoke extraction. | Diagnostics plus threshold smoke test. |

Colab is useful for learning and short demos. It is not a production hosting
surface for a long-running public MotionJSON UI. Do not paste private videos,
provider API keys, hosted segmentation credentials, SAM checkpoints, or other
secrets into shared notebooks.
