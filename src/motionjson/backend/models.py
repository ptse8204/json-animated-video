from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from motionjson.provider_registry import rejected_segmentation_aliases, worker_extract_provider_ids


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


ALLOWED_EXTRACT_MASK_PROVIDERS = worker_extract_provider_ids()
REJECTED_SEGMENTATION_ALIASES = rejected_segmentation_aliases()


def validate_extract_provider_policy(mask_provider: str) -> str:
    provider = (mask_provider or "threshold").strip().lower()
    if provider in REJECTED_SEGMENTATION_ALIASES or provider not in ALLOWED_EXTRACT_MASK_PROVIDERS:
        raise ProviderPolicyError(
            "backend extraction only allows supported local UI engines: threshold, external, mock, motion, sam2-local, sam2-hf-auto-masks, sam2-hosted, sam3-local, or sam3-hosted"
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
