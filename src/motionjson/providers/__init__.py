from __future__ import annotations

from .base import (
    ExportProvider,
    LLMProvider,
    MattingProvider,
    ProviderConfigError,
    ProviderError,
    ProviderExecutionError,
    RenderProvider,
    SegmentationProvider,
    StorageProvider,
)
from .mocks import MockExportProvider, MockLLMProvider, MockMattingProvider, MockRenderProvider, MockSegmentationProvider, MockStorageProvider
from .segmentation import MaskProviderSegmentationAdapter, SegmentationMaskProvider, as_segmentation_provider

__all__ = [
    "ExportProvider",
    "LLMProvider",
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
    "RenderProvider",
    "SegmentationMaskProvider",
    "SegmentationProvider",
    "StorageProvider",
    "as_segmentation_provider",
]


def __getattr__(name: str):
    if name == "OpenRouterLLMProvider":
        from .openrouter import OpenRouterLLMProvider

        return OpenRouterLLMProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
