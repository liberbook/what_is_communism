#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="engels-principi-build"

cd "$ROOT_DIR"
docker build -t "$IMAGE_NAME" .
mkdir -p "$ROOT_DIR/out"
docker run --rm \
	--user "$(id -u):$(id -g)" \
	-v "$ROOT_DIR/out:/work/out" \
	"$IMAGE_NAME"

echo "Docker build completed. Outputs are in $ROOT_DIR/out"
