#!/bin/bash
# 전체 RAG 시스템 시작 스크립트
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "========================================"
echo "    제안서 RAG 시스템 시작"
echo "========================================"

# ─── 1. Docker (Qdrant + 백엔드) ─────────────────────────────────────────────
echo ""
echo "[1/4] Docker 서비스 시작 (Qdrant + 백엔드)..."
cd "$PROJECT_DIR"
docker compose up -d
echo "      완료"

# ─── 2. Python 가상환경 활성화 ───────────────────────────────────────────────
source /opt/rag-venv/bin/activate

# ─── 3. llama.cpp (Qwen3-8B) ─────────────────────────────────────────────────
echo ""
echo "[2/4] llama.cpp 시작 (Qwen3-8B Q4_K_M)..."
GGUF_FILE=$(find /opt/models/qwen3-8b -name "*.gguf" | grep -i q4_k_m | head -1)
if [ -z "$GGUF_FILE" ]; then
  echo "      오류: GGUF 모델 없음. scripts/install_llamacpp.sh 먼저 실행하세요."
  exit 1
fi
pkill -f "llama-server" 2>/dev/null || true
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
echo "      PID $! | 로그: $LOG_DIR/llamacpp.log"

# ─── 4. 임베딩 서비스 (BGE-M3) ───────────────────────────────────────────────
echo ""
echo "[3/4] 임베딩 서비스 시작 (BGE-M3)..."
pkill -f "embedding_service" 2>/dev/null || true
nohup uvicorn embedding_service.app:app \
  --host 0.0.0.0 --port 8001 --workers 1 \
  > "$LOG_DIR/embedding.log" 2>&1 &
echo "      PID $! | 로그: $LOG_DIR/embedding.log"

# ─── 5. 리랭커 서비스 (BGE-Reranker) ────────────────────────────────────────
echo ""
echo "[4/4] 리랭커 서비스 시작 (BGE-Reranker)..."
pkill -f "reranker_service" 2>/dev/null || true
nohup uvicorn reranker_service.app:app \
  --host 0.0.0.0 --port 8002 --workers 1 \
  > "$LOG_DIR/reranker.log" 2>&1 &
echo "      PID $! | 로그: $LOG_DIR/reranker.log"

# ─── 6. 프론트엔드 (Next.js) ─────────────────────────────────────────────────
echo ""
echo "[프론트엔드] Next.js 시작..."
pkill -f "next dev" 2>/dev/null || true
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
nvm use 20 --silent
nohup npm --prefix "$PROJECT_DIR/frontend" run dev \
  > "$LOG_DIR/frontend.log" 2>&1 &
echo "      PID $! | 로그: $LOG_DIR/frontend.log"

# ─── 완료 ─────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  모든 서비스 시작 완료"
echo "  llama.cpp 로딩까지 약 30-60초 소요"
echo ""
echo "  상태 확인:"
echo "    curl http://localhost:8080/health  # LLM"
echo "    curl http://localhost:8001/health  # 임베딩"
echo "    curl http://localhost:8002/health  # 리랭커"
echo "    curl http://localhost:6333/health  # Qdrant"
echo "    docker compose ps                 # 백엔드"
echo ""
echo "  프론트엔드: http://$(hostname -I | awk '{print $1}'):3000"
echo "========================================"
