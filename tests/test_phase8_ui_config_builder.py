from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from motionjson.config import RUN_CONFIG_SCHEMA
from motionjson.config import ExtractionRunConfig


ROOT = Path(__file__).resolve().parents[1]
CONFIG_BUILDER_JS = ROOT / "src" / "motionjson" / "ui" / "static" / "config_builder.js"


@pytest.fixture(scope="module")
def frontend_contract(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for Phase 8 frontend config builder tests")
    if not CONFIG_BUILDER_JS.exists():
        pytest.skip("Phase 8 frontend config builder module is not available")

    script = tmp_path_factory.mktemp("phase8_frontend") / "contract.mjs"
    script.write_text(
        f"""
import assert from "node:assert/strict";
import {{
  buildRunConfig,
  boxFromPoints,
  clientPointToVideoPoint,
  providerWarnings,
  validateRunConfigShape,
}} from {json.dumps(CONFIG_BUILDER_JS.as_uri())};

const commonAdvanced = {{
  sampleFps: 12,
  maxFrames: 48,
  minArea: 100,
  simplify: 0.006,
  keyframe: 12,
  device: "cpu",
  outputMode: "authoring",
}};

const cases = [
  {{
    goal: "trace_one_object",
    input: {{
      presetId: "trace_one_object",
      video: {{ id: "video_trace" }},
      label: "Red Ball",
      objectId: "red_ball",
      maskProvider: "sam2-local",
      prompts: [
        {{ kind: "positive_point", x: 960, y: 540, frameIndex: 12 }},
        {{ kind: "negative_point", x: 24, y: 36, frameIndex: 12 }},
      ],
      advanced: commonAdvanced,
    }},
    expected: {{ provider: "sam2-local", discovery: "manual_prompt", prompts: 2 }},
  }},
  {{
    goal: "find_objects_from_text",
    input: {{
      presetId: "text_detector",
      video: {{ id: "video_text" }},
      label: "Detected object",
      objectId: "detected_object",
      discoveryText: "red ball . hand",
      discoveryMaxCandidates: 4,
      advanced: commonAdvanced,
    }},
    expected: {{ provider: "sam2-local", discovery: "text_detector", prompts: 0 }},
  }},
  {{
    goal: "find_objects_from_text_hosted_sam3",
    input: {{
      presetId: "text_detector",
      video: {{ id: "video_text_hosted" }},
      label: "Detected object",
      objectId: "detected_object",
      discoveryText: "red ball",
      textDiscoveryProvider: "sam3-hosted",
      hostedSam3ProfileId: "roboflow-sam3-pcs",
      hostedSam3AllowHosted: true,
      advanced: commonAdvanced,
    }},
    expected: {{ provider: "sam2-local", discovery: "sam3_concept", prompts: 0 }},
  }},
  {{
    goal: "find_known_classes",
    input: {{
      presetId: "class_detector",
      video: {{ id: "video_classes" }},
      label: "Known class",
      objectId: "known_class",
      discoveryClasses: "forklift, cart",
      discoveryMaxCandidates: 5,
      classPreset: "vehicles",
      advanced: {{ ...commonAdvanced, boxThreshold: 0.42 }},
    }},
    expected: {{ provider: "sam2-local", discovery: "class_detector", prompts: 0 }},
  }},
  {{
    goal: "propose_all_visible_segments",
    input: {{
      presetId: "sam_auto_masks",
      video: {{ id: "video_auto" }},
      label: "Auto segment",
      objectId: "auto_segment",
      discoveryMaxCandidates: 20,
      advanced: commonAdvanced,
    }},
    expected: {{ provider: "sam2-local", discovery: "sam_auto_masks", prompts: 0 }},
  }},
  {{
    goal: "find_moving_objects",
    input: {{
      presetId: "motion_foreground",
      video: {{ id: "video_motion" }},
      label: "Moving object",
      objectId: "moving_object",
      discoveryMaxCandidates: 6,
      advanced: commonAdvanced,
    }},
    expected: {{ provider: "motion", discovery: "motion_foreground", prompts: 0 }},
  }},
  {{
    goal: "import_external_masks",
    input: {{
      presetId: "external_masks",
      video: {{ id: "video_external" }},
      label: "Imported object",
      objectId: "imported_object",
      advanced: {{ ...commonAdvanced, externalMaskDir: "masks/imported_object" }},
    }},
    expected: {{ provider: "external", discovery: "external_masks", prompts: 0 }},
  }},
];

const configs = cases.map((item) => {{
  const config = buildRunConfig(item.input);
  return {{
    goal: item.goal,
    expected: item.expected,
    shapeErrors: validateRunConfigShape(config),
    config,
  }};
}});

const horizontalPoint = clientPointToVideoPoint({{
  clientX: 510,
  clientY: 420,
  rect: {{ left: 10, top: 20, width: 1000, height: 800 }},
  videoWidth: 1920,
  videoHeight: 1080,
}});
const horizontalOutside = clientPointToVideoPoint({{
  clientX: 510,
  clientY: 70,
  rect: {{ left: 10, top: 20, width: 1000, height: 800 }},
  videoWidth: 1920,
  videoHeight: 1080,
}});
const verticalPoint = clientPointToVideoPoint({{
  clientX: 510,
  clientY: 220,
  rect: {{ left: 10, top: 20, width: 1000, height: 400 }},
  videoWidth: 640,
  videoHeight: 480,
}});
const verticalOutside = clientPointToVideoPoint({{
  clientX: 200,
  clientY: 220,
  rect: {{ left: 10, top: 20, width: 1000, height: 400 }},
  videoWidth: 640,
  videoHeight: 480,
}});
const edgePoint = clientPointToVideoPoint({{
  clientX: 1010,
  clientY: 420,
  rect: {{ left: 10, top: 20, width: 1000, height: 800 }},
  videoWidth: 1920,
  videoHeight: 1080,
}});

assert.equal(horizontalPoint.x, 960);
assert.equal(horizontalPoint.y, 540);
assert.equal(horizontalPoint.insideVideo, true);
assert.equal(horizontalOutside.insideVideo, false);
assert.equal(verticalPoint.x, 320);
assert.equal(verticalPoint.y, 240);
assert.equal(verticalPoint.insideVideo, true);
assert.equal(verticalOutside.insideVideo, false);
assert.equal(edgePoint.x, 1919);
assert.equal(edgePoint.insideVideo, true);

const warningConfig = configs[0].config;
const warnings = providerWarnings(warningConfig, {{
  providers: [
    {{ name: "sam2-local", available: false, reasons: ["CUDA unavailable"] }},
    {{ name: "manual_prompt", available: false, status: "mock disabled" }},
  ],
}});

console.log(JSON.stringify({{
  configs,
  coordinates: {{
    horizontalPoint,
    horizontalOutside,
    verticalPoint,
    verticalOutside,
    edgePoint,
    box: boxFromPoints({{ x: 100, y: 80 }}, {{ x: 20, y: 30 }}),
  }},
  warnings,
}}));
""",
        encoding="utf-8",
    )

    completed = subprocess.run([node, str(script)], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_phase8_frontend_wizard_configs_validate_against_backend(frontend_contract: dict[str, Any]):
    for item in frontend_contract["configs"]:
        config = ExtractionRunConfig.from_dict(item["config"])
        round_tripped = ExtractionRunConfig.from_dict(config.to_dict())

        assert item["shapeErrors"] == [], item["goal"]
        assert round_tripped == config, item["goal"]
        assert config.schema == RUN_CONFIG_SCHEMA
        assert config.provider.name == item["expected"]["provider"]
        assert config.discovery.mode == item["expected"]["discovery"]
        assert len(config.prompts) == item["expected"]["prompts"]


def test_phase8_frontend_config_preserves_native_video_pixel_prompts(frontend_contract: dict[str, Any]):
    trace_config = next(item["config"] for item in frontend_contract["configs"] if item["goal"] == "trace_one_object")
    config = ExtractionRunConfig.from_dict(trace_config)

    assert [prompt.to_dict() for prompt in config.prompts] == [
        {
            "kind": "positive_point",
            "frame_index": 12,
            "object_id": "red_ball",
            "label": "Red Ball",
            "data": {"x": 960, "y": 540},
        },
        {
            "kind": "negative_point",
            "frame_index": 12,
            "object_id": "red_ball",
            "label": "Red Ball",
            "data": {"x": 24, "y": 36},
        },
    ]
    assert config.provider.sam2.prompt_frame == 12


def test_phase8_frontend_config_builds_class_detector_preset(frontend_contract: dict[str, Any]):
    class_config = next(item["config"] for item in frontend_contract["configs"] if item["goal"] == "find_known_classes")

    assert class_config["provider"]["name"] == "sam2-local"
    assert class_config["discovery"]["mode"] == "class_detector"
    assert class_config["discovery"]["config"]["mock"] is False
    assert class_config["discovery"]["config"]["class_preset"] == "vehicles"
    assert class_config["discovery"]["config"]["classes"] == ["forklift", "cart"]
    assert class_config["discovery"]["config"]["confidence_threshold"] == 0.42
    assert class_config["discovery"]["config"]["max_candidates"] == 5


def test_phase8_coordinate_mapper_returns_native_pixels_and_letterbox_status(frontend_contract: dict[str, Any]):
    coordinates = frontend_contract["coordinates"]

    assert coordinates["horizontalPoint"] == {"x": 960, "y": 540, "insideVideo": True}
    assert coordinates["horizontalOutside"]["insideVideo"] is False
    assert coordinates["verticalPoint"] == {"x": 320, "y": 240, "insideVideo": True}
    assert coordinates["verticalOutside"]["insideVideo"] is False
    assert coordinates["edgePoint"] == {"x": 1919, "y": 540, "insideVideo": True}
    assert coordinates["box"] == {"x": 20, "y": 30, "w": 80, "h": 50}


def test_phase8_provider_warnings_surface_unavailable_frontend_choices(frontend_contract: dict[str, Any]):
    assert "sam2-local: CUDA unavailable" in frontend_contract["warnings"]
    assert "manual_prompt: mock disabled" in frontend_contract["warnings"]
