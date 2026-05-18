from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]

IMPORTANT_DOCS = [
    "README.md",
    "docs/index.md",
    "docs/first_run.md",
    "docs/run_local.md",
    "docs/local_ui.md",
    "docs/examples.md",
    "docs/troubleshooting.md",
    "docs/glossary.md",
    "docs/run_config.md",
    "docs/job_artifacts.md",
    "docs/provider_pipeline.md",
    "docs/provider_capabilities.md",
    "docs/security/api_keys.md",
    "docs/discovery_providers.md",
    "docs/track_filtering.md",
    "docs/multi_object_extraction.md",
    "docs/mask_correction.md",
    "docs/sam2_segmentation.md",
]

REQUIRED_USER_DOCS = [
    "docs/index.md",
    "docs/first_run.md",
    "docs/run_local.md",
    "docs/run_free_instances.md",
    "docs/examples.md",
    "docs/troubleshooting.md",
    "docs/glossary.md",
    "docs/local_ui.md",
    "docs/run_config.md",
    "docs/job_artifacts.md",
    "docs/provider_pipeline.md",
    "docs/provider_capabilities.md",
    "docs/security/api_keys.md",
    "docs/discovery_providers.md",
    "docs/track_filtering.md",
    "docs/runtime.md",
    "docs/privacy.md",
]

MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def iter_local_links(source: Path):
    text = source.read_text(encoding="utf-8")
    for match in MARKDOWN_LINK_RE.finditer(text):
        raw = match.group(1).strip()
        if not raw or raw.startswith("#"):
            continue
        target = raw.split()[0].strip("<>")
        parsed = urlparse(target)
        if parsed.scheme in {"http", "https", "mailto"}:
            continue
        if parsed.scheme:
            continue
        path = unquote(parsed.path)
        if not path:
            continue
        yield raw, path


def resolve_link(source: Path, target: str) -> Path:
    base = source.parent
    return (base / target).resolve()


def test_required_user_docs_exist_and_are_linked_from_index():
    index = read("docs/index.md")

    for path in REQUIRED_USER_DOCS:
        full_path = ROOT / path
        assert full_path.exists(), path
        assert full_path.read_text(encoding="utf-8").strip(), path

    for link in [
        "first_run.md",
        "run_local.md",
        "run_free_instances.md",
        "examples.md",
        "troubleshooting.md",
        "glossary.md",
        "local_ui.md",
        "run_config.md",
        "job_artifacts.md",
        "provider_pipeline.md",
        "provider_capabilities.md",
        "security/api_keys.md",
        "discovery_providers.md",
        "track_filtering.md",
        "runtime.md",
        "privacy.md",
    ]:
        assert link in index


def test_readme_links_to_core_docs_spine():
    readme = read("README.md")

    for link in [
        "docs/index.md",
        "docs/examples.md",
        "docs/troubleshooting.md",
        "docs/glossary.md",
        "docs/first_run.md",
        "docs/run_local.md",
        "docs/local_ui.md",
    ]:
        assert link in readme


def test_important_markdown_local_links_resolve():
    failures: list[str] = []
    for relative in IMPORTANT_DOCS:
        source = ROOT / relative
        for raw, target in iter_local_links(source):
            resolved = resolve_link(source, target)
            if not resolved.exists():
                failures.append(f"{relative} -> {raw}")

    assert not failures, "\n".join(failures)


def test_important_markdown_links_do_not_escape_repo():
    failures: list[str] = []
    root = ROOT.resolve()
    for relative in IMPORTANT_DOCS:
        source = ROOT / relative
        for raw, target in iter_local_links(source):
            resolved = resolve_link(source, target)
            try:
                resolved.relative_to(root)
            except ValueError:
                failures.append(f"{relative} -> {raw}")

    assert not failures, "\n".join(failures)
