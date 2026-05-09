#!/bin/bash
# GPU 서비스 중지

pkill -f "vllm.entrypoints.openai.api_server" && echo "[vLLM] 중지됨" || echo "[vLLM] 실행 중 아님"
pkill -f "embedding_service.app" && echo "[Embedding] 중지됨" || echo "[Embedding] 실행 중 아님"
pkill -f "reranker_service.app" && echo "[Reranker] 중지됨" || echo "[Reranker] 실행 중 아님"
