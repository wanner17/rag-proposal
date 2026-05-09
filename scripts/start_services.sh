#!/bin/bash
# 호스트에서 GPU 서비스 실행 (vLLM, Embedding, Reranker)
# 서버 재시작 후 또는 최초 실행 시 사용

set -e

source /opt/rag-venv/bin/activate
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# ─── 1. llama.cpp (Qwen3 8B Q4_K_M) ─────────────────────────────────────────
echo "[llama.cpp] Qwen3-8B Q4_K_M 시작 중..."
GGUF_FILE=$(find /opt/models/qwen3-8b -name "*.gguf" | grep -i q4_k_m | head -1)
if [ -z "$GGUF_FILE" ]; then
  echo "오류: GGUF 모델 파일을 찾을 수 없습니다. install_llamacpp.sh 먼저 실행하세요."
  exit 1
fi
nohup /opt/llama.cpp/build/bin/llama-server \
  --model "$GGUF_FILE" \
  --alias qwen3-8b \
  --host 0.0.0.0 \
  --port 8080 \
  --n-gpu-layers 999 \
  --ctx-size 8192 \
  --threads 4 \
  --log-disable \
  > "$LOG_DIR/llamacpp.log" 2>&1 &
echo "[llama.cpp] PID $! | 로그: $LOG_DIR/llamacpp.log"

# ─── 2. Embedding 서비스 (BGE-M3) ───────────────────────────────────────────
echo "[Embedding] BGE-M3 시작 중..."
nohup uvicorn embedding_service.app:app \
  --host 0.0.0.0 \
  --port 8001 \
  --workers 1 \
  > "$LOG_DIR/embedding.log" 2>&1 &
echo "[Embedding] PID $! | 로그: $LOG_DIR/embedding.log"

# ─── 3. Reranker 서비스 (BGE-Reranker-v2-m3) ────────────────────────────────
echo "[Reranker] BGE-Reranker 시작 중..."
nohup uvicorn reranker_service.app:app \
  --host 0.0.0.0 \
  --port 8002 \
  --workers 1 \
  > "$LOG_DIR/reranker.log" 2>&1 &
echo "[Reranker] PID $! | 로그: $LOG_DIR/reranker.log"

echo ""
echo "=== GPU 서비스 시작 완료 ==="
echo "llama.cpp 준비까지 약 30-60초 소요 (모델 로딩)"
echo "확인: curl http://localhost:8080/health"
echo "확인: curl http://localhost:8001/health"
echo "확인: curl http://localhost:8002/health"
