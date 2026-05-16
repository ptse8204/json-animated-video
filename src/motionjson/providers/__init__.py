from __future__ import annotations

from .base import (
    BatchSegmentationProvider,
    BatchSegmentationRequest,
    CompressionOutcome,
    Exporter,
    ExportProvider,
    LLMProvider,
    MaskProvider,
    MattingProvider,
    ObjectCandidateProvider,
    PhaseTiming,
    ProviderConfigError,
    ProviderError,
    ProviderExecutionError,
    ProviderAttempt,
    RenderProvider,
    SegmentationProvider,
    StorageProvider,
    TrackLinker,
    Vectorizer,
    VideoTracker,
)
from .mask_cache import MaskCache, normalize_binary_mask
from .local_storage import LocalStorageProvider
from .mocks import (
    MockExportProvider,
    MockLLMProvider,
    MockMaskProvider,
    MockMattingProvider,
    MockObjectCandidateProvider,
    MockPipelineExporter,
    MockRenderProvider,
    MockSegmentationProvider,
    MockStorageProvider,
    MockTrackLinker,
    MockVectorizer,
    MockVideoTracker,
)
from .pipeline_adapters import (
    ContourVectorizer,
    IdentityTrackLinker,
    ManualPromptCandidateProvider,
    MotionJSONArtifactExporter,
    ObjectSpecCandidateProvider,
    ObjectSpecInitialMaskProvider,
    PerFrameMaskVideoTracker,
)
from .sam2 import HostedSAM2SegmentationProvider, LocalSAM2SegmentationProvider, SAM2HostedSegmentationProvider, SAM2LocalSegmentationProvider
from .segmentation import FallbackSegmentationProvider, MaskProviderSegmentationAdapter, SegmentationMaskProvider, as_segmentation_provider

__all__ = [
    "ExportProvider",
    "BatchSegmentationProvider",
    "BatchSegmentationRequest",
    "CompressionOutcome",
    "ContourVectorizer",
    "Exporter",
    "FallbackSegmentationProvider",
    "HostedSAM2SegmentationProvider",
    "IdentityTrackLinker",
    "LLMProvider",
    "LocalSAM2SegmentationProvider",
    "LocalStorageProvider",
    "MaskCache",
    "MaskProvider",
    "MaskProviderSegmentationAdapter",
    "MattingProvider",
    "ManualPromptCandidateProvider",
    "MotionJSONArtifactExporter",
    "MockExportProvider",
    "MockLLMProvider",
    "MockMaskProvider",
    "MockMattingProvider",
    "MockObjectCandidateProvider",
    "MockPipelineExporter",
    "MockRenderProvider",
    "MockSegmentationProvider",
    "MockStorageProvider",
    "MockTrackLinker",
    "MockVectorizer",
    "MockVideoTracker",
    "OpenRouterLLMProvider",
    "ObjectCandidateProvider",
    "ObjectSpecCandidateProvider",
    "ObjectSpecInitialMaskProvider",
    "PerFrameMaskVideoTracker",
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
    "TrackLinker",
    "Vectorizer",
    "VideoTracker",
    "as_segmentation_provider",
    "normalize_binary_mask",
]


def __getattr__(name: str):
    if name == "OpenRouterLLMProvider":
        from .openrouter import OpenRouterLLMProvider

        return OpenRouterLLMProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
