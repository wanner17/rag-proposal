from uuid import uuid4
import logging
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, resolve_department_scope
from app.models.schemas import (
    ProposalDraftRequest,
    ProposalDraftResponse,
    ProposalSource,
    ProposalVariant,
    UserInfo,
)
from app.services.proposal_llm import generate_proposal_draft
from app.services.retrieval import retrieve_with_metadata
from app.services.retrieval_experiments import CandidateIdentity, quality_summary

router = APIRouter(prefix="/proposals", tags=["proposals"])
logger = logging.getLogger(__name__)

NO_RESULTS_MESSAGE = "관련 제안서 근거 문서를 찾지 못했습니다."
ERROR_MESSAGE = "제안서 초안 생성 중 오류가 발생했습니다."
PARTIAL_MESSAGE = "근거 문서는 찾았지만 초안 생성 모델 호출에 실패했습니다. 근거 출처만 반환합니다."

DEMO_SCENARIOS: dict[str, str] = {
    "demo-public-si-modernization": "교육청 노후 업무시스템 고도화 사업 제안서의 추진전략, 구현방안, 일정/리스크 섹션 초안을 작성해줘.",
    "demo-learning-platform": "공공기관 이러닝 플랫폼 구축 제안서의 사업 이해, 제안 접근방안, 운영 지원 방안을 초안으로 작성해줘.",
    "demo-smart-factory-ai": "제조 설비 예측정비 AI PoC 제안서 초안을 작성하고 데이터 수집, 모델 운영, 현장 적용 리스크를 정리해줘.",
    "demo-public-cloud-migration": "공공기관 클라우드 전환 사업 제안서의 전환 전략, 보안/DR, 비용 최적화, 단계별 이행계획 초안을 작성해줘.",
    "demo-healthcare-scope-check": "병원 데이터 플랫폼 제안서의 개인정보 보호, 데이터 거버넌스, 분석 포털 구축 방안을 초안으로 작성해줘.",
    # Backward-compatible aliases for the PRD/test-spec examples.
    "demo-public-si": "공공기관 SI 구축 사업 제안서의 접근방안과 운영 리스크를 작성해줘.",
    "demo-lms": "교육/LMS 플랫폼 구축 제안서 초안의 요구 해석과 구현 포인트를 작성해줘.",
    "demo-cloud-migration": "클라우드 전환 사업 제안서의 단계별 추진방안과 리스크를 작성해줘.",
    "demo-security": "보안 강화 사업 제안서의 주요 통제 방안과 운영 포인트를 작성해줘.",
}


def _resolve_query(req: ProposalDraftRequest) -> str:
    if req.query and req.query.strip():
        return req.query.strip()
    if req.scenario_id and req.scenario_id in DEMO_SCENARIOS:
        return DEMO_SCENARIOS[req.scenario_id]
    return ""


def _proposal_source(chunk: dict) -> ProposalSource:
    return ProposalSource(
        point_id=str(chunk.get("point_id") or chunk.get("chunk_id") or ""),
        file=chunk.get("file", ""),
        page=chunk.get("page", 0),
        section=chunk.get("section", ""),
        score=chunk.get("score"),
        retrieval_score=chunk.get("retrieval_score"),
        rerank_score=chunk.get("rerank_score"),
        score_source=chunk.get("score_source", "unavailable"),
        department=chunk.get("department"),
    )


@router.post("/draft", response_model=ProposalDraftResponse)
async def draft_proposal(req: ProposalDraftRequest, user: UserInfo = Depends(get_current_user)):
    request_id = str(uuid4())
    query = _resolve_query(req)
    department_scope = resolve_department_scope(user, req.department)

    if not query:
        return ProposalDraftResponse(
            request_id=request_id,
            found=False,
            status="no_results",
            scenario_id=req.scenario_id,
            department_scope=department_scope,
            variants=[],
            shared_sources=[],
            warnings=[NO_RESULTS_MESSAGE],
            no_results_message=NO_RESULTS_MESSAGE,
        )

    try:
        candidates, reranked = await retrieve_with_metadata(
            query,
            department=department_scope,
            top_k=req.top_k,
            top_n=req.top_n,
        )
    except Exception as exc:
        logger.exception("Proposal retrieval failed")
        return ProposalDraftResponse(
            request_id=request_id,
            found=False,
            status="error",
            scenario_id=req.scenario_id,
            department_scope=department_scope,
            variants=[],
            shared_sources=[],
            warnings=[f"{ERROR_MESSAGE} 검색 서비스를 확인하세요. ({type(exc).__name__})"],
            no_results_message=None,
        )

    if not candidates or not reranked:
        return ProposalDraftResponse(
            request_id=request_id,
            found=False,
            status="no_results",
            scenario_id=req.scenario_id,
            department_scope=department_scope,
            variants=[],
            shared_sources=[],
            warnings=[NO_RESULTS_MESSAGE],
            no_results_message=NO_RESULTS_MESSAGE,
        )

    identity = CandidateIdentity(
        query=query,
        department_scope=department_scope,
        top_k=req.top_k,
        retrieval_variant="hybrid_rrf_dense_bm25",
        chunking_variant="default",
        filters={"department": department_scope},
    )
    sources = [_proposal_source(chunk) for chunk in reranked]
    warnings = []
    if len(reranked) < req.top_n:
        warnings.append(f"요청한 근거 수 {req.top_n}개보다 적은 {len(reranked)}개 근거만 발견되었습니다.")
    status = "ok"

    try:
        draft_markdown = await generate_proposal_draft(query, reranked)
    except Exception as exc:
        logger.exception("Proposal draft generation failed")
        status = "partial"
        draft_markdown = PARTIAL_MESSAGE
        warnings.append(f"{PARTIAL_MESSAGE} ({type(exc).__name__})")

    variant = ProposalVariant(
        variant_id="rerank-top-n",
        title="근거 기반 제안서 초안",
        strategy=f"{identity.retrieval_variant} + rerank_top_{req.top_n}",
        draft_markdown=draft_markdown,
        sources=sources,
        warnings=warnings,
        quality_summary=quality_summary(identity, identity, rerank_only=True),
    )

    return ProposalDraftResponse(
        request_id=request_id,
        found=True,
        status=status,
        scenario_id=req.scenario_id,
        department_scope=department_scope,
        variants=[variant],
        shared_sources=sources,
        warnings=warnings,
        no_results_message=None,
    )
