from __future__ import annotations

import fnmatch
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .final_render import final_export_entry, load_scene
from .scene_graph import write_json

EXCLUDE_PATTERNS = (
    ".env",
    ".env.*",
    ".motionjson-cache/*",
    "node_modules/*",
    "frames/*",
    "masks/*",
    "objects/*/masks/*",
    "objects/*/debug/*",
    "objects/*/layers/*",
    "**/.DS_Store",
)


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _is_excluded(rel_path: str) -> bool:
    return any(fnmatch.fnmatch(rel_path, pattern) for pattern in EXCLUDE_PATTERNS)


def _safe_rel_path(rel_path: str) -> str | None:
    normalized = rel_path.replace("\\", "/").lstrip("/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts or not normalized:
        return None
    return normalized


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write_index(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MotionJSON Website Package</title>
    <style>
      body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #fbfaf6; font-family: system-ui, sans-serif; }
      #motion { width: min(640px, 92vw); aspect-ratio: 3 / 2; }
    </style>
  </head>
  <body>
    <div id="motion"></div>
    <script type="module">
      import { mountMotionJSON } from "./runtime/index.js";
      await mountMotionJSON("#motion", "./web_asset_manifest.json", { background: "#fbfaf6" });
    </script>
  </body>
</html>
""",
        encoding="utf-8",
    )


def _copy_file(source: Path, package_root: Path, rel_path: str, files: dict[str, int]) -> None:
    safe_path = _safe_rel_path(rel_path)
    if not safe_path or not source.exists() or not source.is_file() or _is_excluded(safe_path):
        return
    dest = package_root / safe_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    files[safe_path] = dest.stat().st_size


def _copy_tree(source: Path, package_root: Path, rel_base: str, files: dict[str, int]) -> None:
    if not source.exists():
        return
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        rel_path = f"{rel_base}/{_rel(path, source)}"
        _copy_file(path, package_root, rel_path, files)


def _include_scene_assets(out_dir: Path, package_root: Path, scene: dict[str, Any], files: dict[str, int]) -> None:
    for required in ("scene_graph.json", "object_motion.json", "web_asset_manifest.json", "resource_profile.json"):
        _copy_file(out_dir / required, package_root, required, files)

    for obj in scene.get("objects", []):
        object_id = obj.get("id")
        if not object_id:
            continue
        manifest_rel = f"objects/{object_id}/object_manifest.json"
        _copy_file(out_dir / manifest_rel, package_root, manifest_rel, files)

        spritesheet = obj.get("assets", {}).get("spritesheet")
        if isinstance(spritesheet, dict) and spritesheet.get("path"):
            _copy_file(out_dir / spritesheet["path"], package_root, spritesheet["path"], files)

        poster = next((entry.get("asset") for entry in obj.get("motion", []) if entry.get("asset")), None)
        if poster:
            _copy_file(out_dir / poster, package_root, poster, files)

        # Keep sequence fallback available for the browser runtime while omitting masks/debug frames.
        for entry in obj.get("motion", []):
            asset = entry.get("asset")
            if asset:
                _copy_file(out_dir / asset, package_root, asset, files)

        production = obj.get("assets", {}).get("production", {})
        for asset in (production.get("assets") or {}).values():
            if isinstance(asset, dict) and asset.get("status") == "ready" and asset.get("path"):
                _copy_file(out_dir / asset["path"], package_root, asset["path"], files)


def _write_package_manifest(package_root: Path, scene: dict[str, Any], files: dict[str, int]) -> dict[str, Any]:
    rights = {}
    for obj in scene.get("objects", []):
        if obj.get("id") and obj.get("rights"):
            rights[obj["id"]] = obj["rights"]
    manifest = {
        "schema": "motionjson.website_package_manifest.v0.1",
        "packageType": "website_runtime_zip",
        "aiUsage": "none",
        "entrypoint": "index.html",
        "sourceSceneGraph": "scene_graph.json",
        "files": [{"path": path, "bytes": size} for path, size in sorted(files.items())],
        "totalBytes": sum(files.values()),
        "rights": rights,
        "exclusions": list(EXCLUDE_PATTERNS),
        "notes": [
            "All package paths are relative.",
            "Masks, debug frames, caches, node_modules, and environment files are excluded by default.",
        ],
    }
    write_json(package_root / "package_manifest.json", manifest)
    files["package_manifest.json"] = (package_root / "package_manifest.json").stat().st_size
    manifest["files"] = [{"path": path, "bytes": size} for path, size in sorted(files.items())]
    manifest["totalBytes"] = sum(files.values())
    write_json(package_root / "package_manifest.json", manifest)
    files["package_manifest.json"] = (package_root / "package_manifest.json").stat().st_size
    return manifest


def export_website_package(*, out_dir: str | Path, output_path: str | Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene = load_scene(out_dir)

    with tempfile.TemporaryDirectory(prefix="motionjson_website_package_") as tmp:
        package_root = Path(tmp) / "package"
        package_root.mkdir(parents=True)
        files: dict[str, int] = {}

        _include_scene_assets(out_dir, package_root, scene, files)
        _copy_tree(out_dir / "preview" / "runtime", package_root, "runtime", files)
        _copy_tree(out_dir / "preview", package_root, "preview", files)
        _write_index(package_root / "index.html")
        files["index.html"] = (package_root / "index.html").stat().st_size
        _write_index(package_root / "preview" / "index.html")
        files["preview/index.html"] = (package_root / "preview" / "index.html").stat().st_size
        _write_package_manifest(package_root, scene, files)

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(package_root.rglob("*")):
                if not path.is_file():
                    continue
                rel_path = _rel(path, package_root)
                if Path(rel_path).is_absolute() or ".." in Path(rel_path).parts:
                    raise ValueError(f"Unsafe package path: {rel_path}")
                archive.write(path, rel_path)

    return final_export_entry(
        export_type="website_package_zip",
        format_name="zip",
        output_path=output_path,
        out_dir=out_dir,
        status="ready" if output_path.exists() and output_path.stat().st_size > 0 else "error",
        mime_type="application/zip",
        extra={
            "cachedSources": ["scene_graph.json", "web_asset_manifest.json", "object_motion.json", "resource_profile.json", "objects/*"],
            "packageManifest": "package_manifest.json",
            "excludes": list(EXCLUDE_PATTERNS),
            "bytes": _safe_size(output_path),
        },
    )
