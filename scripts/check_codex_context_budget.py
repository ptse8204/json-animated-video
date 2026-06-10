#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/codex/CONTEXT_MANIFEST.yaml"
REQUIRED_ALWAYS_READ = [
    "docs/codex/START_HERE.md",
    "docs/codex/CURRENT_TASK.md",
    "docs/codex/SAFETY_INVARIANTS.md",
    "docs/codex/CURRENT_ARCHITECTURE.md",
    "docs/codex/CONTEXT_MANIFEST.yaml",
]
MAX_LINES = 1500
MAX_CHARS = 60000
COMPACT_WARN_LINES = {
    "AGENTS.md": 80,
    "CODEX_MASTER_PROMPT.md": 80,
}


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


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if not MANIFEST.exists():
        return fail(f"missing manifest: {MANIFEST.relative_to(ROOT)}")

    manifest_text = MANIFEST.read_text(encoding="utf-8")
    always_read = parse_top_level_list(manifest_text, "always_read")
    if always_read != REQUIRED_ALWAYS_READ:
        print("ERROR: always_read must exactly match required default Codex docs.", file=sys.stderr)
        print(f"Expected: {REQUIRED_ALWAYS_READ}", file=sys.stderr)
        print(f"Actual:   {always_read}", file=sys.stderr)
        return 1

    total_lines = 0
    total_chars = 0
    total_words = 0
    for relative in always_read:
        if relative.startswith("docs/archive/") or "/archive/" in relative:
            return fail(f"always_read includes archived path: {relative}")
        path = ROOT / relative
        if not path.exists():
            return fail(f"missing always_read file: {relative}")
        text = path.read_text(encoding="utf-8")
        total_lines += text.count("\n") + (0 if text.endswith("\n") else 1)
        total_chars += len(text)
        total_words += len(text.split())

    if total_lines > MAX_LINES:
        return fail(f"default Codex docs exceed line budget: {total_lines} > {MAX_LINES}")
    if total_chars > MAX_CHARS:
        return fail(f"default Codex docs exceed character budget: {total_chars} > {MAX_CHARS}")

    for relative, warn_lines in COMPACT_WARN_LINES.items():
        path = ROOT / relative
        if not path.exists():
            return fail(f"missing root Codex shim: {relative}")
        line_count = path.read_text(encoding="utf-8").count("\n") + 1
        if line_count > warn_lines:
            print(f"WARNING: {relative} is {line_count} lines; target is <= {warn_lines}.", file=sys.stderr)

    print(
        "Codex context budget OK: "
        f"{len(always_read)} files, {total_lines} lines, {total_words} words, {total_chars} chars."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
