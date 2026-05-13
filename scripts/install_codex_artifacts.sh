#!/usr/bin/env bash
set -euo pipefail

echo "This script assumes it is run from the repository root after extracting the artifact ZIP."
echo "Checking expected Codex artifact files..."

required=(
  "AGENTS.md"
  ".codex/config.toml"
  ".codex/agents/motionjson_planner.toml"
  ".codex/agents/motionjson_executor.toml"
  ".codex/agents/motionjson_reviewer.toml"
  "docs/roadmap.md"
  "docs/phase_gates.md"
  "docs/architecture_context.md"
  "docs/ai_provider_architecture.md"
  "docs/product_requirements.md"
  "docs/commercial_context.md"
)

for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing: $f"
    exit 1
  fi
done

git diff --check
echo "Codex artifacts installed and whitespace check passed."
echo "Next: start Codex from the repository root and begin with Phase 0."
