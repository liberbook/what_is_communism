#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need_cmd python3
need_cmd pdflatex
need_cmd pandoc

if [[ $# -eq 0 ]]; then
  python3 "$ROOT_DIR/build_book.py"
else
  python3 "$ROOT_DIR/build_book.py" "$@"
fi

echo
echo "Build completed. Outputs:"
find "$ROOT_DIR/out" -maxdepth 3 -type f | sort
