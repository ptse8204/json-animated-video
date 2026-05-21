# Run MotionJSON on Free or Low-install Instances

This guide keeps the first path CPU/mock/no-model. Do not assume free hosted
instances have GPUs, persistent disks, model weights, or safe long-running web
service hosting.

## GitHub Codespaces

Codespaces is the best free-instance path for the local UI because it gives you
a terminal, a forwarded port, and a disposable Linux environment.

1. Open the repository in Codespaces.
2. Let the devcontainer build if prompted, or run the manual setup below.
3. Start the mock UI:

```bash
python3 -m pip install -U pip
python3 -m pip install -e ".[ui]"
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli ui --no-open --mock --host 0.0.0.0 --port 8766
```

4. Open the forwarded `8766` port in the browser.

The included `.devcontainer/devcontainer.json` installs Python, Node, FFmpeg,
the local Python package with `ui,dev` extras, and runs the static UI build.
It does not install SAM2, detector weights, or hosted provider credentials.
GitHub's Codespaces docs explain that localhost URLs printed by an app can be
forwarded and opened from the browser.

## Google Colab notebooks

Colab is suitable for short interactive demos and inspecting generated files.
It is not the right place to host a public long-running MotionJSON web service.

Use the checked-in notebooks when you want ready Colab surfaces:

- [Colab local UI demo](../notebooks/colab_ui_local_demo.ipynb): launches
  `python3 -m motionjson.cli ui --no-open --mock` in the notebook runtime,
  displays `/ui/` through Colab's port proxy, and provides the generated
  red-ball video path for UI registration.
- [Colab red-ball CLI demo](../notebooks/colab_red_ball_cli_demo.ipynb): runs
  the compact threshold extraction, validation, and ZIP download path.
- [Colab export and browser preview demo](../notebooks/colab_red_ball_export_preview.ipynb):
  runs extraction, validates output, exports a website ZIP, and previews
  `examples/plain_js_embed.html` against generated MotionJSON assets.
- [Colab provider diagnostics](../notebooks/colab_provider_diagnostics.ipynb):
  reports provider readiness, defensively redacts diagnostic fields that look
  credential-related, and runs a no-model smoke extraction.

The UI notebook is intended for active, short, notebook-driven demos. Keep it in
mock/no-model mode first, avoid secrets in shared notebooks, and prefer
Codespaces or a local machine for sustained UI sessions.

Notebook cells can still use the manual CLI path:

```bash
!git clone https://github.com/ptse8204/json-animated-video.git
%cd json-animated-video
!python3 -m pip install -U pip
!python3 -m pip install -e ".[ui]"
!python3 -m motionjson.cli backend diagnostics --json
!python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4
!python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo_red_ball \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 12
!python3 -m motionjson.cli validate out/demo_red_ball
```

Use Colab file browsing or zip downloads to inspect `out/demo_red_ball/`.
Avoid putting provider credentials in notebooks unless you understand Colab's
sharing and runtime behavior.
Google's Colab FAQ says resources are not guaranteed or unlimited, and it lists
file hosting, media serving, unrelated web services, and bypassing the notebook
UI to interact primarily through a web UI among restricted activities.

## Hugging Face Space plan

A safe first Space should be a CPU Basic demo, not a paid GPU requirement.
The concrete proof-of-concept handoff plan is
[spaces/huggingface/README.md](../spaces/huggingface/README.md).

Recommended scope:

- start the local UI or a minimal wrapper in `--mock` mode;
- include `examples/demo_red_ball.mp4` or generate it at startup;
- show provider diagnostics so missing SAM2/detectors are visible;
- avoid client-side secrets;
- store generated files only in the Space's expected ephemeral or configured
  storage path;
- clearly label any SAM2, detector, or hosted-provider path as optional.

Do not advertise a Space as production hosting until persistence, privacy,
artifact cleanup, credentials, and model download behavior are explicitly
designed and tested.
Hugging Face's Spaces docs describe Docker Spaces, CPU Basic hardware, secrets,
and ephemeral default disk storage. Treat those docs as authoritative if Space
behavior or pricing changes.

## Privacy and persistence warnings

- Treat uploaded videos as local files inside the instance.
- Free instances may reset disks and remove generated outputs.
- Public demos should not expose local absolute paths, storage keys, API keys,
  or provider credentials.
- Hosted segmentation or LLM/VLM providers should stay disabled unless an
  operator explicitly configures them and documents data handling.

## Reference Links

- [GitHub Codespaces port forwarding](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace)
- [Google Colab FAQ](https://research.google.com/colaboratory/faq.html)
- [Hugging Face Spaces overview](https://huggingface.co/docs/hub/spaces-overview)
- [Hugging Face Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker)
- [Hugging Face Spaces storage](https://huggingface.co/docs/hub/spaces-storage)
