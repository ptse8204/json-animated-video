#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/run_backend_api.sh [options]

Initialize and serve the dependency-light local MotionJSON backend API.

Options:
  --host HOST           Host interface. Default: 127.0.0.1.
  --port PORT           Port. Default: 8765.
  --db PATH             SQLite database path. Default: .motionjson/backend.sqlite.
  --storage-root PATH   Local storage root. Default: .motionjson/storage.
  --init-only           Initialize storage/database and exit.
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

HOST="${MOTIONJSON_API_HOST:-127.0.0.1}"
PORT="${MOTIONJSON_API_PORT:-8765}"
DB="${MOTIONJSON_BACKEND_DB:-.motionjson/backend.sqlite}"
STORAGE_ROOT="${MOTIONJSON_STORAGE_ROOT:-.motionjson/storage}"
INIT_ONLY=0

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
    --init-only)
      INIT_ONLY=1
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

"$PYTHON_BIN" -m motionjson.cli backend init \
  --db "$DB" \
  --storage-root "$STORAGE_ROOT"

if [[ "$INIT_ONLY" -eq 1 ]]; then
  echo "Backend initialized at db=$DB storage=$STORAGE_ROOT"
  exit 0
fi

exec "$PYTHON_BIN" -m motionjson.cli backend serve-api \
  --db "$DB" \
  --storage-root "$STORAGE_ROOT" \
  --host "$HOST" \
  --port "$PORT"
