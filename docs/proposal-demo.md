# Proposal Draft Demo and Corpus Setup

This guide defines repeatable demo scenarios for the quality-comparison proposal draft MVP. It is written for a fresh checkout and does not require changing backend or frontend code.

## What this demo must prove

Each scenario should produce a proposal draft response that includes:

- draft content, not only a Q&A answer;
- cited sources with file/page/section and score provenance;
- variant or config labels, such as `rerank_on`, `rerank_off`, or an implementation-specific strategy label;
- warnings for missing evidence, no-results, or non-comparable score sets;
- a quality summary that states whether the compared variants share the same candidate set.

Scenario definitions are also available in `demo/proposal-scenarios.json`.

## Corpus prerequisite

A fresh checkout does not include real proposal documents. Use one of these paths:

1. **Recommended for internal demos:** upload 4-6 sanitized real proposal documents that match the scenario topics below.
2. **Repeatable smoke demo:** create local synthetic `.md` files from the sample corpus outline in this guide, then upload them through the existing ingest flow.

Do not commit confidential proposal files. Keep demo corpus files under a local ignored folder such as `tmp/demo-corpus/`.

## Sample corpus outline

Create one local `.md` file per row. Each file should contain at least a few paragraphs; chunks shorter than about 50 characters may be ignored by the current document processor.

| File | Upload metadata | Content to include |
|---|---|---|
| `public-si-modernization.md` | year `2024`, client `교육청`, domain `공공 SI`, project_type `시스템 고도화`, department `공공사업팀` | 현황 진단, 단계별 전환, 데이터 이관, 보안, 운영 전환, 위험관리 |
| `learning-platform.md` | year `2024`, client `교육청`, domain `이러닝`, project_type `플랫폼 구축`, department `공공사업팀` | LMS 구축 범위, 사용자 포털, 콘텐츠 관리, 학습 분석, 접근성, 운영 지원 |
| `smart-factory-ai.md` | year `2023`, client `제조사`, domain `제조/AI`, project_type `AI 예측정비`, department `제조DX팀` | 설비 데이터 수집, 이상 탐지, 예측정비, 현장 PoC, MLOps, KPI |
| `public-cloud-migration.md` | year `2024`, client `공공기관`, domain `클라우드`, project_type `클라우드 전환`, department `공공사업팀` | 현행 분석, 마이그레이션 웨이브, 보안 인증, DR, 비용 최적화 |
| `healthcare-data-platform.md` | year `2023`, client `병원`, domain `헬스케어`, project_type `데이터 플랫폼`, department `헬스케어팀` | 개인정보 비식별화, 데이터 거버넌스, 분석 포털, 권한 통제, 감사 로그 |

## Indexing setup

Start the normal stack from the project root. The GPU services and Docker services are documented in `SETUP.md`.

Minimum services for API smoke:

```powershell
docker compose up -d qdrant backend
```

Login as admin:

```powershell
$login = Invoke-RestMethod -Method Post http://localhost:8088/api/auth/login `
  -ContentType "application/json" `
  -Body '{"username":"admin","password":"admin1234"}'
$token = $login.access_token
```

Upload each local demo corpus file:

```powershell
curl.exe -X POST http://localhost:8088/api/ingest `
  -H "Authorization: Bearer $token" `
  -F "file=@tmp/demo-corpus/public-si-modernization.md" `
  -F "year=2024" `
  -F "client=교육청" `
  -F "domain=공공 SI" `
  -F "project_type=시스템 고도화" `
  -F "department=공공사업팀"
```

Repeat the upload for each sample file with the metadata from the table above.

> Verification note: these smoke commands require running Docker, Qdrant, backend, embedding, reranker, and vLLM services. They were documented from the current API shapes, but not executed as part of this docs-only change.

## Curated scenarios

### 1. Public SI modernization proposal

- `scenario_id`: `demo-public-si-modernization`
- Department: `공공사업팀`
- Prompt: `교육청 노후 업무시스템 고도화 사업 제안서의 추진전략, 구현방안, 일정/리스크 섹션 초안을 작성해줘.`
- Expected evidence: `public-si-modernization.md`, optionally `public-cloud-migration.md`
- Expected warning: mention any missing budget, staffing, or client-specific constraints if not present in sources.
- Quality summary: rerank comparison is valid only when both variants reuse the same candidate identity.

### 2. LMS platform build proposal

- `scenario_id`: `demo-learning-platform`
- Department: `공공사업팀`
- Prompt: `공공기관 이러닝 플랫폼 구축 제안서의 사업 이해, 제안 접근방안, 운영 지원 방안을 초안으로 작성해줘.`
- Expected evidence: `learning-platform.md`, optionally `public-si-modernization.md`
- Expected warning: state that detailed SLA, license, or integration constraints are not confirmed unless present in uploaded documents.
- Quality summary: should identify strongest evidence sections for LMS, content management, learning analytics, and accessibility.

### 3. Smart factory AI predictive maintenance proposal

- `scenario_id`: `demo-smart-factory-ai`
- Department: `제조DX팀`
- Prompt: `제조 설비 예측정비 AI PoC 제안서 초안을 작성하고 데이터 수집, 모델 운영, 현장 적용 리스크를 정리해줘.`
- Expected evidence: `smart-factory-ai.md`
- Expected warning: if logged in as non-admin `user1`, this scenario should not retrieve `제조DX팀` documents because `user1` is scoped to `공공사업팀`.
- Quality summary: should separate retrieval relevance from rerank score and explain any no-results caused by department scope.

### 4. Public cloud migration proposal

- `scenario_id`: `demo-public-cloud-migration`
- Department: `공공사업팀`
- Prompt: `공공기관 클라우드 전환 사업 제안서의 전환 전략, 보안/DR, 비용 최적화, 단계별 이행계획 초안을 작성해줘.`
- Expected evidence: `public-cloud-migration.md`, optionally `public-si-modernization.md`
- Expected warning: call out unverified target cloud provider, current system inventory, and regulatory constraints if absent.
- Quality summary: should label cross-document support without directly ranking incompatible candidate sets.

### 5. Healthcare data platform no-results/scope check

- `scenario_id`: `demo-healthcare-scope-check`
- Department: `헬스케어팀`
- Prompt: `병원 데이터 플랫폼 제안서의 개인정보 보호, 데이터 거버넌스, 분석 포털 구축 방안을 초안으로 작성해줘.`
- Expected evidence: `healthcare-data-platform.md` for admin or a healthcare-scoped user.
- Expected warning/no-results: non-admin `user1` should remain scoped to `공공사업팀`; if no public-team evidence matches, the proposal response should return `found=false` or `status="no_results"` with `관련 제안서 근거 문서를 찾지 못했습니다.`
- Quality summary: should explain that no draft was generated because no permitted evidence was found.

## Proposal API smoke

Use a scenario after indexing the matching corpus.

```powershell
Invoke-RestMethod -Method Post http://localhost:8088/api/proposals/draft `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body '{"scenario_id":"demo-public-si-modernization","query":"교육청 노후 업무시스템 고도화 사업 제안서의 추진전략, 구현방안, 일정/리스크 섹션 초안을 작성해줘.","department":"공공사업팀","top_k":20,"top_n":5}'
```

Pass criteria:

- HTTP 200 for successful and no-results proposal requests.
- Response includes `request_id`, `found`, `status`, `variants`, `shared_sources`, and `warnings`.
- At least one success scenario includes non-empty `draft_markdown` and cited `shared_sources`.
- Source cards or source JSON label `retrieval_score`, `rerank_score`, and `score_source` clearly.
- If candidate identities differ, the quality summary says scores are not directly comparable.

## Manual UI smoke

Run this after the proposal API and frontend proposal page are available.

1. Open the app and verify an unauthenticated user reaches `/login`.
2. Log in as `admin` / `admin1234`; verify the app routes to chat.
3. Open chat and submit: `LMS 구축 사례 알려줘`. Confirm an answer and sources render after corpus upload.
4. Open upload and upload one demo corpus file with the metadata table above. Confirm the chunk count response appears.
5. Open the proposal page, for example `/proposals`. If this route returns 404, the frontend proposal slice is not complete yet.
6. Select or paste `demo-public-si-modernization`; submit the request.
7. Confirm the page renders draft content, cited sources, variant/config labels, warnings, and quality summary.
8. Log in as `user1` / `user1234` and submit `demo-smart-factory-ai` with department `제조DX팀`. Confirm the response does not widen beyond `공공사업팀` and shows no-results or only permitted public-team evidence.

## Repeatability checklist

- Demo corpus files are uploaded after Qdrant is empty or known-clean.
- Scenario prompt, department, `top_k`, and `top_n` match `demo/proposal-scenarios.json`.
- Admin scenarios can use all or requested departments.
- Non-admin scenarios never retrieve documents outside the token department.
- No-results scenarios do not call the proposal LLM and do not hallucinate draft sections.
