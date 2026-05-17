from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase14_release_candidate_docs_are_linked_and_actionable() -> None:
    index = read_text("docs/index.md")
    release_notes = read_text("docs/release_notes.md")
    migration = read_text("docs/migration_and_known_limitations.md")
    quality = read_text("docs/codex_motionjson_quality_benchmarks.md")

    for link in [
        "release_notes.md",
        "migration_and_known_limitations.md",
        "codex_motionjson_quality_benchmarks.md",
        "benchmark_fixtures.md",
        "final_export.md",
    ]:
        assert link in index

    assert "Release candidate scope" in release_notes
    assert "PYTHONPATH=src python3 -m pytest -q" in release_notes
    assert "benchmark --fixtures whole_frame_regression" in release_notes
    assert "Migration notes" in migration
    assert "Known limitations" in migration
    assert "Job cancellation is cooperative" in migration
    assert "--mock" in migration
    assert "--mock-mode" not in migration
    assert "| Check | Expected result | Evidence |" in quality
    assert "Accessibility smoke" in quality
    assert "Privacy" in quality
    assert "Network" in quality


def test_phase14_static_ui_release_candidate_affordances_are_present() -> None:
    index = read_text("src/motionjson/ui/static/index.html")
    css = read_text("src/motionjson/ui/static/app.css")
    js = read_text("src/motionjson/ui/static/app.js")
    build_guard = read_text("scripts/build_ui_shell.mjs")

    assert 'class="skip-link"' in index
    assert 'id="workspaceMain"' in index
    assert 'id="cancelJobButton"' in index
    assert "Local release candidate" in index
    assert "Object tracing workspace" in index
    assert "aria-keyshortcuts" in index
    assert "data-tooltip" in index
    assert ".skip-link" in css
    assert ".viewer-stage:focus-visible" in css
    assert "[data-tooltip]:focus-visible::after" in css
    assert "@media (max-width: 1360px)" in css
    assert "safeLocalContentUrl" in js
    assert "/api/jobs/{jobId}/cancel" in js
    assert "cancelSelectedJob" in js
    assert "requestAnimationFrame" in js
    assert "rel=\"noopener noreferrer\"" in js
    assert "safeLocalContentUrl" in build_guard
