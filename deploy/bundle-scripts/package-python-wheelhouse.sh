#!/usr/bin/env sh
set -eu

BUNDLE_DIR="${BUNDLE_DIR:-deploy/bundles/current}"
WHEELHOUSE="$BUNDLE_DIR/wheelhouse"
mkdir -p "$WHEELHOUSE"

python3 -m pip wheel --wheel-dir "$WHEELHOUSE" -r backend/requirements.txt
find "$WHEELHOUSE" -type f -maxdepth 1 -print0 | xargs -0 sha256sum > "$WHEELHOUSE/SHA256SUMS"
