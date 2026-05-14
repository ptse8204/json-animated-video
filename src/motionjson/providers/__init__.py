from __future__ import annotations

from .base import (
    ExportProvider,
    BatchSegmentationProvider,
    BatchSegmentationRequest,
    CompressionOutcome,
    LLMProvider,
    MattingProvider,
    PhaseTiming,
    ProviderConfigError,
    ProviderError,
    ProviderExecutionError,
    ProviderAttempt,
    RenderProvider,
    SegmentationProvider,
    StorageProvider,
)
from .mask_cache import MaskCache, normalize_binary_mask
from .local_storage import LocalStorageProvider
from .mocks import MockExportProvider, MockLLMProvider, MockMattingProvider, MockRenderProvider, MockSegmentationProvider, MockStorageProvider
from .sam2 import HostedSAM2SegmentationProvider, LocalSAM2SegmentationProvider, SAM2HostedSegmentationProvider, SAM2LocalSegmentationProvider
from .segmentation import FallbackSegmentationProvider, MaskProviderSegmentationAdapter, SegmentationMaskProvider, as_segmentation_provider

__all__ = [
    "ExportProvider",
    "BatchSegmentationProvider",
    "BatchSegmentationRequest",
    "CompressionOutcome",
    "FallbackSegmentationProvider",
    "HostedSAM2SegmentationProvider",
    "LLMProvider",
    "LocalSAM2SegmentationProvider",
    "LocalStorageProvider",
    "MaskCache",
    "MaskProviderSegmentationAdapter",
    "MattingProvider",
    "MockExportProvider",
    "MockLLMProvider",
    "MockMattingProvider",
    "MockRenderProvider",
    "MockSegmentationProvider",
    "MockStorageProvider",
    "OpenRouterLLMProvider",
    "ProviderConfigError",
    "ProviderError",
    "ProviderExecutionError",
    "PhaseTiming",
    "ProviderAttempt",
    "RenderProvider",
    "SAM2HostedSegmentationProvider",
    "SAM2LocalSegmentationProvider",
    "SegmentationMaskProvider",
    "SegmentationProvider",
    "StorageProvider",
    "as_segmentation_provider",
    "normalize_binary_mask",
]


def __getattr__(name: str):
    if name == "OpenRouterLLMProvider":
        from .openrouter import OpenRouterLLMProvider

        return OpenRouterLLMProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
