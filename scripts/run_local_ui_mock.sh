#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/run_local_ui_mock.sh [options]

Start the local MotionJSON UI in explicit debug mock mode.

Options:
  --host HOST           Host interface. Default: 127.0.0.1.
  --port PORT           Port. Default: 8766.
  --db PATH             SQLite database path. Default: .motionjson/backend.sqlite.
  --storage-root PATH   Local storage root. Default: .motionjson/storage.
  -h, --help            Show this help.

Environment:
  PYTHON_BIN            Python executable. Default: .venv/bin/python if present,
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

HOST="${MOTIONJSON_UI_HOST:-127.0.0.1}"
PORT="${MOTIONJSON_UI_PORT:-8766}"
DB="${MOTIONJSON_BACKEND_DB:-.motionjson/backend.sqlite}"
STORAGE_ROOT="${MOTIONJSON_STORAGE_ROOT:-.motionjson/storage}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:?--host requires a value}"
      shift 2
      ;;
    --port)
      PORT="${2:?--port requires a value}"
      shift 2
      ;;
    --db)
      DB="${2:?--db requires a value}"
      shift 2
      ;;
    --storage-root)
      STORAGE_ROOT="${2:?--storage-root requires a value}"
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
exec "$PYTHON_BIN" -m motionjson.cli ui \
  --no-open \
  --debug-mock \
  --db "$DB" \
  --storage-root "$STORAGE_ROOT" \
  --host "$HOST" \
  --port "$PORT"
