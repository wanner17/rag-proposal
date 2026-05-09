# 사내 제안서 RAG 시스템 구축 계획

**Target:** Ubuntu 24.04 GPU Server (remote)  
**Mode:** Production-ready from day 1  
**Date:** 2026-05-09

---

## 요구사항 요약

- 사내 공공/SI 제안서 문서(PDF/HWP/DOCX) → 검색 가능한 조직 지식
- GPU 서버에서 로컬 LLM 운영 (외부 API 의존 없음)
- 부서별 문서 권한 분리
- 실서비스 수준 운영성

---

## 수락 기준 (Acceptance Criteria)

- [ ] vLLM + Qwen3 14B: 동시 요청 5개 처리, 응답 p99 < 10s
- [ ] Hybrid search (BM25+Vector) recall@10 > 0.85 (제안서 샘플 50건 기준)
- [ ] Reranker 적용 후 MRR 향상 확인
- [ ] HWP 파일 LibreOffice 변환 성공률 > 95%
- [ ] 메타데이터 필터링: department 기반 권한 분리 동작
- [ ] 출처 표시: 모든 답변에 파일명+페이지 반환
- [ ] Docker Compose `up -d` 한 번으로 전체 스택 기동

---

## 시스템 구조

```
[Next.js Frontend :3000]
         ↓ HTTPS (nginx)
[FastAPI Backend :8000]
    ↓           ↓
[vLLM :8080]  [Qdrant :6333]
[Qwen3 14B]
    ↓
[BGE-M3 Embedding Service :8001]
[BGE-Reranker :8002]
```

---

## 구현 단계

### Phase 1: 서버 환경 준비 (Day 1)

**1-1. GPU 서버 기본 설정**
```bash
# CUDA, Docker, NVIDIA Container Toolkit
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
nvidia-smi  # 확인
```

**1-2. 디렉토리 구조**
```
/opt/rag-system/
├── docker-compose.yml
├── .env
├── nginx/
│   └── nginx.conf
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── chat.py
│   │   │   ├── ingest.py
│   │   │   └── auth.py
│   │   ├── services/
│   │   │   ├── embedding.py
│   │   │   ├── reranker.py
│   │   │   ├── retrieval.py
│   │   │   ├── llm.py
│   │   │   └── document_processor.py
│   │   └── models/
│   │       └── schemas.py
├── frontend/
│   └── (Next.js app)
└── volumes/
    ├── qdrant_data/
    ├── models/
    └── documents/
```

---

### Phase 2: Docker Compose 스택 (Day 1-2)

**docker-compose.yml 핵심 구조:**

```yaml
services:
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    depends_on: [frontend, backend]

  frontend:
    build: ./frontend
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000

  backend:
    build: ./backend
    environment:
      - QDRANT_URL=http://qdrant:6333
      - VLLM_URL=http://vllm:8080/v1
      - EMBEDDING_URL=http://embedding:8001
      - RERANKER_URL=http://reranker:8002
    depends_on: [qdrant, vllm, embedding, reranker]

  vllm:
    image: vllm/vllm-openai:latest
    runtime: nvidia
    volumes:
      - ./volumes/models:/root/.cache/huggingface
    command: >
      --model Qwen/Qwen3-14B
      --served-model-name qwen3-14b
      --gpu-memory-utilization 0.85
      --max-model-len 8192
    ports: ["8080:8080"]

  embedding:
    build: ./embedding_service
    runtime: nvidia
    # BAAI/bge-m3 FastAPI 서비스

  reranker:
    build: ./reranker_service
    runtime: nvidia
    # BAAI/bge-reranker-v2-m3 FastAPI 서비스

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - ./volumes/qdrant_data:/qdrant/storage
    ports: ["6333:6333"]
```

---

### Phase 3: Embedding + Reranker 서비스 (Day 2)

**embedding_service/app.py:**
```python
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
import torch

app = FastAPI()
model = SentenceTransformer("BAAI/bge-m3", device="cuda")

@app.post("/embed")
async def embed(texts: list[str]):
    embeddings = model.encode(texts, normalize_embeddings=True)
    return {"embeddings": embeddings.tolist()}
```

**reranker_service/app.py:**
```python
from fastapi import FastAPI
from FlagEmbedding import FlagReranker

app = FastAPI()
reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)

@app.post("/rerank")
async def rerank(query: str, passages: list[str]):
    pairs = [[query, p] for p in passages]
    scores = reranker.compute_score(pairs)
    ranked = sorted(zip(scores, passages), reverse=True)
    return {"results": [{"score": s, "text": t} for s, t in ranked]}
```

---

### Phase 4: 문서 처리 파이프라인 (Day 2-3)

**document_processor.py:**

```python
import fitz  # PyMuPDF
import docx
import subprocess
from pathlib import Path

class DocumentProcessor:
    def extract_text(self, file_path: str) -> list[dict]:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return self._extract_pdf(file_path)
        elif ext == ".docx":
            return self._extract_docx(file_path)
        elif ext == ".hwp":
            pdf_path = self._hwp_to_pdf(file_path)
            return self._extract_pdf(pdf_path)

    def _hwp_to_pdf(self, hwp_path: str) -> str:
        output_dir = "/tmp/converted"
        subprocess.run([
            "libreoffice", "--headless", "--convert-to", "pdf",
            "--outdir", output_dir, hwp_path
        ], check=True)
        return f"{output_dir}/{Path(hwp_path).stem}.pdf"

    def _extract_pdf(self, path: str) -> list[dict]:
        doc = fitz.open(path)
        pages = []
        for i, page in enumerate(doc):
            pages.append({"page": i+1, "text": page.get_text()})
        return pages
```

**Semantic Chunker:**
```python
# 섹션 헤더 기반 분할 (TOC 구조 활용)
SECTION_PATTERNS = [
    r"^\d+\.\s+.+",          # 1. 사업개요
    r"^[가-힣]+\s*\d+\.",     # 가. 추진전략
    r"^제\d+[장절항]",        # 제1장
]

def semantic_chunk(pages: list[dict], metadata: dict) -> list[dict]:
    chunks = []
    current_section = ""
    current_text = ""
    
    for page in pages:
        for line in page["text"].split("\n"):
            if is_section_header(line):
                if current_text.strip():
                    chunks.append({
                        "text": current_text.strip(),
                        "section": current_section,
                        "page": page["page"],
                        **metadata
                    })
                current_section = line.strip()
                current_text = ""
            else:
                current_text += line + "\n"
    return chunks
```

**Metadata 스키마:**
```python
class DocumentMetadata(BaseModel):
    file: str
    page: int
    year: int
    client: str           # "교육청", "행자부"
    domain: str           # "이러닝", "행정시스템"
    project_type: str     # "플랫폼 구축", "유지보수"
    department: str       # "공공사업팀", "금융팀"
    section: str          # "추진전략", "구축방안"
```

---

### Phase 5: Qdrant 컬렉션 + Hybrid Search (Day 3)

```python
from qdrant_client import QdrantClient
from qdrant_client.models import *

client = QdrantClient(url="http://qdrant:6333")

# 컬렉션 생성 (hybrid: dense + sparse)
client.create_collection(
    collection_name="proposals",
    vectors_config={
        "dense": VectorParams(size=1024, distance=Distance.COSINE)
    },
    sparse_vectors_config={
        "bm25": SparseVectorParams(
            index=SparseIndexParams(on_disk=False)
        )
    }
)

# Hybrid Search
async def hybrid_search(query: str, department: str, top_k: int = 20):
    dense_vec = await get_embedding(query)
    sparse_vec = bm25_encode(query)  # BM25 토크나이저
    
    results = client.query_points(
        collection_name="proposals",
        prefetch=[
            Prefetch(query=dense_vec, using="dense", limit=top_k),
            Prefetch(query=sparse_vec, using="bm25", limit=top_k),
        ],
        query=FusionQuery(fusion=Fusion.RRF),  # Reciprocal Rank Fusion
        query_filter=Filter(
            must=[FieldCondition(key="department", match=MatchValue(value=department))]
        ),
        limit=top_k
    )
    return results
```

---

### Phase 6: RAG 파이프라인 (Day 3-4)

**retrieval.py:**
```python
async def retrieve_and_rerank(query: str, user_dept: str, top_n: int = 5):
    # 1. Hybrid search (top 20)
    candidates = await hybrid_search(query, department=user_dept, top_k=20)
    
    # 2. Reranker (top 5)
    texts = [c.payload["text"] for c in candidates]
    reranked = await rerank(query, texts)
    
    return reranked[:top_n]

async def generate_answer(query: str, chunks: list[dict]) -> dict:
    context = "\n\n".join([
        f"[출처: {c['file']} p{c['page']}]\n{c['text']}"
        for c in chunks
    ])
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"참고 문서:\n{context}\n\n질문: {query}"}
    ]
    
    response = await vllm_client.chat.completions.create(
        model="qwen3-14b",
        messages=messages,
        max_tokens=1024,
        temperature=0.1
    )
    
    sources = [{"file": c["file"], "page": c["page"]} for c in chunks]
    return {"answer": response.choices[0].message.content, "sources": sources}
```

**System Prompt:**
```
당신은 공공기관 SI 제안 전문가다.
반드시 제공된 참고 문서를 기반으로만 답변하라.
문서에 없는 내용은 추측하지 마라.
답변 시 반드시 출처(파일명, 페이지)를 함께 표시하라.
관련 문서가 없으면 "관련 문서를 찾지 못했습니다"라고 답하라.
```

---

### Phase 7: FastAPI 백엔드 (Day 4)

**주요 엔드포인트:**
```python
POST /api/chat          # 질문 → 답변 + 출처
POST /api/ingest        # 문서 업로드 + 인덱싱
GET  /api/documents     # 문서 목록 (권한 필터)
DELETE /api/documents/{id}
POST /api/auth/login    # JWT 발급
GET  /api/health        # 헬스체크
```

**인증 미들웨어:**
```python
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return {"user_id": payload["sub"], "department": payload["dept"]}
```

---

### Phase 8: Next.js 프론트엔드 (Day 4-5)

**핵심 화면:**
1. `/login` - JWT 로그인
2. `/chat` - 채팅 UI (스트리밍 응답, 출처 표시)
3. `/documents` - 문서 관리 (업로드/삭제)
4. `/admin` - 사용자/권한 관리

**채팅 UI 필수 기능:**
- 스트리밍 응답 (SSE)
- 출처 카드 (파일명 + 페이지 클릭 가능)
- 검색된 chunk 미리보기 토글
- 답변 신뢰도 표시 (reranker score 기반)
- 관련 문서 없음 fallback 메시지

---

### Phase 9: 운영 설정 (Day 5)

**nginx.conf 핵심:**
```nginx
location /api/ {
    proxy_pass http://backend:8000/;
    proxy_read_timeout 120s;  # LLM 응답 대기
}
location / {
    proxy_pass http://frontend:3000/;
}
```

**모니터링:**
```bash
# GPU 사용률
watch -n 1 nvidia-smi

# 서비스 상태
docker compose ps
docker compose logs -f backend
```

---

## 리스크 & 완화

| 리스크 | 완화 |
|--------|------|
| GPU VRAM 부족 (Qwen3 14B ~28GB) | `--gpu-memory-utilization 0.85`, fp16/bf16 확인 |
| HWP 변환 실패 | LibreOffice 버전 고정, 변환 실패 시 원본 텍스트 직접 추출 fallback |
| BM25 한국어 토크나이징 | kiwipiepy 또는 mecab 형태소 분석기 사용 |
| 초기 문서 없을 때 검색 품질 | 최소 50건 이상 인덱싱 후 서비스 오픈 권장 |
| Qwen3 14B 모델 다운로드 (~28GB) | HuggingFace 사전 다운로드 or volumes 마운트 유지 |

---

## 검증 단계

```bash
# 1. 스택 기동
docker compose up -d
docker compose ps  # 모든 서비스 healthy

# 2. 임베딩 테스트
curl -X POST http://localhost:8001/embed \
  -d '{"texts": ["공공기관 LMS 구축"]}'

# 3. 문서 인제스트
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@test_proposal.pdf" \
  -F "metadata={\"client\":\"교육청\",\"year\":2024}"

# 4. 검색 테스트
curl -X POST http://localhost:8000/api/chat \
  -d '{"query": "LMS 구축 사례", "department": "공공사업팀"}'

# 5. 출처 확인
# 응답에 sources 배열 있는지 확인
```

---

## 구현 순서 요약

```
Day 1: 서버 환경 + Docker Compose 기본 구조
Day 2: Embedding/Reranker 서비스 + 문서 처리
Day 3: Qdrant 컬렉션 + Hybrid Search
Day 4: FastAPI RAG 파이프라인 + 인증
Day 5: Next.js UI + nginx + 통합 테스트
```

---

## ADR (Architecture Decision Record)

**Decision:** vLLM + Qwen3 14B + Qdrant + BGE-M3 단일 스택

**Drivers:**
1. 한국어 제안서 검색 정확도
2. GPU 서버 로컬 운영 (보안/비용)
3. 실서비스 운영성

**Alternatives considered:**
- Ollama: 동시성 약함 → 탈락
- FAISS: persistence/filtering 불편 → 탈락
- Streamlit: 인증/권한 구현 한계 → 탈락

**Why chosen:** vLLM OpenAI 호환 + Qdrant hybrid search + Next.js 조합이 production 최단거리

**Consequences:** GPU VRAM 40GB+ 권장 (Qwen3 14B + BGE-M3 동시 로드)

**Follow-ups:**
- 문서 100건 이상 시 청킹 전략 재검토
- 사용자 피드백 기반 reranker fine-tuning 고려
