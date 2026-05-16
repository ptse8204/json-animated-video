from __future__ import annotations

import json
import shutil
from pathlib import Path

from motionjson import capabilities
from motionjson.cli import main


def _provider(report: dict, name: str) -> dict:
    return next(provider for provider in report["providers"] if provider["name"] == name)


def test_capability_report_is_machine_readable_json() -> None:
    report = capabilities.build_capability_report()

    encoded = json.dumps(report)
    decoded = json.loads(encoded)

    assert decoded["schema"] == capabilities.CAPABILITY_SCHEMA
    assert isinstance(decoded["providers"], list)
    assert decoded["summary"]["providersTotal"] == len(decoded["providers"])
    assert "installHint" in decoded["environment"]["dependencies"][0]
    assert "install_hint" not in decoded["environment"]["dependencies"][0]


def test_capability_report_marks_missing_optional_sam2_without_breaking_base_cli(monkeypatch) -> None:
    monkeypatch.setattr(capabilities, "_module_available", lambda module: module not in {"sam2", "torch"})
    monkeypatch.delenv("SAM2_LOCAL_CHECKPOINT", raising=False)
    monkeypatch.delenv("SAM2_LOCAL_CONFIG", raising=False)

    report = capabilities.build_capability_report()

    assert report["environment"]["cuda"]["torchInstalled"] is False
    assert report["environment"]["cuda"]["available"] is False
    assert _provider(report, "sam2-local")["status"] == "missing_dependency"
    assert _provider(report, "sam2-local")["available"] is False
    assert _provider(report, "sam2-local")["mockAvailable"] is True
    assert _provider(report, "threshold")["available"] is True


def test_capability_report_uses_explicit_sam2_paths_before_environment(tmp_path, monkeypatch) -> None:
    checkpoint = tmp_path / "sam2.pt"
    model_config = tmp_path / "sam2.yaml"
    checkpoint.write_text("checkpoint placeholder")
    model_config.write_text("model config placeholder")
    monkeypatch.setenv("SAM2_LOCAL_CHECKPOINT", str(tmp_path / "missing-env-checkpoint.pt"))
    monkeypatch.setenv("SAM2_LOCAL_CONFIG", str(tmp_path / "missing-env-config.yaml"))
    monkeypatch.setattr(capabilities, "_module_available", lambda module: True)
    monkeypatch.setattr(
        capabilities,
        "cuda_status",
        lambda: {
            "torchInstalled": True,
            "available": False,
            "device": "cpu",
            "reasons": ["CUDA unavailable in test."],
            "devices": [{"name": "cpu", "available": True}, {"name": "cuda", "available": False}],
        },
    )

    report = capabilities.build_capability_report(sam2_checkpoint=checkpoint, sam2_model_config=model_config)

    sam2_local = _provider(report, "sam2-local")
    assert sam2_local["configured"] is True
    assert sam2_local["available"] is True
    assert sam2_local["status"] == "available_cpu_only"
    assert sam2_local["metadata"]["checkpoint"]["source"] == "argument"
    assert sam2_local["metadata"]["checkpoint"]["exists"] is True
    assert sam2_local["metadata"]["modelConfig"]["source"] == "argument"
    assert sam2_local["metadata"]["modelConfig"]["exists"] is True


def test_capability_report_marks_explicit_missing_sam2_model_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(capabilities, "_module_available", lambda module: True)
    monkeypatch.setattr(
        capabilities,
        "cuda_status",
        lambda: {
            "torchInstalled": True,
            "available": True,
            "device": "cuda",
            "reasons": [],
            "devices": [{"name": "cpu", "available": True}, {"name": "cuda", "available": True}],
        },
    )

    report = capabilities.build_capability_report(
        sam2_checkpoint=tmp_path / "missing-checkpoint.pt",
        sam2_model_config=tmp_path / "missing-config.yaml",
    )

    sam2_local = _provider(report, "sam2-local")
    assert sam2_local["available"] is False
    assert sam2_local["status"] == "missing_model"
    assert "Configured sam2 checkpoint path does not point to an existing file." in sam2_local["reasons"]
    assert "Configured sam2 model config path does not point to an existing file." in sam2_local["reasons"]


def test_backend_diagnostics_capability_cli_outputs_json_without_initializing_backend(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    main(["backend", "diagnostics", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == capabilities.CAPABILITY_SCHEMA
    assert "providers" in payload
    assert not (tmp_path / ".motionjson").exists()


def test_backend_diagnostics_cli_accepts_sam2_model_path_flags(tmp_path, monkeypatch, capsys) -> None:
    checkpoint = tmp_path / "sam2.pt"
    model_config = tmp_path / "sam2.yaml"
    checkpoint.write_text("checkpoint placeholder")
    model_config.write_text("model config placeholder")
    monkeypatch.setattr(capabilities, "_module_available", lambda module: True)
    monkeypatch.setattr(
        capabilities,
        "cuda_status",
        lambda: {
            "torchInstalled": True,
            "available": False,
            "device": "cpu",
            "reasons": ["CUDA unavailable in test."],
            "devices": [{"name": "cpu", "available": True}, {"name": "cuda", "available": False}],
        },
    )

    main(
        [
            "backend",
            "diagnostics",
            "--json",
            "--sam2-checkpoint",
            str(checkpoint),
            "--sam2-config",
            str(model_config),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    sam2_local = _provider(payload, "sam2-local")
    assert sam2_local["status"] == "available_cpu_only"
    assert sam2_local["metadata"]["checkpoint"]["source"] == "argument"
    assert sam2_local["metadata"]["modelConfig"]["source"] == "argument"


def test_capability_report_includes_output_and_video_checks(tmp_path) -> None:
    video = Path("examples/demo_red_ball.mp4")

    report = capabilities.build_capability_report(output_dir=tmp_path / "nested" / "out", video_path=video)

    assert report["environment"]["output"]["checked"] is True
    assert report["environment"]["output"]["writable"] is True
    assert report["environment"]["videoIO"]["checkedVideo"] is True
    if report["environment"]["videoIO"]["opencvAvailable"]:
        assert report["environment"]["videoIO"]["readable"] is True


def test_capability_ffmpeg_missing_is_reported_not_crashed(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda executable: None if executable == "ffmpeg" else "/usr/bin/tool")

    report = capabilities.build_capability_report()

    ffmpeg_provider = _provider(report, "ffmpeg-video")
    assert report["environment"]["ffmpeg"]["available"] is False
    assert ffmpeg_provider["available"] is False
    assert ffmpeg_provider["status"] == "missing_dependency"
    assert "ffmpeg-video" in report["summary"]["missingOptional"]


def test_capability_secret_envs_are_presence_only(monkeypatch) -> None:
    monkeypatch.setenv("HOSTED_SEGMENTATION_URL", "https://example.invalid/sam2")
    monkeypatch.setenv("HOSTED_SEGMENTATION_API_KEY", "secret-hosted-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-openrouter-token")

    report = capabilities.build_capability_report()
    encoded = json.dumps(report)

    assert "secret-hosted-token" not in encoded
    assert "secret-openrouter-token" not in encoded
    assert _provider(report, "sam2-hosted")["available"] is True
    assert _provider(report, "openrouter")["available"] is True


def test_capability_report_includes_phase5_discovery_provider_modes(monkeypatch) -> None:
    monkeypatch.setattr(capabilities, "_module_available", lambda module: module in {"cv2", "numpy", "PIL", "jsonschema", "tqdm"})

    report = capabilities.build_capability_report()

    assert _provider(report, "manual_prompt")["status"] == "ready"
    assert _provider(report, "motion_foreground")["status"] == "ready"
    assert _provider(report, "external_masks")["status"] == "ready"
    assert _provider(report, "motion_foreground")["kind"] == "discovery_provider"
    assert _provider(report, "external_masks")["noModelSafe"] is True
    assert _provider(report, "text_detector")["metadata"]["sam2DirectText"] is False


def test_discovery_heavy_providers_report_missing_optional_deps_without_cuda(monkeypatch) -> None:
    monkeypatch.setattr(capabilities, "_module_available", lambda module: module in {"cv2", "numpy", "PIL", "jsonschema", "tqdm"})
    monkeypatch.setattr(
        capabilities,
        "cuda_status",
        lambda: {
            "torchInstalled": False,
            "available": False,
            "device": "cpu",
            "reasons": ["torch is not installed."],
            "devices": [{"name": "cpu", "available": True}],
        },
    )

    report = capabilities.build_capability_report()

    assert _provider(report, "sam_auto_masks")["status"] == "missing_dependency"
    assert _provider(report, "sam_auto_masks")["mockAvailable"] is True
    assert _provider(report, "text_detector")["status"] == "missing_dependency"
    assert _provider(report, "class_detector")["status"] == "missing_dependency"


def test_scaffolded_heavy_discovery_modes_do_not_report_runnable_until_backend_wired(tmp_path, monkeypatch) -> None:
    text_model = tmp_path / "text-detector.bin"
    class_model = tmp_path / "class-detector.pt"
    sam2_checkpoint = tmp_path / "sam2.pt"
    sam2_config = tmp_path / "sam2.yaml"
    for path in (text_model, class_model, sam2_checkpoint, sam2_config):
        path.write_text("placeholder")
    monkeypatch.setenv("TEXT_DETECTOR_MODEL", str(text_model))
    monkeypatch.setenv("CLASS_DETECTOR_MODEL", str(class_model))
    monkeypatch.setenv("SAM2_LOCAL_CHECKPOINT", str(sam2_checkpoint))
    monkeypatch.setenv("SAM2_LOCAL_CONFIG", str(sam2_config))
    monkeypatch.setattr(capabilities, "_module_available", lambda module: True)
    monkeypatch.setattr(
        capabilities,
        "cuda_status",
        lambda: {
            "torchInstalled": True,
            "available": True,
            "device": "cuda",
            "reasons": [],
            "devices": [{"name": "cpu", "available": True}, {"name": "cuda", "available": True}],
        },
    )

    report = capabilities.build_capability_report()

    for name in ("sam_auto_masks", "text_detector", "class_detector"):
        provider = _provider(report, name)
        assert provider["available"] is False
        assert provider["status"] == "not_configured"
        assert "scaffolded" in " ".join(provider["reasons"])


def test_no_model_discovery_modes_are_marked_available_or_mock_available() -> None:
    report = capabilities.build_capability_report()

    for name in ("manual_prompt", "motion_foreground", "external_masks"):
        provider = _provider(report, name)
        assert provider["mockAvailable"] is True
        assert provider["networkRequired"] is False
        assert provider["metadata"]["whenToUse"]
