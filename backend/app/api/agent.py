import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.core.auth import get_current_user, resolve_department_scope
from app.models.agent_schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentWorkflowMetadata,
    AgentWorkflowStep,
)
from app.models.schemas import UserInfo
from app.services.agent_orchestration import run_agent_query, stream_agent_query
from app.services.agent_orchestration.question_classifier import classify_question_with_confidence
from app.services.agent_orchestration.types import AgentWorkflowInput
from app.services.projects import get_default_project, get_project

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/query", response_model=AgentQueryResponse)
async def query_agent(req: AgentQueryRequest, user: UserInfo = Depends(get_current_user)):
    project = get_project(req.project_id) if req.project_id else get_default_project()
    if req.retrieval_scope == "source_code" and project.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="활성 프로젝트 소스만 조회할 수 있습니다.",
        )
    department = (
        None
        if req.retrieval_scope == "source_code"
        else resolve_department_scope(user, req.department)
    )
    workflow_result = await run_agent_query(
        AgentWorkflowInput(
            query=req.query,
            department=department,
            project_id=project.id,
            project_slug=project.slug,
            collection_name=project.rag_config.collection_name,
            top_k=req.top_k or project.rag_config.top_k_default,
            top_n=req.top_n or project.rag_config.top_n_default,
            retrieval_scope=req.retrieval_scope,
            conversation_history=tuple(m.model_dump() for m in req.conversation_history),
        )
    )
    return AgentQueryResponse(
        answer=workflow_result.answer,
        sources=workflow_result.sources,
        found=workflow_result.found,
        metadata=AgentWorkflowMetadata(
            framework=workflow_result.framework,
            graph_version=workflow_result.graph_version,
            graph_run_id=workflow_result.graph_run_id,
            project_id=project.id,
            project_slug=project.slug,
            collection_name=project.rag_config.collection_name,
            selected_pass=workflow_result.selected_pass,
            retry_triggered=workflow_result.retry_triggered,
            fallback_used=workflow_result.fallback_used,
            steps=[
                AgentWorkflowStep(
                    name=step.name,
                    status=step.status,
                    duration_ms=step.duration_ms,
                    detail=step.detail,
                )
                for step in workflow_result.steps
            ],
            answer_quality=(
                asdict(workflow_result.answer_quality)
                if workflow_result.answer_quality is not None
                else None
            ),
        ),
    )


@router.post("/stream")
async def stream_agent(req: AgentQueryRequest, user: UserInfo = Depends(get_current_user)):
    project = get_project(req.project_id) if req.project_id else get_default_project()
    if req.retrieval_scope == "source_code" and project.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="활성 프로젝트 소스만 조회할 수 있습니다.",
        )
    department = (
        None
        if req.retrieval_scope == "source_code"
        else resolve_department_scope(user, req.department)
    )
    workflow_input = AgentWorkflowInput(
        query=req.query,
        department=department,
        project_id=project.id,
        project_slug=project.slug,
        collection_name=project.rag_config.collection_name,
        top_k=req.top_k or project.rag_config.top_k_default,
        top_n=req.top_n or project.rag_config.top_n_default,
        retrieval_scope=req.retrieval_scope,
        conversation_history=tuple(m.model_dump() for m in req.conversation_history),
    )

    async def event_stream():
        async for event in stream_agent_query(workflow_input):
            yield f"data: {json.dumps(jsonable_encoder(event), ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/debug")
async def debug_agent(req: AgentQueryRequest, user: UserInfo = Depends(get_current_user)) -> dict[str, Any]:
    """Full retrieval trace for debugging. Shows classifier, plan, chunk details, retry diffs."""
    project = get_project(req.project_id) if req.project_id else get_default_project()
    department = (
        None
        if req.retrieval_scope == "source_code"
        else resolve_department_scope(user, req.department)
    )

    classification = classify_question_with_confidence(req.query)

    workflow_result = await run_agent_query(
        AgentWorkflowInput(
            query=req.query,
            department=department,
            project_id=project.id,
            project_slug=project.slug,
            collection_name=project.rag_config.collection_name,
            top_k=req.top_k or project.rag_config.top_k_default,
            top_n=req.top_n or project.rag_config.top_n_default,
            retrieval_scope=req.retrieval_scope,
            conversation_history=tuple(m.model_dump() for m in req.conversation_history),
        )
    )

    steps_by_name: dict[str, dict] = {}
    for s in workflow_result.steps:
        steps_by_name.setdefault(s.name, s.detail)

    retrieve_detail = steps_by_name.get("retrieve_evidence", {})
    replan_detail = steps_by_name.get("replan_retrieval", {})
    plan_detail = steps_by_name.get("plan_retrieval", {})
    classify_detail = steps_by_name.get("classify_question", {})

    critic = workflow_result.critic_result
    initial_pass = critic.initial if critic else None
    retry_pass = critic.retry if critic else None

    def _chunk_summary(chunks: list[dict]) -> list[dict[str, Any]]:
        return [
            {
                "path": c.get("relative_path") or c.get("file"),
                "chunk_type": c.get("chunk_type"),
                "score": round(float(c.get("score") or 0), 4),
                "rerank_score": round(float(c.get("rerank_score") or 0), 4) if c.get("rerank_score") is not None else None,
                "text_preview": str(c.get("text", ""))[:120],
            }
            for c in (chunks or [])
        ]

    return {
        "question": req.query,
        "question_type": classify_detail.get("question_type", classification.question_type.value),
        "classifier_confidence": classify_detail.get("confidence", classification.confidence),
        "retrieval_plan": {
            "priority_chunk_types": retrieve_detail.get("plan_priority_chunk_types", []),
            "priority_paths": retrieve_detail.get("plan_priority_paths", []),
            "exclude_paths": retrieve_detail.get("plan_exclude_paths", []),
            "boost_project_summary": retrieve_detail.get("plan_boost_project_summary", False),
            "top_k": plan_detail.get("top_k"),
            "top_n": plan_detail.get("top_n"),
        },
        "retrieved_chunks": _chunk_summary(initial_pass.candidates if initial_pass else []),
        "reranked_chunks": _chunk_summary(initial_pass.reranked if initial_pass else []),
        "chunk_type_distribution": retrieve_detail.get("chunk_type_distribution", {}),
        "summary_chunks_prepended": retrieve_detail.get("summary_chunks_prepended", 0),
        "retry_count": replan_detail.get("retry_count", 0),
        "retry_reasons": replan_detail.get("reasons", []),
        "retry_plan_diff": {
            "new_top_k": replan_detail.get("new_top_k"),
            "new_top_n": replan_detail.get("new_top_n"),
            "extra_exclude_paths": replan_detail.get("extra_exclude_paths", []),
            "boost_project_summary_forced": replan_detail.get("boost_project_summary_forced"),
        } if workflow_result.retry_triggered else None,
        "retry_reranked_chunks": _chunk_summary(retry_pass.reranked if retry_pass else []),
        "final_context_sources": retrieve_detail.get("final_sources", []),
        "answer_preview": (workflow_result.answer or "")[:500],
        "steps": [
            {"name": s.name, "duration_ms": s.duration_ms, "detail": s.detail}
            for s in workflow_result.steps
        ],
    }
