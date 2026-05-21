from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.split())


def test_issue_templates_cover_public_triage_without_secret_leakage() -> None:
    templates = [
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/provider_setup_failure.yml",
        ".github/ISSUE_TEMPLATE/docs_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
    ]

    for path in templates:
        assert (ROOT / path).exists(), path
        text = read(path)
        assert "secret" in text.lower() or "provider keys" in text.lower()
        assert "needs triage" in text or path.endswith("config.yml")

    provider_template = read(".github/ISSUE_TEMPLATE/provider_setup_failure.yml")
    for expected in [
        "openai planner",
        "sam3-hosted",
        "hosted-call opt-in",
        "cost/privacy",
    ]:
        assert expected in provider_template

    config = read(".github/ISSUE_TEMPLATE/config.yml")
    assert "blank_issues_enabled: false" in config
    assert "SECURITY.md" in config
    assert "/security/advisories/new" not in config


def test_release_checklist_has_ui_model_connector_and_repository_gates() -> None:
    checklist = read("docs/release_checklist.md")

    for expected in [
        "License And Release Status Gate",
        "Guided UI And Model Connector Release Gate",
        "Screenshot Freshness And Layout Gate",
        "Repository Security Settings",
        "npm run ui:layout -- --screenshot-dir docs/design/screenshots/<release-id>",
        "OpenAI planning connector is server-side only",
        "Never put model API keys",
        "secret scanning",
        "push protection",
        "Dependabot alerts",
        "Protect the default branch",
        "issue templates",
    ]:
        assert expected in checklist


def test_security_docs_cover_hosted_model_and_repo_safeguards() -> None:
    security_policy = read("SECURITY.md")
    security_checklist = read("docs/security_checklist.md")
    contributing = read("CONTRIBUTING.md")

    combined = "\n".join([security_policy, security_checklist, contributing])
    for expected in [
        "server-side",
        "hosted-call opt-in",
        "cost/privacy acknowledgement",
        "private vulnerability reporting",
        "secret scanning",
        "push protection",
        "Dependabot",
        "required CI checks",
        "Apache-2.0",
    ]:
        assert expected in combined


def test_public_docs_state_current_roadmap_and_apache_license_boundary() -> None:
    readme = read("README.md")
    repo_status = read("docs/repo_status.md")
    release_notes = read("docs/release_notes.md")

    assert "docs/roadmap/ui_model_connector_plan.md" in readme
    assert "docs/roadmap/ui_model_connector_plan.md` before making Local UI" in readme
    assert "Treat `docs/codex_future_plan.md` as historical context" in readme
    assert "Apache License, Version 2.0" in readme
    assert "[LICENSE](LICENSE)" in readme
    assert "source-media rights" in normalized(readme)

    for expected in [
        "UI-MODEL-10",
        "Guided Local UI workflows",
        "Model connector contract",
        "Optional OpenAI planning connector",
        "not a production hosted service",
        "Keep issue templates current",
        "Apache-2.0",
    ]:
        assert expected in repo_status

    for expected in [
        "Guided Local UI setup",
        "Server-side model planning connector",
        "hosted-call gated",
        "No model API keys are sent to browser code",
        "Apache License, Version 2.0",
        "source-media rights",
        "npm run ui:layout",
    ]:
        assert expected in release_notes
