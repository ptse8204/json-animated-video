from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase03a_ui_shell_has_product_layout_primitives():
    html = read("src/motionjson/ui/static/index.html")
    css = read("src/motionjson/ui/static/app.css")
    build_script = read("scripts/build_ui_shell.mjs")

    for expected in [
        "workflow-steps",
        "Run monitor",
        "Review",
        "Artifacts and exports",
        "Corrections",
        "Asset library",
        "providerWarning",
        "Start mock job",
    ]:
        assert expected in html or expected in build_script

    for expected in [
        "--z-sidebar",
        "--z-sticky",
        "--space-sm",
        "height: 100vh",
        "overscroll-behavior",
        "grid-template-areas",
        "@media (max-width: 1180px)",
        "@media (max-width: 560px)",
    ]:
        assert expected in css


def test_phase03a_layout_check_reports_viewport_matrix():
    result = subprocess.run(
        ["node", "scripts/check_local_ui_layout.mjs", "--check"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(result.stdout)

    assert payload["canRun"] is True
    assert {item["name"] for item in payload["viewports"]} == {
        "laptop-1366",
        "desktop-1440",
        "desktop-1920",
        "tablet-1024",
    }
    assert {
        "real-empty-shell",
        "real-seeded-shell",
        "real-expanded-shell",
        "first-run",
        "new-project",
        "extraction-wizard",
        "provider-diagnostics",
        "job-review",
    } <= set(payload["states"])


def test_phase03a_layout_smoke_runs_real_shell_when_chrome_available():
    check = subprocess.run(
        ["node", "scripts/check_local_ui_layout.mjs", "--check"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(check.stdout)
    if not payload["canRun"]:
        pytest.skip("Chrome/Chromium is not available for real layout smoke")

    subprocess.run(
        [
            "node",
            "scripts/check_local_ui_layout.mjs",
            "--state",
            "real-empty-shell",
            "--viewport",
            "tablet-1024",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
