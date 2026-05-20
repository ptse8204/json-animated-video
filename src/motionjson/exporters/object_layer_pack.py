from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Sequence

from .scene_graph import write_json

OBJECT_LAYER_PACK_FORMAT = "motionjson.object_layer_pack.v0.1"


def _object_id(value: dict[str, Any], fallback: str = "") -> str:
    return str(value.get("id") or value.get("objectId") or value.get("object_id") or fallback)


def _unique_ids(values: Sequence[str] | None) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for value in values or []:
        object_id = str(value).strip()
        if object_id and object_id not in seen:
            ids.append(object_id)
            seen.add(object_id)
    return ids


def _routing_by_object(quality_routing: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(quality_routing, dict):
        return {}
    routes: dict[str, dict[str, Any]] = {}
    for item in quality_routing.get("objects", []):
        if not isinstance(item, dict):
            continue
        object_id = str(item.get("objectId") or item.get("object_id") or "")
        if object_id:
            routes[object_id] = item
    return routes


def _review_state(obj: dict[str, Any]) -> dict[str, Any]:
    discovery = obj.get("discovery") if isinstance(obj.get("discovery"), dict) else {}
    quality = obj.get("quality") if isinstance(obj.get("quality"), dict) else {}
    status = (
        discovery.get("reviewStatus")
        or discovery.get("review_status")
        or obj.get("reviewStatus")
        or obj.get("review_status")
        or obj.get("exportStatus")
        or discovery.get("exportStatus")
        or "accepted"
    )
    export_status = obj.get("exportStatus") or discovery.get("exportStatus") or status
    return {
        "status": str(status),
        "required": bool(discovery.get("reviewRequired") or quality.get("reviewRequired")),
        "exportStatus": str(export_status),
    }


def _object_entry(obj: dict[str, Any], route: dict[str, Any] | None) -> dict[str, Any]:
    object_id = _object_id(obj)
    discovery = obj.get("discovery") if isinstance(obj.get("discovery"), dict) else {}
    quality = obj.get("quality") if isinstance(obj.get("quality"), dict) else {}
    route = route or {}
    entry: dict[str, Any] = {
        "objectId": object_id,
        "label": obj.get("label") or object_id,
        "renderMode": obj.get("renderMode") or "raster_alpha_sequence",
        "zIndex": obj.get("zIndex", 0),
        "review": _review_state(obj),
        "artifacts": {
            "objectManifest": f"objects/{object_id}/object_manifest.json",
            "objectMotion": f"objects/{object_id}/object_motion.json",
            "webAssetManifest": f"objects/{object_id}/web_asset_manifest.json",
        },
        "delivery": copy.deepcopy(route.get("selectedDelivery") or {}),
        "quality": {
            "selectedOutput": route.get("selectedOutput") or obj.get("recommendedOutput") or "raster_alpha_sequence",
            "recommendedOutput": route.get("recommendedOutput") or obj.get("recommendedOutput"),
            "productionReadiness": route.get("productionReadiness") or quality.get("productionReadiness"),
            "productionReadinessScore": route.get("productionReadinessScore") or quality.get("productionReadinessScore"),
        },
        "discovery": copy.deepcopy(discovery),
        "rights": copy.deepcopy(obj.get("rights") if isinstance(obj.get("rights"), dict) else {}),
    }
    if not entry["delivery"]:
        entry["delivery"] = {
            "route": "raster_alpha_sequence",
            "status": "ready",
            "path": (obj.get("assets") if isinstance(obj.get("assets"), dict) else {}).get("cutoutPattern") or obj.get("asset") or "",
            "source": "cached_rgba_cutout_sequence",
        }
    return entry


def _runtime_snippets(selected_ids: list[str]) -> dict[str, str]:
    object_ids = ", ".join(f'"{object_id}"' for object_id in selected_ids)
    first_id = selected_ids[0] if selected_ids else "object_0"
    return {
        "plainJs": (
            'import { mountMotionJSON } from "./runtime/index.js";\n\n'
            'await mountMotionJSON("#motion", "./scene_graph.json", {\n'
            '  renderer: "canvas",\n'
            '  background: "#fbfaf6"\n'
            "});\n"
        ),
        "plainJsSingleObject": (
            'import { mountMotionJSON } from "./runtime/index.js";\n\n'
            f'await mountMotionJSON("#motion", "./scene_graph.json", {{ objectId: "{first_id}" }});\n'
        ),
        "react": (
            'import { createMotionJSONReactComponent } from "@motionjson/runtime/react";\n\n'
            'const MotionLayer = createMotionJSONReactComponent("./scene_graph.json");\n'
            "export default function HeroMotion() {\n"
            '  return <MotionLayer renderer="canvas" background="#fbfaf6" />;\n'
            "}\n"
        ),
        "remotion": (
            "const selectedObjectIds = [" + object_ids + "];\n"
            "<MotionJSONComposition\n"
            '  sceneGraphPath="./scene_graph.json"\n'
            "  objectIds={selectedObjectIds}\n"
            '  assetBasePath="."\n'
            "/>\n"
        ),
    }


def _templates(selected_ids: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "id": "website-canvas",
            "label": "Website canvas layer",
            "entrypoint": "scene_graph.json",
            "runtime": "@motionjson/runtime",
            "snippetKey": "plainJs",
            "objectIds": selected_ids,
        },
        {
            "id": "single-object-embed",
            "label": "Single object embed",
            "entrypoint": "scene_graph.json",
            "runtime": "@motionjson/runtime",
            "snippetKey": "plainJsSingleObject",
            "objectIds": selected_ids[:1],
        },
        {
            "id": "remotion-composition",
            "label": "Remotion composition plan",
            "entrypoint": "scene_graph.json",
            "runtime": "application-owned-remotion-project",
            "snippetKey": "remotion",
            "objectIds": selected_ids,
        },
    ]


def build_object_layer_pack(
    scene: dict[str, Any],
    *,
    selected_object_ids: Sequence[str] | None = None,
    excluded_object_ids: Sequence[str] | None = None,
    quality_routing: dict[str, Any] | None = None,
    validation_messages: list[dict[str, Any]] | None = None,
    source_scene_graph: str = "scene_graph.json",
    website_package_path: str | None = None,
    remotion_plan_path: str | None = None,
) -> dict[str, Any]:
    objects = [item for item in scene.get("objects", []) if isinstance(item, dict)]
    requested_ids = _unique_ids(selected_object_ids)
    available_ids = [_object_id(item, f"object_{index}") for index, item in enumerate(objects)]
    selected_ids = requested_ids or available_ids
    selected_set = set(selected_ids)
    routes = _routing_by_object(quality_routing)
    selected_objects = [item for item in objects if _object_id(item) in selected_set]

    pack: dict[str, Any] = {
        "format": OBJECT_LAYER_PACK_FORMAT,
        "aiUsage": "none",
        "sourceSceneGraph": source_scene_graph,
        "websitePackage": website_package_path,
        "remotionPlan": remotion_plan_path,
        "selectedObjectIds": [_object_id(item) for item in selected_objects],
        "excludedObjectIds": _unique_ids(excluded_object_ids),
        "objectCount": len(selected_objects),
        "objects": [_object_entry(item, routes.get(_object_id(item))) for item in selected_objects],
        "templates": _templates([_object_id(item) for item in selected_objects]),
        "snippets": _runtime_snippets([_object_id(item) for item in selected_objects]),
        "validationMessages": copy.deepcopy(validation_messages or []),
        "notes": [
            "This pack describes selected reusable object layers only.",
            "All paths are relative to the export or website package root.",
            "Rendering should use cached assets and JSON transforms; no provider or network calls are required.",
        ],
    }
    return pack


def write_object_layer_pack(path: str | Path, scene: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    pack = build_object_layer_pack(scene, **kwargs)
    write_json(path, pack)
    return pack
