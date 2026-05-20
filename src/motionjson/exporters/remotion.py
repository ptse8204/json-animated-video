from __future__ import annotations

from pathlib import Path
from typing import Any

from .final_render import _canvas, final_export_entry, load_scene
from .scene_graph import write_json


def build_remotion_plan(*, out_dir: str | Path, scene: dict[str, Any]) -> dict[str, Any]:
    """Describe a Remotion integration contract without invoking npm, network, or APIs."""
    out_dir = Path(out_dir)
    canvas = _canvas(scene)
    objects = []
    for obj in scene.get("objects", []):
        objects.append(
            {
                "objectId": obj.get("id"),
                "label": obj.get("label"),
                "renderMode": obj.get("renderMode"),
                "zIndex": obj.get("zIndex", 0),
                "motionFrames": len(obj.get("motion", [])),
                "discovery": obj.get("discovery", {}),
                "review": {
                    "status": (obj.get("discovery") or {}).get("reviewStatus") if isinstance(obj.get("discovery"), dict) else obj.get("exportStatus", "accepted"),
                    "exportStatus": obj.get("exportStatus") or ((obj.get("discovery") or {}).get("exportStatus") if isinstance(obj.get("discovery"), dict) else "accepted"),
                },
                "assets": {
                    "spritesheet": (obj.get("assets", {}).get("spritesheet") or {}).get("path"),
                    "cutoutPattern": obj.get("assets", {}).get("cutoutPattern"),
                    "production": obj.get("assets", {}).get("production"),
                },
                "rights": obj.get("rights", {}),
            }
        )

    return {
        "status": "plan_ready",
        "aiUsage": "none",
        "sourceSceneGraph": "scene_graph.json",
        "rightsManifest": scene.get("rightsManifest", "rights_manifest.json"),
        "projectConfigured": False,
        "dependencyPolicy": {
            "remotionDependencyAdded": False,
            "npmInvoked": False,
            "networkInvoked": False,
            "reason": "Phase 8 writes an adapter plan only; applications wire it into their own Remotion project.",
        },
        "composition": {
            "id": "MotionJSONComposition",
            "width": canvas["width"],
            "height": canvas["height"],
            "fps": canvas["fps"],
            "durationInFrames": canvas["frameCount"],
            "componentContract": {
                "component": "MotionJSONComposition",
                "props": {
                    "sceneGraphPath": "scene_graph.json",
                    "assetBasePath": ".",
                    "objectIds": [item["objectId"] for item in objects if item.get("objectId")],
                    "backgroundColor": "#fbfaf6",
                },
                "rendering": "Composite cached raster/alpha cutouts according to JSON transforms.",
            },
        },
        "objectLayerPack": {
            "format": "motionjson.object_layer_pack.v0.1",
            "path": "object_layer_pack.json",
            "component": "MotionJSONObjectLayers",
            "objectIds": [item["objectId"] for item in objects if item.get("objectId")],
            "dependencyPolicy": "application_owned",
        },
        "assets": {
            "baseDirectory": str(out_dir),
            "objects": objects,
            "runtimeAssumptions": [
                "Use cached cutout PNGs or production spritesheets.",
                "Do not call segmentation, matting, LLM, VLM, or hosted AI providers during rendering.",
            ],
        },
    }


def write_remotion_plan(*, out_dir: str | Path, output_path: str | Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene = load_scene(out_dir)
    plan = build_remotion_plan(out_dir=out_dir, scene=scene)
    write_json(output_path, plan)
    canvas = _canvas(scene)
    return final_export_entry(
        export_type="remotion_plan",
        format_name="json",
        output_path=output_path,
        out_dir=out_dir,
        status=plan["status"],
        mime_type="application/json",
        width=canvas["width"],
        height=canvas["height"],
        fps=canvas["fps"],
        frame_count=canvas["frameCount"],
        extra={
            "cachedSources": ["scene_graph.json", "objects/*/cutouts/*.png", "objects/*/spritesheet.*"],
            "projectConfigured": False,
            "npmInvoked": False,
            "networkInvoked": False,
        },
    )
