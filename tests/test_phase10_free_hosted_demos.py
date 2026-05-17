from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


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
        "notebooks/colab_red_ball_cli_demo.ipynb",
        "spaces/huggingface/README.md",
        "no paid GPU",
        "no client-side secrets",
    ]:
        assert expected in readme

    for expected in [
        "../notebooks/colab_red_ball_cli_demo.ipynb",
        "../spaces/huggingface/README.md",
        "CPU/mock/no-model",
        "public long-running MotionJSON web service",
        "Free instances may reset disks",
        "provider credentials",
    ]:
        assert expected in free_docs


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
