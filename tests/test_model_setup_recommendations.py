from __future__ import annotations

from motionjson.model_setup_recommendations import model_setup_recommendation_for_goal


def provider(name: str, **overrides):
    base = {
        "name": name,
        "status": "not_configured",
        "available": False,
        "configured": False,
        "installed": False,
        "runnable": False,
        "reasons": [],
        "metadata": {},
    }
    base.update(overrides)
    return base


def runtime(classification: str):
    accelerator = {
        "cuda_ready": {"kind": "nvidia_cuda", "name": "NVIDIA L4", "visibleToTorch": True},
        "cuda_hardware_runtime_missing": {"kind": "nvidia_cuda", "name": "NVIDIA T4", "visibleToTorch": False},
        "mps_ready": {"kind": "apple_mps", "name": "Apple Silicon GPU", "visibleToTorch": True},
    }.get(classification, {"kind": "cpu", "name": "CPU", "visibleToTorch": True})
    return {
        "format": "motionjson.runtime_environment.v0.2",
        "host": "runtime",
        "system": "Linux",
        "machine": "x86_64",
        "classification": classification,
        "confidence": "high",
        "hardware": {
            "accelerators": [
                {
                    "kind": accelerator["kind"],
                    "hardwareDetected": True,
                    "visibleToTorch": accelerator["visibleToTorch"],
                    "name": accelerator["name"],
                    "memoryMb": 15360 if "cuda" in accelerator["kind"] else None,
                    "driver": "550.54" if "cuda" in accelerator["kind"] else None,
                    "source": "test",
                }
            ]
        },
        "runtime": {
            "python": "3.13",
            "torchInstalled": classification != "cuda_hardware_runtime_missing",
            "torchVersion": "2.test",
            "torchCudaBuild": "12.4" if classification == "cuda_ready" else None,
            "cudaAvailable": classification == "cuda_ready",
            "mpsAvailable": classification == "mps_ready",
            "xpuAvailable": False,
            "hipVersion": None,
        },
        "reasonCodes": [classification],
        "messages": [],
        "recommendedFixes": [],
    }


def proof(status: str, *, cached: bool = True, allows_run: bool = False):
    return {
        "format": "motionjson.runtime_proof.v0.1",
        "proofRequired": True,
        "proofStatus": status,
        "runtimeProofStatus": status,
        "allowsRun": allows_run,
        "message": "Run proof before extraction.",
        "model": {
            "cacheRequired": True,
            "cacheStatus": "cached" if cached else "not_cached",
            "cached": cached,
            "id": "facebook/sam3",
        },
    }


def report(classification: str, *providers):
    provider_map = {item["name"]: item for item in providers}
    defaults = {
        "mock": provider("mock", status="ready", available=True, configured=True, installed=True, runnable=True),
        "motion": provider("motion", status="ready", available=True, configured=True, installed=True, runnable=True),
        "external": provider("external", status="ready", available=True, configured=True, installed=True, runnable=True),
        "sam2-local": provider("sam2-local", reasons=["SAM2 paths missing"]),
        "sam2-hf-auto-masks": provider("sam2-hf-auto-masks", reasons=["SAM2 HF runtime is missing."]),
        "sam3-auto-masks": provider("sam3-auto-masks", status="missing_dependency", reasons=["SAM3 Tracker classes are missing."]),
        "sam3-hosted": provider("sam3-hosted", status="missing_key", reasons=["ROBOFLOW_API_KEY is not set."]),
        "text_detector": provider("text_detector", status="missing_dependency", reasons=["Local detector is not importable."]),
    }
    defaults.update(provider_map)
    return {
        "schema": "motionjson.provider_diagnostics.v0.1",
        "environment": {"runtimeEnvironment": runtime(classification)},
        "providers": list(defaults.values()),
        "summary": {},
    }


def test_trace_all_cuda_hardware_torch_missing_keeps_sam3_setup_path():
    recommendation = model_setup_recommendation_for_goal(
        "trace_all_objects",
        capability_report=report("cuda_hardware_runtime_missing"),
    )

    assert recommendation["status"] == "needs_input"
    assert recommendation["selectedConnectionId"] == "sam3-local"
    assert recommendation["primaryAction"]["id"] == "save_and_auto_setup"
    assert recommendation["primaryAction"]["label"] == "Set up SAM3 Scene Sweep"
    assert {item["key"] for item in recommendation["requiredInputs"]} == {"hf_token"}
    assert recommendation["alternatives"][0]["connectionId"] == "no_model_cpu_workflow"
    assert "GPU detected" in recommendation["whyThis"]
    assert "runtime" in recommendation["whyThis"]


def test_trace_all_cuda_ready_proof_missing_maps_to_one_setup_action():
    recommendation = model_setup_recommendation_for_goal(
        "trace_all_objects",
        capability_report=report(
            "cuda_ready",
            provider(
                "sam3-auto-masks",
                status="runtime_proof_required",
                available=True,
                configured=True,
                installed=True,
                runnable=False,
                metadata={"runtimeProof": proof("missing")},
            ),
        ),
    )

    assert recommendation["status"] == "needs_setup"
    assert recommendation["selectedConnectionId"] == "sam3-local"
    assert recommendation["primaryAction"]["id"] == "auto_setup"
    assert recommendation["primaryAction"]["label"] == "Set up SAM3 Scene Sweep"


def test_trace_all_cuda_ready_missing_hf_token_requests_input_before_setup():
    recommendation = model_setup_recommendation_for_goal(
        "trace_all_objects",
        capability_report=report(
            "cuda_ready",
            provider(
                "sam3-auto-masks",
                status="runtime_proof_required",
                available=True,
                configured=True,
                installed=True,
                runnable=False,
                metadata={
                    "runtimeProof": proof("missing_cache", cached=False),
                    "trackerModel": {"valueKind": "huggingface_repo_id"},
                },
            ),
            provider(
                "sam3-local",
                status="ready",
                available=True,
                configured=True,
                installed=True,
                runnable=False,
                metadata={"hfTokenConfigured": False},
            ),
        ),
    )

    assert recommendation["status"] == "needs_input"
    assert recommendation["selectedConnectionId"] == "sam3-local"
    assert recommendation["primaryAction"]["id"] == "save_and_auto_setup"
    assert recommendation["primaryAction"]["label"] == "Set up SAM3 Scene Sweep"
    assert {item["key"] for item in recommendation["requiredInputs"]} == {"hf_token"}


def test_trace_all_cpu_only_recommends_no_model_cpu_workflow():
    recommendation = model_setup_recommendation_for_goal(
        "trace_all_objects",
        capability_report=report("cpu_only"),
    )

    assert recommendation["status"] == "fallback_ready"
    assert recommendation["selectedConnectionId"] == "no_model_cpu_workflow"
    assert recommendation["primaryAction"]["id"] == "use_fallback"
    assert recommendation["primaryAction"]["label"] == "Use CPU fallback now"


def test_pick_objects_from_frame_reuses_scene_sweep_setup_path():
    recommendation = model_setup_recommendation_for_goal(
        "pick_objects_from_frame",
        capability_report=report("cuda_ready"),
    )

    assert recommendation["selectedConnectionId"] == "sam3-local"
    assert recommendation["title"] == "Pick objects from one frame"
    assert recommendation["runConfigMapping"]["providerName"] == "sam3-local"
    assert recommendation["runConfigMapping"]["discoveryMode"] == "sam3_auto_masks"


def test_trace_all_mps_ready_does_not_recommend_sam3_primary_when_hf_fallback_missing():
    recommendation = model_setup_recommendation_for_goal(
        "trace_all_objects",
        capability_report=report("mps_ready"),
    )

    assert recommendation["selectedConnectionId"] == "no_model_cpu_workflow"
    assert recommendation["selectedConnectionId"] != "sam3-local"


def test_trace_one_sam2_missing_uses_no_model_without_sam2_path_inputs():
    recommendation = model_setup_recommendation_for_goal(
        "trace_one_object",
        capability_report=report("cpu_only"),
    )

    assert recommendation["selectedConnectionId"] == "no_model_cpu_workflow"
    keys = {item["key"] for item in recommendation["requiredInputs"]}
    assert "sam2_checkpoint_path" not in keys
    assert "sam2_model_config_path" not in keys


def test_trace_one_sam2_configured_recommends_sam2_local():
    recommendation = model_setup_recommendation_for_goal(
        "trace_one_object",
        capability_report=report(
            "cpu_only",
            provider("sam2-local", status="ready", available=True, configured=True, installed=True, runnable=True),
        ),
    )

    assert recommendation["selectedConnectionId"] == "sam2-local"
    assert recommendation["status"] == "ready"
    assert recommendation["requiredInputs"] == []


def test_trace_one_sam2_runtime_missing_paths_requests_only_paths():
    recommendation = model_setup_recommendation_for_goal(
        "trace_one_object",
        capability_report=report(
            "cpu_only",
            provider(
                "sam2-local",
                status="not_configured",
                available=False,
                configured=False,
                installed=True,
                runnable=False,
                metadata={
                    "checkpoint": {"configured": False, "exists": False},
                    "modelConfig": {"configured": False, "exists": False},
                },
            ),
        ),
    )

    assert recommendation["selectedConnectionId"] == "sam2-local"
    assert recommendation["status"] == "needs_input"
    assert recommendation["primaryAction"]["id"] == "save_and_auto_setup"
    assert {item["key"] for item in recommendation["requiredInputs"]} == {
        "sam2_checkpoint_path",
        "sam2_model_config_path",
    }


def test_text_detector_missing_hosted_fields_returns_hosted_setup_inputs():
    recommendation = model_setup_recommendation_for_goal(
        "text_detector",
        capability_report=report(
            "cpu_only",
            provider(
                "sam3-hosted",
                status="not_configured",
                available=False,
                configured=False,
                installed=True,
                runnable=False,
                metadata={
                    "authEnv": {"configured": False},
                    "endpointEnv": {"required": False, "configured": False},
                    "networkOptIn": False,
                },
            ),
        ),
    )

    assert recommendation["selectedConnectionId"] == "sam3-hosted:roboflow-sam3-pcs"
    assert recommendation["status"] == "needs_input"
    assert recommendation["primaryAction"]["id"] == "save_and_auto_setup"
    assert {item["key"] for item in recommendation["requiredInputs"]} == {"api_key", "allow_hosted"}


def test_motion_foreground_no_model_required():
    recommendation = model_setup_recommendation_for_goal(
        "motion_foreground",
        capability_report=report("cpu_only"),
    )

    assert recommendation["requiresModelSetup"] is False
    assert recommendation["selectedConnectionId"] == "no_model_cpu_workflow"
    assert recommendation["status"] == "ready"
