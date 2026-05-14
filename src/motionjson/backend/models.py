from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class BackendError(RuntimeError):
    """Base class for backend service errors."""


class UnauthorizedError(BackendError):
    """Raised when credentials or sessions are invalid."""


class ForbiddenError(BackendError):
    """Raised when a user tries to access another user's resource."""


class NotFoundError(BackendError):
    """Raised when a scoped backend resource cannot be found."""


class ProviderPolicyError(BackendError):
    """Raised when a job payload requests a disallowed provider."""


ALLOWED_EXTRACT_MASK_PROVIDERS = {"threshold", "external", "mock"}
REJECTED_SEGMENTATION_ALIASES = {"openrouter", "llm", "vlm", "sam2", "sam2-local", "sam2-hosted", "hosted", "replicate", "runpod"}


def validate_extract_provider_policy(mask_provider: str) -> str:
    provider = (mask_provider or "threshold").strip().lower()
    if provider in REJECTED_SEGMENTATION_ALIASES or provider not in ALLOWED_EXTRACT_MASK_PROVIDERS:
        raise ProviderPolicyError(
            "backend extraction only allows deterministic local providers: threshold, external, or mock"
        )
    return provider


@dataclass(frozen=True)
class SessionResult:
    token: str
    session: dict[str, Any]


def row_to_dict(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)
