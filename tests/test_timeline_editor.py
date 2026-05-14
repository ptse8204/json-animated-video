from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_timeline_editor_example_uses_local_runtime_and_cached_json_edits():
    html = (ROOT / "examples" / "timeline_editor.html").read_text()
    js = (ROOT / "examples" / "timeline_editor.js").read_text()

    assert "timeline_editor.js" in html
    assert "motionjson-runtime/src/index.js" in js
    assert "loadRuntimeAssets" in js
    assert "updateLayerTransform" in js
    assert "setLayerOpacity" in js
    assert "setLayerZIndex" in js
    assert "duplicateLayer" in js
    assert "setBackground" in js
    assert "https://unpkg" not in html + js
    assert "cdn.jsdelivr" not in html + js


def test_timeline_editor_documents_reuse_without_asset_copying():
    js = (ROOT / "examples" / "timeline_editor.js").read_text()
    editor = (ROOT / "packages" / "motionjson-runtime" / "src" / "editor.js").read_text()

    assert "sourceAssetId: source.sourceAssetId" in editor
    assert "reusedFromLayerId: source.id" in editor
    assert "JSON.stringify(serializeEditState(state), null, 2)" in js
