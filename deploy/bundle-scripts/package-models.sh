#!/usr/bin/env sh
set -eu

if [ -z "${MODEL_SOURCE_DIR:-}" ]; then
  echo "MODEL_SOURCE_DIR is required" >&2
  exit 1
fi

BUNDLE_DIR="${BUNDLE_DIR:-deploy/bundles/current}"
MODEL_DIR="$BUNDLE_DIR/models"
mkdir -p "$MODEL_DIR"

for model in "$MODEL_SOURCE_DIR"/*; do
  [ -f "$model" ] || continue
  cp "$model" "$MODEL_DIR/"
done

find "$MODEL_DIR" -maxdepth 1 -type f -print0 | xargs -0 sha256sum > "$MODEL_DIR/SHA256SUMS"
