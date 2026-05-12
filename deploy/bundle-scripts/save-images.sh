#!/usr/bin/env sh
set -eu

BUNDLE_DIR="${BUNDLE_DIR:-deploy/bundles/current}"
IMAGE_DIR="$BUNDLE_DIR/images"
mkdir -p "$IMAGE_DIR"

save_image() {
  image="$1"
  file="$2"
  docker save "$image" -o "$IMAGE_DIR/$file"
  sha256sum "$IMAGE_DIR/$file" > "$IMAGE_DIR/$file.sha256"
}

save_image "${BACKEND_IMAGE:-rag-proposal-backend:airgap}" "rag-proposal-backend-airgap.tar"
save_image "${FRONTEND_IMAGE:-rag-proposal-frontend:airgap}" "rag-proposal-frontend-airgap.tar"
save_image "${QDRANT_IMAGE:-rag-qdrant:airgap}" "qdrant.tar"
save_image "${NGINX_IMAGE:-rag-nginx:airgap}" "nginx.tar"
save_image "${EMBEDDING_IMAGE:-rag-embedding:airgap}" "embedding.tar"
save_image "${RERANKER_IMAGE:-rag-reranker:airgap}" "reranker.tar"
save_image "${LLM_IMAGE:-rag-llm:airgap}" "llm.tar"
