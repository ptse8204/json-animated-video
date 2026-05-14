"""Packaged MotionJSON JSON Schemas."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

SCHEMA_IDS = {
    "motionjson.scene_graph.v0.1": "motionjson.scene_graph.v0.1.schema.json",
    "motionjson.object_manifest.v0.1": "motionjson.object_manifest.v0.1.schema.json",
    "motionjson.object_motion.v0.1": "motionjson.object_motion.v0.1.schema.json",
    "motionjson.web_asset_manifest.v0.1": "motionjson.web_asset_manifest.v0.1.schema.json",
    "motionjson.resource_profile.v0.1": "motionjson.resource_profile.v0.1.schema.json",
    "motionjson.final_export_manifest.v0.1": "motionjson.final_export_manifest.v0.1.schema.json",
    "motionjson.rights_manifest.v0.1": "motionjson.rights_manifest.v0.1.schema.json",
    "motionjson.correction_request.v0.1": "motionjson.correction_request.v0.1.schema.json",
    "motionjson.correction_manifest.v0.1": "motionjson.correction_manifest.v0.1.schema.json",
}


def schema_path(schema_id: str) -> Path:
    """Return a filesystem path for a packaged schema id."""
    try:
        name = SCHEMA_IDS[schema_id]
    except KeyError as exc:
        raise KeyError(f"Unknown MotionJSON schema: {schema_id}") from exc
    return Path(resources.files(__name__) / name)
