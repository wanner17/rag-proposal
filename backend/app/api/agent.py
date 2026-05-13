import json
from dataclasses import asdict

from fastapi import APIRouter, Depends
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
from app.services.agent_orchestration.types import AgentWorkflowInput
from app.services.projects import get_default_project, get_project

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/query", response_model=AgentQueryResponse)
async def query_agent(req: AgentQueryRequest, user: UserInfo = Depends(get_current_user)):
    project = get_project(req.project_id) if req.project_id else get_default_project()
    department = resolve_department_scope(user, req.department)
    workflow_result = await run_agent_query(
        AgentWorkflowInput(
            query=req.query,
            department=department,
            project_id=project.id,
            project_slug=project.slug,
            collection_name=project.rag_config.collection_name,
            top_k=req.top_k or project.rag_config.top_k_default,
            top_n=req.top_n or project.rag_config.top_n_default,
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
    department = resolve_department_scope(user, req.department)
    workflow_input = AgentWorkflowInput(
        query=req.query,
        department=department,
        project_id=project.id,
        project_slug=project.slug,
        collection_name=project.rag_config.collection_name,
        top_k=req.top_k or project.rag_config.top_k_default,
        top_n=req.top_n or project.rag_config.top_n_default,
    )

    async def event_stream():
        async for event in stream_agent_query(workflow_input):
            yield f"data: {json.dumps(jsonable_encoder(event), ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
