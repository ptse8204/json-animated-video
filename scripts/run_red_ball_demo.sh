#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/run_red_ball_demo.sh [options]

Generate the deterministic red-ball demo video, extract it with the CPU
threshold provider, and validate the output directory.

Options:
  --video PATH      Demo video path. Default: examples/demo_red_ball.mp4.
  --out DIR         Output directory. Default: out/demo_red_ball.
  --max-frames N    Max sampled frames. Default: 12.
  --sample-fps N    Sample FPS. Default: 12.
  --clean           Remove the output directory before running.
  -h, --help        Show this help.

Environment:
  PYTHON_BIN        Python executable. Default: .venv/bin/python if present,
                    otherwise python3.
EOF
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

VIDEO="examples/demo_red_ball.mp4"
OUT_DIR="out/demo_red_ball"
MAX_FRAMES=12
SAMPLE_FPS=12
CLEAN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --video)
      VIDEO="${2:?--video requires a value}"
      shift 2
      ;;
    --out)
      OUT_DIR="${2:?--out requires a value}"
      shift 2
      ;;
    --max-frames)
      MAX_FRAMES="${2:?--max-frames requires a value}"
      shift 2
      ;;
    --sample-fps)
      SAMPLE_FPS="${2:?--sample-fps requires a value}"
      shift 2
      ;;
    --clean)
      CLEAN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT"

if [[ "$CLEAN" -eq 1 ]]; then
  RESOLVED_OUT="$("$PYTHON_BIN" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$OUT_DIR")"
  RESOLVED_ROOT="$(cd "$ROOT" && pwd -P)"
  CLEAN_ALLOWED=0
  case "$RESOLVED_OUT" in
    "$RESOLVED_ROOT"/out/*|/tmp/motionjson-*|/private/tmp/motionjson-*)
      CLEAN_ALLOWED=1
      ;;
  esac
  if [[ "$CLEAN_ALLOWED" -ne 1 ]]; then
    echo "Refusing to clean output path outside repo out/ or /tmp/motionjson-*:" >&2
    echo "  $RESOLVED_OUT" >&2
    exit 2
  fi
  rm -rf "$RESOLVED_OUT"
fi

"$PYTHON_BIN" examples/make_demo_video.py --out "$VIDEO"
"$PYTHON_BIN" -m motionjson.cli extract "$VIDEO" \
  --out "$OUT_DIR" \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps "$SAMPLE_FPS" \
  --max-frames "$MAX_FRAMES"
"$PYTHON_BIN" -m motionjson.cli validate "$OUT_DIR"

echo "Red-ball demo written to $OUT_DIR"
if [[ "$OUT_DIR" = /* ]]; then
  echo "Output is outside the repo, so the built-in localhost preview URL is not printed."
  echo "Use a repo-relative --out path such as out/demo_red_ball for browser preview."
else
  echo "Optional preview:"
  echo "  python3 -m http.server 8080"
  echo "  http://localhost:8080/examples/canvas_player.html?scene=/$OUT_DIR/web_asset_manifest.json"
fi
