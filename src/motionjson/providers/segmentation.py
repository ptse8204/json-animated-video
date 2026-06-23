from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Sequence

import numpy as np

from ..masks import BaseMaskProvider, MaskProvider
from ..video import VideoInfo
from .base import BatchSegmentationProvider, BatchSegmentationRequest, ProviderAttempt, SegmentationProvider


REJECTED_SEGMENTATION_PROVIDER_NAMES = {"evolink", "evolink-planner", "openrouter", "llm", "vlm"}


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


def _provider_name(provider: Any) -> str:
    explicit = getattr(provider, "provider_name", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    return provider.__class__.__name__


@dataclass
class MaskProviderSegmentationAdapter:
    """Expose an existing MaskProvider through the SegmentationProvider contract."""

    mask_provider: MaskProvider
    provider_name: str | None = None

    def prepare(self, video_metadata: VideoInfo) -> None:
        self.mask_provider.prepare(video_metadata)

    def segment(
        self,
        frame_index: int,
        frame_bgr: np.ndarray,
        *,
        prompt_point: tuple[int, int] | None = None,
        prompt_box: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        return self.mask_provider.get_mask(frame_index, frame_bgr)

    def segment_batch(self, requests: Sequence[BatchSegmentationRequest]) -> Sequence[np.ndarray]:
        batch = getattr(self.mask_provider, "get_masks_batch", None)
        if callable(batch):
            return batch(requests)
        return [
            self.segment(
                request.frame_index,
                request.frame_bgr,
                prompt_point=request.prompt_point,
                prompt_box=request.prompt_box,
            )
            for request in requests
        ]

    def close(self) -> None:
        self.mask_provider.close()

    def performance_summary(self) -> dict[str, Any]:
        summary = getattr(self.mask_provider, "performance_summary", None)
        if callable(summary):
            return summary()
        return {"providerName": self.provider_name or _provider_name(self.mask_provider), "attempts": []}


@dataclass
class SegmentationMaskProvider(BaseMaskProvider):
    """Let a SegmentationProvider run in the existing extraction pipeline."""

    segmentation_provider: SegmentationProvider
    prompt_point: tuple[int, int] | None = None
    prompt_box: tuple[int, int, int, int] | None = None
    _attempts: list[dict[str, Any]] = None  # type: ignore[assignment]
    _batch_used: bool = False

    def prepare(self, video_metadata: VideoInfo) -> None:
        super().prepare(video_metadata)
        self._attempts = []
        self.segmentation_provider.prepare(video_metadata)

    def get_mask(self, frame_index: int, frame_bgr: np.ndarray) -> np.ndarray:
        start = time.perf_counter()
        provider_name = _provider_name(self.segmentation_provider)
        try:
            mask = self.segmentation_provider.segment(
                frame_index,
                frame_bgr,
                prompt_point=self.prompt_point,
                prompt_box=self.prompt_box,
            )
        except Exception as exc:
            self._attempts.append(
                ProviderAttempt(
                    provider=provider_name,
                    operation="segment",
                    status="error",
                    elapsed_ms=_elapsed_ms(start),
                    frame_index=frame_index,
                    error=str(exc),
                ).to_dict()
            )
            raise
        self._attempts.append(
            ProviderAttempt(
                provider=provider_name,
                operation="segment",
                status="success",
                elapsed_ms=_elapsed_ms(start),
                frame_index=frame_index,
            ).to_dict()
        )
        return mask

    def get_masks_batch(self, requests: Sequence[BatchSegmentationRequest]) -> Sequence[np.ndarray]:
        provider_name = _provider_name(self.segmentation_provider)
        batch = getattr(self.segmentation_provider, "segment_batch", None)
        if callable(batch):
            self._batch_used = True
            start = time.perf_counter()
            try:
                masks = list(batch(requests))
            except Exception as exc:
                self._attempts.append(
                    ProviderAttempt(
                        provider=provider_name,
                        operation="segment_batch",
                        status="error",
                        elapsed_ms=_elapsed_ms(start),
                        error=str(exc),
                    ).to_dict()
                )
                raise
            self._attempts.append(
                ProviderAttempt(
                    provider=provider_name,
                    operation="segment_batch",
                    status="success",
                    elapsed_ms=_elapsed_ms(start),
                    estimated_cost_units=0.0,
                ).to_dict()
            )
            return masks
        return [self.get_mask(request.frame_index, request.frame_bgr) for request in requests]

    def close(self) -> None:
        self.segmentation_provider.close()

    def performance_summary(self) -> dict[str, Any]:
        nested_summary = getattr(self.segmentation_provider, "performance_summary", None)
        nested = nested_summary() if callable(nested_summary) else {}
        cache_summary = nested.get("cache") if isinstance(nested, dict) else None
        return {
            "providerName": _provider_name(self.segmentation_provider),
            "batching": {
                "supported": isinstance(self.segmentation_provider, BatchSegmentationProvider)
                or callable(getattr(self.segmentation_provider, "segment_batch", None)),
                "used": bool(self._batch_used),
                "fallback": "sequential" if not self._batch_used else None,
            },
            "attempts": list(self._attempts or []),
            "nested": nested or None,
            "cache": cache_summary,
        }


@dataclass
class FallbackSegmentationProvider:
    """Try segmentation providers in order and record deterministic fallback attempts."""

    providers: Sequence[tuple[str, SegmentationProvider]]
    video_metadata: VideoInfo | None = None
    _prepared: dict[str, bool] = None  # type: ignore[assignment]
    _disabled: dict[str, str] = None  # type: ignore[assignment]
    _attempts: list[dict[str, Any]] = None  # type: ignore[assignment]
    provider_name: str = "segmentation-fallback"

    def __post_init__(self) -> None:
        names = [name.strip().lower() for name, _provider in self.providers]
        rejected = sorted(name for name in names if name in REJECTED_SEGMENTATION_PROVIDER_NAMES)
        if rejected:
            raise ValueError(f"OpenRouter/LLM providers are not segmentation providers: {', '.join(rejected)}")
        if not self.providers:
            raise ValueError("At least one segmentation provider is required for fallback routing")
        self._prepared = {}
        self._disabled = {}
        self._attempts = []

    def prepare(self, video_metadata: VideoInfo) -> None:
        self.video_metadata = video_metadata
        last_error: Exception | None = None
        for index in range(len(self.providers)):
            try:
                self._prepare_provider(index)
                return
            except Exception as exc:
                last_error = exc
                if index < len(self.providers) - 1:
                    continue
                raise
        if last_error is not None:
            raise last_error

    def segment(
        self,
        frame_index: int,
        frame_bgr: np.ndarray,
        *,
        prompt_point: tuple[int, int] | None = None,
        prompt_box: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        last_error: Exception | None = None
        for index, (name, provider) in enumerate(self.providers):
            if name in self._disabled and index < len(self.providers) - 1:
                continue
            try:
                self._prepare_provider(index)
            except Exception as exc:
                last_error = exc
                continue
            start = time.perf_counter()
            try:
                mask = provider.segment(
                    frame_index,
                    frame_bgr,
                    prompt_point=prompt_point,
                    prompt_box=prompt_box,
                )
            except Exception as exc:
                last_error = exc
                self._attempts.append(
                    ProviderAttempt(
                        provider=name,
                        operation="segment",
                        status="error",
                        elapsed_ms=_elapsed_ms(start),
                        frame_index=frame_index,
                        error=str(exc),
                    ).to_dict()
                )
                if index < len(self.providers) - 1:
                    self._disabled[name] = str(exc)
                continue
            self._attempts.append(
                ProviderAttempt(
                    provider=name,
                    operation="segment",
                    status="success",
                    elapsed_ms=_elapsed_ms(start),
                    frame_index=frame_index,
                ).to_dict()
            )
            return mask
        raise last_error or RuntimeError("No segmentation provider succeeded")

    def segment_batch(self, requests: Sequence[BatchSegmentationRequest]) -> Sequence[np.ndarray]:
        return [
            self.segment(
                request.frame_index,
                request.frame_bgr,
                prompt_point=request.prompt_point,
                prompt_box=request.prompt_box,
            )
            for request in requests
        ]

    def close(self) -> None:
        errors: list[str] = []
        for name, provider in self.providers:
            try:
                provider.close()
            except Exception as exc:  # pragma: no cover - close should be best effort.
                errors.append(f"{name}: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors))

    def performance_summary(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providers": [name for name, _provider in self.providers],
            "disabledProviders": dict(self._disabled),
            "attempts": list(self._attempts),
            "fallbackUsed": any(attempt["status"] == "success" and attempt["provider"] != self.providers[0][0] for attempt in self._attempts),
        }

    def _prepare_provider(self, index: int) -> None:
        if self.video_metadata is None:
            raise RuntimeError("FallbackSegmentationProvider.prepare() must be called before segment().")
        name, provider = self.providers[index]
        if self._prepared.get(name):
            return
        start = time.perf_counter()
        try:
            provider.prepare(self.video_metadata)
        except Exception as exc:
            self._disabled[name] = str(exc)
            self._attempts.append(
                ProviderAttempt(
                    provider=name,
                    operation="prepare",
                    status="error",
                    elapsed_ms=_elapsed_ms(start),
                    error=str(exc),
                ).to_dict()
            )
            raise
        self._prepared[name] = True
        self._attempts.append(
            ProviderAttempt(
                provider=name,
                operation="prepare",
                status="success",
                elapsed_ms=_elapsed_ms(start),
            ).to_dict()
        )


def as_segmentation_provider(mask_provider: MaskProvider) -> SegmentationProvider:
    """Wrap a legacy mask provider unless it already implements segmentation."""

    if isinstance(mask_provider, SegmentationProvider):
        return mask_provider
    return MaskProviderSegmentationAdapter(mask_provider)
