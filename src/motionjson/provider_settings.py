from __future__ import annotations

import copy
import json
import os
import re
import sqlite3
import sys
import uuid
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from motionjson.backend.usage import utc_now
from motionjson.providers.sam2 import SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
from motionjson.providers.sam3 import (
    SAM3_HF_REPO_ID,
    describe_sam3_model_path,
    describe_sam3_tracker_model,
    sam3_scene_sweep_warmup,
    sam3_tracker_video_runtime_status,
)


PROVIDER_SETTINGS_FORMAT = "motionjson.local_provider_settings.v0.1"
PROVIDER_CATALOG_FORMAT = "motionjson.provider_registry.v0.1"

CUSTOM_MODEL_ID = "__custom__"
LOCAL_MODEL_CACHE_PROVIDER_IDS = {"sam2-hf-auto-masks", "sam3-local"}
LOCAL_MODEL_CACHE_KEYS = {"cached_model_id", "resolved_model_dir", "model_cache_updated_at"}
LOCAL_MODEL_RUNTIME_KEYS = {
    "runtime_verified_at",
    "runtime_verified_model_id",
    "runtime_device_requested",
    "runtime_device_actual",
    "runtime_kind",
    "runtime_accelerator_kind",
    "runtime_proof_status",
    "runtime_loaded_on_cuda",
    "runtime_loaded_on_mps",
    "runtime_cuda_available",
    "runtime_mps_available",
    "runtime_gpu_memory_before",
    "runtime_gpu_memory_after",
    "runtime_warmup_status",
}

SAM2_HOSTED_PROFILES: list[dict[str, Any]] = [
    {
        "id": "replicate-sam2-video",
        "name": "Replicate SAM2 video",
        "runtime": "replicate-sam2-video",
        "providerId": "sam2-hosted",
        "credentialFields": [{"name": "api_key", "label": "Replicate API token", "env": "REPLICATE_API_TOKEN", "required": True}],
        "endpointField": None,
        "defaultModel": "meta/sam-2-video",
        "modelOptions": [{"id": "meta/sam-2-video", "label": "meta/sam-2-video"}],
        "docs": "https://replicate.com/meta/sam-2-video/api",
        "setupGuide": {
            "recommendedFor": "Hosted fallback for tracing one prompted object when the in-process SAM2 runtime is not installed.",
            "setupSummary": "Paste a Replicate API token, keep model meta/sam-2-video, then run the hosted smoke test only after cost/privacy opt-in.",
        },
        "warning": "Uploads the selected video to Replicate for promptable SAM2 video segmentation.",
        "supportedGoals": ["trace_one_object"],
        "supportedPromptTypes": ["point", "box"],
        "supportsConcept": False,
        "supportsExemplar": False,
        "supportsAutoMasks": False,
        "supportsTracking": True,
    },
    {
        "id": "custom-sam2-compatible",
        "name": "Custom SAM2-compatible endpoint",
        "runtime": "custom-sam2-compatible",
        "providerId": "sam2-hosted",
        "credentialFields": [{"name": "api_key", "label": "API key", "env": "HOSTED_SEGMENTATION_API_KEY", "required": True}],
        "endpointField": {"name": "endpoint", "label": "Endpoint URL", "env": "HOSTED_SEGMENTATION_URL", "required": True},
        "defaultModel": "auto",
        "modelOptions": [{"id": "auto", "label": "Provider default"}, {"id": CUSTOM_MODEL_ID, "label": "Custom hosted SAM2 model id"}],
        "docs": "docs/sam2_segmentation.md",
        "warning": "Uses the generic MotionJSON hosted SAM2-compatible JSON contract.",
        "supportedGoals": ["trace_one_object"],
        "supportedPromptTypes": ["point", "box"],
        "supportsConcept": False,
        "supportsExemplar": False,
        "supportsAutoMasks": False,
        "supportsTracking": True,
    },
]

SAM3_HOSTED_PROFILES: list[dict[str, Any]] = [
    {
        "id": "roboflow-sam3-pcs",
        "name": "Roboflow SAM3 concept segmentation",
        "runtime": "roboflow-sam3-pcs",
        "providerId": "sam3-hosted",
        "credentialFields": [{"name": "api_key", "label": "Roboflow API key", "env": "ROBOFLOW_API_KEY", "required": True}],
        "endpointField": {"name": "endpoint", "label": "Endpoint URL", "env": "ROBOFLOW_SAM3_URL", "required": False},
        "defaultEndpoint": "https://serverless.roboflow.com/sam3/concept_segment",
        "defaultModel": "sam3/sam3_final",
        "modelOptions": [{"id": "sam3/sam3_final", "label": "sam3/sam3_final"}],
        "docs": "https://docs.roboflow.com/deploy/supported-models/sam3",
        "setupGuide": {
            "recommendedFor": "Hosted concept segmentation for text prompts like 'red ball' or 'person in white'.",
            "setupSummary": "Paste a Roboflow API key and use sam3/sam3_final for Promptable Concept Segmentation.",
        },
        "warning": "Sends sampled frames and text concepts to Roboflow's SAM3 serverless API.",
        "supportedGoals": ["text_detector"],
        "supportedPromptTypes": [],
        "supportsConcept": True,
        "supportsExemplar": False,
        "supportsAutoMasks": False,
        "supportsTracking": False,
    },
    {
        "id": "fal-sam3-image",
        "name": "Fal SAM3 image",
        "runtime": "fal-sam3-image",
        "providerId": "sam3-hosted",
        "credentialFields": [{"name": "api_key", "label": "Fal API key", "env": "FAL_KEY", "required": True}],
        "endpointField": None,
        "defaultModel": "fal-ai/sam-3/image",
        "modelOptions": [{"id": "fal-ai/sam-3/image", "label": "fal-ai/sam-3/image"}],
        "docs": "https://fal.ai/models/fal-ai/sam-3/image/api",
        "setupGuide": {
            "recommendedFor": "Hosted frame-by-frame SAM3 image segmentation when you want a Fal-backed fallback.",
            "setupSummary": "Paste FAL_KEY and keep fal-ai/sam-3/image selected; MotionJSON downloads returned masks server-side.",
        },
        "warning": "Uploads sampled frames to Fal for SAM3 image segmentation.",
        "supportedGoals": ["text_detector"],
        "supportedPromptTypes": [],
        "supportsConcept": True,
        "supportsExemplar": False,
        "supportsAutoMasks": False,
        "supportsTracking": False,
    },
    {
        "id": "custom-sam3-compatible",
        "name": "Custom SAM3-compatible endpoint",
        "runtime": "custom-sam3-compatible",
        "providerId": "sam3-hosted",
        "credentialFields": [{"name": "api_key", "label": "API key", "env": "SAM3_HOSTED_API_KEY", "required": True}],
        "endpointField": {"name": "endpoint", "label": "Endpoint URL", "env": "SAM3_HOSTED_URL", "required": True},
        "defaultModel": "auto",
        "modelOptions": [{"id": "auto", "label": "Provider default"}, {"id": "sam3/default", "label": "SAM3 default"}, {"id": CUSTOM_MODEL_ID, "label": "Custom hosted SAM3 model id"}],
        "docs": "docs/sam3_hosted.md",
        "warning": "Uses the generic MotionJSON hosted SAM3-compatible JSON contract.",
        "supportedGoals": ["trace_one_object", "trace_all_objects", "text_detector"],
        "supportedPromptTypes": ["box"],
        "supportsConcept": True,
        "supportsExemplar": True,
        "supportsAutoMasks": True,
        "supportsTracking": True,
    },
]

HOSTED_PROFILES_BY_PROVIDER = {
    "sam2-hosted": SAM2_HOSTED_PROFILES,
    "sam3-hosted": SAM3_HOSTED_PROFILES,
}

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*([^\s,;&]+)"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]{8,})")
SIGNED_URL_QUERY_RE = re.compile(r"\b(https?://[^\s?#\"'<>]+)\?([^\s\"'<>]+)")
SECRET_VALUE_PATTERNS = [
    re.compile(r"\bsk-or-v1-[A-Za-z0-9._~-]{8,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9._~-]{8,}\b"),
    re.compile(r"\bmj_local_[A-Za-z0-9._~-]{8,}\b"),
]


PROVIDER_DEFINITIONS: list[dict[str, Any]] = [
    {
        "id": "mock",
        "name": "Mock no-model",
        "capabilityName": "mock",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "mock/no-model", "label": "Mock no-model"}],
        "defaultModel": "mock/no-model",
        "customModelAllowed": False,
        "capabilities": ["segmentation", "tracking smoke", "review smoke"],
        "hardware": "CPU",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime.",
        "warning": "",
        "docs": "docs/local_ui.md",
    },
    {
        "id": "threshold",
        "name": "HSV threshold",
        "capabilityName": "threshold",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "threshold/cpu", "label": "CPU color threshold"}],
        "defaultModel": "threshold/cpu",
        "customModelAllowed": False,
        "capabilities": ["segmentation", "binary masks"],
        "hardware": "CPU",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime.",
        "warning": "",
        "docs": "docs/provider_capabilities.md",
    },
    {
        "id": "motion",
        "name": "Motion foreground",
        "capabilityName": "motion",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "motion/cpu", "label": "CPU frame differencing"}],
        "defaultModel": "motion/cpu",
        "customModelAllowed": False,
        "capabilities": ["moving object proposals", "binary masks"],
        "hardware": "CPU",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime.",
        "warning": "",
        "docs": "docs/provider_capabilities.md",
    },
    {
        "id": "external",
        "name": "External masks",
        "capabilityName": "external",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "external/mask-directory", "label": "Mask directory"}],
        "defaultModel": "external/mask-directory",
        "customModelAllowed": False,
        "capabilities": ["mask import", "multi-object review"],
        "hardware": "CPU",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Imported masks stay inside the selected runtime.",
        "warning": "",
        "docs": "docs/provider_capabilities.md",
    },
    {
        "id": "sam2-local",
        "name": "SAM2 runtime",
        "capabilityName": "sam2-local",
        "kind": "mask_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "localConfigFields": [
            {"name": "sam2_checkpoint_path", "label": "SAM2 checkpoint path", "env": "SAM2_LOCAL_CHECKPOINT", "required": True},
            {"name": "sam2_model_config_path", "label": "SAM2 model config path", "env": "SAM2_LOCAL_CONFIG", "required": True},
            {"name": "sam2_device", "label": "Device", "env": "SAM2_LOCAL_DEVICE", "required": False},
        ],
        "modelOptions": [
            {"id": "sam2/hiera-tiny", "label": "SAM2 Hiera tiny"},
            {"id": "sam2/hiera-small", "label": "SAM2 Hiera small"},
            {"id": "sam2/hiera-base-plus", "label": "SAM2 Hiera base+"},
            {"id": "sam2/hiera-large", "label": "SAM2 Hiera large"},
            {"id": CUSTOM_MODEL_ID, "label": "Custom model id"},
        ],
        "defaultModel": "sam2/hiera-tiny",
        "customModelAllowed": True,
        "capabilities": ["prompt segmentation", "video propagation"],
        "supportedGoals": ["trace_one_object", "trace_all_objects"],
        "supportedPromptTypes": ["point", "box"],
        "supportsConcept": False,
        "supportsExemplar": False,
        "supportsAutoMasks": True,
        "supportsTracking": True,
        "hardware": "CPU, MPS, or CUDA depending on torch/SAM2 setup",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime when SAM2 is installed there.",
        "warning": "Requires SAM2 and model paths in the selected runtime. It is not part of the default CPU install.",
        "setupGuide": {
            "recommendedFor": "Best default for tracing one prompted object through a video.",
            "setupSummary": "Install the official SAM2 package, download a SAM2.1 checkpoint, then save the checkpoint and config paths here.",
            "commands": [
                "git clone https://github.com/facebookresearch/sam2.git",
                "cd sam2 && pip install -e .",
                "cd checkpoints && ./download_ckpts.sh",
                "export SAM2_LOCAL_CHECKPOINT=/path/to/sam2.1_hiera_large.pt",
                "export SAM2_LOCAL_CONFIG=configs/sam2.1/sam2.1_hiera_l.yaml",
            ],
        },
        "docs": "docs/sam2_segmentation.md",
    },
    {
        "id": "sam2-hosted",
        "name": "Hosted SAM2-compatible",
        "capabilityName": "sam2-hosted",
        "kind": "mask_provider",
        "locality": "hosted",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": True,
        "credentialFields": [
            {"name": "api_key", "label": "API key", "env": "HOSTED_SEGMENTATION_API_KEY", "required": True},
        ],
        "endpointField": {"name": "endpoint", "label": "Endpoint URL", "env": "HOSTED_SEGMENTATION_URL", "required": True},
        "hostedProfiles": SAM2_HOSTED_PROFILES,
        "defaultHostedProfile": "replicate-sam2-video",
        "modelOptions": [
            {"id": "meta/sam-2-video", "label": "Replicate meta/sam-2-video"},
            {"id": "auto", "label": "Provider default"},
            {"id": "sam2/hiera-large", "label": "SAM2 Hiera large"},
            {"id": CUSTOM_MODEL_ID, "label": "Custom hosted model id"},
        ],
        "defaultModel": "auto",
        "customModelAllowed": True,
        "capabilities": ["prompt segmentation", "hosted mask generation"],
        "supportedGoals": ["trace_one_object"],
        "supportedPromptTypes": ["point", "box"],
        "supportsConcept": False,
        "supportsExemplar": False,
        "supportsAutoMasks": False,
        "supportsTracking": True,
        "hardware": "Remote provider",
        "cost": {"status": "unknown_provider_cost", "label": "Provider billed"},
        "privacy": "Frames or frame-derived data may leave this machine when hosted calls are enabled.",
        "warning": "Hosted segmentation is opt-in. Confirm cost and privacy before sending frames off-device.",
        "docs": "docs/security/api_keys.md",
    },
    {
        "id": "sam2-hf-auto-masks",
        "name": "SAM2 HF automatic masks",
        "capabilityName": "sam2-hf-auto-masks",
        "kind": "discovery_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [],
        "localConfigFields": [
            {"name": "sam2_hf_device", "label": "Device", "env": "SAM2_HF_DEVICE", "required": False},
        ],
        "modelOptions": [
            {"id": SAM2_HF_AUTO_MASKS_DEFAULT_MODEL, "label": "facebook/sam2.1-hiera-large"},
            { "id": CUSTOM_MODEL_ID, "label": "Custom HF SAM2 model directory or repo id" },
        ],
        "defaultModel": SAM2_HF_AUTO_MASKS_DEFAULT_MODEL,
        "customModelAllowed": True,
        "capabilities": ["automatic masks", "Hugging Face Transformers", "scene-sweep fallback"],
        "supportedGoals": ["trace_all_objects"],
        "supportedPromptTypes": [],
        "supportsConcept": False,
        "supportsExemplar": False,
        "supportsAutoMasks": True,
        "supportsTracking": False,
        "hardware": "CPU, MPS, or CUDA depending on torch/Transformers setup",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime. Model caching may download weights after confirmation.",
        "warning": "This is the HF automatic-mask fallback for scene sweep. It is separate from official SAM2 prompt tracking and does not use official SAM2 checkpoint/config paths.",
        "setupGuide": {
            "recommendedFor": "Fallback for finding everything in scene when SAM3 Scene Sweep is blocked.",
            "setupSummary": "Install the SAM2 Transformers extra, cache facebook/sam2.1-hiera-large, then run a smoke test.",
            "commands": [
                "pip install 'motionjson[sam2-transformers]'",
                "python -c \"from transformers import pipeline; pipeline('mask-generation', model='facebook/sam2.1-hiera-large')\"",
            ],
        },
        "docs": "docs/sam2_segmentation.md",
    },
    {
        "id": "sam3-local",
        "name": "SAM3 Scene Sweep runtime",
        "capabilityName": "sam3-local",
        "kind": "discovery_provider",
        "locality": "local",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": False,
        "credentialFields": [
            {
                "name": "hf_token",
                "label": "Hugging Face token",
                "env": "HF_TOKEN",
                "required": False,
                "helpText": "Needed only when facebook/sam3 access is gated or the model is not cached yet.",
            },
        ],
        "localConfigFields": [
            {
                "name": "sam3_model_path",
                "label": "Advanced SAM3 checkpoint file path",
                "env": "SAM3_LOCAL_MODEL",
                "required": False,
                "placeholder": "/root/.cache/huggingface/hub/models--facebook--sam3/snapshots/<hash>/sam3.pt",
                "helpText": "Only for advanced official-package concept/exemplar workflows. Do not enter /content/sam3 or facebook/sam3.",
            },
            {
                "name": "sam3_device",
                "label": "Device",
                "env": "SAM3_LOCAL_DEVICE",
                "required": False,
                "placeholder": "cuda",
                "helpText": "Normal Colab setup should use cuda. Use cpu or mps only when you intentionally choose a non-CUDA fallback.",
            },
        ],
        "modelOptions": [
            {"id": SAM3_HF_REPO_ID, "label": "facebook/sam3 (SAM3 Scene Sweep)"},
            {"id": CUSTOM_MODEL_ID, "label": "Custom HF repo id or runtime model directory"},
        ],
        "defaultModel": SAM3_HF_REPO_ID,
        "customModelAllowed": True,
        "capabilities": ["scene sweep via HF tracker", "advanced concept discovery", "advanced exemplar discovery", "SAM3 Tracker video"],
        "supportedGoals": ["trace_one_object", "trace_all_objects", "text_detector"],
        "supportedPromptTypes": ["box"],
        "supportsConcept": True,
        "supportsExemplar": True,
        "supportsAutoMasks": True,
        "supportsTracking": True,
        "hardware": "CUDA-capable SAM3 runtime",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime unless a hosted SAM provider is chosen.",
        "warning": "Normal scene sweep uses the independent sam3-transformers extra and facebook/sam3 access. Concept/exemplar workflows are advanced and require the official SAM3 package plus a sam3.pt checkpoint path.",
        "setupGuide": {
            "recommendedFor": "Best runtime path for scene-wide discovery, concept prompts such as 'red ball', and one-object SAM3 tracking.",
            "setupSummary": "For scene sweep, install the sam3-transformers extra, paste a Hugging Face token if the model is gated, and cache facebook/sam3 from the UI. For advanced concept/exemplar workflows, install the official SAM3 source package and save a sam3.pt checkpoint path.",
            "commands": [
                "pip install 'motionjson[sam3-transformers]'",
                "conda create -n sam3 python=3.12",
                "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128",
                "git clone https://github.com/facebookresearch/sam3.git /content/sam3",
                "python -m pip install -e /content/sam3",
                "hf auth login",
                "python -c \"from huggingface_hub import hf_hub_download; print(hf_hub_download(repo_id='facebook/sam3', filename='sam3.pt'))\"",
                "export SAM3_LOCAL_MODEL=/root/.cache/huggingface/hub/models--facebook--sam3/snapshots/<hash>/sam3.pt",
            ],
        },
        "docs": "docs/sam3_local.md",
    },
    {
        "id": "sam3-hosted",
        "name": "Hosted SAM3-compatible",
        "capabilityName": "sam3-hosted",
        "kind": "discovery_provider",
        "locality": "hosted",
        "implemented": True,
        "runsInLocalWorker": True,
        "credentialRequired": True,
        "credentialFields": [
            {"name": "api_key", "label": "API key", "env": "SAM3_HOSTED_API_KEY", "required": True},
        ],
        "endpointField": {"name": "endpoint", "label": "Endpoint URL", "env": "SAM3_HOSTED_URL", "required": True},
        "hostedProfiles": SAM3_HOSTED_PROFILES,
        "defaultHostedProfile": "roboflow-sam3-pcs",
        "modelOptions": [
            {"id": "sam3/sam3_final", "label": "Roboflow sam3/sam3_final"},
            {"id": "fal-ai/sam-3/image", "label": "Fal fal-ai/sam-3/image"},
            {"id": "auto", "label": "Provider default"},
            {"id": "sam3/default", "label": "SAM3 default"},
            {"id": CUSTOM_MODEL_ID, "label": "Custom hosted SAM3 model id"},
        ],
        "defaultModel": "auto",
        "customModelAllowed": True,
        "capabilities": ["hosted concept discovery", "hosted exemplar discovery", "hosted tracking"],
        "supportedGoals": ["trace_one_object", "trace_all_objects", "text_detector"],
        "supportedPromptTypes": ["box"],
        "supportsConcept": True,
        "supportsExemplar": True,
        "supportsAutoMasks": True,
        "supportsTracking": True,
        "hardware": "Remote provider",
        "cost": {"status": "unknown_provider_cost", "label": "Provider billed"},
        "privacy": "Frames or frame-derived data may leave this machine when hosted calls are enabled.",
        "warning": "Hosted SAM3 is opt-in. Confirm cost and privacy before sending frames off-device.",
        "docs": "docs/security/api_keys.md",
    },
    {
        "id": "sam3-concept",
        "name": "SAM3 concept",
        "capabilityName": "sam3-concept",
        "kind": "discovery_provider",
        "locality": "local",
        "implemented": False,
        "runsInLocalWorker": False,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "sam3/local-model-path", "label": "Configured SAM3 concept model"}],
        "defaultModel": "sam3/local-model-path",
        "customModelAllowed": True,
        "capabilities": ["text concept discovery", "open-vocabulary instances", "mock candidates"],
        "hardware": "CUDA-capable SAM3 runtime",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime when SAM3 is installed there.",
        "warning": "Real concept discovery requires SAM3. Mock mode is available for Runtime API smoke checks.",
        "docs": "docs/discovery_providers.md",
    },
    {
        "id": "sam3-exemplar",
        "name": "SAM3 exemplar",
        "capabilityName": "sam3-exemplar",
        "kind": "discovery_provider",
        "locality": "local",
        "implemented": False,
        "runsInLocalWorker": False,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "sam3/local-model-path", "label": "Configured SAM3 exemplar model"}],
        "defaultModel": "sam3/local-model-path",
        "customModelAllowed": True,
        "capabilities": ["visual exemplar discovery", "similar object instances", "mock candidates"],
        "hardware": "CUDA-capable SAM3 runtime",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime when SAM3 is installed there.",
        "warning": "Real exemplar discovery requires SAM3. Mock mode is available for Runtime API smoke checks.",
        "docs": "docs/discovery_providers.md",
    },
    {
        "id": "sam3-auto-masks",
        "name": "SAM3 auto masks",
        "capabilityName": "sam3-auto-masks",
        "kind": "discovery_provider",
        "locality": "local",
        "implemented": False,
        "runsInLocalWorker": False,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "sam3/local-model-path", "label": "Configured SAM3 auto proposal model"}],
        "defaultModel": "sam3/local-model-path",
        "customModelAllowed": True,
        "capabilities": ["higher recall proposals", "semantic masks", "mock candidates"],
        "hardware": "CUDA-capable SAM3 runtime",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime when SAM3 is installed there.",
        "warning": "Real SAM3 auto masks require SAM3. Mock mode is available for Runtime API smoke checks.",
        "docs": "docs/discovery_providers.md",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter LLM/VLM",
        "capabilityName": "openrouter",
        "kind": "llm_provider",
        "locality": "hosted",
        "implemented": True,
        "runsInLocalWorker": False,
        "credentialRequired": True,
        "credentialFields": [
            {"name": "api_key", "label": "API key", "env": "OPENROUTER_API_KEY", "required": True},
        ],
        "baseUrlField": {"name": "base_url", "label": "Base URL", "env": "OPENROUTER_BASE_URL", "required": False},
        "modelOptions": [
            {"id": "openrouter/auto", "label": "OpenRouter auto"},
            {"id": CUSTOM_MODEL_ID, "label": "Custom OpenRouter model id"},
        ],
        "defaultModel": "openrouter/auto",
        "customModelAllowed": True,
        "capabilities": ["LLM reasoning", "VLM/object identification", "labels"],
        "hardware": "Remote provider",
        "cost": {"status": "unknown_provider_cost", "label": "Provider billed"},
        "privacy": "Text prompts and any future VLM payloads are sent to a hosted provider.",
        "warning": "OpenRouter is for reasoning only. It is not a segmentation or mask provider.",
        "docs": "docs/ai_provider_architecture.md",
    },
    {
        "id": "openai",
        "name": "OpenAI planning",
        "capabilityName": "openai",
        "kind": "llm_provider",
        "locality": "hosted",
        "implemented": True,
        "runsInLocalWorker": False,
        "credentialRequired": True,
        "credentialFields": [
            {"name": "api_key", "label": "API key", "env": "OPENAI_API_KEY", "required": True},
        ],
        "baseUrlField": {"name": "base_url", "label": "Base URL", "env": "OPENAI_BASE_URL", "required": False},
        "modelOptions": [
            {"id": "gpt-5.4-mini", "label": "GPT-5.4 mini"},
            {"id": "gpt-5.5", "label": "GPT-5.5"},
            {"id": CUSTOM_MODEL_ID, "label": "Custom OpenAI model id"},
        ],
        "defaultModel": "gpt-5.4-mini",
        "customModelAllowed": True,
        "capabilities": ["intent parsing", "run planning", "labels", "troubleshooting"],
        "hardware": "Remote provider",
        "cost": {"status": "unknown_provider_cost", "label": "Provider billed"},
        "privacy": "Text prompts and redacted project context are sent to OpenAI only after hosted calls are explicitly enabled.",
        "warning": "OpenAI planning proposes run configs only. It is not a segmentation or mask provider.",
        "docs": "docs/local_ui.md",
    },
    {
        "id": "text_detector",
        "name": "Text detector",
        "capabilityName": "text_detector",
        "kind": "discovery_provider",
        "locality": "local",
        "implemented": False,
        "runsInLocalWorker": False,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "detector/local-model-path", "label": "Configured detector"}],
        "defaultModel": "detector/local-model-path",
        "customModelAllowed": True,
        "capabilities": ["text-guided boxes", "object candidates"],
        "hardware": "CPU/GPU depending on detector package",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime when a detector is configured.",
        "warning": "The current text detector path is scaffolded and remains capability-gated.",
        "docs": "docs/provider_capabilities.md",
    },
    {
        "id": "class_detector",
        "name": "Known-class detector",
        "capabilityName": "class_detector",
        "kind": "discovery_provider",
        "locality": "local",
        "implemented": False,
        "runsInLocalWorker": False,
        "credentialRequired": False,
        "credentialFields": [],
        "modelOptions": [{"id": "yolo/local-model-path", "label": "Configured class model"}],
        "defaultModel": "yolo/local-model-path",
        "customModelAllowed": True,
        "capabilities": ["known-class boxes", "object candidates"],
        "hardware": "CPU/GPU depending on detector package",
        "cost": {"status": "zero_local", "label": "No hosted cost"},
        "privacy": "Frames stay inside the selected runtime when a detector is configured.",
        "warning": "The current class detector path is scaffolded and remains capability-gated.",
        "docs": "docs/provider_capabilities.md",
    },
]

PROVIDER_BY_ID = {provider["id"]: provider for provider in PROVIDER_DEFINITIONS}


def provider_catalog() -> dict[str, Any]:
    return {"format": PROVIDER_CATALOG_FORMAT, "providers": copy.deepcopy(PROVIDER_DEFINITIONS)}


def hosted_profiles_for(provider_id: str) -> list[dict[str, Any]]:
    return copy.deepcopy(HOSTED_PROFILES_BY_PROVIDER.get(provider_id, []))


def _default_hosted_profile_id(definition: Mapping[str, Any]) -> str:
    profiles = list(definition.get("hostedProfiles") or [])
    return str(definition.get("defaultHostedProfile") or (profiles[0]["id"] if profiles else "") or "")


def _selected_hosted_profile_id(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> str:
    requested = str(settings.get("hosted_profile_id") or _default_hosted_profile_id(definition)).strip()
    profiles = {str(profile["id"]): profile for profile in definition.get("hostedProfiles") or []}
    if requested and requested in profiles:
        return requested
    return _default_hosted_profile_id(definition)


def _settings_with_environment_profile(
    provider_id: str,
    settings: Mapping[str, Any],
    environ: Mapping[str, str],
) -> dict[str, Any]:
    enriched = dict(settings)
    if enriched.get("hosted_profile_id"):
        return enriched
    if provider_id == "sam2-hosted":
        if environ.get("HOSTED_SEGMENTATION_API_KEY") or environ.get("HOSTED_SEGMENTATION_URL"):
            enriched["hosted_profile_id"] = "custom-sam2-compatible"
        elif environ.get("REPLICATE_API_TOKEN"):
            enriched["hosted_profile_id"] = "replicate-sam2-video"
    elif provider_id == "sam3-hosted":
        if environ.get("SAM3_HOSTED_API_KEY") or environ.get("SAM3_HOSTED_URL"):
            enriched["hosted_profile_id"] = "custom-sam3-compatible"
        elif environ.get("FAL_KEY"):
            enriched["hosted_profile_id"] = "fal-sam3-image"
        elif environ.get("ROBOFLOW_API_KEY"):
            enriched["hosted_profile_id"] = "roboflow-sam3-pcs"
    return enriched


def _profile_definition(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> Mapping[str, Any]:
    profile_id = _selected_hosted_profile_id(definition, settings)
    for profile in definition.get("hostedProfiles") or []:
        if str(profile["id"]) == profile_id:
            return profile
    return definition


def _profiled_definition(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> dict[str, Any]:
    profile = _profile_definition(definition, settings)
    merged = dict(definition)
    if profile is not definition:
        for key in ("credentialFields", "endpointField", "modelOptions", "defaultModel", "docs", "warning"):
            if key in profile:
                merged[key] = profile[key]
    return merged


def redact_secret_value(value: str | None, *, provider_id: str = "secret") -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) < 9:
        return f"<redacted:{provider_id}>"
    return f"{text[:3]}...{text[-4:]}"


def redact_secret_text(value: Any) -> str:
    text = str(value)
    text = SIGNED_URL_QUERY_RE.sub(lambda match: f"{match.group(1)}?[REDACTED_QUERY]", text)
    text = BEARER_RE.sub("Bearer [REDACTED]", text)
    text = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    for pattern in SECRET_VALUE_PATTERNS:
        text = pattern.sub(lambda match: redact_secret_value(match.group(0)), text)
    return text


def redact_secret_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): ("[REDACTED]" if _is_secret_key(key) else redact_secret_payload(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secret_payload(item) for item in value]
    if isinstance(value, str):
        return redact_secret_text(value)
    return value


def provider_settings_for_capabilities(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    environ = environ or os.environ
    rows = _settings_rows(conn, user_id=user_id)
    return {
        provider_id: _capability_override(provider_id, rows.get(provider_id), environ)
        for provider_id in PROVIDER_BY_ID
    }


def provider_settings_response(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environ = environ or os.environ
    rows = _settings_rows(conn, user_id=user_id)
    providers = [
        _public_provider_state(provider, rows.get(provider["id"]), environ)
        for provider in PROVIDER_DEFINITIONS
    ]
    return {
        "format": PROVIDER_SETTINGS_FORMAT,
        "catalogFormat": PROVIDER_CATALOG_FORMAT,
        "providers": providers,
        "defaults": {
            "safeMaskProvider": "sam2-local",
            "debugMaskProvider": "mock",
            "safeReasoningProvider": "none",
            "hostedCallsDefault": "disabled",
            "credentialPrecedence": ["environment", "local_settings", "unset"],
        },
        "redaction": {
            "policy": "Raw keys are never returned by the Runtime API.",
            "displayExample": "sk-...abcd",
            "environmentOverridesLocal": True,
        },
    }


def provider_runtime_settings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return raw server-side provider settings for connector execution.

    This function is for backend-only use. Do not return its payload from a
    public API route because it may include raw credential material.
    """

    environ = environ or os.environ
    definition = _definition(provider_id)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)
    settings = _settings_with_environment_profile(provider_id, settings, environ)
    profiled_definition = _profiled_definition(definition, settings)
    profile = _profile_definition(definition, settings)
    api_key = ""
    credential_source = "none"
    credential_values: dict[str, str] = {}
    credential_sources: dict[str, str] = {}
    for credential_field in profiled_definition.get("credentialFields", []):
        name = str(credential_field["name"])
        env = str(credential_field.get("env") or "")
        env_value = environ.get(env)
        if name == "hf_token" and not env_value:
            env_value = environ.get("HUGGINGFACE_HUB_TOKEN")
        local_value = secrets.get(name)
        value = str(env_value or local_value or "")
        source = "environment" if env_value else "local_settings" if local_value else "unset"
        credential_values[name] = value
        credential_sources[name] = source
        if name == "api_key":
            api_key = value
            credential_source = source

    base_url_field = profiled_definition.get("baseUrlField")
    base_url = ""
    base_url_source = "unset"
    if base_url_field:
        env = str(base_url_field.get("env") or "")
        env_value = environ.get(env)
        local_value = settings.get("base_url")
        base_url = str(env_value or local_value or "")
        base_url_source = "environment" if env_value else "local_settings" if local_value else "unset"

    endpoint_field = profiled_definition.get("endpointField")
    endpoint = ""
    endpoint_source = "unset"
    if endpoint_field:
        env = str(endpoint_field.get("env") or "")
        env_value = environ.get(env)
        local_value = settings.get("endpoint")
        endpoint = str(env_value or local_value or "")
        endpoint_source = "environment" if env_value else "local_settings" if local_value else "unset"

    if not endpoint and profile.get("defaultEndpoint"):
        endpoint = str(profile.get("defaultEndpoint") or "")
        endpoint_source = "profile_default"

    readiness = _readiness(definition, settings, secrets, environ)
    runtime_model_info = _runtime_model_info(definition, settings, secrets, environ)
    model_cache = runtime_model_info["modelCache"]
    runtime_verification = _runtime_verification_state(definition, settings, model_cache, environ)
    return {
        "providerId": provider_id,
        "hosted_profile_id": _selected_hosted_profile_id(definition, settings),
        "effective_profile": _public_profile(profile),
        "api_key": api_key,
        "credential_source": credential_source,
        "base_url": base_url,
        "base_url_source": base_url_source,
        "endpoint": endpoint,
        "endpoint_source": endpoint_source,
        "credentials": credential_values,
        "credential_sources": credential_sources,
        "hf_token": str(
            environ.get("HF_TOKEN")
            or environ.get("HUGGINGFACE_HUB_TOKEN")
            or credential_values.get("hf_token")
            or ""
        ),
        "selected_model": runtime_model_info["selectedModel"],
        "runtime_model": runtime_model_info["runtimeModel"],
        "runtime_model_source": runtime_model_info["runtimeModelSource"],
        "resolved_model_dir": runtime_model_info["resolvedModelDir"],
        "model_cache": model_cache,
        "runtime_verification": runtime_verification,
        "allow_hosted": bool(settings.get("allow_hosted", False)),
        "sam2_checkpoint_path": str(environ.get("SAM2_LOCAL_CHECKPOINT") or settings.get("sam2_checkpoint_path") or ""),
        "sam2_model_config_path": str(environ.get("SAM2_LOCAL_CONFIG") or settings.get("sam2_model_config_path") or ""),
        "sam2_device": str(environ.get("SAM2_LOCAL_DEVICE") or settings.get("sam2_device") or ""),
        "sam2_hf_device": str(environ.get("SAM2_HF_DEVICE") or settings.get("sam2_hf_device") or ""),
        "sam3_model_path": str(environ.get("SAM3_LOCAL_MODEL") or settings.get("sam3_model_path") or ""),
        "sam3_device": str(environ.get("SAM3_LOCAL_DEVICE") or settings.get("sam3_device") or ""),
        "configured": readiness["configured"],
        "readiness": readiness,
        "settings_source": "local_settings" if row is not None else "default",
    }


def provider_runtime_model_info(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return backend-only runtime model resolution for cached providers."""

    environ = environ or os.environ
    definition = _definition(provider_id)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)
    settings = _settings_with_environment_profile(provider_id, settings, environ)
    return _runtime_model_info(definition, settings, secrets, environ)


def record_provider_model_cache(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    model_id: str,
    local_model_dir: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Persist a resolved from_pretrained directory without exposing it publicly."""

    definition = _definition(provider_id)
    if provider_id not in LOCAL_MODEL_CACHE_PROVIDER_IDS:
        return provider_settings_response(conn, user_id=user_id, environ=environ)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)
    settings["cached_model_id"] = str(model_id or "").strip()
    settings["resolved_model_dir"] = str(local_model_dir or "").strip()
    settings["model_cache_updated_at"] = utc_now()
    for key in LOCAL_MODEL_RUNTIME_KEYS:
        settings.pop(key, None)
    try:
        model_path = Path(str(model_id or "")).expanduser()
        if model_path.exists() and model_path.is_dir():
            settings["selected_model"] = CUSTOM_MODEL_ID
            settings["custom_model_id"] = str(model_path)
    except OSError:
        pass
    _upsert_provider_settings(conn, user_id=user_id, provider_id=provider_id, settings=settings, secrets=secrets, existing=row)
    return provider_settings_response(conn, user_id=user_id, environ=environ)


def record_provider_runtime_verification(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    verification: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Persist a backend-only proof that a cached local model loaded and warmed up."""

    definition = _definition(provider_id)
    if provider_id not in LOCAL_MODEL_CACHE_PROVIDER_IDS:
        return provider_settings_response(conn, user_id=user_id, environ=environ)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)
    runtime_info = _runtime_model_info(definition, settings, secrets, environ or os.environ)
    device_requested = str(verification.get("deviceRequested") or "")
    device_actual = str(verification.get("deviceActual") or "")
    loaded_on_cuda = bool(verification.get("loadedOnCuda"))
    loaded_on_mps = bool(verification.get("loadedOnMps"))
    accelerator_kind = str(
        verification.get("acceleratorKind")
        or _runtime_accelerator_kind(device_actual, device_requested, loaded_on_cuda=loaded_on_cuda, loaded_on_mps=loaded_on_mps)
    )
    warmup_status = str(verification.get("warmupStatus") or verification.get("status") or "")
    runtime_proof_status = str(verification.get("runtimeProofStatus") or "")
    if not runtime_proof_status:
        runtime_proof_status = "verified" if warmup_status == "succeeded" else "failed" if warmup_status else "not_verified"
    settings["runtime_verified_at"] = utc_now()
    settings["runtime_verified_model_id"] = str(runtime_info.get("selectedModel") or runtime_info.get("modelCache", {}).get("model") or "")
    settings["runtime_device_requested"] = device_requested
    settings["runtime_device_actual"] = device_actual
    settings["runtime_kind"] = str(verification.get("runtimeKind") or "")
    settings["runtime_accelerator_kind"] = accelerator_kind
    settings["runtime_proof_status"] = runtime_proof_status
    settings["runtime_loaded_on_cuda"] = loaded_on_cuda
    settings["runtime_loaded_on_mps"] = loaded_on_mps
    settings["runtime_cuda_available"] = bool(verification.get("cudaAvailable"))
    settings["runtime_mps_available"] = bool(verification.get("mpsAvailable"))
    settings["runtime_gpu_memory_before"] = _safe_runtime_snapshot(verification.get("gpuMemoryBefore"))
    settings["runtime_gpu_memory_after"] = _safe_runtime_snapshot(verification.get("gpuMemoryAfter"))
    settings["runtime_warmup_status"] = warmup_status
    _upsert_provider_settings(conn, user_id=user_id, provider_id=provider_id, settings=settings, secrets=secrets, existing=row)
    return provider_settings_response(conn, user_id=user_id, environ=environ)


def provider_advanced_local_paths(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return intentionally raw runtime paths for Workspace Advanced display only."""

    if provider_id != "sam3-local":
        return {
            "format": "motionjson.provider_advanced_local_paths.v0.1",
            "providerId": provider_id,
            "available": False,
            "message": "Advanced local path display is only available for SAM3 Scene Sweep.",
        }
    runtime = provider_runtime_settings(conn, user_id=user_id, provider_id=provider_id, environ=environ)
    model_cache = runtime.get("model_cache") if isinstance(runtime.get("model_cache"), Mapping) else {}
    raw_dir = str(runtime.get("resolved_model_dir") or "").strip() if model_cache.get("cached") else ""
    return {
        "format": "motionjson.provider_advanced_local_paths.v0.1",
        "providerId": provider_id,
        "available": bool(raw_dir),
        "model": str(model_cache.get("model") or runtime.get("selected_model") or SAM3_HF_REPO_ID),
        "serverPathRecorded": bool(model_cache.get("serverPathRecorded") and raw_dir),
        "cachedSceneSweepModelDir": raw_dir,
        "localModelDirDisplayRaw": raw_dir,
        "localPathDisplay": "[LOCAL_PATH_REDACTED]" if raw_dir else "",
        "recordedAt": model_cache.get("recordedAt") or None,
        "message": "Cached SAM3 Scene Sweep directory is available for Advanced display." if raw_dir else "No cached SAM3 Scene Sweep directory is recorded yet.",
    }


def _module_available(name: str) -> bool:
    if name in sys.modules:
        return True
    try:
        return find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _local_from_pretrained_dir_status(path: Path) -> tuple[bool, str]:
    try:
        if not path.exists():
            return False, "Local model directory does not exist."
        if not path.is_dir():
            return False, "Selected model path is not a directory. Use a Hugging Face repo id or local from_pretrained directory."
        if not os.access(path, os.R_OK):
            return False, "Local model directory is not readable by this process."
        if any(path.rglob("*.incomplete")):
            return False, "Local model directory contains incomplete download files. Retry Cache model after checking disk/network access."
        if not (path / "config.json").exists():
            return False, "Local model directory is missing config.json and may not be loadable with from_pretrained."
    except OSError as exc:
        return False, f"Local model directory could not be inspected: {type(exc).__name__}: {exc}."
    return True, "Local from_pretrained model directory is available."


def _looks_like_local_model_path(raw: str) -> bool:
    return raw.startswith(("/", ".", "~")) or raw.lower().startswith("file://") or "\\" in raw


def _looks_like_hf_repo_id(raw: str) -> bool:
    return "/" in raw and not _looks_like_local_model_path(raw) and not raw.endswith(".pt")


def _is_redacted_public_placeholder(value: Any) -> bool:
    return str(value or "").strip() == "[LOCAL_PATH_REDACTED]"


def _hf_cache_error_message(exc: Exception, model_id: str) -> str:
    name = type(exc).__name__
    text = redact_secret_text(str(exc) or name)
    lowered = text.lower()
    if "offline" in lowered:
        return f"Offline mode is enabled and {model_id} is not cached in this runtime. Disable offline mode or cache the model first."
    if "not found" in lowered or "cannot find" in lowered or "localentrynotfound" in name.lower():
        return f"{model_id} is not cached in this runtime yet. Use Cache model after confirming network and disk access."
    if "permission" in lowered or "denied" in lowered:
        return "MotionJSON cannot read the Hugging Face cache directory. Fix local permissions or choose a readable model directory."
    if "no space" in lowered or "enospc" in lowered or "disk" in lowered:
        return "Local disk space is insufficient for this model cache. Free disk space or choose another cache location."
    if "corrupt" in lowered:
        return "The Hugging Face cache entry appears corrupted. Delete the partial cache and run Cache model again."
    return f"Local Hugging Face cache inspection for {model_id} did not find a runnable cache: {text}"


def _model_cache_state(
    definition: Mapping[str, Any],
    settings: Mapping[str, Any],
    secrets: Mapping[str, str],
    environ: Mapping[str, str],
    *,
    include_runtime_path: bool = False,
) -> dict[str, Any]:
    provider_id = str(definition["id"])
    if provider_id not in LOCAL_MODEL_CACHE_PROVIDER_IDS:
        return {"required": False, "cached": True, "status": "not_required", "networkAttempted": False}

    model_id = _runtime_effective_model(definition, settings, environ)
    cached_model_id = str(settings.get("cached_model_id") or "").strip()
    saved_dir = str(settings.get("resolved_model_dir") or "").strip()
    token = str(environ.get("HF_TOKEN") or environ.get("HUGGINGFACE_HUB_TOKEN") or secrets.get("hf_token") or "").strip()
    base: dict[str, Any] = {
        "required": True,
        "providerId": provider_id,
        "model": model_id,
        "cached": False,
        "status": "not_cached",
        "source": "unresolved",
        "networkAttempted": False,
        "localPathKnown": False,
        "serverPathRecorded": False,
        "recordedAt": settings.get("model_cache_updated_at") or None,
        "message": "Model cache has not been resolved yet.",
    }

    def cached_state(local_dir: str, *, source: str, message: str) -> dict[str, Any]:
        recorded = bool(saved_dir and source == "saved_cache")
        result = {
            **base,
            "cached": True,
            "status": "cached",
            "source": source,
            "localPathKnown": True,
            "serverPathRecorded": recorded,
            "localPathDisplay": "[LOCAL_PATH_REDACTED]",
            "pathSummary": "Resolved model directory is recorded server-side and redacted in browser responses."
            if recorded
            else "Resolved model directory was found in the runtime cache and is redacted in browser responses.",
            "message": message,
        }
        if include_runtime_path:
            result["localModelDir"] = local_dir
            result["runtimeModel"] = local_dir
        return result

    if saved_dir and (not cached_model_id or cached_model_id == model_id):
        saved_path = Path(saved_dir).expanduser()
        ok, detail = _local_from_pretrained_dir_status(saved_path)
        if ok:
            return cached_state(str(saved_path), source="saved_cache", message="Previously cached runtime model directory is available.")
        base.update({"status": "invalid_cache", "source": "saved_cache", "message": detail, "nextAction": "cache_model"})
        return base

    raw = str(model_id or "").strip()
    if not raw:
        base.update({"status": "missing_model", "message": "No model id or runtime model directory is selected.", "nextAction": "choose_model"})
        return base
    if raw == "[LOCAL_PATH_REDACTED]":
        base.update({"status": "invalid_model", "message": "The saved model path was redacted in the browser. Choose the runtime model directory again from Model setup.", "nextAction": "choose_model"})
        return base
    if raw.endswith(".pt"):
        base.update(
            {
                "status": "invalid_model",
                "message": "A single .pt checkpoint is not valid for this from_pretrained model path. Choose a Hugging Face repo id or runtime model directory.",
                "nextAction": "choose_model",
            }
        )
        return base
    if _looks_like_local_model_path(raw):
        path = Path(raw.replace("file://", "", 1)).expanduser()
        ok, detail = _local_from_pretrained_dir_status(path)
        if ok:
            return cached_state(str(path), source="local_directory", message=detail)
        base.update({"status": "invalid_model", "source": "local_directory", "message": detail, "nextAction": "choose_model"})
        return base
    if not _looks_like_hf_repo_id(raw):
        base.update({"status": "invalid_model", "message": f"{raw} is neither a Hugging Face repo id nor a runtime model directory.", "nextAction": "choose_model"})
        return base
    if not _module_available("huggingface_hub"):
        base.update({"status": "cache_unknown", "message": "huggingface_hub is not installed, so MotionJSON cannot inspect the runtime model cache. Install the Transformers setup extra first.", "nextAction": "install"})
        return base
    try:
        from huggingface_hub import snapshot_download  # type: ignore

        local_dir = snapshot_download(repo_id=raw, token=token or None, local_files_only=True)
        path = Path(str(local_dir)).expanduser()
        ok, detail = _local_from_pretrained_dir_status(path)
        if not ok:
            base.update({"status": "invalid_cache", "source": "hf_cache", "message": detail, "nextAction": "cache_model"})
            return base
        return cached_state(str(path), source="hf_cache", message=f"{raw} is already available in the local Hugging Face cache.")
    except Exception as exc:
        base.update({"status": "not_cached", "source": "hf_cache", "message": _hf_cache_error_message(exc, raw), "nextAction": "cache_model"})
        return base


def _runtime_model_source(
    definition: Mapping[str, Any],
    settings: Mapping[str, Any],
    environ: Mapping[str, str],
    model_cache: Mapping[str, Any],
) -> str:
    provider_id = str(definition.get("id") or "")
    if model_cache.get("serverPathRecorded") is True:
        return "saved_cache"
    if settings.get("selected_model"):
        return "selected_model"
    env_defaults = {
        "sam2-hf-auto-masks": "SAM2_HF_AUTO_MASKS_MODEL",
        "sam3-local": "SAM3_TRACKER_MODEL",
    }
    env = env_defaults.get(provider_id)
    if env and environ.get(env):
        return "selected_model"
    return "default"


def _runtime_model_info(
    definition: Mapping[str, Any],
    settings: Mapping[str, Any],
    secrets: Mapping[str, str],
    environ: Mapping[str, str],
) -> dict[str, Any]:
    selected_model = _runtime_effective_model(definition, settings, environ)
    model_cache = _model_cache_state(definition, settings, secrets, environ, include_runtime_path=True)
    runtime_model = selected_model
    resolved_model_dir = ""
    if str(definition.get("id") or "") in LOCAL_MODEL_CACHE_PROVIDER_IDS and model_cache.get("cached") is True:
        local_model_dir = str(model_cache.get("localModelDir") or "").strip()
        if local_model_dir:
            runtime_model = local_model_dir
            resolved_model_dir = local_model_dir
    source = _runtime_model_source(definition, settings, environ, model_cache)
    model_cache = {
        **dict(model_cache),
        "runtimeModelSource": source,
    }
    return {
        "providerId": str(definition.get("id") or ""),
        "selectedModel": selected_model,
        "runtimeModel": runtime_model,
        "runtimeModelSource": source,
        "resolvedModelDir": resolved_model_dir,
        "modelCache": model_cache,
        "runtimeVerification": _runtime_verification_state(definition, settings, model_cache, environ),
    }


def _safe_runtime_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, Any] = {}
    for key in ("index", "name", "deviceCount", "freeBytes", "totalBytes", "usedBytes", "freeMiB", "totalMiB", "usedMiB"):
        item = value.get(key)
        if isinstance(item, (str, int, float, bool)) or item is None:
            safe[str(key)] = item
    return safe


def _runtime_accelerator_kind(
    device_actual: str,
    device_requested: str = "",
    *,
    loaded_on_cuda: bool = False,
    loaded_on_mps: bool = False,
) -> str:
    actual = str(device_actual or "").strip().lower()
    requested = str(device_requested or "").strip().lower()
    if loaded_on_cuda or actual.startswith("cuda"):
        return "cuda"
    if loaded_on_mps or actual.startswith("mps"):
        return "mps"
    if actual.startswith("cpu") or actual == "-1":
        return "cpu"
    if requested.startswith("cuda") or requested.startswith("mps"):
        return "unknown"
    if requested.startswith("cpu") or requested in {"", "auto"}:
        return "cpu" if actual else "unknown"
    return "unknown"


def _runtime_verification_state(
    definition: Mapping[str, Any],
    settings: Mapping[str, Any],
    model_cache: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environ = environ or os.environ
    provider_id = str(definition.get("id") or "")
    if provider_id not in LOCAL_MODEL_CACHE_PROVIDER_IDS:
        return {"required": False, "verified": True, "status": "not_required"}
    cached = bool(model_cache.get("cached"))
    warmup_status = str(settings.get("runtime_warmup_status") or "").strip()
    verified_at = settings.get("runtime_verified_at") or None
    current_model = str(model_cache.get("model") or _runtime_effective_model(definition, settings, environ) or "").strip()
    verified_model = str(settings.get("runtime_verified_model_id") or "").strip()
    requested_device = _runtime_requested_device(provider_id, settings, environ)
    verified_device = str(settings.get("runtime_device_requested") or "").strip()
    recorded_at = str(model_cache.get("recordedAt") or "")
    model_matches = bool(not verified_model or not current_model or verified_model == current_model)
    device_matches = bool(not verified_device or verified_device == requested_device)
    cache_is_current = bool(not recorded_at or not verified_at or str(verified_at) >= recorded_at)
    requested_lower = requested_device.lower()
    cuda_requested = requested_lower.startswith("cuda")
    mps_requested = requested_lower.startswith("mps")
    loaded_on_cuda = bool(settings.get("runtime_loaded_on_cuda"))
    loaded_on_mps = bool(settings.get("runtime_loaded_on_mps"))
    actual_device = str(settings.get("runtime_device_actual") or "")
    accelerator_kind = str(settings.get("runtime_accelerator_kind") or "").strip().lower() or _runtime_accelerator_kind(
        actual_device,
        requested_device,
        loaded_on_cuda=loaded_on_cuda,
        loaded_on_mps=loaded_on_mps,
    )
    cuda_available = bool(settings.get("runtime_cuda_available"))
    mps_available = bool(settings.get("runtime_mps_available"))
    gpu_memory_before = _safe_runtime_snapshot(settings.get("runtime_gpu_memory_before"))
    gpu_memory_after = _safe_runtime_snapshot(settings.get("runtime_gpu_memory_after"))
    cuda_verified = bool(not cuda_requested or (loaded_on_cuda and actual_device.lower().startswith("cuda")))
    mps_verified = bool(not mps_requested or (loaded_on_mps and actual_device.lower().startswith("mps")))
    device_verified = bool(cuda_verified and mps_verified)
    verified = bool(cached and verified_at and warmup_status == "succeeded" and model_matches and device_matches and cache_is_current and device_verified)
    stale_reasons = []
    if cached and verified_at:
        if not model_matches:
            stale_reasons.append("model changed")
        if not device_matches:
            stale_reasons.append("device changed")
        if not cache_is_current:
            stale_reasons.append("cache changed")
        if cuda_requested and not cuda_verified:
            stale_reasons.append("CUDA placement not verified")
        if mps_requested and not mps_verified:
            stale_reasons.append("MPS placement not verified")
    stale_detail = f" Previous smoke verification is stale because {', '.join(stale_reasons)}." if stale_reasons else ""
    persisted_proof_status = str(settings.get("runtime_proof_status") or "").strip()
    if verified:
        runtime_proof_status = "verified"
        reason_code = ""
    elif cuda_requested and not cuda_verified and verified_at:
        runtime_proof_status = "gpu_device_mismatch"
        reason_code = "gpu_device_mismatch"
    elif mps_requested and not mps_verified and verified_at:
        runtime_proof_status = "gpu_device_mismatch"
        reason_code = "gpu_device_mismatch"
    elif stale_reasons:
        runtime_proof_status = "stale"
        reason_code = "runtime_verification_stale"
    elif persisted_proof_status:
        runtime_proof_status = persisted_proof_status
        reason_code = "runtime_verification_stale" if persisted_proof_status == "stale" else persisted_proof_status if persisted_proof_status.endswith("_mismatch") else ""
    elif warmup_status and warmup_status != "succeeded":
        runtime_proof_status = "failed"
        reason_code = "runtime_warmup_failed"
    else:
        runtime_proof_status = "not_verified"
        reason_code = ""
    return {
        "required": True,
        "verified": verified,
        "status": "verified" if verified else "not_verified",
        "runtimeKind": settings.get("runtime_kind") or "",
        "acceleratorKind": accelerator_kind,
        "runtimeProofStatus": runtime_proof_status,
        "deviceRequested": verified_device or requested_device,
        "deviceActual": actual_device,
        "loadedOnCuda": loaded_on_cuda,
        "loadedOnMps": loaded_on_mps,
        "cudaAvailable": cuda_available,
        "mpsAvailable": mps_available,
        "gpuMemoryBefore": gpu_memory_before,
        "gpuMemoryAfter": gpu_memory_after,
        "warmupStatus": warmup_status or "not_run",
        "lastVerifiedAt": verified_at,
        "reasonCode": reason_code,
        "message": (
            f"Cached model loaded and warmed up successfully on {accelerator_kind.upper() if accelerator_kind in {'cuda', 'mps'} else accelerator_kind}."
            if verified
            else f"Run a smoke test to load the cached model on the selected device and warm it up.{stale_detail}"
            if cached
            else "Cache the model before running runtime warmup."
        ),
    }


def _runtime_requested_device(provider_id: str, settings: Mapping[str, Any], environ: Mapping[str, str]) -> str:
    if provider_id == "sam3-local":
        return str(environ.get("SAM3_LOCAL_DEVICE") or settings.get("sam3_device") or "cuda")
    if provider_id == "sam2-hf-auto-masks":
        return str(environ.get("SAM2_HF_DEVICE") or settings.get("sam2_hf_device") or "cpu")
    return ""


def _apply_settings_payload(
    definition: Mapping[str, Any],
    settings: dict[str, Any],
    secrets: dict[str, str],
    payload: Mapping[str, Any],
    *,
    validate_profile: bool = True,
) -> None:
    runtime_sensitive_changed = False
    provider_id = str(definition.get("id") or "")

    def assign_runtime_sensitive(key: str, value: Any, *, default: Any = "") -> None:
        nonlocal runtime_sensitive_changed
        current = settings.get(key)
        comparable_current = current if current not in (None, "") else default
        comparable_next = value if value not in (None, "") else default
        if comparable_current != comparable_next:
            runtime_sensitive_changed = True
        settings[key] = value

    if "enabled" in payload:
        settings["enabled"] = bool(payload.get("enabled"))
    if "selectedModel" in payload or "selected_model" in payload:
        selected_model = _optional_text(payload.get("selectedModel", payload.get("selected_model")))
        if not _is_redacted_public_placeholder(selected_model):
            assign_runtime_sensitive("selected_model", selected_model, default=definition.get("defaultModel") or "")
    if "customModelId" in payload or "custom_model_id" in payload:
        custom_model_id = _optional_text(payload.get("customModelId", payload.get("custom_model_id")))
        if not _is_redacted_public_placeholder(custom_model_id) and custom_model_id:
            assign_runtime_sensitive("custom_model_id", custom_model_id)
    if "endpoint" in payload:
        settings["endpoint"] = _optional_url(payload.get("endpoint"), "endpoint")
    if "baseUrl" in payload or "base_url" in payload:
        settings["base_url"] = _optional_url(payload.get("baseUrl", payload.get("base_url")), "baseUrl")
    if "allowHosted" in payload or "allow_hosted" in payload:
        settings["allow_hosted"] = bool(payload.get("allowHosted", payload.get("allow_hosted")))
    if "hostedProfileId" in payload or "hosted_profile_id" in payload:
        profile_id = _optional_text(payload.get("hostedProfileId", payload.get("hosted_profile_id")))
        if profile_id and validate_profile:
            _ensure_valid_hosted_profile(definition, profile_id)
        settings["hosted_profile_id"] = profile_id
    if "sam2CheckpointPath" in payload or "sam2_checkpoint_path" in payload:
        value = _optional_text(payload.get("sam2CheckpointPath", payload.get("sam2_checkpoint_path")))
        if not _is_redacted_public_placeholder(value):
            settings["sam2_checkpoint_path"] = value
    if "sam2ModelConfigPath" in payload or "sam2_model_config_path" in payload:
        value = _optional_text(payload.get("sam2ModelConfigPath", payload.get("sam2_model_config_path")))
        if not _is_redacted_public_placeholder(value):
            settings["sam2_model_config_path"] = value
    if "sam2Device" in payload or "sam2_device" in payload:
        settings["sam2_device"] = _optional_text(payload.get("sam2Device", payload.get("sam2_device")))
    if "sam2HfDevice" in payload or "sam2_hf_device" in payload:
        assign_runtime_sensitive("sam2_hf_device", _optional_text(payload.get("sam2HfDevice", payload.get("sam2_hf_device"))), default="cpu")
    if "sam3ModelPath" in payload or "sam3_model_path" in payload:
        value = _optional_text(payload.get("sam3ModelPath", payload.get("sam3_model_path")))
        if not _is_redacted_public_placeholder(value):
            settings["sam3_model_path"] = value
    if "sam3Device" in payload or "sam3_device" in payload:
        assign_runtime_sensitive("sam3_device", _optional_text(payload.get("sam3Device", payload.get("sam3_device"))), default="cuda")

    if runtime_sensitive_changed and provider_id in LOCAL_MODEL_CACHE_PROVIDER_IDS:
        had_runtime_verification = any(settings.get(key) for key in LOCAL_MODEL_RUNTIME_KEYS)
        for key in LOCAL_MODEL_RUNTIME_KEYS:
            settings.pop(key, None)
        if had_runtime_verification:
            settings["runtime_proof_status"] = "stale"

    profiled_definition = _profiled_definition(definition, settings)
    for field in profiled_definition.get("credentialFields", []):
        name = str(field["name"])
        camel_name = _credential_payload_name(name)
        value = payload.get(camel_name, payload.get(name))
        clear_value = bool(
            payload.get(f"clear{camel_name[0].upper()}{camel_name[1:]}")
            or payload.get(f"clear_{name}")
            or payload.get(f"{camel_name}Action") == "clear"
            or payload.get(f"{name}_action") == "clear"
        )
        if clear_value:
            secrets.pop(name, None)
        elif isinstance(value, str) and value.strip():
            _ensure_accepts_credentials(profiled_definition)
            secrets[name] = _clean_credential(str(definition["id"]), field, value)


def save_provider_settings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    payload: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    provider_id = str(payload.get("providerId") or payload.get("provider_id") or "").strip()
    definition = _definition(provider_id)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)
    if provider_id == "sam2-hosted" and not settings.get("hosted_profile_id") and payload.get("endpoint"):
        settings["hosted_profile_id"] = "custom-sam2-compatible"
    if provider_id == "sam3-hosted" and not settings.get("hosted_profile_id") and payload.get("endpoint"):
        settings["hosted_profile_id"] = "custom-sam3-compatible"

    _apply_settings_payload(definition, settings, secrets, payload)

    _validate_model_settings(definition, settings)
    _upsert_provider_settings(conn, user_id=user_id, provider_id=provider_id, settings=settings, secrets=secrets, existing=row)
    return provider_settings_response(conn, user_id=user_id, environ=environ)


def reset_provider_settings(conn: sqlite3.Connection, *, user_id: str, provider_id: str) -> dict[str, Any]:
    _definition(provider_id)
    conn.execute("DELETE FROM provider_settings WHERE user_id = ? AND provider_id = ?", (user_id, provider_id))
    conn.commit()
    return {"reset": True, "providerId": provider_id}


def test_provider_settings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environ = environ or os.environ
    definition = _definition(provider_id)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)
    settings = _settings_with_environment_profile(provider_id, settings, environ)
    profiled_definition = _profiled_definition(definition, settings)

    missing: list[str] = []
    invalid: list[str] = []
    for field in profiled_definition.get("credentialFields", []):
        name = str(field["name"])
        env = str(field.get("env") or "")
        value = environ.get(env) or secrets.get(name)
        if field.get("required") and not value:
            missing.append(env or name)
        elif value and not _api_key_plausible(value):
            invalid.append(env or name)

    endpoint_field = profiled_definition.get("endpointField")
    if endpoint_field:
        env = str(endpoint_field.get("env") or "")
        endpoint = environ.get(env) or settings.get("endpoint")
        if endpoint_field.get("required") and not endpoint:
            missing.append(env or "endpoint")
        elif endpoint and not _valid_http_url(str(endpoint)):
            invalid.append(env or "endpoint")

    model_status = _model_status(definition, settings)
    if model_status.get("status") == "missing_model":
        missing.append("model")

    if invalid:
        status = "invalid_key"
        message = f"{definition['name']} has a credential with an invalid local format."
    elif missing:
        status = "missing_configuration"
        message = f"{definition['name']} needs setup: {', '.join(missing)}."
    elif definition.get("locality") == "hosted":
        status = "configured"
        message = f"{definition['name']} is configured. No hosted network request was made by this safety check."
    else:
        status = "ready"
        message = f"{definition['name']} does not require API credentials."

    return {
        "format": "motionjson.provider_settings_test.v0.1",
        "providerId": provider_id,
        "status": status,
        "ready": status in {"ready", "configured"},
        "networkAttempted": False,
        "message": redact_secret_text(message),
        "missing": missing,
        "invalid": invalid,
        "model": model_status,
        "hostedProfileId": _selected_hosted_profile_id(definition, settings),
    }


def hosted_sam3_smoke_test(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    payload: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Run an explicit hosted SAM2/SAM3 smoke test without exposing secrets."""

    from motionjson.providers.base import ProviderConfigError, ProviderExecutionError
    from motionjson.providers.hosted_sam import (
        FalSAM3ImageBackend,
        ReplicateSAM2VideoClient,
        RoboflowSAM3ConceptBackend,
    )
    from motionjson.providers.sam3 import HostedSAM3DiscoveryBackend

    environ = environ or os.environ
    provider_id = str(payload.get("providerId") or payload.get("provider_id") or "sam3-hosted")
    if provider_id not in {"sam2-hosted", "sam3-hosted"}:
        raise ValueError("Hosted SAM smoke tests are only available for providerId sam2-hosted or sam3-hosted.")
    definition = _definition(provider_id)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)
    settings = _settings_with_environment_profile(provider_id, settings, environ)
    profile = _profile_definition(definition, settings)
    profiled_definition = _profiled_definition(definition, settings)
    profile_id = _selected_hosted_profile_id(definition, settings)

    endpoint_field = profiled_definition.get("endpointField") or {}
    endpoint_env = str(endpoint_field.get("env") or ("HOSTED_SEGMENTATION_URL" if provider_id == "sam2-hosted" else "SAM3_HOSTED_URL"))
    endpoint = str(environ.get(endpoint_env) or settings.get("endpoint") or profile.get("defaultEndpoint") or "").strip()
    endpoint_source = "environment" if environ.get(endpoint_env) else "local_settings" if endpoint else "unset"
    if endpoint and profile.get("defaultEndpoint") and endpoint == profile.get("defaultEndpoint") and not environ.get(endpoint_env) and not settings.get("endpoint"):
        endpoint_source = "profile_default"
    token_env = str((profiled_definition.get("credentialFields") or [{}])[0].get("env") or ("HOSTED_SEGMENTATION_API_KEY" if provider_id == "sam2-hosted" else "SAM3_HOSTED_API_KEY"))
    api_key = str(environ.get(token_env) or secrets.get("api_key") or "").strip()
    credential_source = "environment" if environ.get(token_env) else "local_settings" if api_key else "unset"
    model_env = "HOSTED_SEGMENTATION_MODEL" if provider_id == "sam2-hosted" else "SAM3_HOSTED_MODEL"
    model = str(environ.get(model_env) or _effective_model(definition, settings) or "auto").strip() or "auto"

    missing: list[str] = []
    invalid: list[str] = []
    if endpoint_field.get("required") and not endpoint:
        missing.append(endpoint_env)
    elif endpoint and not _valid_http_url(endpoint):
        invalid.append(endpoint_env)
    if not api_key:
        missing.append(token_env)
    elif not _api_key_plausible(api_key):
        invalid.append(token_env)

    if invalid:
        raise ValueError(f"Hosted SAM smoke test has invalid configuration: {', '.join(invalid)}.")
    if missing:
        raise ValueError(f"Hosted SAM smoke test needs setup: {', '.join(missing)}.")

    allow_network = _truthy(payload.get("allowNetwork", payload.get("allow_network")))
    acknowledge_cost_privacy = _truthy(
        payload.get(
            "acknowledgeCostPrivacy",
            payload.get("acknowledge_cost_privacy", payload.get("costPrivacyAcknowledged")),
        )
    )
    hosted_ack = bool(settings.get("allow_hosted")) or _truthy(payload.get("allowHosted", payload.get("allow_hosted")))
    if not allow_network or not acknowledge_cost_privacy:
        raise ValueError(
            "Hosted SAM smoke test requires allowNetwork=true and acknowledgeCostPrivacy=true before sending a frame."
        )
    if not hosted_ack:
        raise ValueError("Hosted SAM smoke test requires the hosted cost/privacy opt-in in settings or allowHosted=true.")

    timeout_seconds = min(max(_float_payload(payload, "timeoutSeconds", 60.0), 1.0), 300.0)
    retries = min(max(int(_float_payload(payload, "retries", 1.0)), 0), 3)
    try:
        prompt = str(payload.get("prompt") or "object").strip() or "object"
        if provider_id == "sam2-hosted" and profile_id == "replicate-sam2-video":
            client = ReplicateSAM2VideoClient(
                source_video="motionjson-smoke.mp4",
                api_key=api_key,
                model=model,
                transport=transport,
            )
            smoke = client.smoke_test()
        elif provider_id == "sam3-hosted" and profile_id == "roboflow-sam3-pcs":
            client = RoboflowSAM3ConceptBackend(
                endpoint=endpoint,
                api_key=api_key,
                model=model,
                allow_network=True,
                acknowledge_cost_privacy=True,
                transport=transport,
            )
            smoke = client.smoke_test(prompt=prompt)
        elif provider_id == "sam3-hosted" and profile_id == "fal-sam3-image":
            client = FalSAM3ImageBackend(
                api_key=api_key,
                model=model,
                allow_network=True,
                acknowledge_cost_privacy=True,
                client=transport,
            )
            smoke = client.smoke_test(prompt=prompt)
        else:
            client = HostedSAM3DiscoveryBackend(
                endpoint=endpoint,
                api_key=api_key,
                model=model,
                allow_network=True,
                acknowledge_cost_privacy=True,
                timeout_seconds=timeout_seconds,
                retries=retries,
                transport=transport,
            )
            smoke = client.smoke_test(prompt=prompt)
    except (ProviderConfigError, ProviderExecutionError) as exc:
        raise ValueError(redact_secret_text(str(exc))) from exc

    return {
        "format": "motionjson.provider_network_smoke_test.v0.1",
        "providerId": provider_id,
        "hostedProfileId": profile_id,
        "effectiveProfile": _public_profile(profile),
        "status": "ok",
        "ready": True,
        "networkAttempted": True,
        "message": f"{definition['name']} smoke test completed. Review provider billing and privacy terms before real runs.",
        "costPrivacyAcknowledged": True,
        "endpoint": {
            "configured": True,
            "source": endpoint_source,
            "host": urlparse(endpoint).netloc,
        },
        "credentials": {
            "configured": True,
            "source": credential_source,
            "display": redact_secret_value(api_key, provider_id=provider_id),
        },
        "model": model,
        "timeoutSeconds": timeout_seconds,
        "retries": retries,
        "smokeTest": redact_secret_payload(smoke),
    }


def diagnose_provider_settings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    payload: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return a provider-specific setup checklist without making network calls."""

    environ = environ or os.environ
    payload = payload or {}
    definition = _definition(provider_id)
    row = _settings_rows(conn, user_id=user_id).get(provider_id)
    settings, secrets = _row_payloads(row)
    settings = dict(settings)
    _apply_settings_payload(definition, settings, secrets, payload, validate_profile=False)
    readiness = _readiness(definition, settings, secrets, environ)
    credentials = _credential_states(definition, settings, secrets, environ)
    model_cache = _model_cache_state(definition, settings, secrets, environ)
    model_cache["runtimeModelSource"] = _runtime_model_source(definition, settings, environ, model_cache)
    runtime_verification = _runtime_verification_state(definition, settings, model_cache, environ)
    checklist: list[dict[str, Any]] = []
    commands: list[str] = []
    docs = definition.get("docs")

    def item(id_: str, label: str, ok: bool, detail: str, action: str = "", *, required: bool = True) -> None:
        checklist.append(
            {
                "id": id_,
                "label": label,
                "status": "ok" if ok else "missing",
                "ok": ok,
                "required": required,
                "detail": redact_secret_text(detail),
                "action": action,
            }
        )

    if provider_id == "sam2-local":
        checkpoint = str(environ.get("SAM2_LOCAL_CHECKPOINT") or settings.get("sam2_checkpoint_path") or "")
        model_config = str(environ.get("SAM2_LOCAL_CONFIG") or settings.get("sam2_model_config_path") or "")
        item("sam2_package", "SAM2 package", find_spec("sam2") is not None, "Python can import sam2.", "Install official facebookresearch/sam2.")
        item("torch_package", "PyTorch", find_spec("torch") is not None, "Python can import torch.", "Install torch for the selected CPU/MPS/CUDA runtime.")
        item("checkpoint", "Checkpoint path", bool(checkpoint and Path(checkpoint).exists()), checkpoint or "SAM2_LOCAL_CHECKPOINT is not configured.", "Download SAM2.1 checkpoints and save the .pt path.")
        item("model_config", "Model config path", bool(model_config and Path(model_config).exists()), model_config or "SAM2_LOCAL_CONFIG is not configured.", "Use the matching SAM2 config YAML.")
        item("device", "Device", True, str(environ.get("SAM2_LOCAL_DEVICE") or settings.get("sam2_device") or "auto/cpu"), "Choose cpu, mps, cuda, or cuda:0.")
        commands = list((definition.get("setupGuide") or {}).get("commands") or [])
    elif provider_id == "sam2-hf-auto-masks":
        model = _runtime_effective_model(definition, settings, environ) or SAM2_HF_AUTO_MASKS_DEFAULT_MODEL
        model_detail = "Selected model: server-side cached path recorded and redacted." if model_cache.get("serverPathRecorded") else f"Selected model: {model}"
        device = str(environ.get("SAM2_HF_DEVICE") or settings.get("sam2_hf_device") or "auto/cpu")
        device_problem = _device_problem(device, torch_ok=find_spec("torch") is not None)
        item("transformers_package", "SAM2 Transformers package", find_spec("transformers") is not None, "Python can import transformers." if find_spec("transformers") is not None else "Python cannot import transformers.", "Install the independent sam2-transformers extra. Official SAM2 is not required.")
        item("torch_package", "PyTorch", find_spec("torch") is not None, "Python can import torch.", "Install torch for the selected CPU/MPS/CUDA runtime.")
        item("model_id", "HF model id or directory", True, model_detail, "Use Cache model if the model is not already available in this runtime.")
        item("model_cache", "Runtime model cache", bool(model_cache.get("cached")), str(model_cache.get("message") or "Model cache has not been resolved."), "Run Cache model, choose a from_pretrained directory, or fix runtime cache access.")
        item(
            "runtime_warmup",
            "Load and warm up model",
            bool(runtime_verification.get("verified")),
            str(runtime_verification.get("message") or "Run a smoke test after caching the model."),
            "Run smoke test or Prepare runtime model.",
        )
        item("device", "Device", not device_problem, device_problem or f"Selected device: {device}", "Choose cpu, mps, cuda, or cuda:0.")
        item("official_sam2", "Official SAM2 checkpoint/config", True, "Not required for SAM2 HF automatic masks.", "", required=False)
        commands = list((definition.get("setupGuide") or {}).get("commands") or [])
    elif provider_id == "sam3-local":
        model_path = str(environ.get("SAM3_LOCAL_MODEL") or settings.get("sam3_model_path") or "")
        model_path_source = "environment" if environ.get("SAM3_LOCAL_MODEL") else "local_settings" if settings.get("sam3_model_path") else "unset"
        model_status = describe_sam3_model_path(model_path, source=model_path_source)
        tracker_model_value = environ.get("SAM3_TRACKER_MODEL") or _runtime_effective_model(definition, settings, environ) or SAM3_HF_REPO_ID
        tracker_model_status = describe_sam3_tracker_model(
            tracker_model_value,
            source="environment" if environ.get("SAM3_TRACKER_MODEL") else "local_settings" if settings.get("selected_model") else "default",
        )
        tracker_model_ok = bool(tracker_model_status["valid"] or model_cache.get("cached"))
        tracker_model_detail = (
            "SAM3 Tracker model path is recorded server-side and redacted."
            if model_cache.get("serverPathRecorded")
            else str(tracker_model_status.get("resolvedModel") or tracker_model_status.get("reason") or "facebook/sam3")
        )
        py_ok = (sys.version_info.major, sys.version_info.minor) >= (3, 12)
        transformers_ok = find_spec("transformers") is not None
        torch_ok = find_spec("torch") is not None
        device = str(environ.get("SAM3_LOCAL_DEVICE") or settings.get("sam3_device") or "cuda")
        device_problem = _device_problem(device, torch_ok=torch_ok)
        tracker_auto_masks_ok = _sam3_tracker_auto_masks_importable() if transformers_ok else False
        tracker_video_status = sam3_tracker_video_runtime_status() if transformers_ok else {}
        tracker_video_ok = _sam3_tracker_video_importable() if transformers_ok else False
        item("transformers_package", "SAM3 Transformers package", transformers_ok, "Python can import transformers." if transformers_ok else "Python cannot import transformers.", "Install the independent sam3-transformers extra. SAM2 is not required.")
        item("sam3_tracker_auto_masks", "SAM3 Tracker automatic masks", tracker_auto_masks_ok, "Transformers exposes SAM3 Tracker mask-generation classes." if tracker_auto_masks_ok else "Transformers does not expose Sam3TrackerModel/Sam3TrackerProcessor.", "Upgrade/install the sam3-transformers extra. SAM2 is not required.")
        item(
            "sam3_tracker_video",
            "SAM3 Tracker Video API",
            tracker_video_ok,
            "Transformers exposes SAM3 Tracker Video classes."
            if tracker_video_ok
            else str(tracker_video_status.get("message") or "Transformers does not expose Sam3TrackerVideoModel/Sam3TrackerVideoProcessor."),
            "Upgrade/install the sam3-transformers extra, then restart the runtime before enabling true video propagation.",
            required=False,
        )
        item("sam3_tracker_model", "SAM3 Tracker model id or directory", tracker_model_ok, tracker_model_detail, str(tracker_model_status.get("action") or "Use Cache model for facebook/sam3."), required=True)
        item("model_cache", "Local model cache", bool(model_cache.get("cached")), str(model_cache.get("message") or "Model cache has not been resolved."), "Run Cache model, choose a local from_pretrained directory, or fix local Hugging Face cache access.")
        item("torch_package", "PyTorch", torch_ok, "Python can import torch.", "Install torch for the selected CPU/MPS/CUDA runtime.")
        item("device", "Device", not device_problem, device_problem or f"Selected device: {device}", "Choose cpu, mps, cuda, or cuda:0.")
        item(
            "runtime_warmup",
            "Load on GPU and warm up",
            bool(runtime_verification.get("verified")),
            str(runtime_verification.get("message") or "Run a smoke test after caching the model."),
            "Run smoke test or Prepare runtime model.",
        )
        item("python", "Python >= 3.12 for concept/exemplar", py_ok, f"Current Python is {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}.", "Use a Python 3.12 environment for official-package SAM3 concept/exemplar workflows.", required=False)
        item("sam3_package", "Official SAM3 package for concept/exemplar", find_spec("sam3") is not None, "Python can import sam3.", "Install official facebookresearch/sam3 for concept/exemplar workflows.", required=False)
        item(
            "model_path",
            "SAM3 checkpoint file path for concept/exemplar",
            bool(model_status["valid"]),
            str(model_status.get("resolvedPath") or model_status.get("reason") or "SAM3_LOCAL_MODEL is not configured."),
            str(model_status.get("action") or "Request Hugging Face access, authenticate, then save the local sam3.pt checkpoint path."),
            required=False,
        )
        hf_token_ok = bool(environ.get("HF_TOKEN") or environ.get("HUGGINGFACE_HUB_TOKEN") or secrets.get("hf_token"))
        item("hf_token", "Hugging Face auth for gated downloads", hf_token_ok, "Hugging Face token configured." if hf_token_ok else "No Hugging Face token is saved for this UI session.", "Paste a Hugging Face token in Model setup, then use Check access before caching facebook/sam3.", required=False)
        commands = list((definition.get("setupGuide") or {}).get("commands") or [])
    elif provider_id in {"sam2-hosted", "sam3-hosted"}:
        profile = _profile_definition(definition, settings)
        profiled = _profiled_definition(definition, settings)
        credentials = _credential_states(definition, settings, secrets, environ)
        api_state = next((entry for entry in credentials if entry.get("name") == "api_key"), None)
        endpoint_state = next((entry for entry in credentials if entry.get("name") == "endpoint"), None)
        item("profile", "Hosted profile", True, str(profile.get("name") or profile.get("id") or "selected"), "Pick the provider that matches the workflow.")
        item("api_key", "API key", bool(api_state and api_state.get("configured")), str(api_state.get("env") if api_state else "API key") + " configured.", "Paste a temporary key or set the provider environment variable.")
        if profiled.get("endpointField"):
            required = bool(profiled["endpointField"].get("required"))
            item("endpoint", "Endpoint", bool(endpoint_state and endpoint_state.get("configured")) or not required, str((endpoint_state or {}).get("display") or "provider default"), "Use the provider default or paste a custom endpoint URL.")
        item("hosted_opt_in", "Hosted cost/privacy opt-in", bool(settings.get("allow_hosted")), "Hosted calls are enabled in saved settings." if settings.get("allow_hosted") else "Hosted calls remain disabled.", "Check the hosted-cost/privacy box before smoke tests or extraction.")
        commands = ["Save setup", "Run setup test", "Run hosted smoke after explicit opt-in"]
    else:
        item("provider", "Provider registered", True, definition["name"], "No additional setup checklist is defined.")

    ok = all(entry["ok"] for entry in checklist if entry.get("required", True))
    setup_state = _setup_state_for_provider(definition, readiness, model_cache, credentials, runtime_verification)
    runnable = bool(ok and readiness.get("configured") and setup_state.get("runnable", setup_state.get("status") == "ready"))
    return {
        "format": "motionjson.provider_settings_diagnose.v0.1",
        "providerId": provider_id,
        "status": "ready" if runnable else "needs_setup",
        "setupState": setup_state,
        "ready": runnable,
        "networkAttempted": False,
        "heavyLocalAttempted": False,
        "message": setup_state.get("message") or readiness.get("message") or ("Ready" if ok else "Setup is incomplete."),
        "modelCache": model_cache,
        "runtimeVerification": runtime_verification,
        "checklist": checklist,
        "commands": commands,
        "docs": docs,
        "setupGuide": definition.get("setupGuide") or {},
    }


def local_sam_smoke_test(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    payload: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
    progress: Any | None = None,
) -> dict[str, Any]:
    """Run a bounded SAM runtime setup smoke check without network access."""

    if provider_id not in {"sam2-local", "sam2-hf-auto-masks", "sam3-local"}:
        raise ValueError("Local SAM smoke tests are only available for sam2-local, sam2-hf-auto-masks, or sam3-local.")
    if not _truthy(payload.get("allowHeavyLocal", payload.get("allow_heavy_local"))):
        raise ValueError("SAM runtime smoke test requires allowHeavyLocal=true before importing heavy model runtimes.")
    diagnosis = diagnose_provider_settings(conn, user_id=user_id, provider_id=provider_id, payload=payload, environ=environ)
    smoke: dict[str, Any] | None = None
    runtime = provider_runtime_settings(conn, user_id=user_id, provider_id=provider_id, environ=environ)
    runtime_model_source = str(runtime.get("runtime_model_source") or "default")
    model_cache = runtime.get("model_cache") if isinstance(runtime.get("model_cache"), Mapping) else {}
    readiness = runtime.get("readiness") if isinstance(runtime.get("readiness"), Mapping) else {}
    sam3_scene_sweep_smoke = provider_id == "sam3-local" and (
        _truthy(payload.get("sceneSweep", payload.get("scene_sweep")))
        or bool(model_cache.get("cached"))
        or not str(runtime.get("sam3_model_path") or "").strip()
    )
    if sam3_scene_sweep_smoke:
        can_attempt_scene_sweep = bool(readiness.get("configured") and model_cache.get("cached"))
        if not can_attempt_scene_sweep:
            missing_text = ", ".join(str(item) for item in readiness.get("missing") or [])
            cuda_failed = "cuda" in missing_text.lower()
            return {
                "format": "motionjson.provider_local_sam_smoke_test.v0.1",
                "providerId": provider_id,
                "status": "failed" if cuda_failed else "blocked",
                "ready": False,
                "networkAttempted": False,
                "heavyLocalAttempted": True,
                "message": redact_secret_text(missing_text or "SAM3 Scene Sweep setup is incomplete; cache the model and install the runtime before smoke testing."),
                "diagnosis": diagnosis,
                "smokeTest": None,
            }
        try:
            smoke_timeout_seconds = _sam3_smoke_timeout_seconds(payload, environ)
            if _truthy(payload.get("useSubprocessSmoke", payload.get("use_subprocess_smoke"))):
                from motionjson.backend.sam3_smoke_subprocess import run_sam3_scene_sweep_warmup_subprocess

                smoke = run_sam3_scene_sweep_warmup_subprocess(
                    str(runtime.get("runtime_model") or runtime.get("selected_model") or SAM3_HF_REPO_ID),
                    device=str(runtime.get("sam3_device") or "cuda"),
                    progress=progress,
                    timeout_seconds=smoke_timeout_seconds,
                    environ=environ,
                )
            else:
                smoke = sam3_scene_sweep_warmup(
                    str(runtime.get("runtime_model") or runtime.get("selected_model") or SAM3_HF_REPO_ID),
                    device=str(runtime.get("sam3_device") or "cuda"),
                    progress=progress,
                )
            smoke = {
                **smoke,
                "sam2Required": False,
                "runtimeModelSource": runtime_model_source,
                "localPathDisplay": "[LOCAL_PATH_REDACTED]" if model_cache.get("localPathKnown") else "",
                "checks": [
                    "transformers",
                    "torch",
                    "sam3_tracker_auto_masks",
                    "cuda" if str(runtime.get("sam3_device") or "cuda").lower().startswith("cuda") else "device",
                    "warmup_inference",
                ],
            }
            record_provider_runtime_verification(
                conn,
                user_id=user_id,
                provider_id=provider_id,
                verification=smoke,
                environ=environ,
            )
            diagnosis = diagnose_provider_settings(conn, user_id=user_id, provider_id=provider_id, payload=payload, environ=environ)
        except Exception as exc:
            return {
                "format": "motionjson.provider_local_sam_smoke_test.v0.1",
                "providerId": provider_id,
                "status": "failed",
                "ready": False,
                "networkAttempted": False,
                "heavyLocalAttempted": True,
                "message": redact_secret_text(str(exc) or type(exc).__name__),
                "diagnosis": diagnosis,
                "smokeTest": None,
            }
        return {
            "format": "motionjson.provider_local_sam_smoke_test.v0.1",
            "providerId": provider_id,
            "status": "ready",
            "ready": True,
            "networkAttempted": False,
            "heavyLocalAttempted": True,
            "message": "SAM3 Scene Sweep loaded on the selected device and completed bounded warmup inference.",
            "diagnosis": diagnosis,
            "smokeTest": redact_secret_payload(smoke),
        }
    can_attempt_local_smoke = bool(diagnosis["ready"]) or (
        provider_id in LOCAL_MODEL_CACHE_PROVIDER_IDS
        and bool(readiness.get("configured"))
        and bool(model_cache.get("cached"))
    )
    if can_attempt_local_smoke:
        from motionjson.providers.base import ProviderConfigError, ProviderExecutionError

        try:
            if provider_id == "sam2-local":
                import numpy as np

                from motionjson.providers.sam2 import LocalSAM2AutomaticMaskProposalBackend

                backend = LocalSAM2AutomaticMaskProposalBackend.from_config(
                    {
                        "checkpoint": runtime.get("sam2_checkpoint_path"),
                        "model_config": runtime.get("sam2_model_config_path"),
                        "device": runtime.get("sam2_device") or "cpu",
                    }
                )
                records = backend.propose_masks(np.zeros((8, 8, 3), dtype=np.uint8), frame_index=0, config={"max_candidates": 1})
                smoke = {"providerName": "sam2-local", "recordCount": len(list(records)), "frameShape": [8, 8, 3]}
            elif provider_id == "sam2-hf-auto-masks":
                import numpy as np

                from motionjson.providers.sam2 import LocalSAM2HFAutomaticMaskProposalBackend

                backend = LocalSAM2HFAutomaticMaskProposalBackend.from_config(
                    {
                        "sam2HfModel": runtime.get("runtime_model") or runtime.get("selected_model") or SAM2_HF_AUTO_MASKS_DEFAULT_MODEL,
                        "sam2HfDevice": runtime.get("sam2_hf_device") or "cpu",
                    }
                )
                records = backend.propose_masks(np.zeros((8, 8, 3), dtype=np.uint8), frame_index=0, config={"max_candidates": 1})
                smoke = {
                    "providerName": "sam2-hf-auto-masks",
                    "recordCount": len(list(records)),
                    "frameShape": [8, 8, 3],
                    "officialSam2Required": False,
                    "runtimeModelSource": runtime_model_source,
                    "localPathDisplay": "[LOCAL_PATH_REDACTED]" if model_cache.get("localPathKnown") else "",
                    "runtimeKind": "transformers_mask_generation",
                    "deviceRequested": runtime.get("sam2_hf_device") or "cpu",
                    "deviceActual": runtime.get("sam2_hf_device") or "cpu",
                    "warmupStatus": "succeeded",
                }
                record_provider_runtime_verification(
                    conn,
                    user_id=user_id,
                    provider_id=provider_id,
                    verification=smoke,
                    environ=environ,
                )
                diagnosis = diagnose_provider_settings(conn, user_id=user_id, provider_id=provider_id, payload=payload, environ=environ)
            else:
                from motionjson.providers.sam3 import LocalSAM3DiscoveryBackend

                backend = LocalSAM3DiscoveryBackend.from_config(
                    {
                        "sam3ModelPath": runtime.get("sam3_model_path"),
                        "sam3Device": runtime.get("sam3_device") or "cuda",
                    }
                )
                smoke = backend.smoke_test(prompt=str(payload.get("prompt") or "object"))
        except (ProviderConfigError, ProviderExecutionError, ImportError) as exc:
            return {
                "format": "motionjson.provider_local_sam_smoke_test.v0.1",
                "providerId": provider_id,
                "status": "failed",
                "ready": False,
                "networkAttempted": False,
                "heavyLocalAttempted": True,
                "message": redact_secret_text(str(exc)),
                "diagnosis": diagnosis,
                "smokeTest": None,
            }
    return {
        "format": "motionjson.provider_local_sam_smoke_test.v0.1",
        "providerId": provider_id,
        "status": "ready" if diagnosis["ready"] else "blocked",
        "ready": bool(diagnosis["ready"]),
        "networkAttempted": False,
        "heavyLocalAttempted": True,
        "message": "Local SAM bounded smoke completed." if diagnosis["ready"] else "Local SAM setup is incomplete; no model run was attempted.",
        "diagnosis": diagnosis,
        "smokeTest": redact_secret_payload(smoke),
    }


def _definition(provider_id: str) -> dict[str, Any]:
    if provider_id not in PROVIDER_BY_ID:
        raise ValueError(f"Unknown provider settings id: {provider_id}")
    return PROVIDER_BY_ID[provider_id]


def _ensure_valid_hosted_profile(definition: Mapping[str, Any], profile_id: str) -> None:
    allowed = {str(profile["id"]) for profile in definition.get("hostedProfiles") or []}
    if allowed and profile_id not in allowed:
        raise ValueError(f"{definition['name']} hosted profile must be one of: {', '.join(sorted(allowed))}.")


def _public_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    if not profile:
        return {}
    public = {
        key: value
        for key, value in dict(profile).items()
        if key not in {"credentialFields", "endpointField"}
    }
    credential_fields = []
    for field in profile.get("credentialFields") or []:
        credential_fields.append({key: value for key, value in dict(field).items() if key != "value"})
    public["credentialFields"] = credential_fields
    if profile.get("endpointField"):
        public["endpointField"] = dict(profile["endpointField"])
    return public


def _settings_rows(conn: sqlite3.Connection, *, user_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT *
        FROM provider_settings
        WHERE user_id = ?
        ORDER BY provider_id
        """,
        (user_id,),
    ).fetchall()
    return {str(row["provider_id"]): row for row in rows}


def _row_payloads(row: sqlite3.Row | None) -> tuple[dict[str, Any], dict[str, str]]:
    if row is None:
        return {}, {}
    settings = json.loads(row["settings_json"] or "{}")
    secrets = json.loads(row["secret_json"] or "{}")
    if not isinstance(settings, dict):
        settings = {}
    if not isinstance(secrets, dict):
        secrets = {}
    return settings, {str(key): str(value) for key, value in secrets.items() if value}


def _upsert_provider_settings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider_id: str,
    settings: Mapping[str, Any],
    secrets: Mapping[str, str],
    existing: sqlite3.Row | None,
) -> None:
    now = utc_now()
    row = {
        "id": existing["id"] if existing is not None else uuid.uuid4().hex,
        "user_id": user_id,
        "provider_id": provider_id,
        "settings_json": json.dumps(dict(settings), sort_keys=True),
        "secret_json": json.dumps(dict(secrets), sort_keys=True),
        "created_at": existing["created_at"] if existing is not None else now,
        "updated_at": now,
    }
    conn.execute(
        """
        INSERT INTO provider_settings
        (id, user_id, provider_id, settings_json, secret_json, created_at, updated_at)
        VALUES (:id, :user_id, :provider_id, :settings_json, :secret_json, :created_at, :updated_at)
        ON CONFLICT(user_id, provider_id)
        DO UPDATE SET
            settings_json = excluded.settings_json,
            secret_json = excluded.secret_json,
            updated_at = excluded.updated_at
        """,
        row,
    )
    conn.commit()


def _public_provider_state(
    definition: Mapping[str, Any],
    row: sqlite3.Row | None,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    settings, secrets = _row_payloads(row)
    settings = _settings_with_environment_profile(str(definition["id"]), settings, environ)
    profile = _profile_definition(definition, settings)
    profiled_definition = _profiled_definition(definition, settings)
    provider = copy.deepcopy(dict(profiled_definition))
    provider["settings"] = {
        "enabled": bool(settings.get("enabled", definition.get("locality") != "hosted")),
        "selectedModel": settings.get("selected_model") or profiled_definition.get("defaultModel"),
        "customModelId": _public_custom_model_id(definition, settings),
        "endpoint": settings.get("endpoint") or "",
        "baseUrl": settings.get("base_url") or "",
        "allowHosted": bool(settings.get("allow_hosted", False)),
        "hostedProfileId": _selected_hosted_profile_id(definition, settings),
        "sam2CheckpointPath": settings.get("sam2_checkpoint_path") or "",
        "sam2ModelConfigPath": settings.get("sam2_model_config_path") or "",
        "sam2Device": settings.get("sam2_device") or "",
        "sam2HfDevice": settings.get("sam2_hf_device") or "",
        "sam3ModelPath": settings.get("sam3_model_path") or "",
        "sam3Device": settings.get("sam3_device") or "",
        "updatedAt": row["updated_at"] if row is not None else None,
        "source": "local_settings" if row is not None else "default",
    }
    provider["credentials"] = _credential_states(definition, settings, secrets, environ)
    provider["readiness"] = _readiness(definition, settings, secrets, environ)
    provider["modelCache"] = _model_cache_state(definition, settings, secrets, environ)
    provider["modelCache"]["runtimeModelSource"] = _runtime_model_source(definition, settings, environ, provider["modelCache"])
    provider["runtimeVerification"] = _runtime_verification_state(definition, settings, provider["modelCache"], environ)
    provider["setupState"] = _setup_state_for_provider(
        definition,
        provider["readiness"],
        provider["modelCache"],
        provider["credentials"],
        provider["runtimeVerification"],
    )
    provider["effectiveModel"] = _runtime_effective_model(definition, settings, environ)
    provider["effectiveProfile"] = _public_profile(profile)
    return provider


def _public_custom_model_id(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> str:
    custom_model_id = str(settings.get("custom_model_id") or "").strip()
    if not custom_model_id:
        return ""
    if str(definition.get("id") or "") not in LOCAL_MODEL_CACHE_PROVIDER_IDS:
        return custom_model_id
    saved_dir = str(settings.get("resolved_model_dir") or "").strip()
    cached_model_id = str(settings.get("cached_model_id") or "").strip()
    if _looks_like_local_model_path(custom_model_id) and custom_model_id in {saved_dir, cached_model_id}:
        return ""
    return custom_model_id


def _capability_override(
    provider_id: str,
    row: sqlite3.Row | None,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    definition = PROVIDER_BY_ID[provider_id]
    settings, secrets = _row_payloads(row)
    settings = _settings_with_environment_profile(provider_id, settings, environ)
    profile = _profile_definition(definition, settings)
    profiled_definition = _profiled_definition(definition, settings)
    credential_states = _credential_states(definition, settings, secrets, environ)
    api_credential = next((item for item in credential_states if item.get("name") == "api_key"), None)
    endpoint_field = profiled_definition.get("endpointField")
    base_url_field = profiled_definition.get("baseUrlField")
    endpoint = None
    base_url = None
    endpoint_source = "unset"
    base_url_source = "unset"
    endpoint_valid = True
    base_url_valid = True
    if endpoint_field:
        env = str(endpoint_field.get("env") or "")
        endpoint = environ.get(env) or settings.get("endpoint")
        endpoint_source = "environment" if environ.get(env) else "local_settings" if endpoint else "unset"
        if not endpoint and profile.get("defaultEndpoint"):
            endpoint = str(profile.get("defaultEndpoint") or "")
            endpoint_source = "profile_default"
        endpoint_valid = not endpoint or _valid_http_url(str(endpoint))
    if base_url_field:
        env = str(base_url_field.get("env") or "")
        base_url = environ.get(env) or settings.get("base_url")
        base_url_source = "environment" if environ.get(env) else "local_settings" if base_url else "unset"
        base_url_valid = not base_url or _valid_http_url(str(base_url))
    selected_model = _runtime_effective_model(definition, settings, environ)
    runtime_settings_only = bool(endpoint_source == "local_settings" or (api_credential and api_credential.get("source") == "local_settings"))
    if provider_id in {"sam2-hosted", "sam3-hosted"}:
        runtime_settings_only = False
    return {
        "configured": _readiness(definition, settings, secrets, environ)["configured"],
        "api_key_configured": bool(api_credential and api_credential.get("configured")),
        "credential_source": api_credential.get("source") if api_credential else "none",
        "endpoint_configured": bool(endpoint),
        "endpoint_source": endpoint_source,
        "endpoint_valid": endpoint_valid,
        "base_url_configured": bool(base_url),
        "base_url_source": base_url_source,
        "base_url_valid": base_url_valid,
        "settings_only": runtime_settings_only,
        "allow_hosted": bool(settings.get("allow_hosted", False)),
        "selected_model": selected_model,
        "hosted_profile_id": _selected_hosted_profile_id(definition, settings),
        "effective_profile": _public_profile(profile),
        "sam2_checkpoint_path": str(environ.get("SAM2_LOCAL_CHECKPOINT") or settings.get("sam2_checkpoint_path") or ""),
        "sam2_model_config_path": str(environ.get("SAM2_LOCAL_CONFIG") or settings.get("sam2_model_config_path") or ""),
        "sam2_device": str(environ.get("SAM2_LOCAL_DEVICE") or settings.get("sam2_device") or ""),
        "sam2_hf_device": str(environ.get("SAM2_HF_DEVICE") or settings.get("sam2_hf_device") or ""),
        "sam3_model_path": str(environ.get("SAM3_LOCAL_MODEL") or settings.get("sam3_model_path") or ""),
        "sam3_device": str(environ.get("SAM3_LOCAL_DEVICE") or settings.get("sam3_device") or ""),
        "hf_token_configured": bool(environ.get("HF_TOKEN") or environ.get("HUGGINGFACE_HUB_TOKEN") or secrets.get("hf_token")),
        "settings_source": "local_settings" if row is not None else "default",
    }


def _credential_states(
    definition: Mapping[str, Any],
    settings: Mapping[str, Any],
    secrets: Mapping[str, str],
    environ: Mapping[str, str],
) -> list[dict[str, Any]]:
    definition = _profiled_definition(definition, settings)
    states: list[dict[str, Any]] = []
    for field in definition.get("credentialFields", []):
        name = str(field["name"])
        env = str(field.get("env") or "")
        env_value = environ.get(env)
        if name == "hf_token" and not env_value:
            env_value = environ.get("HUGGINGFACE_HUB_TOKEN")
        local_value = secrets.get(name)
        source = "environment" if env_value else "local_settings" if local_value else "unset"
        raw_value = env_value or local_value or ""
        states.append(
            {
                "name": name,
                "label": field.get("label") or name,
                "env": env,
                "required": bool(field.get("required")),
                "configured": bool(raw_value),
                "source": source,
                "display": redact_secret_value(raw_value, provider_id=str(definition["id"])) if raw_value else "",
            }
        )
    endpoint = definition.get("endpointField")
    if endpoint:
        env = str(endpoint.get("env") or "")
        value = environ.get(env) or settings.get("endpoint")
        source = "environment" if environ.get(env) else "local_settings" if value else "unset"
        if not value and endpoint.get("required") is False:
            profile = _profile_definition(definition, settings)
            value = profile.get("defaultEndpoint") or ""
            source = "profile_default" if value else source
        states.append(
            {
                "name": "endpoint",
                "label": endpoint.get("label") or "Endpoint",
                "env": env,
                "required": bool(endpoint.get("required")),
                "configured": bool(value),
                "source": source,
                "display": value or "",
            }
        )
    return states


def _readiness(
    definition: Mapping[str, Any],
    settings: Mapping[str, Any],
    secrets: Mapping[str, str],
    environ: Mapping[str, str],
) -> dict[str, Any]:
    if definition.get("id") == "sam3-local":
        transformers_ok = find_spec("transformers") is not None
        torch_ok = find_spec("torch") is not None
        tracker_auto_masks_ok = _sam3_tracker_auto_masks_importable() if transformers_ok else False
        missing = []
        if not transformers_ok:
            missing.append("sam3-transformers extra")
        if not torch_ok:
            missing.append("torch")
        if not tracker_auto_masks_ok:
            missing.append("SAM3 Tracker automatic-mask Transformers classes")
        device_problem = _device_problem(str(environ.get("SAM3_LOCAL_DEVICE") or settings.get("sam3_device") or "cuda"), torch_ok=torch_ok)
        if device_problem:
            missing.append(device_problem)
        if missing:
            return {
                "status": "not_configured",
                "configured": False,
                "missing": missing,
                "message": f"Needs SAM3 Scene Sweep setup: {', '.join(missing)}. SAM2 is not required.",
            }
        concept_ready = (
            find_spec("sam3") is not None
            and bool(describe_sam3_model_path(str(environ.get("SAM3_LOCAL_MODEL") or settings.get("sam3_model_path") or ""), source="environment" if environ.get("SAM3_LOCAL_MODEL") else "local_settings").get("valid"))
        )
        return {
            "status": "ready",
            "configured": True,
            "missing": [],
            "message": (
                "SAM3 Scene Sweep runtime is ready. Concept and exemplar workflows are also ready."
                if concept_ready
                else "SAM3 Scene Sweep runtime is ready. Concept and exemplar workflows still need the official SAM3 package and a local sam3.pt checkpoint."
            ),
        }
    if definition.get("id") == "sam2-hf-auto-masks":
        transformers_ok = find_spec("transformers") is not None
        torch_ok = find_spec("torch") is not None
        missing = []
        if not transformers_ok:
            missing.append("sam2-transformers extra")
        if not torch_ok:
            missing.append("torch")
        device_problem = _device_problem(str(environ.get("SAM2_HF_DEVICE") or settings.get("sam2_hf_device") or ""), torch_ok=torch_ok)
        if device_problem:
            missing.append(device_problem)
        if missing:
            return {
                "status": "not_configured",
                "configured": False,
                "missing": missing,
                "message": f"Needs SAM2 HF fallback setup: {', '.join(missing)}. Official SAM2 checkpoint/config is not required.",
            }
        return {
            "status": "ready",
            "configured": True,
            "missing": [],
            "message": "SAM2 HF automatic-mask fallback is ready. It uses Hugging Face Transformers, not official SAM2 checkpoint/config paths.",
        }

    profiled_definition = _profiled_definition(definition, settings)
    profile = _profile_definition(definition, settings)
    missing = []
    for field in profiled_definition.get("credentialFields", []):
        env = str(field.get("env") or "")
        name = str(field["name"])
        if field.get("required") and not (environ.get(env) or secrets.get(name)):
            missing.append(env or name)
    for field in profiled_definition.get("localConfigFields", []):
        env = str(field.get("env") or "")
        name = str(field["name"])
        value = environ.get(env) or settings.get(name)
        if field.get("required") and not value:
            missing.append(env or name)
        elif value and name == "sam3_model_path":
            source = "environment" if environ.get(env) else "local_settings"
            path_status = describe_sam3_model_path(str(value), env=env or "SAM3_LOCAL_MODEL", source=source)
            if not path_status["valid"]:
                if path_status.get("valueKind") in {"huggingface_repo_id", "source_package_directory"}:
                    missing.append(str(path_status["reason"]))
                elif path_status.get("valueKind") == "directory_with_checkpoint":
                    missing.append(f"{env or name} points to a directory; use the sam3.pt file inside it")
                else:
                    missing.append(f"{env or name} valid local sam3.pt checkpoint file")
        elif value and name.endswith("_path") and not os.path.exists(str(value)):
            missing.append(f"{env or name} existing path")
    endpoint = profiled_definition.get("endpointField")
    if endpoint and endpoint.get("required"):
        env = str(endpoint.get("env") or "")
        value = environ.get(env) or settings.get("endpoint") or profile.get("defaultEndpoint")
        if not value:
            missing.append(env or "endpoint")
        elif not _valid_http_url(str(value)):
            missing.append(f"{env or 'endpoint'} valid URL")
    model_status = _model_status(definition, settings)
    if model_status.get("status") == "missing_model":
        missing.append("model")
    if missing:
        status = "missing_key" if any("KEY" in item or "key" in item for item in missing) else "not_configured"
        message = f"Needs setup: {', '.join(missing)}."
    elif definition.get("locality") == "hosted" and not settings.get("allow_hosted"):
        status = "needs_hosted_confirmation"
        message = "Configured, but hosted calls remain disabled until you confirm cost and privacy."
    elif definition.get("locality") == "hosted":
        status = "configured"
        message = "Configured for hosted use. Extraction still requires a generated run config with network and cost/privacy opt-in."
    elif definition.get("implemented"):
        status = "ready"
        message = "No API key required. Capability diagnostics still decide runtime availability."
    else:
        status = "planned"
        message = "Provider surface is planned or scaffolded and remains capability-gated."
    return {"status": status, "configured": not missing, "missing": missing, "message": message}


def _device_problem(device: str, *, torch_ok: bool) -> str:
    normalized = str(device or "").strip().lower()
    if not normalized or normalized in {"auto", "cpu"}:
        return ""
    if not torch_ok:
        return f"{device} requested but torch is not installed"
    try:
        import torch  # type: ignore
    except Exception as exc:
        return f"{device} requested but torch could not be imported: {type(exc).__name__}"
    if normalized.startswith("cuda"):
        try:
            if not bool(torch.cuda.is_available()):
                return f"{device} requested but CUDA is not available; choose cpu or a CUDA runtime"
        except Exception as exc:
            return f"{device} requested but CUDA status could not be checked: {type(exc).__name__}"
    if normalized == "mps":
        try:
            if not bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()):
                return "mps requested but Apple MPS is not available; choose cpu or an MPS-capable runtime"
        except Exception as exc:
            return f"mps requested but MPS status could not be checked: {type(exc).__name__}"
    return ""


def _setup_state_from_readiness(readiness: Mapping[str, Any]) -> dict[str, Any]:
    status = str(readiness.get("status") or "")
    configured = bool(readiness.get("configured"))
    if status in {"ready", "configured"} and configured:
        return {"status": "ready", "label": "Ready", "message": readiness.get("message") or "Ready for setup-guided runs."}
    missing = " ".join(str(item) for item in readiness.get("missing") or [])
    message = str(readiness.get("message") or "")
    lower = f"{missing} {message}".lower()
    if "token" in lower or "access" in lower or "hf_" in lower or "hugging face" in lower:
        return {"status": "needs_access", "label": "Needs access", "message": readiness.get("message") or "Sign in or confirm model access before caching."}
    if "download" in lower or "cache" in lower or "model" in lower:
        return {"status": "needs_download_confirmation", "label": "Needs download confirmation", "message": readiness.get("message") or "Confirm model caching before downloading weights."}
    if status in {"planned", "unsupported"}:
        return {"status": "blocked", "label": "Blocked", "message": readiness.get("message") or "This provider is not runnable yet."}
    return {"status": "not_configured", "label": "Not configured", "message": readiness.get("message") or "Complete setup before running."}


def _setup_state_for_provider(
    definition: Mapping[str, Any],
    readiness: Mapping[str, Any],
    model_cache: Mapping[str, Any],
    credentials: list[dict[str, Any]],
    runtime_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    provider_id = str(definition.get("id") or "")
    base = _setup_state_from_readiness(readiness)
    if provider_id not in LOCAL_MODEL_CACHE_PROVIDER_IDS:
        return base
    runtime_verification = runtime_verification or {}
    runtime_verified = bool(runtime_verification.get("verified"))
    preflight = {
        "runtimeAvailable": bool(readiness.get("configured")),
        "accessConfigured": any(item.get("name") == "hf_token" and item.get("configured") for item in credentials) if provider_id == "sam3-local" else True,
        "accessVerified": bool(model_cache.get("cached")) or provider_id != "sam3-local",
        "modelCached": bool(model_cache.get("cached")),
        "smokeTested": runtime_verified,
        "runnable": bool(readiness.get("configured") and model_cache.get("cached") and runtime_verified),
    }
    if not readiness.get("configured"):
        return {**base, "preflight": preflight, "runnable": False, "nextAction": "install"}
    if model_cache.get("cached") and runtime_verified:
        return {
            "status": "ready",
            "label": "Ready",
            "message": runtime_verification.get("message") or model_cache.get("message") or "Model setup is ready for this workflow.",
            "preflight": preflight,
            "runnable": True,
            "nextAction": "continue",
        }
    if model_cache.get("cached"):
        return {
            "status": "needs_smoke",
            "label": "Ready to verify",
            "message": str(runtime_verification.get("message") or "The model cache is recorded. Run a smoke test to load it on the selected device and warm it up."),
            "preflight": preflight,
            "runnable": False,
            "nextAction": "smoke",
        }
    if provider_id == "sam3-local" and not preflight["accessConfigured"] and model_cache.get("status") in {"not_cached", "cache_unknown"}:
        return {
            "status": "needs_access",
            "label": "Needs Hugging Face access",
            "message": "Paste a Hugging Face token for facebook/sam3, then check access before caching the model.",
            "preflight": preflight,
            "runnable": False,
            "nextAction": "check_access",
        }
    if model_cache.get("status") in {"invalid_model", "invalid_cache", "missing_model"}:
        return {
            "status": "needs_path",
            "label": "Needs model directory",
            "message": str(model_cache.get("message") or "Choose a valid Hugging Face repo id or local from_pretrained directory."),
            "preflight": preflight,
            "runnable": False,
            "nextAction": "choose_model",
        }
    if model_cache.get("status") == "cache_unknown":
        return {
            "status": "not_configured",
            "label": "Needs setup",
            "message": str(model_cache.get("message") or "Install setup tools before checking the runtime model cache."),
            "preflight": preflight,
            "runnable": False,
            "nextAction": "install",
        }
    return {
        "status": "needs_download_confirmation",
        "label": "Confirm model cache",
        "message": str(model_cache.get("message") or "Cache the selected model before running."),
        "preflight": preflight,
        "runnable": False,
        "nextAction": "cache_model",
    }


def _sam3_tracker_auto_masks_importable() -> bool:
    try:
        from transformers import Sam3TrackerModel, Sam3TrackerProcessor, pipeline  # type: ignore
    except Exception:
        return False
    return Sam3TrackerModel is not None and Sam3TrackerProcessor is not None and pipeline is not None


def _model_status(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> dict[str, Any]:
    profile = _profile_definition(definition, settings)
    selected = settings.get("selected_model") or profile.get("defaultModel") or definition.get("defaultModel")
    custom = str(settings.get("custom_model_id") or "").strip()
    if selected == CUSTOM_MODEL_ID and not custom:
        return {"status": "missing_model", "selectedModel": selected, "effectiveModel": ""}
    return {"status": "ready", "selectedModel": selected, "effectiveModel": custom if selected == CUSTOM_MODEL_ID else selected}


def _effective_model(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> str:
    status = _model_status(definition, settings)
    profile = _profile_definition(definition, settings)
    return str(status.get("effectiveModel") or profile.get("defaultModel") or definition.get("defaultModel") or "")


def _runtime_effective_model(
    definition: Mapping[str, Any],
    settings: Mapping[str, Any],
    environ: Mapping[str, str],
) -> str:
    effective_model = _effective_model(definition, settings)
    env_defaults = {
        "openrouter": "OPENROUTER_DEFAULT_MODEL",
        "openai": "OPENAI_DEFAULT_MODEL",
        "sam3-hosted": "SAM3_HOSTED_MODEL",
        "sam2-hosted": "HOSTED_SEGMENTATION_MODEL",
        "sam2-hf-auto-masks": "SAM2_HF_AUTO_MASKS_MODEL",
        "sam3-local": "SAM3_TRACKER_MODEL",
    }
    env = env_defaults.get(str(definition["id"]))
    if env and not settings.get("selected_model") and environ.get(env):
        effective_model = str(environ[env])
    return effective_model


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_url(value: Any, field_name: str) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if not _valid_http_url(text):
        raise ValueError(f"{field_name}: expected an http:// or https:// URL.")
    return text


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _sam3_tracker_video_importable() -> bool:
    status = sam3_tracker_video_runtime_status()
    return bool(status.get("importable") and not status.get("knownBroken"))


def _float_payload(payload: Mapping[str, Any], key: str, default: float) -> float:
    snake = "".join([f"_{char.lower()}" if char.isupper() else char for char in key]).lstrip("_")
    try:
        return float(payload.get(key, payload.get(snake, default)))
    except (TypeError, ValueError):
        return default


def _sam3_smoke_timeout_seconds(payload: Mapping[str, Any], environ: Mapping[str, str] | None) -> float:
    default = 900.0
    if environ and environ.get("MOTIONJSON_SAM3_SMOKE_TIMEOUT_SECONDS"):
        try:
            default = float(environ["MOTIONJSON_SAM3_SMOKE_TIMEOUT_SECONDS"])
        except (TypeError, ValueError):
            default = 900.0
    return min(max(_float_payload(payload, "sam3SmokeTimeoutSeconds", default), 30.0), 7200.0)


def _ensure_accepts_credentials(definition: Mapping[str, Any]) -> None:
    if not definition.get("credentialFields"):
        raise ValueError(f"{definition['name']} does not use API keys. Leave mock/local providers credential-free.")


def _credential_payload_name(name: str) -> str:
    if name == "api_key":
        return "apiKey"
    if name == "hf_token":
        return "hfToken"
    parts = [part for part in str(name).split("_") if part]
    if not parts:
        return str(name)
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _clean_credential(provider_id: str, field: Mapping[str, Any], value: str) -> str:
    text = value.strip()
    if not _api_key_plausible(text):
        label = str(field.get("label") or field.get("name") or "credential")
        raise ValueError(f"{provider_id} {label} is invalid or too short. Paste the value without spaces.")
    return text


def _clean_api_key(provider_id: str, value: str) -> str:
    return _clean_credential(provider_id, {"name": "api_key", "label": "API key"}, value)


def _api_key_plausible(value: str) -> bool:
    text = str(value or "").strip()
    return len(text) >= 8 and not re.search(r"\s", text)


def _validate_model_settings(definition: Mapping[str, Any], settings: Mapping[str, Any]) -> None:
    selected = settings.get("selected_model")
    if not selected:
        return
    allowed = {option["id"] for option in definition.get("modelOptions", [])}
    if selected not in allowed:
        raise ValueError(f"{definition['name']} model selection is not in the provider registry.")
    if selected == CUSTOM_MODEL_ID and not definition.get("customModelAllowed"):
        raise ValueError(f"{definition['name']} does not allow custom model ids.")


def _is_secret_key(key: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(part in normalized for part in ("apikey", "authorization", "password", "secret", "token"))
