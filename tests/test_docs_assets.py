from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"

README_ASSETS = {
    "local-ui-first-run.png": (1440, 1000),
    "local-ui-new-project.png": (1440, 1000),
    "local-ui-extraction-wizard.png": (1440, 1000),
    "local-ui-provider-diagnostics.png": (1440, 1000),
    "local-ui-job-review.png": (1440, 1000),
    "canvas-preview-red-ball.png": (640, 360),
    "red-ball-demo.gif": (320, 180),
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_capture_docs_assets_check_is_ci_safe():
    result = subprocess.run(
        [sys.executable, "scripts/capture_docs_assets.py", "--check"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(result.stdout)

    assert payload["assetDir"] == str(ASSET_DIR)
    assert "canCaptureScreenshots" in payload


def test_readme_embeds_generated_docs_assets():
    readme = read(ROOT / "README.md")
    asset_doc = read(ASSET_DIR / "README_ASSETS.md")

    assert "python3 scripts/capture_docs_assets.py --check" in readme
    assert "python3 scripts/capture_docs_assets.py" in readme
    assert "python3 scripts/capture_docs_assets.py --skip-browser" in asset_doc
    for filename in README_ASSETS:
        assert f"docs/assets/{filename}" in readme or f"`docs/assets/{filename}`" in asset_doc


def test_generated_docs_assets_are_real_images():
    for filename, expected_size in README_ASSETS.items():
        path = ASSET_DIR / filename
        assert path.exists(), path
        assert path.stat().st_size > 2048, path
        with Image.open(path) as image:
            assert image.size == expected_size
            extrema = image.convert("RGB").getextrema()
            assert any(low != high for low, high in extrema), path
            if filename.endswith(".gif"):
                assert getattr(image, "is_animated", False)


def test_ui_screenshots_capture_distinct_states():
    screenshot_names = [name for name in README_ASSETS if name.startswith("local-ui-")]
    hashes = {
        name: hashlib.sha256((ASSET_DIR / name).read_bytes()).hexdigest()
        for name in screenshot_names
    }

    assert len(set(hashes.values())) == len(hashes), hashes
