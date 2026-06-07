from __future__ import annotations

import copy
from typing import Any, Mapping

from motionjson.providers.sam2 import SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
from motionjson.providers.sam3 import SAM3_HF_REPO_ID


PROVIDER_WORKFLOW_REGISTRY_FORMAT = "motionjson.provider_workflow_registry.v0.1"

WORKFLOW_IDS = (
    "no_model_cpu",
    "trace_one_object",
    "trace_all_objects",
    "auto_object_proposals",
    "find_objects_from_text",
    "find_moving_things",
    "import_masks",
    "review_existing_result",
)

_REJECTED_SEGMENTATION_ALIASES = {
    "hosted",
    "llm",
    "openai",
    "openai-planner",
    "openrouter",
    "openrouter-planner",
    "replicate",
    "runpod",
    "sam2",
    "vlm",
}

_HOSTED_PROFILE_ALIASES: dict[str, tuple[str, str]] = {
    "replicate-sam2-video": ("sam2-hosted", "replicate-sam2-video"),
    "sam2-hosted:replicate-sam2-video": ("sam2-hosted", "replicate-sam2-video"),
    "custom-sam2-compatible": ("sam2-hosted", "custom-sam2-compatible"),
    "sam2-hosted:custom-sam2-compatible": ("sam2-hosted", "custom-sam2-compatible"),
    "roboflow-sam3-pcs": ("sam3-hosted", "roboflow-sam3-pcs"),
    "sam3-hosted:roboflow-sam3-pcs": ("sam3-hosted", "roboflow-sam3-pcs"),
    "fal-sam3-image": ("sam3-hosted", "fal-sam3-image"),
    "sam3-hosted:fal-sam3-image": ("sam3-hosted", "fal-sam3-image"),
    "custom-sam3-compatible": ("sam3-hosted", "custom-sam3-compatible"),
    "sam3-hosted:custom-sam3-compatible": ("sam3-hosted", "custom-sam3-compatible"),
}


def _workflow_support(
    supported: bool | str,
    *,
    prompt_types: list[str] | None = None,
    requires_model_path: bool = False,
    requires_credentials: bool = False,
    requires_hosted_opt_in: bool = False,
    requires_runtime_proof: bool = False,
    run_config_provider_name: str = "",
    run_config_discovery_mode: str = "",
    validation_policy: str = "allow_when_runnable",
    fallbacks: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "supported": supported,
        "promptTypes": list(prompt_types or []),
        "requiresModelPath": requires_model_path,
        "requiresCredentials": requires_credentials,
        "requiresHostedOptIn": requires_hosted_opt_in,
        "requiresRuntimeProof": requires_runtime_proof,
        "runConfigProviderName": run_config_provider_name,
        "runConfigDiscoveryMode": run_config_discovery_mode,
        "validationPolicy": validation_policy,
        "fallbacks": list(fallbacks or []),
    }


def _unsupported() -> dict[str, Any]:
    return _workflow_support(False, validation_policy="unsupported")


def _support_map(**overrides: dict[str, Any]) -> dict[str, dict[str, Any]]:
    support = {workflow_id: _unsupported() for workflow_id in WORKFLOW_IDS}
    support.update(overrides)
    return support


def _entry(
    provider_id: str,
    *,
    capability_id: str | None = None,
    connection_id: str | None = None,
    aliases: list[str] | None = None,
    label: str,
    description: str,
    kind: str,
    locality: str,
    implemented: bool,
    worker_eligible: bool = False,
    settings_provider_id: str | None = None,
    credential_fields: list[dict[str, Any]] | None = None,
    endpoint_fields: list[dict[str, Any]] | None = None,
    local_config_fields: list[dict[str, Any]] | None = None,
    model_options: list[dict[str, Any]] | None = None,
    default_model: str | None = None,
    optional_extra: str | None = None,
    setup_actions: list[str] | None = None,
    runtime_proof_required: bool = False,
    expected_capability_names: list[str] | None = None,
    remediation: str = "",
    validation_policy: str = "allow_when_runnable",
    workflow_support: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "providerId": provider_id,
        "capabilityId": capability_id or provider_id,
        "connectionId": connection_id or provider_id,
        "aliases": list(aliases or []),
        "label": label,
        "description": description,
        "kind": kind,
        "locality": locality,
        "implemented": implemented,
        "workerEligible": worker_eligible,
        "settingsProviderId": settings_provider_id or provider_id,
        "credentialFields": list(credential_fields or []),
        "endpointFields": list(endpoint_fields or []),
        "localConfigFields": list(local_config_fields or []),
        "modelOptions": list(model_options or []),
        "defaultModel": default_model,
        "optionalExtra": optional_extra,
        "setupActions": list(setup_actions or []),
        "runtimeProofRequired": runtime_proof_required,
        "expectedCapabilityNames": list(expected_capability_names or [capability_id or provider_id]),
        "remediation": remediation,
        "validationPolicy": validation_policy,
        "workflowSupport": workflow_support or _support_map(),
    }


_PROVIDER_REGISTRY: list[dict[str, Any]] = [
    _entry(
        "mock",
        aliases=["debug_mock", "mock-no-model"],
        label="Mock no-model",
        description="Deterministic local provider for first-run smoke checks and UI tests.",
        kind="mask_provider",
        locality="local",
        implemented=True,
        worker_eligible=True,
        model_options=[{"id": "mock/no-model", "label": "Mock no-model"}],
        default_model="mock/no-model",
        remediation="Use this when a machine has no ML runtime configured.",
        workflow_support=_support_map(
            no_model_cpu=_workflow_support(True, run_config_provider_name="mock", validation_policy="always_local"),
            trace_one_object=_workflow_support(True, prompt_types=["point", "box"], run_config_provider_name="mock", run_config_discovery_mode="manual_prompt", validation_policy="always_local"),
            auto_object_proposals=_workflow_support(True, run_config_provider_name="mock", run_config_discovery_mode="auto_object_proposals", validation_policy="mock_required"),
            find_objects_from_text=_workflow_support(True, prompt_types=["text"], run_config_provider_name="mock", run_config_discovery_mode="text_detector", validation_policy="mock_required"),
        ),
    ),
    _entry(
        "threshold",
        label="HSV threshold",
        description="CPU color-threshold mask provider for simple local cutouts.",
        kind="mask_provider",
        locality="local",
        implemented=True,
        worker_eligible=True,
        model_options=[{"id": "threshold/cpu", "label": "CPU color threshold"}],
        default_model="threshold/cpu",
        remediation="Install OpenCV/numpy if diagnostics report missing base dependencies.",
        workflow_support=_support_map(
            trace_one_object=_workflow_support(True, prompt_types=["point", "box"], run_config_provider_name="threshold", run_config_discovery_mode="manual_prompt", validation_policy="base_dependency_required"),
        ),
    ),
    _entry(
        "motion",
        aliases=["motion_mask_provider"],
        label="Motion foreground",
        description="CPU frame-difference mask provider for moving objects.",
        kind="mask_provider",
        locality="local",
        implemented=True,
        worker_eligible=True,
        model_options=[{"id": "motion/cpu", "label": "CPU frame differencing"}],
        default_model="motion/cpu",
        remediation="Use only for footage where target objects move more than the background.",
        workflow_support=_support_map(
            find_moving_things=_workflow_support(True, run_config_provider_name="motion", run_config_discovery_mode="motion_foreground", validation_policy="base_dependency_required"),
        ),
    ),
    _entry(
        "external",
        aliases=["external-masks-provider"],
        label="External masks",
        description="Local import path for masks or boxes made by another tool.",
        kind="mask_provider",
        locality="local",
        implemented=True,
        worker_eligible=True,
        model_options=[{"id": "external/mask-directory", "label": "Mask directory"}],
        default_model="external/mask-directory",
        remediation="Provide a mask directory before starting an import run.",
        workflow_support=_support_map(
            import_masks=_workflow_support(True, prompt_types=["mask"], run_config_provider_name="external", run_config_discovery_mode="external_masks", validation_policy="mask_directory_required"),
        ),
    ),
    _entry(
        "no_model_cpu_workflow",
        aliases=["no-model-cpu-workflow", "no_model_cpu", "cpu_no_model_workflow"],
        label="No-model CPU workflow",
        description="Fast local smoke checks, simple motion/threshold masks, and imported masks. No hosted cost.",
        kind="product_workflow",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="mock",
        expected_capability_names=["no_model_cpu_workflow", "mock", "threshold", "motion", "external", "motion_foreground", "external_masks"],
        remediation="Use mock for smoke checks, threshold or motion for simple CPU masks, or external masks from another tool.",
        validation_policy="always_local",
        workflow_support=_support_map(
            no_model_cpu=_workflow_support(True, run_config_provider_name="mock", validation_policy="always_local"),
            trace_one_object=_workflow_support(True, prompt_types=["point", "box"], run_config_provider_name="mock", run_config_discovery_mode="manual_prompt", validation_policy="always_local", fallbacks=["threshold", "sam2-local"]),
            find_moving_things=_workflow_support(True, run_config_provider_name="motion", run_config_discovery_mode="motion_foreground", validation_policy="base_dependency_required", fallbacks=["mock", "external"]),
            import_masks=_workflow_support(True, prompt_types=["mask"], run_config_provider_name="external", run_config_discovery_mode="external_masks", validation_policy="mask_directory_required", fallbacks=["mock"]),
            review_existing_result=_workflow_support(True, validation_policy="always_local"),
        ),
    ),
    _entry(
        "sam2_prompt_tracking",
        aliases=["sam2-prompt-tracking"],
        label="SAM2 prompt tracking",
        description="Best for cutting out one prompted object with a point or box.",
        kind="product_workflow",
        locality="hybrid",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="sam2-local",
        expected_capability_names=["sam2_prompt_tracking", "sam2-local", "sam2-hosted"],
        remediation="Use local SAM2 checkpoint/config paths, or choose hosted SAM2 only with explicit cost/privacy opt-in.",
        workflow_support=_support_map(
            trace_one_object=_workflow_support(True, prompt_types=["point", "box"], requires_model_path=True, run_config_provider_name="sam2-local", run_config_discovery_mode="manual_prompt", fallbacks=["sam2-hosted", "mock", "threshold"]),
        ),
    ),
    _entry(
        "sam2_hf_scene_fallback",
        aliases=["sam2-hf-scene-fallback"],
        label="SAM2 HF automatic masks fallback",
        description="Fallback for finding visible segments when SAM3 Scene Sweep is unavailable.",
        kind="product_workflow",
        locality="local",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="sam2-hf-auto-masks",
        optional_extra="sam2-transformers",
        expected_capability_names=["sam2_hf_scene_fallback", "sam2-hf-auto-masks"],
        runtime_proof_required=True,
        remediation="Install the SAM2 Transformers fallback and cache facebook/sam2.1-hiera-large; official SAM2 checkpoint/config is not required.",
        workflow_support=_support_map(
            trace_all_objects=_workflow_support("conditional", requires_runtime_proof=True, run_config_provider_name="sam2-hf-auto-masks", run_config_discovery_mode="sam2_hf_auto_masks", fallbacks=["sam3_tracker_scene_sweep", "motion_foreground"]),
            auto_object_proposals=_workflow_support("conditional", requires_runtime_proof=True, run_config_provider_name="sam2-hf-auto-masks", run_config_discovery_mode="sam2_hf_auto_masks", fallbacks=["sam2_prompt_tracking", "motion_foreground"]),
        ),
    ),
    _entry(
        "sam2",
        aliases=["legacy-sam2"],
        label="Legacy SAM2 alias",
        description="Legacy ambiguous SAM2 provider name retained for diagnostics; workspace runs must choose sam2-local, sam2-hosted, or sam2-hf-auto-masks explicitly.",
        kind="mask_provider",
        locality="local",
        implemented=False,
        worker_eligible=False,
        settings_provider_id="sam2-local",
        optional_extra="sam2",
        remediation="Choose sam2-local for local prompt tracking, sam2-hosted for hosted tracking, or sam2-hf-auto-masks for automatic-mask fallback.",
        validation_policy="legacy_rejected",
    ),
    _entry(
        "sam2-local",
        aliases=["local-sam2"],
        label="SAM2 prompt tracking",
        description="Local promptable SAM2 video segmentation/tracking for one selected object.",
        kind="mask_provider",
        locality="local",
        implemented=True,
        worker_eligible=True,
        local_config_fields=[
            {"name": "sam2_checkpoint_path", "env": "SAM2_LOCAL_CHECKPOINT", "required": True},
            {"name": "sam2_model_config_path", "env": "SAM2_LOCAL_CONFIG", "required": True},
            {"name": "sam2_device", "env": "SAM2_LOCAL_DEVICE", "required": False},
        ],
        model_options=[
            {"id": "sam2/hiera-tiny", "label": "SAM2 Hiera tiny"},
            {"id": "sam2/hiera-small", "label": "SAM2 Hiera small"},
            {"id": "sam2/hiera-base-plus", "label": "SAM2 Hiera base+"},
            {"id": "sam2/hiera-large", "label": "SAM2 Hiera large"},
            {"id": "__custom__", "label": "Custom model id"},
        ],
        default_model="sam2/hiera-tiny",
        optional_extra="sam2",
        setup_actions=["diagnose", "install", "smoke"],
        runtime_proof_required=False,
        remediation="Install SAM2 and save checkpoint/config paths, or switch to mock/threshold for CPU-only smoke checks.",
        workflow_support=_support_map(
            trace_one_object=_workflow_support(True, prompt_types=["point", "box"], requires_model_path=True, run_config_provider_name="sam2-local", run_config_discovery_mode="manual_prompt", fallbacks=["mock", "threshold", "sam2-hosted"]),
            auto_object_proposals=_workflow_support("conditional", requires_model_path=True, run_config_provider_name="sam2-local", run_config_discovery_mode="auto_object_proposals", fallbacks=["sam2-hf-auto-masks", "motion_foreground"]),
            trace_all_objects=_workflow_support("conditional", requires_model_path=True, run_config_provider_name="sam2-local", run_config_discovery_mode="auto_object_proposals", fallbacks=["sam3-local", "sam2-hf-auto-masks"]),
        ),
    ),
    _entry(
        "sam2-hf-auto-masks",
        aliases=["sam2_hf_auto_masks", "sam2-transformers-auto-masks"],
        label="SAM2 HF automatic masks fallback",
        description="Hugging Face Transformers automatic-mask fallback for scene proposals.",
        kind="discovery_provider",
        locality="local",
        implemented=True,
        worker_eligible=True,
        local_config_fields=[{"name": "sam2_hf_device", "env": "SAM2_HF_DEVICE", "required": False}],
        model_options=[
            {"id": SAM2_HF_AUTO_MASKS_DEFAULT_MODEL, "label": "facebook/sam2.1-hiera-large"},
            {"id": "__custom__", "label": "Custom HF SAM2 model directory or repo id"},
        ],
        default_model=SAM2_HF_AUTO_MASKS_DEFAULT_MODEL,
        optional_extra="sam2-transformers",
        setup_actions=["diagnose", "install", "cache_model", "smoke"],
        expected_capability_names=["sam2-hf-auto-masks"],
        runtime_proof_required=True,
        remediation="Install the SAM2 Transformers extra and cache the selected model, or use motion foreground/import masks.",
        workflow_support=_support_map(
            trace_all_objects=_workflow_support("conditional", requires_runtime_proof=True, run_config_provider_name="sam2-hf-auto-masks", run_config_discovery_mode="sam2_hf_auto_masks", fallbacks=["sam3-local", "motion_foreground"]),
            auto_object_proposals=_workflow_support("conditional", requires_runtime_proof=True, run_config_provider_name="sam2-hf-auto-masks", run_config_discovery_mode="sam2_hf_auto_masks", fallbacks=["sam2-local", "motion_foreground"]),
        ),
    ),
    _entry(
        "sam2-hosted",
        aliases=[
            "replicate-sam2-video",
            "custom-sam2-compatible",
            "hosted-sam2",
            "sam2-hosted:replicate-sam2-video",
            "sam2-hosted:custom-sam2-compatible",
        ],
        label="Hosted SAM2-compatible",
        description="Opt-in hosted SAM2-compatible prompt tracking.",
        kind="mask_provider",
        locality="hosted",
        implemented=True,
        worker_eligible=True,
        credential_fields=[
            {"name": "api_key", "env": "REPLICATE_API_TOKEN", "required": True},
            {"name": "api_key", "env": "HOSTED_SEGMENTATION_API_KEY", "required": True},
        ],
        endpoint_fields=[{"name": "endpoint", "env": "HOSTED_SEGMENTATION_URL", "required": False}],
        model_options=[
            {"id": "meta/sam-2-video", "label": "Replicate meta/sam-2-video"},
            {"id": "auto", "label": "Provider default"},
            {"id": "__custom__", "label": "Custom hosted model id"},
        ],
        default_model="auto",
        setup_actions=["test", "smoke"],
        remediation="Save credentials and explicitly confirm hosted cost/privacy before a run.",
        workflow_support=_support_map(
            trace_one_object=_workflow_support("conditional", prompt_types=["point", "box"], requires_credentials=True, requires_hosted_opt_in=True, run_config_provider_name="sam2-hosted", run_config_discovery_mode="manual_prompt", validation_policy="hosted_opt_in_required", fallbacks=["sam2-local", "mock"]),
        ),
    ),
    _entry(
        "sam3_tracker_scene_sweep",
        aliases=["sam3-tracker-scene-sweep"],
        label="SAM3 Scene Sweep",
        description="Recommended CUDA path for scene-wide object proposals and review before export.",
        kind="product_workflow",
        locality="local",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="sam3-local",
        optional_extra="sam3-transformers",
        setup_actions=["diagnose", "install", "check_access", "cache_model", "smoke"],
        expected_capability_names=["sam3_tracker_scene_sweep", "sam3-auto-masks"],
        runtime_proof_required=True,
        remediation="Install the sam3-transformers runtime, check Hugging Face access when needed, cache facebook/sam3, then run scene-sweep proof.",
        workflow_support=_support_map(
            trace_all_objects=_workflow_support("conditional", requires_runtime_proof=True, run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_auto_masks", fallbacks=["sam2_hf_scene_fallback", "motion_foreground"]),
            auto_object_proposals=_workflow_support("conditional", requires_runtime_proof=True, run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_auto_masks", fallbacks=["sam2_hf_scene_fallback", "sam2_prompt_tracking"]),
        ),
    ),
    _entry(
        "hosted_sam3_concept_text",
        aliases=["hosted-sam3-concept-text"],
        label="Hosted SAM3 text discovery",
        description="Find objects from descriptions using a hosted SAM3 provider. Requires explicit cost/privacy opt-in.",
        kind="product_workflow",
        locality="hosted",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="sam3-hosted",
        credential_fields=[
            {"name": "api_key", "env": "ROBOFLOW_API_KEY", "required": True},
            {"name": "api_key", "env": "FAL_KEY", "required": True},
            {"name": "api_key", "env": "SAM3_HOSTED_API_KEY", "required": True},
        ],
        endpoint_fields=[{"name": "endpoint", "env": "SAM3_HOSTED_URL", "required": False}],
        expected_capability_names=["hosted_sam3_concept_text", "sam3-hosted"],
        remediation="Save hosted SAM3 credentials and confirm network/cost/privacy before sending frames off-device.",
        validation_policy="hosted_opt_in_required",
        workflow_support=_support_map(
            find_objects_from_text=_workflow_support("conditional", prompt_types=["text"], requires_credentials=True, requires_hosted_opt_in=True, run_config_provider_name="sam3-hosted", run_config_discovery_mode="sam3_concept", validation_policy="hosted_opt_in_required", fallbacks=["advanced_local_sam3_concept_exemplar", "text_detector"]),
        ),
    ),
    _entry(
        "advanced_local_sam3_concept_exemplar",
        aliases=["advanced-local-sam3-concept-exemplar", "local-sam3-concept-exemplar"],
        label="Advanced local SAM3 concept/exemplar",
        description="For advanced users with the official SAM3 package and local checkpoint configured.",
        kind="product_workflow",
        locality="local",
        implemented=False,
        worker_eligible=False,
        settings_provider_id="sam3-local",
        local_config_fields=[{"name": "sam3_model_path", "env": "SAM3_LOCAL_MODEL", "required": True}],
        optional_extra="sam3",
        expected_capability_names=["advanced_local_sam3_concept_exemplar", "sam3-concept", "sam3-exemplar"],
        runtime_proof_required=True,
        remediation="Keep this advanced path hidden until the official SAM3 package, CUDA runtime, and sam3.pt checkpoint have proof.",
        validation_policy="advanced_local_only",
        workflow_support=_support_map(
            trace_one_object=_workflow_support("conditional", prompt_types=["box"], requires_model_path=True, requires_runtime_proof=True, run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_exemplar", validation_policy="advanced_local_only", fallbacks=["sam2_prompt_tracking", "hosted_sam3_concept_text"]),
            find_objects_from_text=_workflow_support("conditional", prompt_types=["text"], requires_model_path=True, requires_runtime_proof=True, run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_concept", validation_policy="advanced_local_only", fallbacks=["hosted_sam3_concept_text", "text_detector"]),
        ),
    ),
    _entry(
        "sam3-local",
        capability_id="sam3-auto-masks",
        aliases=["sam3-scene-sweep", "sam3_scene_sweep"],
        label="SAM3 Scene Sweep",
        description="Local SAM3 Tracker scene-sweep workflow for broad visible-object proposals.",
        kind="discovery_provider",
        locality="local",
        implemented=True,
        worker_eligible=True,
        credential_fields=[{"name": "hf_token", "env": "HF_TOKEN", "required": False}],
        local_config_fields=[
            {"name": "sam3_model_path", "env": "SAM3_LOCAL_MODEL", "required": False},
            {"name": "sam3_device", "env": "SAM3_LOCAL_DEVICE", "required": False},
        ],
        model_options=[
            {"id": SAM3_HF_REPO_ID, "label": "facebook/sam3 (SAM3 Scene Sweep)"},
            {"id": "__custom__", "label": "Custom HF repo id or runtime model directory"},
        ],
        default_model=SAM3_HF_REPO_ID,
        optional_extra="sam3-transformers",
        setup_actions=["diagnose", "install", "check_access", "cache_model", "smoke"],
        expected_capability_names=["sam3-auto-masks", "sam3-local"],
        runtime_proof_required=True,
        remediation="Install scene sweep, check Hugging Face access when needed, cache facebook/sam3, then prove the runtime.",
        workflow_support=_support_map(
            trace_all_objects=_workflow_support("conditional", prompt_types=["box"], requires_runtime_proof=True, run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_auto_masks", fallbacks=["sam2-hf-auto-masks", "motion_foreground"]),
            auto_object_proposals=_workflow_support("conditional", prompt_types=["box"], requires_runtime_proof=True, run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_auto_masks", fallbacks=["sam2-hf-auto-masks", "sam2-local"]),
        ),
    ),
    _entry(
        "sam3-hosted",
        aliases=[
            "roboflow-sam3-pcs",
            "fal-sam3-image",
            "custom-sam3-compatible",
            "hosted-sam3",
            "sam3-hosted:roboflow-sam3-pcs",
            "sam3-hosted:fal-sam3-image",
            "sam3-hosted:custom-sam3-compatible",
        ],
        label="Hosted SAM3-compatible",
        description="Opt-in hosted SAM3 concept, exemplar, tracking, or auto-mask workflow.",
        kind="discovery_provider",
        locality="hosted",
        implemented=True,
        worker_eligible=True,
        credential_fields=[
            {"name": "api_key", "env": "ROBOFLOW_API_KEY", "required": True},
            {"name": "api_key", "env": "FAL_KEY", "required": True},
            {"name": "api_key", "env": "SAM3_HOSTED_API_KEY", "required": True},
        ],
        endpoint_fields=[{"name": "endpoint", "env": "SAM3_HOSTED_URL", "required": False}],
        model_options=[
            {"id": "sam3/sam3_final", "label": "Roboflow sam3/sam3_final"},
            {"id": "fal-ai/sam-3/image", "label": "Fal fal-ai/sam-3/image"},
            {"id": "auto", "label": "Provider default"},
            {"id": "__custom__", "label": "Custom hosted SAM3 model id"},
        ],
        default_model="auto",
        setup_actions=["test", "smoke"],
        remediation="Save credentials and explicitly confirm hosted cost/privacy before frames leave the device.",
        workflow_support=_support_map(
            trace_one_object=_workflow_support("conditional", prompt_types=["box"], requires_credentials=True, requires_hosted_opt_in=True, run_config_provider_name="sam3-hosted", run_config_discovery_mode="sam3_exemplar", validation_policy="hosted_opt_in_required", fallbacks=["sam2-local", "mock"]),
            trace_all_objects=_workflow_support("conditional", requires_credentials=True, requires_hosted_opt_in=True, run_config_provider_name="sam3-hosted", run_config_discovery_mode="sam3_auto_masks", validation_policy="hosted_opt_in_required", fallbacks=["sam3-local", "sam2-hf-auto-masks"]),
            find_objects_from_text=_workflow_support("conditional", prompt_types=["text"], requires_credentials=True, requires_hosted_opt_in=True, run_config_provider_name="sam3-hosted", run_config_discovery_mode="sam3_concept", validation_policy="hosted_opt_in_required", fallbacks=["sam3-concept", "text_detector"]),
        ),
    ),
    _entry(
        "sam3-concept",
        aliases=["sam3_concept", "local-sam3-concept"],
        label="SAM3 local concept adapter",
        description="Advanced local official SAM3 concept/text discovery adapter.",
        kind="discovery_provider",
        locality="local",
        implemented=False,
        worker_eligible=False,
        settings_provider_id="sam3-local",
        local_config_fields=[{"name": "sam3_model_path", "env": "SAM3_LOCAL_MODEL", "required": True}],
        model_options=[{"id": "sam3/local-model-path", "label": "Configured SAM3 concept model"}],
        default_model="sam3/local-model-path",
        optional_extra="sam3",
        runtime_proof_required=True,
        remediation="Use hosted SAM3 concept discovery or configure the advanced official SAM3 package plus a sam3.pt path.",
        validation_policy="advanced_local_only",
        workflow_support=_support_map(
            find_objects_from_text=_workflow_support("conditional", prompt_types=["text"], requires_model_path=True, requires_runtime_proof=True, run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_concept", validation_policy="advanced_local_only", fallbacks=["sam3-hosted", "text_detector"]),
        ),
    ),
    _entry(
        "sam3-exemplar",
        aliases=["sam3_exemplar", "local-sam3-exemplar"],
        label="SAM3 local exemplar adapter",
        description="Advanced local official SAM3 visual exemplar discovery adapter.",
        kind="discovery_provider",
        locality="local",
        implemented=False,
        worker_eligible=False,
        settings_provider_id="sam3-local",
        local_config_fields=[{"name": "sam3_model_path", "env": "SAM3_LOCAL_MODEL", "required": True}],
        model_options=[{"id": "sam3/local-model-path", "label": "Configured SAM3 exemplar model"}],
        default_model="sam3/local-model-path",
        optional_extra="sam3",
        runtime_proof_required=True,
        remediation="Use SAM2 prompt tracking or configure the advanced official SAM3 package plus a sam3.pt path.",
        validation_policy="advanced_local_only",
        workflow_support=_support_map(
            trace_one_object=_workflow_support("conditional", prompt_types=["box"], requires_model_path=True, requires_runtime_proof=True, run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_exemplar", validation_policy="advanced_local_only", fallbacks=["sam2-local", "sam3-hosted"]),
        ),
    ),
    _entry(
        "sam3-auto-masks",
        aliases=["sam3_auto_masks"],
        label="SAM3 auto masks catalog placeholder",
        description="Provider-settings catalog placeholder for SAM3 automatic masks. The runnable scene-sweep connection is sam3-local and is gated by the sam3-auto-masks capability.",
        kind="discovery_provider",
        locality="local",
        implemented=False,
        worker_eligible=False,
        settings_provider_id="sam3-local",
        optional_extra="sam3-transformers",
        expected_capability_names=["sam3-auto-masks"],
        remediation="Select the SAM3 Scene Sweep connection, which stores settings under sam3-local.",
        workflow_support=_support_map(
            trace_all_objects=_workflow_support("conditional", run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_auto_masks", fallbacks=["sam2-hf-auto-masks", "motion_foreground"]),
            auto_object_proposals=_workflow_support("conditional", run_config_provider_name="sam3-local", run_config_discovery_mode="sam3_auto_masks", fallbacks=["sam2-hf-auto-masks", "sam2-local"]),
        ),
    ),
    _entry(
        "manual_prompt",
        aliases=["manual-prompt"],
        label="Manual prompt",
        description="User-created point, box, or mask candidates.",
        kind="discovery_provider",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="mock",
        remediation="Use point or box prompts for one-object tracing.",
        workflow_support=_support_map(
            trace_one_object=_workflow_support(True, prompt_types=["point", "box", "mask"], run_config_discovery_mode="manual_prompt", validation_policy="always_local"),
        ),
    ),
    _entry(
        "motion_foreground",
        aliases=["motion-foreground"],
        label="Find moving objects",
        description="CPU moving-region proposals for stable-background footage.",
        kind="discovery_provider",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="motion",
        remediation="Use with motion provider for local no-model moving object discovery.",
        workflow_support=_support_map(
            find_moving_things=_workflow_support(True, run_config_provider_name="motion", run_config_discovery_mode="motion_foreground", validation_policy="base_dependency_required"),
        ),
    ),
    _entry(
        "external_masks",
        aliases=["external-masks"],
        label="Import masks",
        description="Import existing masks or boxes as object candidates.",
        kind="discovery_provider",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="external",
        remediation="Choose a mask directory or MotionJSON import before running.",
        workflow_support=_support_map(
            import_masks=_workflow_support(True, prompt_types=["mask"], run_config_provider_name="external", run_config_discovery_mode="external_masks", validation_policy="mask_directory_required"),
        ),
    ),
    _entry(
        "auto_object_proposals",
        aliases=["discover_objects"],
        label="Discover objects",
        description="SAM2 automatic proposal workflow with review required before export.",
        kind="discovery_provider",
        locality="local",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="sam2-local",
        expected_capability_names=["auto_object_proposals"],
        remediation="Use mock for smoke checks, SAM2 local when configured, or SAM3 Scene Sweep for trace-all workflows.",
        workflow_support=_support_map(
            auto_object_proposals=_workflow_support("conditional", requires_model_path=True, run_config_provider_name="sam2-local", run_config_discovery_mode="auto_object_proposals", fallbacks=["mock", "sam2-hf-auto-masks", "motion_foreground"]),
            trace_all_objects=_workflow_support("conditional", requires_model_path=True, run_config_provider_name="sam2-local", run_config_discovery_mode="auto_object_proposals", fallbacks=["sam3-local", "sam2-hf-auto-masks"]),
        ),
    ),
    _entry(
        "sam_auto_masks",
        aliases=["sam-auto-masks", "sam2-auto-masks"],
        label="Propose visible segments",
        description="Legacy SAM2 automatic visible-segment proposal workflow.",
        kind="discovery_provider",
        locality="local",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="sam2-local",
        expected_capability_names=["sam_auto_masks"],
        remediation="Use mock for smoke checks or install/configure SAM2 automatic masks.",
        workflow_support=_support_map(
            trace_all_objects=_workflow_support("conditional", requires_model_path=True, run_config_provider_name="sam2-local", run_config_discovery_mode="sam_auto_masks", fallbacks=["sam3-local", "sam2-hf-auto-masks", "motion_foreground"]),
        ),
    ),
    _entry(
        "text_detector",
        aliases=["text-detector", "find_by_description"],
        label="Text detector",
        description="Scaffolded local open-vocabulary detector candidate provider.",
        kind="discovery_provider",
        locality="local",
        implemented=False,
        worker_eligible=False,
        model_options=[{"id": "detector/local-model-path", "label": "Configured detector"}],
        default_model="detector/local-model-path",
        optional_extra="detectors",
        remediation="Use hosted SAM3 concept discovery or mock text-detector smoke mode until a concrete local detector is configured.",
        validation_policy="mock_or_unavailable",
        workflow_support=_support_map(
            find_objects_from_text=_workflow_support("conditional", prompt_types=["text"], requires_model_path=True, run_config_discovery_mode="text_detector", validation_policy="mock_or_unavailable", fallbacks=["sam3-hosted", "mock"]),
        ),
    ),
    _entry(
        "class_detector",
        aliases=["class-detector"],
        label="Known-class detector",
        description="Scaffolded local known-class detector candidate provider.",
        kind="discovery_provider",
        locality="local",
        implemented=False,
        worker_eligible=False,
        model_options=[{"id": "yolo/local-model-path", "label": "Configured class model"}],
        default_model="yolo/local-model-path",
        optional_extra="yolo",
        remediation="Use mock class-detector smoke mode until a concrete known-class detector is configured.",
        validation_policy="mock_or_unavailable",
        workflow_support=_support_map(
            auto_object_proposals=_workflow_support("conditional", prompt_types=["class"], requires_model_path=True, run_config_discovery_mode="class_detector", validation_policy="mock_or_unavailable", fallbacks=["mock", "motion_foreground"]),
        ),
    ),
    _entry(
        "openai",
        aliases=["openai-settings"],
        label="OpenAI planning settings",
        description="Server-side OpenAI credentials and model selection for planning.",
        kind="llm_provider",
        locality="hosted",
        implemented=True,
        worker_eligible=False,
        credential_fields=[{"name": "api_key", "env": "OPENAI_API_KEY", "required": True}],
        endpoint_fields=[{"name": "base_url", "env": "OPENAI_BASE_URL", "required": False}],
        model_options=[
            {"id": "gpt-5.4-mini", "label": "GPT-5.4 mini"},
            {"id": "gpt-5.5", "label": "GPT-5.5"},
            {"id": "__custom__", "label": "Custom OpenAI model id"},
        ],
        default_model="gpt-5.4-mini",
        remediation="OpenAI planning is server-side only and requires explicit hosted opt-in.",
    ),
    _entry(
        "openrouter",
        aliases=["openrouter-settings"],
        label="OpenRouter settings",
        description="Settings-only hosted planner provider until runtime planning transport exists.",
        kind="llm_provider",
        locality="hosted",
        implemented=True,
        worker_eligible=False,
        credential_fields=[{"name": "api_key", "env": "OPENROUTER_API_KEY", "required": True}],
        endpoint_fields=[{"name": "base_url", "env": "OPENROUTER_BASE_URL", "required": False}],
        model_options=[{"id": "openrouter/auto", "label": "OpenRouter auto"}, {"id": "__custom__", "label": "Custom OpenRouter model id"}],
        default_model="openrouter/auto",
        remediation="OpenRouter remains settings-only and not runnable until a hosted planning connector is implemented.",
        validation_policy="settings_only",
    ),
    _entry(
        "fake-local-planner",
        aliases=["fake_planner", "local-fake-planner"],
        label="Fake in-process planner",
        description="Deterministic no-network model-planning connector.",
        kind="planning_provider",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="mock",
        remediation="Use this as the default planning path for tests and no-model smoke checks.",
        workflow_support=_support_map(
            no_model_cpu=_workflow_support(True, validation_policy="always_local"),
            trace_one_object=_workflow_support(True, validation_policy="always_local"),
            trace_all_objects=_workflow_support(True, validation_policy="always_local"),
            find_objects_from_text=_workflow_support(True, validation_policy="always_local"),
            find_moving_things=_workflow_support(True, validation_policy="always_local"),
            import_masks=_workflow_support(True, validation_policy="always_local"),
            review_existing_result=_workflow_support(True, validation_policy="always_local"),
        ),
    ),
    _entry(
        "openai-planner",
        aliases=["openai_planner"],
        label="OpenAI planner",
        description="Server-side OpenAI planning connector; output is a proposed run config only.",
        kind="planning_provider",
        locality="hosted",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="openai",
        credential_fields=[{"name": "api_key", "env": "OPENAI_API_KEY", "required": True}],
        endpoint_fields=[{"name": "base_url", "env": "OPENAI_BASE_URL", "required": False}],
        remediation="Requires saved server-side configuration, hosted opt-in, and per-request cost/privacy acknowledgement.",
        validation_policy="hosted_opt_in_required",
        workflow_support=_support_map(
            trace_one_object=_workflow_support("conditional", requires_credentials=True, requires_hosted_opt_in=True, validation_policy="hosted_opt_in_required"),
            trace_all_objects=_workflow_support("conditional", requires_credentials=True, requires_hosted_opt_in=True, validation_policy="hosted_opt_in_required"),
            auto_object_proposals=_workflow_support("conditional", requires_credentials=True, requires_hosted_opt_in=True, validation_policy="hosted_opt_in_required"),
            find_objects_from_text=_workflow_support("conditional", prompt_types=["text"], requires_credentials=True, requires_hosted_opt_in=True, validation_policy="hosted_opt_in_required"),
            find_moving_things=_workflow_support("conditional", requires_credentials=True, requires_hosted_opt_in=True, validation_policy="hosted_opt_in_required"),
            import_masks=_workflow_support("conditional", requires_credentials=True, requires_hosted_opt_in=True, validation_policy="hosted_opt_in_required"),
            review_existing_result=_workflow_support("conditional", requires_credentials=True, requires_hosted_opt_in=True, validation_policy="hosted_opt_in_required"),
        ),
    ),
    _entry(
        "openrouter-planner",
        aliases=["openrouter_planner"],
        label="OpenRouter planner",
        description="Settings-only hosted planner placeholder; not runnable until transport is implemented.",
        kind="planning_provider",
        locality="settings_only",
        implemented=False,
        worker_eligible=False,
        settings_provider_id="openrouter",
        credential_fields=[{"name": "api_key", "env": "OPENROUTER_API_KEY", "required": True}],
        remediation="Keep readiness visible, but do not allow planning runs until implementation exists.",
        validation_policy="settings_only",
    ),
    _entry(
        "review_existing",
        capability_id="review_existing_result",
        aliases=["review_existing_result", "review_previous_result", "import"],
        label="Review existing result",
        description="Workflow-only path for inspecting/correcting an existing MotionJSON result.",
        kind="workflow_provider",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="mock",
        remediation="Import a MotionJSON result and use review/correction tools before export.",
        workflow_support=_support_map(
            review_existing_result=_workflow_support(True, validation_policy="always_local"),
        ),
    ),
    _entry(
        "trace_one_object",
        aliases=["cut_out_one_object"],
        label="Trace one object workflow",
        description="Workflow identity for tracing one prompted object.",
        kind="workflow_provider",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="mock",
        remediation="Choose a promptable provider such as mock, SAM2 prompt tracking, hosted SAM2, or advanced SAM3 exemplar.",
        workflow_support=_support_map(
            trace_one_object=_workflow_support(True, validation_policy="workflow_selector"),
        ),
    ),
    _entry(
        "trace_all_objects",
        label="Trace all objects workflow",
        description="Workflow identity for finding and reviewing broad object proposals.",
        kind="workflow_provider",
        locality="hybrid",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="mock",
        remediation="Choose SAM3 Scene Sweep, SAM2 HF automatic masks, SAM2 proposals, or a no-model fallback.",
        workflow_support=_support_map(
            trace_all_objects=_workflow_support(True, validation_policy="workflow_selector"),
        ),
    ),
    _entry(
        "video-tracker",
        label="Video tracker",
        description="Local per-frame mask tracking component.",
        kind="video_tracker",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="mock",
        remediation="Install OpenCV/numpy when diagnostics report missing base dependencies.",
    ),
    _entry(
        "track-linker",
        label="Track linker",
        description="Local object identity linker.",
        kind="track_linker",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="mock",
        remediation="No setup required.",
    ),
    _entry(
        "contour-vectorizer",
        label="Contour vectorizer",
        description="Local contour simplification and vectorization component.",
        kind="vectorizer",
        locality="no_model",
        implemented=True,
        worker_eligible=False,
        settings_provider_id="mock",
        remediation="Install OpenCV/numpy when diagnostics report missing base dependencies.",
    ),
    *[
        _entry(
            provider_id,
            label=label,
            description=description,
            kind="exporter",
            locality="no_model",
            implemented=True,
            worker_eligible=False,
            settings_provider_id="mock",
            remediation=remediation,
        )
        for provider_id, label, description, remediation in [
            ("motionjson-json", "MotionJSON JSON", "Local scene graph and manifest exporter.", "No setup required."),
            ("website-zip", "Website package", "Local embeddable website package exporter.", "No setup required."),
            ("remotion-plan", "Remotion plan", "Local Remotion plan handoff exporter.", "No setup required."),
            ("silhouette-lottie", "Silhouette Lottie", "Local silhouette Lottie exporter.", "No setup required."),
            ("ffmpeg-video", "FFmpeg video", "Local MP4/WebM exporter using FFmpeg.", "Install FFmpeg when diagnostics report it missing."),
        ]
    ],
]


def _canonical_key(value: str) -> str:
    return str(value or "").strip()


def _registry_index() -> dict[str, dict[str, Any]]:
    return {str(entry["providerId"]): entry for entry in _PROVIDER_REGISTRY}


def _alias_index() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for entry in _PROVIDER_REGISTRY:
        provider_id = str(entry["providerId"])
        for key in {
            provider_id,
            str(entry.get("capabilityId") or ""),
            str(entry.get("connectionId") or ""),
            *[str(alias) for alias in entry.get("aliases") or []],
        }:
            normalized = _canonical_key(key)
            if normalized:
                aliases[normalized] = provider_id
    return aliases


def provider_registry() -> list[dict[str, Any]]:
    return copy.deepcopy(_PROVIDER_REGISTRY)


def normalize_provider_id(provider_id: str) -> str:
    value = _canonical_key(provider_id)
    return _alias_index().get(value, value)


def provider_by_id(provider_id: str) -> dict[str, Any] | None:
    normalized = normalize_provider_id(provider_id)
    entry = _registry_index().get(normalized)
    return copy.deepcopy(entry) if entry else None


def hosted_profile_for_alias(provider_id: str) -> tuple[str, str] | None:
    value = _canonical_key(provider_id)
    profile = _HOSTED_PROFILE_ALIASES.get(value)
    return tuple(profile) if profile else None


def workflow_connections_for_goal(goal: str) -> list[dict[str, Any]]:
    workflow_id = normalize_workflow_id(goal)
    connections: list[dict[str, Any]] = []
    for entry in _PROVIDER_REGISTRY:
        support = dict((entry.get("workflowSupport") or {}).get(workflow_id) or {})
        if support.get("supported") is False:
            continue
        connections.append(
            {
                "providerId": entry["providerId"],
                "capabilityId": entry["capabilityId"],
                "connectionId": entry["connectionId"],
                "label": entry["label"],
                "kind": entry["kind"],
                "locality": entry["locality"],
                "implemented": entry["implemented"],
                "workerEligible": entry["workerEligible"],
                "support": support,
            }
        )
    return connections


def normalize_workflow_id(goal: str) -> str:
    value = str(goal or "").strip()
    aliases = {
        "cut_out_one_object": "trace_one_object",
        "manual_prompt": "trace_one_object",
        "discover_objects": "auto_object_proposals",
        "find_moving_objects": "find_moving_things",
        "motion_foreground": "find_moving_things",
        "find_by_description": "find_objects_from_text",
        "text_detector": "find_objects_from_text",
        "external_masks": "import_masks",
        "review_existing": "review_existing_result",
        "review_previous_result": "review_existing_result",
    }
    return aliases.get(value, value)


def registry_capability_ids() -> set[str]:
    ids: set[str] = set()
    for entry in _PROVIDER_REGISTRY:
        ids.add(str(entry["capabilityId"]))
        ids.update(str(name) for name in entry.get("expectedCapabilityNames") or [])
    return ids


def worker_extract_provider_ids() -> set[str]:
    provider_ids = {
        str(entry["providerId"])
        for entry in _PROVIDER_REGISTRY
        if entry.get("workerEligible") is True
    }
    for entry in _PROVIDER_REGISTRY:
        for support in (entry.get("workflowSupport") or {}).values():
            provider_name = str((support or {}).get("runConfigProviderName") or "").strip()
            if provider_name and entry.get("workerEligible") is True:
                provider_ids.add(provider_name)
    return provider_ids


def rejected_segmentation_aliases() -> set[str]:
    return set(_REJECTED_SEGMENTATION_ALIASES)


def registry_public_payload() -> dict[str, Any]:
    providers = provider_registry()
    aliases = _alias_index()
    workflows = [
        {
            "id": workflow_id,
            "connections": workflow_connections_for_goal(workflow_id),
        }
        for workflow_id in WORKFLOW_IDS
    ]
    return {
        "format": PROVIDER_WORKFLOW_REGISTRY_FORMAT,
        "providers": providers,
        "workflows": workflows,
        "aliases": aliases,
        "workerPolicy": {
            "allowedExtractMaskProviders": sorted(worker_extract_provider_ids()),
            "rejectedSegmentationAliases": sorted(_REJECTED_SEGMENTATION_ALIASES),
        },
    }


def registry_entry_summary(provider_id: str) -> dict[str, Any]:
    entry = provider_by_id(provider_id)
    if not entry:
        return {}
    return {
        "providerId": entry["providerId"],
        "capabilityId": entry["capabilityId"],
        "connectionId": entry["connectionId"],
        "aliases": list(entry.get("aliases") or []),
        "label": entry["label"],
        "kind": entry["kind"],
        "locality": entry["locality"],
        "implemented": entry["implemented"],
        "workerEligible": entry["workerEligible"],
        "settingsProviderId": entry["settingsProviderId"],
        "runtimeProofRequired": entry["runtimeProofRequired"],
        "validationPolicy": entry["validationPolicy"],
        "remediation": entry["remediation"],
    }


def registry_has_provider_or_alias(provider_id: str) -> bool:
    return bool(provider_by_id(provider_id))


def registry_kind(provider_id: str) -> str:
    entry = provider_by_id(provider_id)
    return str(entry.get("kind") or "") if entry else ""


def registry_settings_provider_id(provider_id: str) -> str:
    entry = provider_by_id(provider_id)
    return str(entry.get("settingsProviderId") or "") if entry else ""


def registry_support(provider_id: str, workflow_id: str) -> Mapping[str, Any]:
    entry = provider_by_id(provider_id)
    if not entry:
        return {}
    return dict((entry.get("workflowSupport") or {}).get(normalize_workflow_id(workflow_id)) or {})
