#!/usr/bin/env sh
set -eu

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
EMBEDDING_URL="${EMBEDDING_URL:-http://localhost:8001}"
RERANKER_URL="${RERANKER_URL:-http://localhost:8002}"
LLM_URL="${LLM_URL:-http://localhost:8080/v1}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
VERIFY_USER="${VERIFY_USER:-user1}"
VERIFY_PASSWORD="${VERIFY_PASSWORD:-user1234}"

curl -fsS "$BACKEND_URL/api/health" >/dev/null
curl -fsS "$BACKEND_URL/api/plugins" >/dev/null
curl -fsS "$EMBEDDING_URL/health" >/dev/null || curl -fsS "$EMBEDDING_URL/docs" >/dev/null
curl -fsS "$RERANKER_URL/health" >/dev/null || curl -fsS "$RERANKER_URL/docs" >/dev/null
curl -fsS "$LLM_URL/models" >/dev/null
curl -fsS "$QDRANT_URL/collections" >/dev/null

TOKEN="$(
  curl -fsS "$BACKEND_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$VERIFY_USER\",\"password\":\"$VERIFY_PASSWORD\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
)"

SAMPLE_FILE="$(mktemp /tmp/rag-airgap-sample.XXXXXX.txt)"
cat > "$SAMPLE_FILE" <<'EOF'
1. 사업개요
이 문서는 airgap 설치 검증을 위한 샘플 문서입니다. 공공기관 클라우드 전환 사업의 보안, 운영, 단계별 이행계획, 장애 대응, 문서 검색 검증을 위한 충분한 길이의 내용을 포함합니다.
2. 추진전략
검색과 제안서 초안 생성은 업로드된 근거 문서를 기반으로 수행되어야 하며, 출처와 페이지 정보가 함께 반환되어야 합니다.
EOF

curl -fsS "$BACKEND_URL/api/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$SAMPLE_FILE" \
  -F "year=2026" \
  -F "client=airgap-verify" \
  -F "domain=검증" \
  -F "project_type=오프라인 설치" \
  -F "department=공공사업팀" >/dev/null

curl -fsS "$BACKEND_URL/api/documents/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"airgap 설치 검증", "top_k": 3}' \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["found"] is True'

curl -fsS "$BACKEND_URL/api/proposals/draft" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"airgap 설치 검증 제안서 초안을 작성해줘", "top_k": 5, "top_n": 3}' \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["status"] in {"ok","partial"}; assert data["shared_sources"]'

echo "offline install health checks passed"
