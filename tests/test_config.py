import pytest

from motionjson import cli
from motionjson.config import (
    ConfigValidationError,
    ExtractionRunConfig,
    ProjectConfig,
    build_extraction_run_config_from_args,
    load_project_config,
    load_run_config,
    write_project_config,
    write_run_config,
)


def parse_extract_args(*args):
    return cli.build_parser().parse_args(["extract", *args])


def test_cli_args_build_typed_config_with_point_prompt_and_round_trip(tmp_path):
    args = parse_extract_args(
        "input.mp4",
        "--out",
        "out/run",
        "--mask-provider",
        "sam2-local",
        "--prompt-point",
        "3,2",
        "--sam2-prompt-frame",
        "4",
        "--sam2-checkpoint",
        "checkpoints/sam2.pt",
        "--sam2-config",
        "configs/sam2.yaml",
        "--sam2-device",
        "cuda:0",
        "--sample-fps",
        "6",
        "--max-frames",
        "12",
        "--output-mode",
        "both",
        "--sprite-format",
        "png",
        "--production-avif",
    )

    config = build_extraction_run_config_from_args(args)
    path = tmp_path / "run_config.json"
    write_run_config(config, path)
    reloaded = load_run_config(path)

    assert reloaded == config
    assert config.input_video.path == "input.mp4"
    assert config.output.directory == "out/run"
    assert config.provider.name == "sam2-local"
    assert config.provider.sam2.checkpoint == "checkpoints/sam2.pt"
    assert config.provider.sam2.model_config == "configs/sam2.yaml"
    assert config.provider.sam2.device == "cuda:0"
    assert config.prompts[0].to_dict() == {
        "kind": "point",
        "frame_index": 4,
        "object_id": "object_0",
        "label": "selected_object",
        "data": {"x": 3, "y": 2},
    }
    assert config.sampling.sample_fps == 6
    assert config.sampling.max_frames == 12
    assert config.export.output_mode == "both"
    assert config.export.sprite_format == "png"
    assert config.export.production_avif is True


def test_mode_alias_and_hosted_sam2_config_preserve_secret_free_provider_settings():
    args = parse_extract_args(
        "input.mp4",
        "--mode",
        "sam2-hosted",
        "--prompt-box",
        "1,2,30,40",
        "--sam2-endpoint-env",
        "CUSTOM_SAM2_URL",
        "--sam2-auth-env",
        "CUSTOM_SAM2_AUTH_ENV",
        "--sam2-hosted-config",
        '{"model":"sam2"}',
    )

    config = build_extraction_run_config_from_args(args)

    assert config.provider.name == "sam2-hosted"
    assert config.provider.sam2.endpoint_env == "CUSTOM_SAM2_URL"
    assert config.provider.sam2.auth_env == "CUSTOM_SAM2_AUTH_ENV"
    assert config.provider.sam2.hosted_config == {"model": "sam2"}
    assert config.provider.sam2.hosted_allow_network is False
    assert config.prompts[0].data == {"x": 1, "y": 2, "w": 30, "h": 40}


def test_multi_object_external_mask_config_preserves_order_labels_and_paths():
    args = parse_extract_args(
        "input.mp4",
        "--object-mask-dir",
        "ball=/tmp/ball_masks",
        "--object-mask-dir",
        "shadow=/tmp/shadow_masks",
        "--object-label",
        "ball=Red ball",
    )

    config = build_extraction_run_config_from_args(args)

    assert [obj.object_id for obj in config.objects] == ["ball", "shadow"]
    assert [obj.label for obj in config.objects] == ["Red ball", "shadow"]
    assert [obj.mask_dir for obj in config.objects] == ["/tmp/ball_masks", "/tmp/shadow_masks"]
    assert [obj.z_index for obj in config.objects] == [10, 20]


def test_discovery_config_round_trips_text_detector_settings(tmp_path):
    args = parse_extract_args(
        "input.mp4",
        "--discovery-provider",
        "text_detector",
        "--discovery-text",
        "red ball . hand",
        "--discovery-config",
        '{"mock":true}',
        "--discovery-max-candidates",
        "2",
    )

    config = build_extraction_run_config_from_args(args)
    path = tmp_path / "run_config.json"
    write_run_config(config, path)
    reloaded = load_run_config(path)

    assert reloaded.discovery.mode == "text_detector"
    assert reloaded.discovery.config == {"mock": True, "text": "red ball . hand", "max_candidates": 2}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"input": {"path": "in.mp4"}, "output": {"directory": "out"}, "provider": {"name": "openrouter"}}, "provider.name"),
        (
            {
                "input": {"path": "in.mp4"},
                "output": {"directory": "out"},
                "export": {"output_mode": "invalid"},
            },
            "export.output_mode",
        ),
        (
            {
                "input": {"path": "in.mp4"},
                "output": {"directory": "out"},
                "prompts": [{"kind": "point", "data": {"x": -1, "y": 2}}],
            },
            "point coordinates",
        ),
        (
            {
                "input": {"path": "in.mp4"},
                "output": {"directory": "out"},
                "prompts": [{"kind": "box", "data": {"x": 1, "y": 2, "w": 0, "h": 4}}],
            },
            "box width",
        ),
        (
            {
                "input": {"path": "in.mp4"},
                "output": {"directory": "out"},
                "provider": {"name": "external"},
            },
            "provider.external.mask_dir",
        ),
        (
            {
                "input": {"path": "in.mp4"},
                "output": {"directory": "out"},
                "provider": {"name": "sam2-local"},
            },
            "requires a point or box prompt",
        ),
        (
            {
                "input": {"path": "in.mp4"},
                "output": {"directory": "out"},
                "discovery": {"mode": "unknown_mode"},
            },
            "discovery.mode",
        ),
        (
            {
                "input": {"path": "in.mp4"},
                "output": {"directory": "out"},
                "discovery": {"mode": "motion_foreground", "config": []},
            },
            "discovery.config",
        ),
    ],
)
def test_run_config_validation_errors_are_field_specific(payload, message):
    payload.setdefault("schema", "motionjson.extraction_run_config.v0.1")

    with pytest.raises(ConfigValidationError, match=message):
        ExtractionRunConfig.from_dict(payload)


def test_project_config_round_trips_embedded_run_configs(tmp_path):
    run = build_extraction_run_config_from_args(parse_extract_args("input.mp4", "--out", "out/project"))
    project = ProjectConfig(name="Demo Project", runs=[run])
    path = tmp_path / "motionjson.project.json"

    write_project_config(project, path)
    reloaded = load_project_config(path)

    assert reloaded == project
    assert reloaded.runs[0].provider.name == "threshold"


def test_run_extract_builds_config_before_existing_pipeline_call(tmp_path, monkeypatch):
    out_dir = tmp_path / "configured"
    args = parse_extract_args(
        "input.mp4",
        "--out",
        str(out_dir),
        "--mask-provider",
        "threshold",
        "--sample-fps",
        "6",
        "--max-frames",
        "2",
        "--output-mode",
        "production",
        "--sprite-format",
        "png",
    )
    captured = {}

    monkeypatch.setattr(cli, "build_provider", lambda _args: object())

    def fake_run_pipeline(**kwargs):
        captured.update(kwargs)
        return {"source": {"sampledFrameCount": 2, "width": 96, "height": 64}, "objects": [{"id": "object_0"}]}

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    cli.run_extract(args)

    assert captured["video_path"] == "input.mp4"
    assert captured["out_dir"] == str(out_dir)
    assert captured["sample_fps"] == 6
    assert captured["max_frames"] == 2
    assert captured["output_mode"] == "production"
    assert captured["sprite_format"] == "png"


def test_run_extract_reports_config_validation_errors_before_provider_build(monkeypatch):
    args = parse_extract_args("input.mp4", "--mask-provider", "sam2-local")
    called = False

    def fail_if_called(_args):
        nonlocal called
        called = True
        raise AssertionError("provider construction should not run for invalid config")

    monkeypatch.setattr(cli, "build_provider", fail_if_called)

    with pytest.raises(SystemExit, match="Invalid extraction config: prompts: sam2-local requires"):
        cli.run_extract(args)

    assert called is False
