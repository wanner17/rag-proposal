# 사내 제안서 RAG 시스템 설치 가이드

대상 서버: Ubuntu 24.04 + NVIDIA GB10 (ThinkStation PGX, aarch64)

---

## 1단계: 코드 서버에 복사

```bash
# Windows에서 서버로 전송 (scp 또는 git)
scp -r . pgxuser@<서버IP>:/opt/rag-system/
# 또는
git clone <repo> /opt/rag-system
```

---

## 2단계: GPU 서비스 설치 (최초 1회)

```bash
cd /opt/rag-system
bash scripts/install_vllm.sh
```

약 10~20분 소요. vLLM + BGE 모델 다운로드 포함.

---

## 3단계: 환경 파일 설정

```bash
cp .env.example .env
# .env에서 SECRET_KEY를 안전한 랜덤 문자열로 교체
nano .env
```

---

## 4단계: Docker 서비스 시작

```bash
# 볼륨 디렉토리 생성
mkdir -p volumes/qdrant_data volumes/documents logs

# Docker 서비스 기동 (Qdrant, Backend, Frontend, nginx)
docker compose up -d --build

# 상태 확인
docker compose ps
```

---

## 5단계: GPU 서비스 시작

```bash
# vLLM + Embedding + Reranker 호스트에서 실행
bash scripts/start_services.sh

# vLLM 준비 확인 (약 2~3분 후)
curl http://localhost:8080/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

---

## 6단계: SVN 체크아웃 서버 시작

소스코드 관리 화면의 "저장소 내려받기" 버튼은 백엔드 컨테이너에서 호스트의
`SVN_CHECKOUT_WEBHOOK_URL`로 HTTP 요청을 보냅니다. 기본 주소는
`http://host.docker.internal:8089`입니다.

호스트에서 별도 터미널로 체크아웃 서버를 실행하세요.

```bash
cd /opt/rag-system
export BACKEND_URL=http://127.0.0.1:8088
export SOURCE_INDEX_API_TOKEN="<.env의 SOURCE_INDEX_API_TOKEN과 같은 값>"
export SVN_USERNAME="<svn 계정>"
export SVN_PASSWORD="<svn 비밀번호>"
python3 scripts/checkout-server.py
```

연결 확인:

```bash
curl http://127.0.0.1:8089/status/test
```

응답이 `{"status": "idle" ...}` 형태로 나오면 웹 화면에서 체크아웃을 시작할 수 있습니다.

---

## 7단계: 동작 확인

```bash
# 전체 헬스체크
curl http://localhost/api/health

# 로그인 테스트
curl -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin1234"}'
```

---

## 일상 운영

| 작업 | 명령어 |
|------|--------|
| GPU 서비스 시작 | `bash scripts/start_services.sh` |
| GPU 서비스 중지 | `bash scripts/stop_services.sh` |
| Docker 재시작 | `docker compose restart` |
| 로그 확인 (backend) | `docker compose logs -f backend` |
| 로그 확인 (vLLM) | `tail -f logs/vllm.log` |
| GPU 상태 | `nvidia-smi` |

---

## 기본 계정

| 계정 | 비밀번호 | 권한 |
|------|----------|------|
| admin | admin1234 | 전체 부서 조회 |
| user1 | user1234 | 공공사업팀만 조회 |

**운영 전 반드시 `backend/app/core/auth.py`의 FAKE_USERS를 DB 연동으로 교체할 것.**

---

## 문서 업로드

```bash
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin1234"}' | jq -r .access_token)

curl -X POST http://localhost/api/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@제안서.pdf" \
  -F "year=2024" \
  -F "client=교육청" \
  -F "domain=이러닝" \
  -F "project_type=플랫폼 구축" \
  -F "department=공공사업팀"
```
