from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


PUBLIC_TUNNEL_MARKERS = [
    "ngrok",
    "localtunnel",
    "lt --port",
    "cloudflared",
    "trycloudflare",
    "serveo",
]


def assert_no_public_tunnel_helpers(text: str) -> None:
    lowered = text.lower()
    for marker in PUBLIC_TUNNEL_MARKERS:
        assert marker not in lowered


def test_devcontainer_is_cpu_mock_first_and_codespaces_ready() -> None:
    config = json.loads(read(".devcontainer/devcontainer.json"))
    post_create = config["postCreateCommand"]

    assert "python:1-3.11" in config["image"]
    assert "ghcr.io/devcontainers/features/node:1" in config["features"]
    assert config["containerEnv"]["SAM2_LOCAL_DEVICE"] == "cpu"
    assert "python3 -m pip install -e \".[ui,dev]\"" in post_create
    assert "npm run build" in post_create
    assert "backend diagnostics --json" in post_create
    assert "sam2" not in post_create.lower()
    assert 8766 in config["forwardPorts"]


def test_readme_and_free_instance_docs_link_hosted_demo_surfaces() -> None:
    readme = read("README.md")
    free_docs = read("docs/run_free_instances.md")

    for expected in [
        "https://github.com/codespaces/badge.svg",
        "https://codespaces.new/ptse8204/json-animated-video",
        "notebooks/colab_ui_local_demo.ipynb",
        "notebooks/colab_ui_provider_connect_demo.ipynb",
        "notebooks/colab_red_ball_cli_demo.ipynb",
        "notebooks/colab_red_ball_export_preview.ipynb",
        "notebooks/colab_provider_diagnostics.ipynb",
        "https://colab.research.google.com/assets/colab-badge.svg",
        "spaces/huggingface/README.md",
        "no paid GPU",
        "no client-side secrets",
    ]:
        assert expected in readme

    for expected in [
        "../notebooks/colab_ui_local_demo.ipynb",
        "../notebooks/colab_ui_provider_connect_demo.ipynb",
        "../notebooks/colab_red_ball_cli_demo.ipynb",
        "../notebooks/colab_red_ball_export_preview.ipynb",
        "../notebooks/colab_provider_diagnostics.ipynb",
        "https://colab.research.google.com/assets/colab-badge.svg",
        "../spaces/huggingface/README.md",
        "real-provider-oriented",
        "public long-running MotionJSON web service",
        "motionjson.cli ui --no-open --host",
        "Colab's port proxy",
        "defensively redacts diagnostic fields",
        "Free instances may reset disks",
        "provider credentials",
    ]:
        assert expected in free_docs


def test_all_checked_in_notebooks_have_colab_badges_in_docs() -> None:
    docs_text = "\n".join(
        [
            read("README.md"),
            read("notebooks/README.md"),
            read("docs/run_free_instances.md"),
        ]
    )
    notebooks = sorted(path.name for path in (ROOT / "notebooks").glob("*.ipynb"))

    assert notebooks
    for notebook in notebooks:
        badge_url = f"https://colab.research.google.com/github/ptse8204/json-animated-video/blob/main/notebooks/{notebook}"
        assert notebook in docs_text
        assert badge_url in docs_text


def test_colab_notebook_is_valid_cpu_cli_demo() -> None:
    notebook = json.loads(read("notebooks/colab_red_ball_cli_demo.ipynb"))
    joined = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert notebook["nbformat"] == 4
    assert "https://github.com/ptse8204/json-animated-video.git" in joined
    assert "subprocess.run([\"git\", \"clone\"" in joined
    assert "python3 -m pip install -e \".[ui]\"" in joined
    assert "backend diagnostics --json" in joined
    assert "examples/make_demo_video.py --out examples/demo_red_ball.mp4" in joined
    assert "--mask-provider threshold" in joined
    assert "python3 -m motionjson.cli validate out/demo_red_ball" in joined
    assert "web_asset_manifest.json" in joined
    assert "motionjson_red_ball_output.zip" in joined
    assert "long-running public web service" in joined
    assert "provider credentials" in joined
    assert "SAM2 checkpoints" in joined
    assert "OPENROUTER_API_KEY" not in joined


def test_colab_ui_notebook_is_valid_mock_local_ui_demo() -> None:
    notebook = json.loads(read("notebooks/colab_ui_local_demo.ipynb"))
    joined = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert notebook["nbformat"] == 4
    assert "https://github.com/ptse8204/json-animated-video.git" in joined
    assert "sys.executable" in joined
    assert "pip\", \"install\", \"-e\", \".[ui]\"" in joined
    assert "examples/make_demo_video.py" in joined
    assert "backend\", \"diagnostics\", \"--text\"" in joined
    assert "motionjson.cli" in joined
    assert "\"ui\"" in joined
    assert "\"--no-open\"" in joined
    assert "\"--debug-mock\"" in joined
    assert "\"127.0.0.1\"" in joined
    assert "output.serve_kernel_port_as_iframe" in joined
    assert "output.serve_kernel_port_as_window" in joined
    assert "Demo video path to register in the UI" in joined
    assert "long-running/public UI hosting" in joined
    assert "provider credentials" in joined
    assert "hosted-service secrets" in joined
    assert "OPENROUTER_API_KEY" not in joined
    assert_no_public_tunnel_helpers(joined)
    assert "ZipFile" not in joined
    assert "files.download" not in joined
    assert "archive.write" not in joined
    assert "workspace_zip" not in joined
    assert "secret_json" not in joined
    assert all(not cell.get("outputs") for cell in notebook["cells"])


def test_colab_export_preview_notebook_is_valid_browser_handoff_demo() -> None:
    notebook = json.loads(read("notebooks/colab_red_ball_export_preview.ipynb"))
    joined = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert notebook["nbformat"] == 4
    assert "https://github.com/ptse8204/json-animated-video.git" in joined
    assert "pip\", \"install\", \"-e\", \".[ui]\"" in joined
    assert "examples/make_demo_video.py" in joined
    assert "\"extract\"" in joined
    assert "\"--mask-provider\"" in joined
    assert "\"threshold\"" in joined
    assert "\"validate\"" in joined
    assert "\"export\"" in joined
    assert "\"website-zip\"" in joined
    assert "website_package.zip" in joined
    assert "examples/plain_js_embed.html?manifest=/out/demo_red_ball/web_asset_manifest.json" in joined
    assert "\"http.server\"" in joined
    assert "\"127.0.0.1\"" in joined
    assert "output.serve_kernel_port_as_iframe" in joined
    assert "files.download(str(export_zip))" in joined
    assert "provider credentials" in joined
    assert "OPENROUTER_API_KEY" not in joined
    assert_no_public_tunnel_helpers(joined)
    assert all(not cell.get("outputs") for cell in notebook["cells"])


def test_colab_provider_diagnostics_notebook_is_redacted_and_no_model() -> None:
    notebook = json.loads(read("notebooks/colab_provider_diagnostics.ipynb"))
    joined = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert notebook["nbformat"] == 4
    assert "https://github.com/ptse8204/json-animated-video.git" in joined
    assert "pip\", \"install\", \"-e\", \".[ui]\"" in joined
    assert "backend\", \"diagnostics\", \"--text\"" in joined
    assert "backend\", \"diagnostics\", \"--json\"" in joined
    assert "sensitive_key_fragments" in joined
    assert "redact_diagnostics" in joined
    assert "safe_diagnostics" in joined
    assert "secret_value_patterns" in joined
    assert "redact_string" in joined
    assert "bearer\\s+" in joined
    assert "api[_-]?key" in joined
    assert "sk-[A-Za-z0-9_-]{12,}" in joined
    assert "report_path.write_text(json.dumps(safe_diagnostics" in joined
    assert "out/diagnostics_red_ball" in joined
    assert "\"--mask-provider\"" in joined
    assert "\"threshold\"" in joined
    assert "validate\", \"out/diagnostics_red_ball\"" in joined
    assert "This notebook intentionally does not request API keys" in joined
    assert "provider secrets" in joined
    assert "OPENROUTER_API_KEY" not in joined
    assert "secret_json" not in joined
    assert_no_public_tunnel_helpers(joined)
    assert all(not cell.get("outputs") for cell in notebook["cells"])


def test_colab_ui_provider_connect_notebook_uses_private_colab_proxy_and_vendor_profiles() -> None:
    notebook = json.loads(read("notebooks/colab_ui_provider_connect_demo.ipynb"))
    joined = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert notebook["nbformat"] == 4
    assert "https://github.com/ptse8204/json-animated-video.git" in joined
    assert '".[ui,hosted-segmentation,hosted-sam3,hosted-sam-vendors]"' in joined
    assert "ROBOFLOW_API_KEY" in joined
    assert "REPLICATE_API_TOKEN" in joined
    assert "FAL_KEY" in joined
    assert "userdata.get" in joined
    assert "getpass" in joined
    assert '"motionjson", "ui", "--no-open", "--host", "127.0.0.1"' in joined
    assert '"--mock"' not in joined
    assert "HF_TOKEN" in joined
    assert "SAM3_LOCAL_MODEL" in joined
    assert "RUN_LOCAL_SAM2_SETUP" in joined
    assert "RUN_LOCAL_SAM3_SETUP" in joined
    assert "CUDA available" in joined
    assert "output.serve_kernel_port_as_iframe" in joined
    assert "output.serve_kernel_port_as_window" in joined
    assert "Roboflow SAM3" in joined
    assert "Replicate SAM2 video" in joined
    assert "Fal SAM3 image" in joined
    assert "paste temporary credentials into the UI Model Connections form" in joined
    assert "secret_json" not in joined
    assert_no_public_tunnel_helpers(joined)
    assert all(not cell.get("outputs") for cell in notebook["cells"])


def test_huggingface_space_plan_is_cpu_basic_no_secret_no_gpu() -> None:
    plan = read("spaces/huggingface/README.md")

    for expected in [
        "sdk: docker",
        "app_port: 8766",
        "CPU Basic",
        "mock mode",
        "examples/demo_red_ball.mp4",
        "backend diagnostics --json",
        "ui --no-open --mock --host 0.0.0.0 --port 8766",
        "Do not put API keys",
        "Do not promise persistence",
        "paid GPU",
        "provider credentials",
    ]:
        assert expected in plan


def test_canonical_phase10_report_matches_free_hosted_demo_phase() -> None:
    report = read("docs/roadmap/phase-10-report.md")
    older_report = read("docs/roadmap/phase-10-correction-workflows-report.md")

    assert "Free Hosted Demo Paths" in report
    assert "Colab notebook" in report
    assert "Hugging Face Space" in report
    assert "local UI correction workflows" in older_report
