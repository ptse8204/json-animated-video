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


def test_discovery_config_round_trips_class_detector_preset_and_classes(tmp_path):
    args = parse_extract_args(
        "input.mp4",
        "--discovery-provider",
        "class_detector",
        "--discovery-class-preset",
        "vehicles",
        "--discovery-class",
        "forklift",
        "--discovery-config",
        '{"mock":true,"confidence_threshold":0.4}',
        "--discovery-max-candidates",
        "3",
    )

    config = build_extraction_run_config_from_args(args)
    path = tmp_path / "run_config.json"
    write_run_config(config, path)
    reloaded = load_run_config(path)

    assert reloaded.discovery.mode == "class_detector"
    assert reloaded.discovery.config == {
        "mock": True,
        "confidence_threshold": 0.4,
        "classes": ["forklift"],
        "class_preset": "vehicles",
        "max_candidates": 3,
    }


def auto_discovery_payload(config):
    return {
        "schema": "motionjson.extraction_run_config.v0.1",
        "input": {"path": "input.mp4"},
        "output": {"directory": "out/auto"},
        "discovery": {"mode": "auto_object_proposals", "config": config},
    }


def test_auto_object_proposals_clean_preset_defaults_are_low_cost():
    config = ExtractionRunConfig.from_dict(auto_discovery_payload({}))

    discovery = config.discovery.config
    assert discovery["qualityPreset"] == "clean"
    assert discovery["intent"] == "discover_objects_clean"
    assert discovery["providerPreference"] == "auto"
    assert discovery["keyframePolicy"] == "scene_changes"
    assert discovery["maxKeyframes"] == 3
    assert discovery["frameInterval"] is None
    assert discovery["maxCandidatesPerKeyframe"] == 32
    assert discovery["maxObjects"] == 12
    assert discovery["minMaskArea"] == 96
    assert discovery["maxMaskAreaRatio"] == 0.45
    assert discovery["dedupeIou"] == 0.78
    assert discovery["stabilityThreshold"] == 0.86
    assert discovery["trackSelectedOnly"] is True
    assert discovery["requireReview"] is True
    assert discovery["writeRejectedCandidates"] is True


def test_auto_object_proposals_maximum_recall_defaults_are_review_gated():
    config = ExtractionRunConfig.from_dict(
        auto_discovery_payload({"qualityPreset": "maximum_recall"})
    )

    discovery = config.discovery.config
    assert discovery["qualityPreset"] == "maximum_recall"
    assert discovery["maxKeyframes"] == 8
    assert discovery["frameInterval"] == 24
    assert discovery["maxCandidatesPerKeyframe"] == 128
    assert discovery["maxObjects"] == 64
    assert discovery["minMaskArea"] == 32
    assert discovery["maxMaskAreaRatio"] == 0.75
    assert discovery["dedupeIou"] == 0.9
    assert discovery["stabilityThreshold"] == 0.7
    assert discovery["trackSelectedOnly"] is True
    assert discovery["requireReview"] is True
    assert discovery["writeRejectedCandidates"] is True


def test_auto_object_proposals_accepts_snake_case_api_aliases():
    config = ExtractionRunConfig.from_dict(
        auto_discovery_payload(
            {
                "quality_preset": "maximum_recall",
                "max_candidates": 99,
                "max_objects": 32,
                "track_selected_only": True,
                "mock": True,
            }
        )
    )

    discovery = config.discovery.config
    assert discovery["qualityPreset"] == "maximum_recall"
    assert discovery["maxCandidatesPerKeyframe"] == 99
    assert discovery["maxObjects"] == 32
    assert discovery["trackSelectedOnly"] is True
    assert discovery["mock"] is True
    assert "max_candidates" not in discovery


def test_cli_args_build_auto_object_proposals_preset_config():
    args = parse_extract_args(
        "input.mp4",
        "--discovery-provider",
        "auto_object_proposals",
        "--discovery-config",
        '{"quality_preset":"balanced","mock":true}',
        "--discovery-max-candidates",
        "40",
    )

    config = build_extraction_run_config_from_args(args)

    assert config.discovery.mode == "auto_object_proposals"
    assert config.discovery.config["qualityPreset"] == "balanced"
    assert config.discovery.config["maxCandidatesPerKeyframe"] == 40
    assert config.discovery.config["trackSelectedOnly"] is True
    assert config.discovery.config["mock"] is True


def test_trace_everything_requires_explicit_cost_warning_acknowledgement():
    with pytest.raises(ConfigValidationError, match="costWarningAcknowledged"):
        ExtractionRunConfig.from_dict(
            auto_discovery_payload({"qualityPreset": "trace_everything"})
        )

    config = ExtractionRunConfig.from_dict(
        auto_discovery_payload(
            {"qualityPreset": "trace_everything", "costWarningAcknowledged": True}
        )
    )

    discovery = config.discovery.config
    assert discovery["qualityPreset"] == "trace_everything"
    assert discovery["requireExplicitCostWarning"] is True
    assert discovery["costWarningAcknowledged"] is True
    assert discovery["trackSelectedOnly"] is False
    assert discovery["trackTopCandidates"] is True
    assert discovery["requireReview"] is True


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"requireReview": False}, "requireReview"),
        ({"writeRejectedCandidates": False}, "writeRejectedCandidates"),
    ],
)
def test_trace_everything_forces_review_and_rejected_candidate_records(config, message):
    with pytest.raises(ConfigValidationError, match=message):
        ExtractionRunConfig.from_dict(
            auto_discovery_payload(
                {
                    "qualityPreset": "trace_everything",
                    "costWarningAcknowledged": True,
                    **config,
                }
            )
        )


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"maxCandidatesPerKeyframe": 0}, "maxCandidatesPerKeyframe"),
        ({"maxCandidatesPerKeyframe": 999}, "maxCandidatesPerKeyframe"),
        ({"maxObjects": 0}, "maxObjects"),
        ({"maxObjects": 999}, "maxObjects"),
        ({"maxKeyframes": 99}, "maxKeyframes"),
        ({"frameInterval": 9999}, "frameInterval"),
        ({"maxMaskAreaRatio": 1.5}, "maxMaskAreaRatio"),
        ({"stabilityThreshold": -0.1}, "stabilityThreshold"),
        ({"providerPreference": "openrouter"}, "providerPreference"),
    ],
)
def test_auto_object_proposals_invalid_caps_fail_clearly(config, message):
    with pytest.raises(ConfigValidationError, match=message):
        ExtractionRunConfig.from_dict(auto_discovery_payload(config))


@pytest.mark.parametrize("quality_preset", ["clean", "balanced", "maximum_recall"])
def test_auto_object_proposals_selected_only_defaults_true_for_non_expert_presets(quality_preset):
    config = ExtractionRunConfig.from_dict(
        auto_discovery_payload({"qualityPreset": quality_preset})
    )

    assert config.discovery.config["trackSelectedOnly"] is True


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
