from __future__ import annotations

from typing import Any, Mapping

from motionjson.providers.sam2 import SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
from motionjson.providers.sam3 import SAM3_HF_REPO_ID


MODEL_SETUP_RECOMMENDATION_FORMAT = "motionjson.model_setup_recommendation.v0.1"


def _providers(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(provider.get("name") or ""): dict(provider)
        for provider in report.get("providers") or []
        if isinstance(provider, Mapping)
    }


def _runtime_environment(report: Mapping[str, Any]) -> dict[str, Any]:
    environment = report.get("environment") if isinstance(report.get("environment"), Mapping) else {}
    runtime = environment.get("runtimeEnvironment") if isinstance(environment.get("runtimeEnvironment"), Mapping) else {}
    profile = environment.get("profile") if isinstance(environment.get("profile"), Mapping) else {}
    if runtime:
        return dict(runtime)
    return {
        "format": "motionjson.runtime_environment.v0.2",
        "host": profile.get("host") or "runtime",
        "system": profile.get("system") or "",
        "machine": profile.get("machine") or "",
        "classification": profile.get("classification") or "unknown",
        "confidence": "low",
        "hardware": {"accelerators": []},
        "runtime": {
            "python": profile.get("python") or "",
            "torchInstalled": bool(profile.get("torchInstalled")),
            "torchVersion": profile.get("torchVersion"),
            "torchCudaBuild": None,
            "cudaAvailable": bool(profile.get("cudaAvailable")),
            "mpsAvailable": bool(profile.get("mpsAvailable")),
            "xpuAvailable": False,
            "hipVersion": None,
        },
        "reasonCodes": [],
        "messages": [profile.get("summary") or ""],
        "recommendedFixes": [],
    }


def _first_accelerator_label(runtime: Mapping[str, Any]) -> str:
    accelerators = runtime.get("hardware", {}).get("accelerators", []) if isinstance(runtime.get("hardware"), Mapping) else []
    for accelerator in accelerators:
        if not isinstance(accelerator, Mapping):
            continue
        if str(accelerator.get("kind") or "") == "cpu":
            continue
        return str(accelerator.get("name") or accelerator.get("kind") or "Accelerator detected")
    return "CPU"


def _provider_status(provider: Mapping[str, Any] | None) -> str:
    if not provider:
        return "not_configured"
    return str(provider.get("status") or "not_configured")


def _provider_ready(provider: Mapping[str, Any] | None) -> bool:
    return bool(provider and (provider.get("runnable") is True or _provider_status(provider) == "ready"))


def _provider_runtime_configured(provider: Mapping[str, Any] | None) -> bool:
    return bool(provider and (provider.get("configured") is True or provider.get("installed") is True or _provider_status(provider) == "ready"))


def _metadata(provider: Mapping[str, Any] | None) -> dict[str, Any]:
    value = provider.get("metadata") if provider else {}
    return dict(value) if isinstance(value, Mapping) else {}


def _runtime_proof(provider: Mapping[str, Any] | None) -> dict[str, Any]:
    metadata = _metadata(provider)
    proof = metadata.get("runtimeProof")
    return dict(proof) if isinstance(proof, Mapping) else {}


def _runtime_badges(
    *,
    runtime: Mapping[str, Any],
    provider: Mapping[str, Any] | None,
    model_label: str,
    no_model: bool = False,
) -> list[dict[str, str]]:
    classification = str(runtime.get("classification") or "unknown")
    proof = _runtime_proof(provider)
    model = proof.get("model") if isinstance(proof.get("model"), Mapping) else {}
    model_cached = bool(model.get("cached"))
    model_cache_required = bool(model.get("cacheRequired"))
    proof_required = bool(proof.get("proofRequired"))
    proof_allows = bool(proof.get("allowsRun"))
    hardware_ok = classification not in {"unknown"}
    runtime_ok = classification.endswith("_ready") or no_model
    if classification.endswith("_hardware_runtime_missing"):
        runtime_status = "missing"
    elif classification == "unknown":
        runtime_status = "warn"
    else:
        runtime_status = "ok" if runtime_ok else "warn"
    return [
        {
            "id": "hardware",
            "label": _first_accelerator_label(runtime),
            "status": "ok" if hardware_ok else "warn",
        },
        {
            "id": "runtime",
            "label": _runtime_label(classification),
            "status": runtime_status,
        },
        {
            "id": "model",
            "label": "No model required" if no_model else model_label,
            "status": "ok" if no_model or not model_cache_required or model_cached else "missing",
        },
        {
            "id": "proof",
            "label": "Proof not required" if no_model or not proof_required else proof.get("message") or "Runtime proof required",
            "status": "ok" if no_model or not proof_required or proof_allows else "missing",
        },
    ]


def _runtime_label(classification: str) -> str:
    labels = {
        "cuda_ready": "PyTorch CUDA ready",
        "cuda_hardware_runtime_missing": "PyTorch CUDA not ready",
        "mps_ready": "PyTorch MPS ready",
        "mps_hardware_runtime_missing": "PyTorch MPS not ready",
        "xpu_ready": "PyTorch XPU ready",
        "xpu_hardware_runtime_missing": "PyTorch XPU not ready",
        "rocm_ready": "PyTorch ROCm ready",
        "rocm_hardware_runtime_missing": "PyTorch ROCm not ready",
        "cpu_only": "CPU-only runtime",
        "unknown": "Runtime unknown",
    }
    return labels.get(classification, classification.replace("_", " ") or "Runtime unknown")


def _action(action_id: str, label: str) -> dict[str, str]:
    return {"id": action_id, "label": label}


def _no_model_alternative(status: str = "ready") -> dict[str, str]:
    return {
        "connectionId": "no_model_cpu_workflow",
        "label": "No-model CPU smoke run",
        "status": status,
        "cost": "zero_local",
    }


def _required_input(key: str, label: str, input_type: str = "text", required: bool = True, when: str = "") -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": input_type,
        "required": required,
        "when": when,
    }


def _base_recommendation(
    *,
    goal: str,
    selected_connection_id: str,
    selected_provider_id: str,
    selected_capability_id: str,
    title: str,
    subtitle: str,
    status: str,
    primary_action: dict[str, str],
    runtime_badges: list[dict[str, str]],
    why_this: str,
    run_config_mapping: dict[str, str],
    requires_model_setup: bool = True,
    required_inputs: list[dict[str, Any]] | None = None,
    optional_inputs: list[dict[str, Any]] | None = None,
    advanced_inputs: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    alternatives: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "format": MODEL_SETUP_RECOMMENDATION_FORMAT,
        "goal": goal,
        "requiresModelSetup": requires_model_setup,
        "selectedConnectionId": selected_connection_id,
        "selectedProviderId": selected_provider_id,
        "selectedCapabilityId": selected_capability_id,
        "title": title,
        "subtitle": subtitle,
        "status": status,
        "primaryAction": primary_action,
        "requiredInputs": list(required_inputs or []),
        "optionalInputs": list(optional_inputs or []),
        "advancedInputs": list(advanced_inputs or []),
        "runtimeBadges": runtime_badges,
        "whyThis": why_this,
        "warnings": list(warnings or []),
        "alternatives": list(alternatives or []),
        "runConfigMapping": dict(run_config_mapping),
    }


def _no_model_recommendation(goal: str, runtime: Mapping[str, Any], *, why: str = "") -> dict[str, Any]:
    discovery_mode = {
        "motion_foreground": "motion_foreground",
        "external_masks": "external_masks",
        "review_existing": "manual_prompt",
        "trace_one_object": "manual_prompt",
        "text_detector": "text_detector",
    }.get(goal, "auto_object_proposals")
    provider_name = {
        "motion_foreground": "motion",
        "external_masks": "external",
        "review_existing": "mock",
        "trace_one_object": "mock",
        "text_detector": "mock",
    }.get(goal, "mock")
    title = "No-model CPU workflow"
    return _base_recommendation(
        goal=goal,
        requires_model_setup=goal not in {"motion_foreground", "external_masks", "review_existing"},
        selected_connection_id="no_model_cpu_workflow",
        selected_provider_id="mock",
        selected_capability_id=provider_name,
        title=title,
        subtitle="Safe local workflow with no model paths or hosted calls.",
        status="fallback_ready",
        primary_action=_action("continue", "Run local smoke now"),
        runtime_badges=_runtime_badges(runtime=runtime, provider=None, model_label="", no_model=True),
        why_this=why or "This workflow can run locally without model setup, GPU runtime, credentials, or network access.",
        warnings=[],
        alternatives=[],
        run_config_mapping={"providerName": provider_name, "discoveryMode": discovery_mode},
    )


def _sam3_status_for_trace_all(provider: Mapping[str, Any] | None, classification: str) -> tuple[str, dict[str, str]]:
    if classification == "cuda_hardware_runtime_missing":
        return "needs_install", _action("install", "Install runtime")
    status = _provider_status(provider)
    proof = _runtime_proof(provider)
    if not provider or status in {"missing_dependency", "not_configured", "available_cpu_only", "unsupported_runtime"}:
        return "needs_install", _action("install", "Install runtime")
    if status == "missing_model":
        return "needs_model", _action("cache_model", "Cache/download model")
    if proof.get("proofRequired") is True and proof.get("allowsRun") is not True:
        return "needs_smoke", _action("run_smoke", "Run proof")
    if status == "runtime_proof_required":
        return "needs_smoke", _action("run_smoke", "Run proof")
    if _provider_ready(provider):
        return "ready", _action("continue", "Continue to run")
    return "needs_install", _action("install", "Install runtime")


def _sam2_hf_status(provider: Mapping[str, Any] | None) -> tuple[str, dict[str, str]]:
    status = _provider_status(provider)
    proof = _runtime_proof(provider)
    if not provider or status in {"missing_dependency", "not_configured", "unsupported_runtime"}:
        return "needs_install", _action("install", "Install runtime")
    if status == "missing_model":
        return "needs_model", _action("cache_model", "Cache/download model")
    if proof.get("proofRequired") is True and proof.get("allowsRun") is not True:
        return "needs_smoke", _action("run_smoke", "Run proof")
    if status == "runtime_proof_required":
        return "needs_smoke", _action("run_smoke", "Run proof")
    if _provider_ready(provider):
        return "ready", _action("continue", "Continue to run")
    return "needs_install", _action("install", "Install runtime")


def _trace_all_recommendation(goal: str, report: Mapping[str, Any]) -> dict[str, Any]:
    providers = _providers(report)
    runtime = _runtime_environment(report)
    classification = str(runtime.get("classification") or "unknown")
    sam3 = providers.get("sam3-auto-masks")
    sam2_hf = providers.get("sam2-hf-auto-masks")
    if classification in {"cuda_ready", "cuda_hardware_runtime_missing"}:
        status, primary_action = _sam3_status_for_trace_all(sam3, classification)
        why = (
            "GPU detected, but the Python runtime is not ready for CUDA. SAM3 Scene Sweep remains the recommended setup path after installing CUDA-enabled PyTorch."
            if classification == "cuda_hardware_runtime_missing"
            else "CUDA is ready, so SAM3 Scene Sweep is the best local path for scene-wide object discovery."
        )
        return _base_recommendation(
            goal=goal,
            selected_connection_id="sam3-local",
            selected_provider_id="sam3-local",
            selected_capability_id="sam3-auto-masks",
            title="SAM3 Scene Sweep",
            subtitle="Best local path for scene-wide object discovery on CUDA.",
            status=status,
            primary_action=primary_action,
            runtime_badges=_runtime_badges(runtime=runtime, provider=sam3, model_label=SAM3_HF_REPO_ID),
            why_this=why,
            warnings=[] if status != "needs_install" else ["CUDA hardware is present, but this Python runtime cannot use it yet."],
            alternatives=[_no_model_alternative()],
            run_config_mapping={"providerName": "sam3-local", "discoveryMode": "sam3_auto_masks"},
            optional_inputs=[_required_input("hf_token", "Hugging Face token", "secret", False, "model access is gated")],
        )
    if classification == "mps_ready" and _provider_runtime_configured(sam2_hf):
        status, primary_action = _sam2_hf_status(sam2_hf)
        return _base_recommendation(
            goal=goal,
            selected_connection_id="sam2-hf-auto-masks",
            selected_provider_id="sam2-hf-auto-masks",
            selected_capability_id="sam2-hf-auto-masks",
            title="SAM2 HF automatic masks",
            subtitle="Apple Silicon fallback for scene proposals.",
            status=status,
            primary_action=primary_action,
            runtime_badges=_runtime_badges(runtime=runtime, provider=sam2_hf, model_label=SAM2_HF_AUTO_MASKS_DEFAULT_MODEL),
            why_this="Apple MPS is available; use the SAM2 HF fallback unless you move this project to a CUDA runtime.",
            alternatives=[_no_model_alternative()],
            run_config_mapping={"providerName": "sam2-hf-auto-masks", "discoveryMode": "sam2_hf_auto_masks"},
        )
    return _no_model_recommendation(
        goal,
        runtime,
        why=(
            "CPU-only runtime detected. Use the no-model local workflow now, then switch to SAM3 Scene Sweep on a CUDA runtime for full scene discovery."
            if classification == "cpu_only"
            else "This runtime is not a CUDA-ready SAM3 path. Use the safe no-model workflow now or configure a supported local/hosted provider explicitly."
        ),
    )


def _trace_one_recommendation(goal: str, report: Mapping[str, Any]) -> dict[str, Any]:
    providers = _providers(report)
    runtime = _runtime_environment(report)
    sam2 = providers.get("sam2-local")
    if sam2 and _provider_ready(sam2):
        return _base_recommendation(
            goal=goal,
            selected_connection_id="sam2-local",
            selected_provider_id="sam2-local",
            selected_capability_id="sam2-local",
            title="SAM2 prompt tracking",
            subtitle="Best local path for cutting out one prompted object.",
            status="ready",
            primary_action=_action("continue", "Continue to run"),
            required_inputs=[],
            runtime_badges=_runtime_badges(runtime=runtime, provider=sam2, model_label="SAM2 checkpoint/config"),
            why_this="SAM2 local is configured enough to run prompt-based object tracking.",
            alternatives=[_no_model_alternative()],
            run_config_mapping={"providerName": "sam2-local", "discoveryMode": "manual_prompt"},
        )
    return _no_model_recommendation(
        goal,
        runtime,
        why="Local SAM2 is not configured enough to run. Start with a no-model local smoke path without entering checkpoint or config paths.",
    )


def _text_detector_recommendation(goal: str, report: Mapping[str, Any], *, mock_mode: bool = False) -> dict[str, Any]:
    providers = _providers(report)
    runtime = _runtime_environment(report)
    hosted = providers.get("sam3-hosted")
    hosted_status = _provider_status(hosted)
    hosted_metadata = _metadata(hosted)
    network_opt_in = bool(hosted_metadata.get("networkOptIn"))
    hosted_configured = bool(hosted and hosted.get("configured"))
    if hosted and _provider_ready(hosted) and network_opt_in:
        return _base_recommendation(
            goal=goal,
            selected_connection_id="sam3-hosted:roboflow-sam3-pcs",
            selected_provider_id="sam3-hosted",
            selected_capability_id="sam3-hosted",
            title="Hosted SAM3 text discovery",
            subtitle="Text prompts through an explicitly enabled hosted provider.",
            status="ready",
            primary_action=_action("continue", "Continue to run"),
            runtime_badges=_runtime_badges(runtime=runtime, provider=hosted, model_label="Hosted SAM3"),
            why_this="Hosted SAM3 credentials and cost/privacy opt-in are already configured.",
            warnings=["Hosted calls can send frames off-device and may cost money."],
            run_config_mapping={"providerName": "sam3-hosted", "discoveryMode": "sam3_concept"},
        )
    if hosted_configured and not network_opt_in:
        return _base_recommendation(
            goal=goal,
            selected_connection_id="sam3-hosted:roboflow-sam3-pcs",
            selected_provider_id="sam3-hosted",
            selected_capability_id="sam3-hosted",
            title="Hosted SAM3 text discovery",
            subtitle="Confirm hosted use before text-guided discovery.",
            status="needs_hosted_opt_in",
            primary_action=_action("confirm_hosted", "Confirm hosted use"),
            required_inputs=[_required_input("allow_hosted", "Hosted cost/privacy confirmation", "checkbox", True, "hosted provider is selected")],
            runtime_badges=_runtime_badges(runtime=runtime, provider=hosted, model_label="Hosted SAM3"),
            why_this="Credentials are present, but hosted calls remain disabled until you confirm cost and privacy.",
            warnings=["Hosted calls are opt-in only."],
            alternatives=[_no_model_alternative("ready")],
            run_config_mapping={"providerName": "sam3-hosted", "discoveryMode": "sam3_concept"},
        )
    if hosted_status in {"missing_key", "not_configured"} and not mock_mode:
        return _no_model_recommendation(
            goal,
            runtime,
            why="Text-guided hosted setup is hidden until credentials and hosted opt-in are explicit. Local text detectors remain hidden while unimplemented.",
        )
    return _no_model_recommendation(
        goal,
        runtime,
        why="Use a mock/no-model text smoke path for UI testing; hosted text discovery remains opt-in.",
    )


def model_setup_recommendation_for_goal(
    goal: str,
    *,
    capability_report: Mapping[str, Any],
    mock_mode: bool = False,
) -> dict[str, Any]:
    normalized_goal = str(goal or "trace_one_object").strip() or "trace_one_object"
    runtime = _runtime_environment(capability_report)
    if normalized_goal in {"motion_foreground", "external_masks", "review_existing"}:
        recommendation = _no_model_recommendation(
            normalized_goal,
            runtime,
            why="No model setup is required for this workflow.",
        )
        recommendation["requiresModelSetup"] = False
        recommendation["status"] = "ready"
        recommendation["primaryAction"] = _action("continue", "Continue to run")
        return recommendation
    if normalized_goal in {"trace_all_objects", "auto_object_proposals"}:
        return _trace_all_recommendation(normalized_goal, capability_report)
    if normalized_goal == "text_detector":
        return _text_detector_recommendation(normalized_goal, capability_report, mock_mode=mock_mode)
    return _trace_one_recommendation(normalized_goal, capability_report)
