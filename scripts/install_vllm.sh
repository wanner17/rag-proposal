#!/bin/bash
# GB10 aarch64 서버에서 vLLM + Embedding + Reranker 설치
# 한 번만 실행하면 됨

set -e

echo "=== [1/4] Python 가상환경 생성 ==="
python3 -m venv /opt/rag-venv
source /opt/rag-venv/bin/activate

echo "=== [2/4] pip 업그레이드 ==="
pip install --upgrade pip

echo "=== [3/4] vLLM 설치 (arm64 지원) ==="
# vLLM 0.9+ 부터 aarch64 wheel 공식 제공
pip install vllm

echo "=== [4/4] Embedding / Reranker 패키지 설치 ==="
pip install \
  fastapi \
  uvicorn[standard] \
  sentence-transformers \
  FlagEmbedding \
  torch \
  kiwipiepy \
  httpx

echo ""
echo "=== 설치 완료 ==="
echo "다음 단계: bash scripts/start_services.sh"
