#!/usr/bin/env sh
set -eu

BUNDLE_DIR="${BUNDLE_DIR:-deploy/bundles/current}"
MANIFEST="${MANIFEST:-$BUNDLE_DIR/manifest.json}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/airgap-compose/compose.yml}"

deploy/bundle-scripts/validate-manifest.py "$MANIFEST"
BUNDLE_DIR="$BUNDLE_DIR" deploy/bundle-scripts/load-images.sh
docker compose -f "$COMPOSE_FILE" up -d
deploy/bundle-scripts/verify-offline-install.sh
