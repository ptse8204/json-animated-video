#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/codex/CONTEXT_MANIFEST.yaml"
ALWAYS_READ = [
    "docs/codex/START_HERE.md",
    "docs/codex/CURRENT_TASK.md",
    "docs/codex/SAFETY_INVARIANTS.md",
    "docs/codex/CURRENT_ARCHITECTURE.md",
    "docs/codex/CONTEXT_MANIFEST.yaml",
]
LINE_LIMITS = {
    "docs/codex/START_HERE.md": 45,
    "docs/codex/CURRENT_TASK.md": 45,
    "docs/codex/SAFETY_INVARIANTS.md": 70,
    "docs/codex/CURRENT_ARCHITECTURE.md": 80,
    "docs/codex/CONTEXT_MANIFEST.yaml": 120,
}
DENIED_UI_DOCS = {
    "docs/local_ui.md",
    "docs/design/local-ui-audit.md",
    "docs/design/design-system.md",
}
DENIED_OLD_PATTERNS = [
    "README_old.md",
    "AGENTS_old.md",
    "docs/codex_future_plan.md",
    "docs/codex_motionjson_*.md",
    "docs/MOTIONJSON_CODEX_FUTURE_PLAN.md",
    "docs/archive/codex_prompts/*.md",
    "docs/archive/root_docs/*.md",
]


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def line_count(text: str) -> int:
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def top_level_list(text: str, key: str) -> list[str]:
    values: list[str] = []
    in_section = False
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith(" ") and raw.rstrip().endswith(":"):
            in_section = raw.rstrip()[:-1] == key
            continue
        if in_section:
            if raw.startswith("  - "):
                values.append(raw.split("  - ", 1)[1].strip().strip('"'))
            elif raw and not raw.startswith(" "):
                break
    return values


def subsystem_docs(text: str) -> dict[str, list[str]]:
    routes: dict[str, list[str]] = {}
    current: str | None = None
    in_docs = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw.startswith("  ") and not raw.startswith("    ") and stripped.endswith(":"):
            current = stripped[:-1]
            routes[current] = []
            in_docs = False
            continue
        if current and raw.startswith("    ") and not raw.startswith("      "):
            in_docs = stripped == "docs:"
            continue
        if current and in_docs:
            if raw.startswith("      - "):
                routes[current].append(raw.split("      - ", 1)[1].strip().strip('"'))
            elif raw.startswith("    ") and stripped:
                in_docs = False
    return routes


def tracked_markdown() -> list[tuple[int, int, str]]:
    files = subprocess.check_output(["git", "ls-files", "*.md"], cwd=ROOT, text=True).splitlines()
    rows: list[tuple[int, int, str]] = []
    for relative in files:
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        rows.append((line_count(text), len(text), relative))
    return rows


def main() -> int:
    if not MANIFEST.exists():
        return fail("missing docs/codex/CONTEXT_MANIFEST.yaml")

    manifest = MANIFEST.read_text(encoding="utf-8")
    always = top_level_list(manifest, "always_read")
    if always != ALWAYS_READ:
        return fail(f"always_read mismatch: {always}")

    default_lines = 0
    default_chars = 0
    for relative in always:
        if relative.startswith("docs/archive/"):
            return fail(f"archived path in always_read: {relative}")
        path = ROOT / relative
        if not path.exists():
            return fail(f"missing always_read file: {relative}")
        text = path.read_text(encoding="utf-8")
        lines = line_count(text)
        chars = len(text)
        if lines > LINE_LIMITS[relative]:
            return fail(f"{relative} exceeds line budget: {lines} > {LINE_LIMITS[relative]}")
        default_lines += lines
        default_chars += chars

    if default_lines > 350:
        return fail(f"default read set exceeds line budget: {default_lines} > 350")
    if default_chars > 25000:
        return fail(f"default read set exceeds char budget: {default_chars} > 25000")

    shim_lines = line_count(read("AGENTS.md")) + line_count(read("CODEX_MASTER_PROMPT.md"))
    if shim_lines > 70:
        return fail(f"root shims exceed combined line budget: {shim_lines} > 70")

    routes = subsystem_docs(manifest)
    if "ui_redesign" not in routes:
        return fail("missing ui_redesign route")
    for name, docs in routes.items():
        if len(docs) > 3:
            return fail(f"{name}.docs has {len(docs)} entries; max is 3")
        for doc in docs:
            if doc.startswith("docs/archive/"):
                return fail(f"{name}.docs includes archive doc: {doc}")
            if fnmatch.fnmatch(doc, "docs/roadmap/phase-*-report.md"):
                return fail(f"{name}.docs includes phase report: {doc}")
            if not (ROOT / doc).exists():
                return fail(f"{name}.docs missing file: {doc}")

    ui_docs = routes["ui_redesign"]
    for doc in ui_docs:
        if doc in DENIED_UI_DOCS or doc.startswith("docs/roadmap/") or doc.startswith("docs/archive/"):
            return fail(f"ui_redesign.docs includes denied doc: {doc}")

    for pattern in DENIED_OLD_PATTERNS:
        for match in ROOT.glob(pattern):
            if match.exists():
                return fail(f"denied old doc still exists: {match.relative_to(ROOT)}")

    ui_lines = 0
    ui_chars = 0
    for doc in ui_docs:
        text = read(doc)
        ui_lines += line_count(text)
        ui_chars += len(text)

    rows = tracked_markdown()
    total_lines = sum(row[0] for row in rows)
    total_chars = sum(row[1] for row in rows)

    print(f"default_docs_lines={default_lines}")
    print(f"default_docs_chars={default_chars}")
    print(f"ui_route_docs_lines={ui_lines}")
    print(f"ui_route_docs_chars={ui_chars}")
    print(f"tracked_md_files={len(rows)}")
    print(f"tracked_md_lines={total_lines}")
    print(f"tracked_md_chars={total_chars}")
    print("largest_md_files:")
    for lines, chars, relative in sorted(rows, reverse=True)[:20]:
        print(f"{lines:6d} {chars:8d} {relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
