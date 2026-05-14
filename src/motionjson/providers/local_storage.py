from __future__ import annotations

import re
from pathlib import Path

SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class LocalStorageProvider:
    """Filesystem-backed StorageProvider with normalized relative keys."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for_key(self, key: str) -> Path:
        raw_path = Path(key.replace("\\", "/"))
        if raw_path.is_absolute():
            raise ValueError(f"unsafe storage key: {key!r}")
        normalized = key.replace("\\", "/").lstrip("/")
        path = Path(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts or not SAFE_KEY_RE.match(normalized):
            raise ValueError(f"unsafe storage key: {key!r}")
        resolved = (self.root / path).resolve()
        if self.root not in (resolved, *resolved.parents):
            raise ValueError(f"storage key escapes root: {key!r}")
        return resolved

    def save_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(data))
        return path.as_uri()

    def load_bytes(self, key: str) -> bytes:
        path = self._path_for_key(key)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"storage key not found: {key}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path_for_key(key).is_file()
