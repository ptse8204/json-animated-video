from __future__ import annotations

import json
from pathlib import Path

import motionjson

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback.
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ci_workflow_covers_python_js_docs_packaging_and_docker() -> None:
    workflow = read(".github/workflows/ci.yml")

    for expected in [
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "python -m pip install -e \".[dev]\"",
        "python -m pytest -p no:cacheprovider -q",
        "tests/test_docs_links.py tests/test_phase09_release_readiness.py",
        "python -m motionjson.cli --help",
        "python -m build --sdist --wheel",
        "actions/setup-node@v4",
        "npm test",
        "npm run lint",
        "npm run build",
        "npm run embed:smoke",
        "npm --workspace @motionjson/runtime run test",
        "npm pack --dry-run --workspace @motionjson/sdk",
        "docker build -t motionjson-ci .",
        "docker run --rm motionjson-ci python -m motionjson.cli backend diagnostics --json",
        "docker compose config",
    ]:
        assert expected in workflow


def test_package_versions_and_publish_metadata_are_release_ready() -> None:
    pyproject = tomllib.loads(read("pyproject.toml"))
    runtime = json.loads(read("packages/motionjson-runtime/package.json"))
    sdk = json.loads(read("packages/motionjson-sdk/package.json"))

    assert pyproject["project"]["version"] == motionjson.__version__
    assert pyproject["project"]["readme"] == "README.md"
    assert pyproject["project"]["urls"]["Repository"] == "https://github.com/ptse8204/json-animated-video"

    for package in [runtime, sdk]:
        assert package["version"] == motionjson.__version__
        assert package["homepage"].startswith("https://github.com/ptse8204/json-animated-video")
        assert package["repository"]["url"] == "git+https://github.com/ptse8204/json-animated-video.git"
        assert package["bugs"]["url"] == "https://github.com/ptse8204/json-animated-video/issues"
        assert package["files"] == ["src"]


def test_release_readiness_docs_exist_and_are_linked() -> None:
    for path in ["CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md", "docs/release_checklist.md"]:
        assert (ROOT / path).exists(), path
        assert read(path).strip(), path

    readme = read("README.md")
    index = read("docs/index.md")

    for expected in [
        "docs/release_checklist.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
    ]:
        assert expected in readme

    for expected in [
        "release_checklist.md",
        "../CONTRIBUTING.md",
        "../SECURITY.md",
        "../CHANGELOG.md",
    ]:
        assert expected in index


def test_release_checklist_covers_required_gates() -> None:
    checklist = read("docs/release_checklist.md")

    for expected in [
        "Bump `pyproject.toml`",
        "packages/motionjson-runtime/package.json",
        "packages/motionjson-sdk/package.json",
        "Update `CHANGELOG.md`",
        "Update `docs/release_notes.md`",
        "docs/migration_and_known_limitations.md",
        "python3 scripts/capture_docs_assets.py --check",
        "python3 -m build --sdist --wheel",
        "npm pack --dry-run --workspace @motionjson/runtime",
        "npm run embed:smoke",
        "docker build -t motionjson-ga .",
        "docker run --rm motionjson-ga python -m motionjson.cli backend diagnostics --json",
        "Known",
        "out/demo/",
    ]:
        assert expected in checklist


def test_gitignore_documents_generated_output_policy() -> None:
    gitignore = read(".gitignore")

    for expected in [
        ".motionjson/",
        ".env",
        "!.env.example",
        "out/*",
        "!out/demo/",
        "!out/demo/**",
        "output/",
        "*.sqlite",
        "*.db",
        "Generated outputs are ignored",
    ]:
        assert expected in gitignore


def test_repo_status_contains_about_topics_and_release_status() -> None:
    status = read("docs/repo_status.md")

    for expected in [
        "GitHub About description",
        "Website",
        "Topics",
        "motionjson",
        "video-editing",
        "local-first",
        "Release status",
        "release checklist",
    ]:
        assert expected in status
