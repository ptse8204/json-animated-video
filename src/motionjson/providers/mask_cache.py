from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np
from PIL import Image


def normalize_binary_mask(mask: np.ndarray, *, threshold: float | None = None) -> np.ndarray:
    """Return a provider-independent 2D uint8 mask with values 0 or 255."""

    arr = np.asarray(mask)
    while arr.ndim > 2 and 1 in arr.shape:
        arr = np.squeeze(arr)
    if arr.ndim == 3:
        arr = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    if arr.ndim != 2:
        raise ValueError(f"Mask must normalize to a 2D array, got shape {arr.shape}.")

    if arr.dtype == np.bool_:
        binary = arr
    elif np.issubdtype(arr.dtype, np.floating):
        cutoff = 0.0 if threshold is None else threshold
        if threshold is None and arr.size and float(np.nanmax(arr)) <= 1.0 and float(np.nanmin(arr)) >= 0.0:
            cutoff = 0.5
        binary = arr > cutoff
    else:
        cutoff = 127 if threshold is None else threshold
        binary = arr > cutoff
    return np.where(binary, 255, 0).astype(np.uint8)


@dataclass
class MaskCache:
    """Filesystem cache for normalized binary PNG masks plus a manifest."""

    root: str | Path = ".motionjson-cache/masks"
    manifest_name: str = "manifest.json"
    _manifest: dict[str, Any] = field(default_factory=dict, init=False)
    hits: int = field(default=0, init=False)
    misses: int = field(default=0, init=False)
    read_bytes: int = field(default=0, init=False)
    written_bytes: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.manifest_path = self.root / self.manifest_name
        self._manifest = self._load_manifest()

    def key_for(
        self,
        *,
        provider: str,
        config: Mapping[str, Any],
        source: str | Path,
        prompt: Mapping[str, Any],
        frame_index: int,
        object_id: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        payload = {
            "provider": provider,
            "config": dict(config),
            "source": self._source_identity(source),
            "prompt": dict(prompt),
            "object_id": object_id,
            "metadata": dict(metadata or {}),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, key: str, *, frame_index: int = 0) -> np.ndarray | None:
        entry = self._manifest.get("entries", {}).get(key)
        if not entry:
            self.misses += 1
            return None
        masks = entry.get("masks", {})
        rel_path = masks.get(str(frame_index))
        if rel_path is None:
            self.misses += 1
            return None
        path = self.root / rel_path
        if not path.exists():
            self.misses += 1
            return None
        self.hits += 1
        self.read_bytes += path.stat().st_size
        return normalize_binary_mask(np.array(Image.open(path).convert("L")))

    def set(self, key: str, mask: np.ndarray, *, frame_index: int = 0, metadata: Mapping[str, Any] | None = None) -> Path:
        binary = normalize_binary_mask(mask)
        path = self._path_for_key(key, frame_index=frame_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(binary).save(path)
        self.written_bytes += path.stat().st_size

        self.root.mkdir(parents=True, exist_ok=True)
        entries = self._manifest.setdefault("entries", {})
        entry = entries.setdefault(key, {"masks": {}, "metadata": dict(metadata or {})})
        entry["masks"][str(frame_index)] = path.relative_to(self.root).as_posix()
        entry["width"] = int(binary.shape[1])
        entry["height"] = int(binary.shape[0])
        entry["metadata"] = {**dict(entry.get("metadata", {})), **dict(metadata or {})}
        self._write_entry_manifest(key, entry)
        self._write_manifest()
        return path

    def summary(self) -> dict[str, Any]:
        entries = self._manifest.get("entries", {})
        manifest_masks = 0
        manifest_bytes = 0
        for entry in entries.values():
            masks = entry.get("masks", {}) if isinstance(entry, Mapping) else {}
            manifest_masks += len(masks)
            for rel_path in masks.values():
                path = self.root / str(rel_path)
                if path.exists():
                    manifest_bytes += path.stat().st_size
        requests = self.hits + self.misses
        hit_rate = round(self.hits / requests, 4) if requests else None
        return {
            "schema": "motionjson.mask_cache_summary.v0.1",
            "root": str(self.root),
            "entries": len(entries),
            "maskCount": manifest_masks,
            "storedBytes": manifest_bytes,
            "hits": self.hits,
            "misses": self.misses,
            "hitRate": hit_rate,
            "readBytes": self.read_bytes,
            "writtenBytes": self.written_bytes,
            "aiUsage": "none",
        }

    def _path_for_key(self, key: str, *, frame_index: int) -> Path:
        return self.root / key / f"mask_{frame_index:06d}.png"

    def _source_identity(self, source: str | Path) -> Mapping[str, Any]:
        path = Path(source)
        identity: dict[str, Any] = {"path": str(source)}
        try:
            stat = path.stat()
        except OSError:
            return identity
        identity.update({"size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
        return identity

    def _write_entry_manifest(self, key: str, entry: Mapping[str, Any]) -> None:
        directory = self.root / key
        directory.mkdir(parents=True, exist_ok=True)
        (directory / self.manifest_name).write_text(
            json.dumps({"schema": "motionjson.mask_cache_entry.v0.1", "key": key, **dict(entry)}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"schema": "motionjson.mask_cache.v0.1", "entries": {}}
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if "entries" not in data or not isinstance(data["entries"], dict):
            data["entries"] = {}
        return data

    def _write_manifest(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._manifest, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.manifest_path)
