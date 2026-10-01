#!/usr/bin/env bash
# Stop whatever is listening on PORT, then start the System 1 playground.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PORT="${1:-${PORT:-8000}}"
HOST="${HOST:-127.0.0.1}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "error: port must be an integer from 1 to 65535 (got: $PORT)" >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "error: virtualenv not found at $VENV_DIR" >&2
  echo "Run ./install.sh first." >&2
  exit 1
fi

if ! command -v lsof >/dev/null 2>&1; then
  echo "error: lsof is required to free port $PORT" >&2
  exit 1
fi

stop_listeners() {
  local pids=()
  local pid
  while IFS= read -r pid; do
    [[ -n "$pid" ]] && pids+=("$pid")
  done < <(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)

  if [[ ${#pids[@]} -eq 0 ]]; then
    echo "==> Nothing listening on port $PORT"
    return
  fi

  echo "==> Stopping process on port $PORT: ${pids[*]}"
  kill "${pids[@]}" 2>/dev/null || true

  local attempt still
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    still="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
    if [[ -z "${still//[[:space:]]/}" ]]; then
      return
    fi
    sleep 0.2
  done

  echo "==> Force stopping process on port $PORT"
  kill -9 "${pids[@]}" 2>/dev/null || true
}

stop_listeners

echo "==> Starting playground at http://$HOST:$PORT"
exec "$VENV_DIR/bin/python" -m uvicorn playground.app:app --host "$HOST" --port "$PORT"
