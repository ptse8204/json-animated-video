from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def read_json(path: str) -> dict:
    return json.loads(read(path))


def test_runtime_and_sdk_workspace_metadata_are_actionable() -> None:
    root_package = read_json("package.json")
    runtime_package = read_json("packages/motionjson-runtime/package.json")
    sdk_package = read_json("packages/motionjson-sdk/package.json")

    assert root_package["scripts"]["test"].startswith("node --test ")
    assert root_package["scripts"]["lint"] == "node scripts/lint_runtime.mjs"
    assert root_package["scripts"]["build"] == "node scripts/build_ui_shell.mjs"
    assert root_package["scripts"]["embed:smoke"] == "node scripts/smoke_embed_examples.mjs"

    assert runtime_package["scripts"]["test"] == "node --test test/*.test.mjs"
    assert runtime_package["exports"] == {
        ".": "./src/index.js",
        "./canvas": "./src/canvas.js",
        "./pixi": "./src/pixi.js",
        "./embed": "./src/embed.js",
        "./react": "./src/react.js",
        "./templates": "./src/templates.js",
    }
    assert runtime_package["peerDependenciesMeta"]["pixi.js"]["optional"] is True
    assert runtime_package["peerDependenciesMeta"]["react"]["optional"] is True

    assert sdk_package["scripts"]["test"] == "node --test test/*.test.mjs"
    assert sdk_package["exports"] == {".": "./src/index.js"}


def test_readme_explains_website_embed_runtime_sdk_and_export_paths() -> None:
    readme = read("README.md")

    for expected in [
        "## Use MotionJSON on a website",
        "examples/plain_js_embed.html?manifest=/out/demo_red_ball/web_asset_manifest.json",
        "@motionjson/runtime",
        "packages/motionjson-runtime",
        "data-motionjson-src",
        "web_asset_manifest.json",
        "scene_graph.json",
        "npm --workspace @motionjson/runtime run test",
        "npm --workspace @motionjson/sdk run test",
        "npm pack --dry-run --workspace @motionjson/runtime",
        "npm run embed:smoke",
        "@motionjson/sdk",
        "MotionJSONClient",
        "website-zip",
        "remotion-plan",
        "does not install Remotion",
    ]:
        assert expected in readme


def test_runtime_doc_is_honest_about_supported_web_formats() -> None:
    runtime = read("docs/runtime.md")
    developer_api = read("docs/developer_api.md")

    for expected in [
        "## What The Runtime Supports Today",
        "`web_asset_manifest.json` | Supported",
        "`scene_graph.json` | Supported",
        "Canvas2D renderer | Supported",
        "Plain JavaScript auto-mount | Supported",
        "Pixi/WebGL renderer | Optional",
        "Website ZIP export | Supported",
        "Remotion adapter | Plan only",
        "AI/model calls in browser runtime | Not supported",
        "## Output Manifest Anatomy",
        "motionjson.web_asset_manifest.v0.1",
        "motionjson.scene_graph.v0.1",
        "npm --workspace @motionjson/runtime run test",
        "npm pack --dry-run --workspace @motionjson/sdk",
        "## SDK Usage",
        "MotionJSONClient",
        'format: "website-zip"',
        'format: "remotion-plan"',
    ]:
        assert expected in runtime

    assert "[runtime guide](runtime.md)" in developer_api
    assert "@motionjson/runtime" in developer_api


def test_plain_js_embed_example_and_demo_manifest_are_local_first() -> None:
    example = read("examples/plain_js_embed.html")
    manifest = read_json("out/demo/web_asset_manifest.json")

    assert "data-motionjson-src" in example
    assert "autoMountMotionJSON" in example
    assert "motionjson-runtime/src/index.js" in example
    assert "https://unpkg" not in example
    assert "https://cdn" not in example

    assert manifest["schema"] == "motionjson.web_asset_manifest.v0.1"
    assert manifest["canvas"]["width"] > 0
    assert manifest["canvas"]["height"] > 0
    assert manifest["assets"]["sequence"]


def test_plain_js_embed_browser_smoke_script_is_documented() -> None:
    script = read("scripts/smoke_embed_examples.mjs")
    runtime = read("docs/runtime.md")

    assert "plain_js_embed.html" in script
    assert "visiblePixels" in script
    assert "variedPixels" in script
    assert "npm run embed:smoke" in runtime
