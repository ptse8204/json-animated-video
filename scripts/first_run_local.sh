#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/first_run_local.sh [options]

Set up a local Python virtual environment, install MotionJSON in CPU/mock UI
mode, run provider diagnostics, and start the local UI unless disabled.

Options:
  --no-launch       Install and run diagnostics, but do not start the UI.
  --skip-install    Do not create a venv or install; use the current Python.
  --run-demo        Also run the deterministic red-ball CLI demo.
  --host HOST       UI host. Default: 127.0.0.1.
  --port PORT       UI port. Default: 8766.
  --venv DIR        Virtual environment directory. Default: .venv.
  -h, --help        Show this help.

Environment:
  PYTHON_BIN        Python executable for creating the venv. Default: python3.
  VENV_DIR          Virtual environment directory. Default: .venv.
EOF
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
HOST="${MOTIONJSON_UI_HOST:-127.0.0.1}"
PORT="${MOTIONJSON_UI_PORT:-8766}"
LAUNCH=1
RUN_DEMO=0
SKIP_INSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-launch)
      LAUNCH=0
      shift
      ;;
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    --run-demo)
      RUN_DEMO=1
      shift
      ;;
    --host)
      HOST="${2:?--host requires a value}"
      shift 2
      ;;
    --port)
      PORT="${2:?--port requires a value}"
      shift 2
      ;;
    --venv)
      VENV_DIR="${2:?--venv requires a value}"
      shift 2
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

PYTHON_CMD="python"
if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  echo "Creating virtual environment in ${VENV_DIR}"
  "$PYTHON_BIN" -m venv "$VENV_DIR"

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  python -m pip install -U pip
  python -m pip install -e ".[ui]"
else
  echo "Skipping install; using existing environment"
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
  else
    PYTHON_CMD="$PYTHON_BIN"
  fi
fi

echo "Running provider diagnostics"
mkdir -p .motionjson/storage
"$PYTHON_CMD" -m motionjson.cli backend diagnostics --json \
  --video examples/demo_red_ball.mp4 \
  --output-dir .motionjson/storage

if [[ "$RUN_DEMO" -eq 1 ]]; then
  scripts/run_red_ball_demo.sh
fi

if [[ "$LAUNCH" -eq 1 ]]; then
  echo "Starting MotionJSON UI in CPU/mock mode"
  exec "$PYTHON_CMD" -m motionjson.cli ui --no-open --mock --host "$HOST" --port "$PORT"
fi

echo "Setup complete. Start the UI with:"
if [[ -x "$VENV_DIR/bin/python" ]]; then
  echo "  ${VENV_DIR}/bin/python -m motionjson.cli ui --no-open --mock --host ${HOST} --port ${PORT}"
else
  echo "  ${PYTHON_BIN} -m motionjson.cli ui --no-open --mock --host ${HOST} --port ${PORT}"
fi
