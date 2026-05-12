#!/usr/bin/env sh
set -eu

BUNDLE_DIR="${BUNDLE_DIR:-deploy/bundles/current}"
IMAGE_DIR="$BUNDLE_DIR/images"

for checksum in "$IMAGE_DIR"/*.sha256; do
  sha256sum -c "$checksum"
done

for image_tar in "$IMAGE_DIR"/*.tar; do
  docker load -i "$image_tar"
done
