#!/usr/bin/env sh
set -eu

BUNDLE_DIR="${BUNDLE_DIR:-deploy/bundles/current}"
ARTIFACT_DIR="$BUNDLE_DIR/frontend"
mkdir -p "$ARTIFACT_DIR"

npm --prefix frontend run build
tar -C frontend -cf "$ARTIFACT_DIR/next-build.tar" .next public package.json package-lock.json next.config.ts
sha256sum "$ARTIFACT_DIR/next-build.tar" > "$ARTIFACT_DIR/next-build.tar.sha256"
