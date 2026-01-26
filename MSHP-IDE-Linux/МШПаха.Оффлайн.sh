#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ARCH="$(uname -m)"
PYDIR=""

case "$ARCH" in
  arm64|aarch64) PYDIR="$ROOT/python/aarch64" ;;
  x86_64|amd64) PYDIR="$ROOT/python/x86_64" ;;
  *) PYDIR="$ROOT/python/x86_64" ;;
esac

if [[ ! -d "$PYDIR" ]]; then
  if [[ -d "$ROOT/python/x86_64" ]]; then
    PYDIR="$ROOT/python/x86_64"
  elif [[ -d "$ROOT/python/aarch64" ]]; then
    PYDIR="$ROOT/python/aarch64"
  fi
fi

PY="${PYTHON_PORTABLE:-}"

if [[ -z "$PY" ]]; then
  for cand in "$PYDIR/bin/python3" "$PYDIR/bin/python3.13" "$PYDIR/bin/python"; do
    if [[ -f "$cand" ]]; then
      PY="$cand"
      break
    fi
  done
fi

if [[ -z "$PY" ]]; then
  echo "Portable Python not found in: $PYDIR"
  exit 1
fi

if [[ -f "$PY" && ! -x "$PY" ]]; then
  chmod +x "$PY" 2>/dev/null || true
fi

if [[ -d "$PYDIR/lib/tcl8.6" ]]; then
  export TCL_LIBRARY="$PYDIR/lib/tcl8.6"
fi
if [[ -d "$PYDIR/lib/tk8.6" ]]; then
  export TK_LIBRARY="$PYDIR/lib/tk8.6"
fi
export PYTHONHOME="$PYDIR"
export PYTHON_PORTABLE="$PY"
export LD_LIBRARY_PATH="$PYDIR/lib:${LD_LIBRARY_PATH:-}"

exec "$PY" "$ROOT/app/ide.py"
