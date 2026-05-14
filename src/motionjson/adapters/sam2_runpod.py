"""RunPod SAM2 adapter stub.

This module is credential-gated and intentionally avoids default network calls.
Inject a transport/client from application code when wiring a real hosted
segmentation deployment.
"""
from __future__ import annotations

import os
from typing import Any, Mapping

from ..providers.base import ProviderConfigError


def run_sam2_video_runpod(
    *,
    payload: Mapping[str, Any],
    endpoint_id: str | None = None,
    api_key: str | None = None,
    transport: Any | None = None,
    base_url: str = "https://api.runpod.ai/v2",
) -> Any:
    token = api_key or os.environ.get("RUNPOD_API_KEY")
    resolved_endpoint = endpoint_id or os.environ.get("RUNPOD_SAM2_ENDPOINT_ID")
    if not token:
        raise ProviderConfigError("Set RUNPOD_API_KEY or pass api_key before using the RunPod SAM2 stub.")
    if not resolved_endpoint:
        raise ProviderConfigError("Set RUNPOD_SAM2_ENDPOINT_ID or pass endpoint_id before using the RunPod SAM2 stub.")
    if transport is None:
        raise ProviderConfigError("RunPod SAM2 stub requires an injected transport/client; it makes no default network calls.")
    return transport.post_json(
        f"{base_url.rstrip('/')}/{resolved_endpoint}/runsync",
        {"input": dict(payload)},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
