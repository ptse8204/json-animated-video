from __future__ import annotations

import re
import subprocess
import sys
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
    "docs/sam3_local.md",
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

CODEX_ALWAYS_READ = [
    "docs/codex/START_HERE.md",
    "docs/codex/CURRENT_TASK.md",
    "docs/codex/SAFETY_INVARIANTS.md",
    "docs/codex/CURRENT_ARCHITECTURE.md",
    "docs/codex/CONTEXT_MANIFEST.yaml",
]

MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.split())


def parse_top_level_list(text: str, key: str) -> list[str]:
    values: list[str] = []
    in_section = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith(" ") and line.endswith(":"):
            in_section = line[:-1] == key
            continue
        if in_section:
            if raw_line.startswith("  - "):
                values.append(raw_line.split("  - ", 1)[1].strip().strip('"'))
                continue
            if raw_line and not raw_line.startswith(" "):
                break
    return values


def parse_subsystem_docs(text: str) -> dict[str, list[str]]:
    routes: dict[str, list[str]] = {}
    current: str | None = None
    in_docs = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line.startswith("  ") and not raw_line.startswith("    ") and stripped.endswith(":"):
            current = stripped[:-1]
            routes[current] = []
            in_docs = False
            continue
        if current and raw_line.startswith("    ") and not raw_line.startswith("      "):
            in_docs = stripped == "docs:"
            continue
        if current and in_docs:
            if raw_line.startswith("      - "):
                routes[current].append(raw_line.split("      - ", 1)[1].strip().strip('"'))
            elif raw_line.startswith("    ") and stripped:
                in_docs = False
    return routes


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


def test_codex_default_context_is_small_explicit_and_non_archive():
    manifest = read("docs/codex/CONTEXT_MANIFEST.yaml")
    always_read = parse_top_level_list(manifest, "always_read")
    never_default = parse_top_level_list(manifest, "never_default_read")

    assert always_read == CODEX_ALWAYS_READ
    assert "docs/archive/" in never_default
    assert "docs/roadmap/phase-*-report.md" in never_default

    total_lines = 0
    total_chars = 0
    for relative in always_read:
        assert "archive" not in Path(relative).parts
        path = ROOT / relative
        assert path.exists(), relative
        text = path.read_text(encoding="utf-8")
        total_lines += text.count("\n") + 1
        total_chars += len(text)

    assert total_lines <= 350
    assert total_chars <= 25000

    assert len(read("AGENTS.md").splitlines()) + len(read("CODEX_MASTER_PROMPT.md").splitlines()) <= 70


def test_codex_context_budget_script_passes_and_blocks_old_ui_docs():
    result = subprocess.run(
        [sys.executable, "scripts/check_codex_context_budget.py"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    assert "default_docs_lines=" in result.stdout
    assert "tracked_md_lines=" in result.stdout

    manifest = read("docs/codex/CONTEXT_MANIFEST.yaml")
    routes = parse_subsystem_docs(manifest)
    ui_docs = routes["ui_redesign"]

    assert len(ui_docs) <= 3
    assert "docs/local_ui.md" not in ui_docs
    assert "docs/design/local-ui-audit.md" not in ui_docs
    assert "docs/design/design-system.md" not in ui_docs
    assert all(not doc.startswith("docs/archive/") for docs in routes.values() for doc in docs)
    assert all("phase-" not in doc for docs in routes.values() for doc in docs)


def test_codex_docs_are_linked_from_human_index_without_becoming_default_map():
    index = read("docs/index.md")

    for link in [
        "codex/START_HERE.md",
        "codex/CURRENT_TASK.md",
        "codex/SAFETY_INVARIANTS.md",
        "codex/CURRENT_ARCHITECTURE.md",
        "codex/CONTEXT_MANIFEST.yaml",
        "product/ui_redesign_brief.md",
    ]:
        assert link in index

    assert "default Codex read map" in index


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


def test_od06_sam2_automatic_proposal_docs_are_truthful():
    discovery = read("docs/discovery_providers.md")
    sam2 = read("docs/sam2_segmentation.md")
    capabilities_doc = read("docs/provider_capabilities.md")

    for text in (discovery, sam2):
        assert "SAM2_LOCAL_CHECKPOINT" in text
        assert "SAM2_LOCAL_CONFIG" in text
        lowered = text.lower()
        assert "automatic mask" in lowered or "automatic-mask" in lowered
        assert "propagation" in text.lower()

    assert "LocalSAM2AutomaticMaskProposalBackend" in sam2
    assert "sam2.automatic_mask_generator" in capabilities_doc
    assert "does not silently" in discovery


def test_od07_sam3_mock_and_hosted_docs_are_truthful():
    discovery = read("docs/discovery_providers.md")
    capabilities_doc = read("docs/provider_capabilities.md")
    security = read("docs/security/api_keys.md")

    for phrase in ("sam3_concept", "sam3_exemplar", "sam3_auto_masks"):
        assert phrase in discovery
        assert phrase in capabilities_doc
    assert "SAM3_LOCAL_MODEL" in capabilities_doc
    assert "SAM3_HOSTED_URL" in security
    assert "SAM3_HOSTED_API_KEY" in security
    assert "do not send frames or make network calls" in normalized(security)


def test_od08_sam3_local_adapter_docs_are_truthful():
    sam3 = read("docs/sam3_local.md")
    capabilities_doc = read("docs/provider_capabilities.md")
    run_config = read("docs/run_config.md")

    for phrase in (
        "Python 3.12",
        "CUDA",
        "SAM3_LOCAL_MODEL",
        "MOTIONJSON_RUN_REAL_SAM3_TESTS",
        "/content/sam3",
        "facebook/sam3",
        "sam3.pt",
        "hf_hub_download",
        "Meta approval",
        "GOOGLE_DRIVE_SAM3_CHECKPOINT_PATH",
        "avoid Hugging Face token setup",
    ):
        assert phrase in sam3
    assert "unsupported_runtime" in capabilities_doc
    assert "sam3ModelPath" in run_config
    assert "not install SAM3" in sam3


def test_od14_object_discovery_release_docs_cover_workflow():
    readme = read("README.md")
    index = read("docs/index.md")
    checklist = read("docs/release_checklist.md")
    troubleshooting = read("docs/troubleshooting.md")
    repo_status = read("docs/repo_status.md")
    release_notes = read("docs/release_notes.md")

    for text in (readme, index, checklist, release_notes):
        compact = normalized(text)
        assert "Clean" in text
        assert "Maximum Recall" in compact
        assert "Trace Everything" in compact

    for phrase in (
        "API-first object discovery",
        "Selected-candidate tracking",
        "Review-gated exports",
        "Historical phase evidence",
    ):
        assert phrase in repo_status

    assert "review API-returned object candidates" in readme
    assert "API review payloads own candidates" in checklist
    assert "SAM2 automatic proposals stay optional" in checklist
    assert "SAM3 local/hosted concept" in checklist
    assert "Object Discovery Finds Too Few Candidates" in troubleshooting
    assert "Object Discovery Finds Too Many Candidates" in troubleshooting


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
