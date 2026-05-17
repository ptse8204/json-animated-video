from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE19_DOCS = [
    ROOT / "docs" / "index.md",
    ROOT / "docs" / "ga_launch.md",
    ROOT / "docs" / "deployment.md",
    ROOT / "docs" / "billing_pricing.md",
    ROOT / "docs" / "onboarding.md",
    ROOT / "docs" / "security_checklist.md",
]
STATIC_PAGES = [
    ROOT / "examples" / "landing_page.html",
    ROOT / "examples" / "demo_gallery.html",
]
DEPLOYMENT_FILES = [
    ROOT / "Dockerfile",
    ROOT / ".dockerignore",
    ROOT / "docker-compose.yml",
    ROOT / ".env.example",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_phase19_public_docs_and_deployment_files_exist():
    for path in [*PHASE19_DOCS, *STATIC_PAGES, *DEPLOYMENT_FILES]:
        assert path.exists(), path
        assert read(path).strip(), path


def test_public_copy_uses_motionjson_product_framing():
    combined = "\n".join(read(path) for path in [ROOT / "README.md", *PHASE19_DOCS, *STATIC_PAGES])
    lowered = combined.lower()

    assert "ai object-layer editing" in lowered
    assert "reusable motion layers" in lowered
    assert "cached raster/alpha assets" in lowered
    assert "svg and lottie" in lowered or "svg/lottie" in lowered
    assert "convert all video to json" not in lowered
    assert "convert all video to svg" not in lowered
    assert "convert all video to lottie" not in lowered


def test_static_pages_are_local_only_and_first_view_product_signal():
    remote = re.compile(r"""(?:src|href)=["']https?://""", re.IGNORECASE)
    cdn = re.compile(r"unpkg|jsdelivr|cdnjs|googleapis|gstatic", re.IGNORECASE)

    for path in STATIC_PAGES:
        text = read(path)
        first_view = text[:4500].lower()
        assert "motionjson" in first_view
        assert "reusable motion layers" in first_view or "ai object-layer editing" in first_view
        assert not remote.search(text), path
        assert not cdn.search(text), path
        assert "<script" not in text.lower(), path
        assert "emoji" not in text.lower(), path


def test_landing_hero_uses_full_bleed_local_media_not_split_layout():
    landing = read(ROOT / "examples" / "landing_page.html")
    first_view = landing[:6500].lower()

    assert '<section class="product-hero"' in landing
    assert 'class="hero-media"' in landing
    assert 'src="../out/demo/frames/frame_000001.png"' in landing
    assert "<h1>MotionJSON</h1>" in landing
    assert "grid-template-columns: minmax(0, 1fr) minmax" not in first_view
    assert 'class="shell hero"' not in landing
    assert 'class="video-frame"' not in landing


def test_env_and_deployment_artifacts_do_not_contain_secret_values():
    credential_assignment = re.compile(
        r"(?im)^(?:[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)=(?P<value>.+)$"
    )
    for path in DEPLOYMENT_FILES:
        text = read(path)
        assert "sk-" not in text
        assert "mj_local_" not in text
        assert "whsec_" not in text
        for match in credential_assignment.finditer(text):
            assert match.group("value").strip() in {"", "${MOTIONJSON_DEFAULT_PLAN:-starter}"}


def test_docs_reference_phase19_validation_commands():
    launch = read(ROOT / "docs" / "ga_launch.md")
    billing = read(ROOT / "docs" / "billing_pricing.md")
    security = read(ROOT / "docs" / "security_checklist.md")

    assert "pytest -q tests/test_backend_billing.py tests/test_ga_launch_docs.py" in launch
    assert "python3 -m motionjson.cli extract examples/demo_red_ball.mp4" in launch
    assert "pytest -q tests/test_backend_billing.py" in billing
    assert "pytest -q tests/test_ga_launch_docs.py tests/test_backend_billing.py" in security
