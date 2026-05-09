#!/bin/bash
# 호스트에서 GPU 서비스 실행 (vLLM, Embedding, Reranker)
# 서버 재시작 후 또는 최초 실행 시 사용

set -e

source /opt/rag-venv/bin/activate
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# ─── 1. vLLM (Qwen3 14B) ────────────────────────────────────────────────────
echo "[vLLM] Qwen3-14B 시작 중..."
# GB10 통합 메모리 128GB → gpu_memory_utilization 0.7로 여유 확보
# enforce_eager: GB10에서 CUDA graph 컴파일 문제 방지
nohup python3 -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-14B \
  --served-model-name qwen3-14b \
  --host 0.0.0.0 \
  --port 8080 \
  --gpu-memory-utilization 0.7 \
  --max-model-len 8192 \
  --enforce-eager \
  --dtype bfloat16 \
  > "$LOG_DIR/vllm.log" 2>&1 &
echo "[vLLM] PID $! | 로그: $LOG_DIR/vllm.log"

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
echo "vLLM 준비까지 약 2-3분 소요 (모델 로딩)"
echo "확인: curl http://localhost:8080/health"
echo "확인: curl http://localhost:8001/health"
echo "확인: curl http://localhost:8002/health"
