from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "examples" / "object_selection_workflow.html"
JS = ROOT / "examples" / "object_selection_workflow.js"


class PrototypeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []
        self.scripts = []
        self.options = []
        self.details = 0
        self.canvas_ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.inputs.append(attrs)
        if tag == "script":
            self.scripts.append(attrs)
        if tag == "option":
            self.options.append(attrs)
        if tag == "details":
            self.details += 1
        if tag == "canvas" and attrs.get("id"):
            self.canvas_ids.add(attrs["id"])


def read_files() -> tuple[str, str]:
    return HTML.read_text(encoding="utf-8"), JS.read_text(encoding="utf-8")


def test_static_prototype_structure_has_required_surfaces():
    html, _ = read_files()
    parser = PrototypeParser()
    parser.feed(html)

    assert any(attrs.get("type") == "file" and attrs.get("accept") == "video/*" for attrs in parser.inputs)
    assert {"selectionOverlay", "assetCanvas"}.issubset(parser.canvas_ids)
    assert any(attrs.get("src") == "object_selection_workflow.js" for attrs in parser.scripts)
    assert any(attrs.get("value") == "threshold" and "selected" in attrs for attrs in parser.options)
    assert parser.details >= 2
    assert "Mask Correction" in html
    assert "correction_request.json" in html
    assert "AI object-layer editing for video and web graphics" in html
    assert "Cached raster/alpha assets" in html
    assert "universal video-to-JSON" not in html
    assert "CDN" not in html


def test_upload_uses_local_object_url_and_revokes_prior_url():
    _, js = read_files()

    assert 'type="file"' not in js
    assert "URL.createObjectURL(file)" in js
    assert "URL.revokeObjectURL(appState.objectUrl)" in js
    assert "accept=\"video/*\"" not in js


def test_selection_mapping_handles_object_fit_contain_letterboxing():
    _, js = read_files()

    assert "function displayedVideoRect()" in js
    assert "Math.min(host.width / videoWidth, host.height / videoHeight)" in js
    assert "left: (host.width - width) / 2" in js
    assert "top: (host.height - height) / 2" in js
    assert "function pointerToVideoPoint(event)" in js
    assert "px < fit.left" in js
    assert "(px - fit.left) / fit.scale" in js
    assert "(py - fit.top) / fit.scale" in js


def test_point_box_prompt_state_and_cli_command_are_generated_only():
    _, js = read_files()

    for status in ["queued", "prompt ready", "extracting", "caching", "ready"]:
        assert f"'{status}'" in js

    assert "--mask-provider" in js
    assert "--prompt-point" in js
    assert "--prompt-box" in js
    assert "--sam2-prompt-frame" in js
    assert "motionjson.cli" in js
    assert "'correct'" in js
    assert "motionjson.correction_request.v0.1" in js
    assert "add_point" in js
    assert "remove_point" in js
    assert "brush" in js
    assert "same_coordinates" in js
    assert "centroid_delta" in js
    assert "frameRange" in js
    assert "# Simulated by this browser prototype; not executed here." in js
    assert "fetch(" in js
    assert "function loadJson(url)" in js
    assert "XMLHttpRequest" not in js
    assert "WebSocket" not in js
    assert "openrouter" not in js.lower()
    assert "https://" not in js
    assert "http://" not in js


def test_cached_asset_defaults_and_transform_policy_are_explicit():
    _, js = read_files()

    assert "window.location.pathname.includes('/preview/') ? '..' : '/out/demo'" in js
    assert "web_asset_manifest.json" in js
    assert "scene_graph.json" in js
    assert "layerFromManifest" in js
    assert "layerFromScene" in js
    assert "spriteSheet" in js
    assert "drawAssetPreview" in js
    assert "cached assets + JSON transforms; no AI rerun" in js
    assert "Local deterministic correction only; no provider, network, or model-router call." in js
