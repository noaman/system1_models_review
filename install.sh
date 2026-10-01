#!/usr/bin/env bash
# Recreate the project virtualenv and install the playground dependencies.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-$ROOT/requirements.txt}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "==> Project root: $ROOT"
echo "==> Virtualenv:   $VENV_DIR"

if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
  echo "error: requirements file not found: $REQUIREMENTS_FILE" >&2
  exit 1
fi

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo "==> Deactivating active virtualenv ($VIRTUAL_ENV)"
  deactivate 2>/dev/null || true
  unset VIRTUAL_ENV
fi

echo "==> Cleaning previous install"
rm -rf "$VENV_DIR"

echo "==> Creating fresh virtualenv"
"$PYTHON_BIN" -m venv "$VENV_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> Upgrading pip"
python -m pip install --upgrade pip

echo "==> Installing Python packages from requirements.txt"
python -m pip install -r "$REQUIREMENTS_FILE"

echo
echo "Install complete."
echo "Start the playground:"
echo "  ./run.sh 8000"
