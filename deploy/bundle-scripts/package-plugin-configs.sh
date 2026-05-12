#!/usr/bin/env sh
set -eu

BUNDLE_DIR="${BUNDLE_DIR:-deploy/bundles/current}"
PLUGIN_DIR="$BUNDLE_DIR/plugins"
mkdir -p "$PLUGIN_DIR"

for plugin in ${RAG_ENABLED_PLUGINS:-proposal}; do
  mkdir -p "$PLUGIN_DIR/$plugin"
  cp "plugins/$plugin/plugin.yaml" "$PLUGIN_DIR/$plugin/plugin.yaml"
  sha256sum "$PLUGIN_DIR/$plugin/plugin.yaml" > "$PLUGIN_DIR/$plugin/plugin.yaml.sha256"
done
