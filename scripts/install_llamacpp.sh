#!/bin/bash
# llama.cpp 설치 + Qwen3-8B Q4_K_M 모델 다운로드
set -e

MODEL_DIR="/opt/models/qwen3-8b"

echo "=== [1/3] 빌드 의존성 설치 ==="
sudo apt install -y cmake build-essential

echo "=== [2/3] llama.cpp 빌드 (CUDA 활성화) ==="
cd /opt
if [ ! -d "llama.cpp" ]; then
  git clone https://github.com/ggerganov/llama.cpp
fi
cd /opt/llama.cpp
git pull

cmake -B build \
  -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=native \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j$(nproc)

echo "=== [3/3] Qwen3-8B Q4_K_M 다운로드 (~5GB) ==="
mkdir -p "$MODEL_DIR"
source /opt/rag-venv/bin/activate
hf download Qwen/Qwen3-8B-GGUF \
  --include "*q4_k_m*" \
  --local-dir "$MODEL_DIR"

echo ""
echo "=== 완료 ==="
echo "모델 위치: $MODEL_DIR"
ls -lh "$MODEL_DIR"
echo ""
echo "다음: bash scripts/start_services.sh"
