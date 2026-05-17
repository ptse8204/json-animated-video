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
        "roadmap/final-qa-release-report.md",
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


def test_final_qa_release_report_lists_phase_commits_checks_and_manual_qa() -> None:
    report = read_text("docs/roadmap/final-qa-release-report.md")

    for phase, commit in [
        (0, "2d4c126"),
        (1, "0dc8c72"),
        (2, "7f46106"),
        (3, "a9c8fc6"),
        (4, "e8e9203"),
        (5, "7991798"),
        (6, "42faae2"),
        (7, "1baed49"),
        (8, "79a113a"),
        (9, "79297f0"),
        (10, "7e77319"),
        (11, "404b45d"),
        (12, "a46bbba"),
        (13, "629f7c8"),
        (14, "3fc7451"),
    ]:
        assert f"| {phase} | `{commit}" in report
        assert f"docs/roadmap/phase-{phase}-report.md" in report

    for section in [
        "## Final Checks",
        "## Manual Verification",
        "## Known Limitations",
        "## Release Decision",
    ]:
        assert section in report

    assert "227 tests" in report
    assert "npm test" in report
    assert "backend diagnostics --json" in report
    assert "mock extraction run" in report
    assert "local `/api/artifacts/.../content` routes" in report


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
