from __future__ import annotations

from pathlib import Path

from motionjson.capabilities import build_capability_report

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback.
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pyproject_declares_phase13_optional_dependency_extras():
    pyproject = tomllib.loads(read("pyproject.toml"))
    extras = pyproject["project"]["optional-dependencies"]

    for name in ["ui", "sam2", "detectors", "yolo", "hosted-segmentation", "openrouter", "dev"]:
        assert name in extras

    assert extras["ui"] == []
    assert any(dep.lower().startswith("torch") for dep in extras["sam2"])
    assert any(dep.lower().startswith("sam2") for dep in extras["sam2"])
    assert any(dep.lower().startswith("groundingdino") for dep in extras["detectors"])
    assert any(dep.lower().startswith("ultralytics") for dep in extras["yolo"])
    assert any(dep.lower().startswith("pytest") for dep in extras["dev"])
    assert not any(dep.lower().startswith(("torch", "sam2", "groundingdino", "ultralytics")) for dep in pyproject["project"]["dependencies"])


def test_provider_optional_extras_align_with_packaging_metadata():
    extras = tomllib.loads(read("pyproject.toml"))["project"]["optional-dependencies"]
    report = build_capability_report()
    advertised = {
        provider["optionalExtra"]
        for provider in report["providers"]
        if provider.get("optionalExtra")
    }

    assert advertised <= set(extras)
    assert {"sam2", "detectors", "yolo", "hosted-segmentation", "openrouter"} <= advertised


def test_first_run_docs_cover_install_launch_demos_and_powershell():
    first_run = read("docs/first_run.md")
    onboarding = read("docs/onboarding.md")
    index = read("docs/index.md")

    assert 'python3 -m pip install -e ".[ui]"' in first_run
    assert 'python -m pip install -e ".[ui]"' in first_run
    assert "Windows PowerShell" in first_run
    assert "backend diagnostics --json" in first_run
    assert "python3 -m motionjson.cli ui --no-open --mock" in first_run
    assert "examples/demo_red_ball.mp4" in first_run
    assert "--fixtures multi_object" in first_run
    assert "--object-mask-dir red_ball=" in first_run
    assert "masks_too_large_whole_frame" in first_run
    assert "[First run setup](first_run.md)" in onboarding
    assert "[First run setup](first_run.md)" in index


def test_local_ui_exposes_first_run_diagnostics_panel():
    index = read("src/motionjson/ui/static/index.html")
    app = read("src/motionjson/ui/static/app.js")
    build_script = read("scripts/build_ui_shell.mjs")

    assert 'id="firstRunChecklist"' in index
    assert "First Run" in index
    assert "function renderFirstRunChecklist" in app
    assert "No-model smoke" in app
    assert "Optional models" in app
    assert "Next action" in app
    assert "recommendedCommand" in app
    assert "local/free" in app
    assert "configured, not runnable" in app
    assert "firstRunChecklist" in build_script
    assert "renderFirstRunChecklist" in build_script


def test_extraction_mode_docs_include_failure_modes_and_multi_object_sample():
    discovery = read("docs/discovery_providers.md")
    provider_capabilities = read("docs/provider_capabilities.md")
    multi = read("docs/multi_object_extraction.md")
    local_ui = read("docs/local_ui.md")

    assert "When To Use And Failure Modes" in discovery
    assert "whole-frame masks" in discovery
    assert "UI vs CLI Support Today" in discovery
    assert "Safer Fallback" in discovery
    assert "Provider Matrix" in provider_capabilities
    for phrase in ["Local/free", "GPU required", "Model weights", "Credentials", "Best for", "Common failure modes"]:
        assert phrase in provider_capabilities
    for provider in ["`threshold`", "`motion_foreground`", "`external_masks`", "`sam2-local`", "`sam2-hosted`", "`text_detector`", "`class_detector`", "`openrouter`"]:
        assert provider in provider_capabilities
    assert "python3 -m motionjson.cli benchmark --fixtures multi_object" in multi
    assert "blue_block=out/benchmarks/fixtures/multi_object/masks/blue_block" in multi
    assert "PowerShell" in local_ui
    assert "First Run checklist" in local_ui
