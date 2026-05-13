import asyncio
import builtins
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.agent import router as agent_router
from app.core.auth import create_token
from app.core.config import settings
from app.main import app
from app.models.project_schemas import ProjectCreateRequest, ProjectRagConfig
from app.models.schemas import Source
from app.services.agent_orchestration import workflow
from app.services.agent_orchestration.types import (
    AgentWorkflowResult,
    AgentWorkflowTraceStep,
    AnswerQualityFinding,
    AnswerQualityReport,
)
from app.services.projects import create_project
from app.services.retrieval_critic import CriticPass, CriticResult, assess_retrieval


def _headers(user_id="admin", department="전체", is_admin=True):
    return {"Authorization": f"Bearer {create_token(user_id, department, is_admin)}"}


def _chunk(text: str, score: float):
    return {
        "text": text,
        "file": "manual.pdf",
        "page": 3,
        "section": "개요",
        "score": score,
        "rerank_score": score,
    }


def _critic_result(chunks: list[dict]) -> CriticResult:
    decision = assess_retrieval(
        "클라우드 전환 전략",
        chunks,
        requested_top_n=max(len(chunks), 1),
        retry_triggered=False,
        selected_pass="initial",
    )
    selected = CriticPass("initial", chunks, chunks, decision)
    return CriticResult(selected=selected, initial=selected)


def test_agent_route_is_not_registered_when_feature_flag_is_off():
    client = TestClient(app)

    response = client.post(
        "/api/agent/query",
        headers=_headers(),
        json={"query": "클라우드 전환 전략"},
    )

    assert response.status_code == 404


def test_agent_router_requires_auth_when_included_experimentally():
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(agent_router, prefix="/api")
    client = TestClient(test_app)

    response = client.post("/api/agent/query", json={"query": "클라우드 전환 전략"})

    assert response.status_code == 401


def test_agent_query_endpoint_returns_metadata_contract(tmp_path, monkeypatch):
    from fastapi import FastAPI
    import app.api.agent as agent_api

    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))

    async def fake_run_agent_query(workflow_input):
        assert workflow_input.query == "클라우드 전환 전략"
        assert workflow_input.department is None
        assert workflow_input.project_slug == "proposal-default"
        assert workflow_input.collection_name
        return AgentWorkflowResult(
            answer="생성된 답변",
            sources=[Source(file="manual.pdf", page=3, section="개요", score=0.91)],
            found=True,
            graph_run_id="run-test",
            framework="langgraph",
            graph_version="agent-query-v1",
            selected_pass="initial",
            retry_triggered=False,
            fallback_used=False,
            steps=[
                AgentWorkflowTraceStep(
                    name="retrieve_evidence",
                    duration_ms=1.25,
                    detail={"selected_pass": "initial", "result_count": 1},
                )
            ],
            answer_quality=AnswerQualityReport(
                status="issues_found",
                findings=[
                    AnswerQualityFinding(
                        category="source_attribution",
                        severity="warning",
                        message="출처 표시가 부족합니다.",
                    )
                ],
                evidence_sufficiency={"available": True, "sufficient": True},
                revision_recommended=True,
                revision_triggered=False,
                revision_count=0,
            ),
        )

    monkeypatch.setattr(agent_api, "run_agent_query", fake_run_agent_query)
    test_app = FastAPI()
    test_app.include_router(agent_router, prefix="/api")
    client = TestClient(test_app)

    response = client.post(
        "/api/agent/query",
        headers=_headers(),
        json={"query": "클라우드 전환 전략"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "생성된 답변"
    assert payload["found"] is True
    assert payload["sources"] == [
        {"file": "manual.pdf", "page": 3, "section": "개요", "score": 0.91}
    ]
    assert payload["metadata"]["framework"] == "langgraph"
    assert payload["metadata"]["graph_version"] == "agent-query-v1"
    assert payload["metadata"]["graph_run_id"] == "run-test"
    assert payload["metadata"]["project_id"] == "project-proposal-default"
    assert payload["metadata"]["project_slug"] == "proposal-default"
    assert payload["metadata"]["collection_name"] == "proposals"
    assert payload["metadata"]["selected_pass"] == "initial"
    assert payload["metadata"]["retry_triggered"] is False
    assert payload["metadata"]["fallback_used"] is False
    assert payload["metadata"]["answer_quality"]["status"] == "issues_found"
    assert payload["metadata"]["answer_quality"]["revision_recommended"] is True
    assert payload["metadata"]["answer_quality"]["revision_triggered"] is False
    assert payload["metadata"]["answer_quality"]["revision_count"] == 0
    assert payload["metadata"]["answer_quality"]["findings"][0]["category"] == "source_attribution"
    assert payload["metadata"]["steps"] == [
        {
            "name": "retrieve_evidence",
            "status": "ok",
            "duration_ms": 1.25,
            "detail": {"selected_pass": "initial", "result_count": 1},
        }
    ]


def test_agent_stream_endpoint_returns_sse_events(tmp_path, monkeypatch):
    from fastapi import FastAPI
    import app.api.agent as agent_api

    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))

    async def fake_stream_agent_query(workflow_input):
        assert workflow_input.query == "클라우드 전환 전략"
        yield {"sources": [{"file": "manual.pdf", "page": 3, "section": "개요", "score": 0.91}]}
        yield {"token": "생성된 "}
        yield {"token": "답변"}
        yield {
            "metadata": {
                "framework": "langgraph",
                "graph_version": "agent-query-v1",
                "graph_run_id": "run-stream",
                "project_id": "project-proposal-default",
                "project_slug": "proposal-default",
                "collection_name": "proposals",
                "selected_pass": "initial",
                "retry_triggered": False,
                "fallback_used": False,
                "answer_quality": {
                    "status": "passed",
                    "findings": [],
                    "coverage": [],
                    "evidence_sufficiency": {"available": True, "sufficient": True},
                    "revision_recommended": False,
                    "revision_triggered": False,
                    "revision_count": 0,
                },
                "steps": [],
            }
        }

    monkeypatch.setattr(agent_api, "stream_agent_query", fake_stream_agent_query)
    test_app = FastAPI()
    test_app.include_router(agent_router, prefix="/api")
    client = TestClient(test_app)

    response = client.post(
        "/api/agent/stream",
        headers=_headers(),
        json={"query": "클라우드 전환 전략"},
    )

    assert response.status_code == 200
    body = response.text
    assert 'data: {"sources":' in body
    assert 'data: {"token": "생성된 "}' in body
    assert 'data: {"token": "답변"}' in body
    assert 'data: {"metadata":' in body
    assert "data: [DONE]" in body


def test_agent_query_uses_project_rag_config_and_user_department_scope(tmp_path, monkeypatch):
    from fastapi import FastAPI
    import app.api.agent as agent_api

    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    project = create_project(
        ProjectCreateRequest(
            slug="manual-qa",
            name="매뉴얼 QA",
            description="운영 매뉴얼 질의응답",
            plugins=[],
            rag_config=ProjectRagConfig(
                collection_name="manual-docs",
                top_k_default=17,
                top_n_default=4,
                prompt_profile="manual",
                storage_namespace="manual-qa",
            ),
        )
    )

    async def fake_run_agent_query(workflow_input):
        assert workflow_input.project_id == project.id
        assert workflow_input.project_slug == "manual-qa"
        assert workflow_input.collection_name == "manual-docs"
        assert workflow_input.top_k == 17
        assert workflow_input.top_n == 4
        assert workflow_input.department == "공공사업팀"
        return AgentWorkflowResult(
            answer="프로젝트 답변",
            sources=[],
            found=False,
            graph_run_id="run-project",
        )

    monkeypatch.setattr(agent_api, "run_agent_query", fake_run_agent_query)
    test_app = FastAPI()
    test_app.include_router(agent_router, prefix="/api")
    client = TestClient(test_app)

    response = client.post(
        "/api/agent/query",
        headers=_headers("user1", "공공사업팀", False),
        json={
            "query": "운영 매뉴얼",
            "project_id": project.id,
            "department": "다른부서",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["project_id"] == project.id
    assert payload["metadata"]["project_slug"] == "manual-qa"
    assert payload["metadata"]["collection_name"] == "manual-docs"


def test_build_graph_reports_clear_error_when_langgraph_is_missing(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "langgraph.graph":
            raise ImportError("No module named langgraph")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(workflow.HTTPException) as exc_info:
        workflow._build_graph()

    assert exc_info.value.status_code == 503
    assert "langgraph is not installed" in exc_info.value.detail


def test_graph_nodes_return_no_results_without_generation(monkeypatch):
    async def fake_ensure_collection(collection_name):
        return None

    async def fake_retrieve_with_critic(*args, **kwargs):
        return _critic_result([])

    async def fake_generate(*args, **kwargs):
        raise AssertionError("generate should not be called without evidence")

    monkeypatch.setattr(workflow, "ensure_collection", fake_ensure_collection)
    monkeypatch.setattr(workflow, "retrieve_with_critic", fake_retrieve_with_critic)
    monkeypatch.setattr(workflow, "generate", fake_generate)

    state = {
        "query": "없는 근거",
        "department": None,
        "collection_name": "test-docs",
        "top_k": 20,
        "top_n": 5,
        "graph_run_id": str(uuid4()),
        "project_id": "project-test",
        "project_slug": "test",
        "steps": [],
    }

    async def run_nodes():
        prepared = await workflow._prepare_context(state)
        state.update(prepared)
        retrieved = await workflow._retrieve_evidence(state)
        state.update(retrieved)
        assert workflow._route_after_retrieval(state) == "finalize_response"
        finalized = await workflow._finalize_response(state)
        state.update(finalized)

    asyncio.run(run_nodes())

    assert state["found"] is False
    assert state["answer"] == workflow.NO_RESULTS_MESSAGE
    assert state["sources"] == []
    assert [step.name for step in state["steps"]] == [
        "prepare_context",
        "retrieve_evidence",
        "finalize_response",
    ]


def test_graph_nodes_generate_answer_with_trace_metadata(monkeypatch):
    chunks = [_chunk("클라우드 전환 전략과 보안 이행계획", 0.91)]

    async def fake_ensure_collection(collection_name):
        return None

    async def fake_retrieve_with_critic(*args, **kwargs):
        return _critic_result(chunks)

    async def fake_generate(query, evidence):
        assert evidence == chunks
        return "생성된 답변"

    monkeypatch.setattr(workflow, "ensure_collection", fake_ensure_collection)
    monkeypatch.setattr(workflow, "retrieve_with_critic", fake_retrieve_with_critic)
    monkeypatch.setattr(workflow, "generate", fake_generate)

    state = {
        "query": "클라우드 전환 전략",
        "department": "공공사업팀",
        "collection_name": "test-docs",
        "top_k": 20,
        "top_n": 5,
        "graph_run_id": str(uuid4()),
        "project_id": "project-test",
        "project_slug": "test",
        "steps": [],
    }

    async def run_nodes():
        prepared = await workflow._prepare_context(state)
        state.update(prepared)
        retrieved = await workflow._retrieve_evidence(state)
        state.update(retrieved)
        assert workflow._route_after_retrieval(state) == "generate_answer"
        generated = await workflow._generate_answer(state)
        state.update(generated)
        reviewed = await workflow._review_answer_quality(state)
        state.update(reviewed)
        finalized = await workflow._finalize_response(state)
        state.update(finalized)

    asyncio.run(run_nodes())

    assert state["found"] is True
    assert state["answer"] == "생성된 답변"
    assert state["sources"][0].file == "manual.pdf"
    assert state["critic_result"].selected.name == "initial"
    assert [step.name for step in state["steps"]] == [
        "prepare_context",
        "retrieve_evidence",
        "generate_answer",
        "review_answer_quality",
        "finalize_response",
    ]
    assert state["steps"][1].detail["selected_pass"] == "initial"
    assert state["answer_quality"].status == "issues_found"
    assert state["answer_quality"].revision_recommended is True
    assert state["answer_quality"].revision_triggered is False
    assert state["answer_quality"].revision_count == 0
    assert state["answer"] == "생성된 답변"


def test_agent_stream_reviews_accumulated_answer_and_preserves_tokens(monkeypatch):
    chunks = [_chunk("보안과 DR 근거", 0.91)]

    async def fake_ensure_collection(collection_name):
        return None

    async def fake_retrieve_with_critic(*args, **kwargs):
        return _critic_result(chunks)

    async def fake_generate_tokens(query, evidence):
        assert evidence == chunks
        yield "보안 "
        yield "답변"

    monkeypatch.setattr(workflow, "ensure_collection", fake_ensure_collection)
    monkeypatch.setattr(workflow, "retrieve_with_critic", fake_retrieve_with_critic)
    monkeypatch.setattr(workflow, "generate_tokens", fake_generate_tokens)

    async def collect_events():
        return [
            event
            async for event in workflow.stream_agent_query(
                workflow.AgentWorkflowInput(
                    query="보안과 DR 전략",
                    department=None,
                    collection_name="test-docs",
                    top_k=20,
                    top_n=5,
                    project_id="project-test",
                    project_slug="test",
                )
            )
        ]

    events = asyncio.run(collect_events())

    assert events[0]["sources"][0].file == "manual.pdf"
    assert [event["token"] for event in events if "token" in event] == ["보안 ", "답변"]
    metadata = events[-1]["metadata"]
    answer_quality = metadata["answer_quality"]
    assert answer_quality["status"] == "issues_found"
    assert answer_quality["revision_triggered"] is False
    assert answer_quality["revision_count"] == 0
    assert "review_answer_quality" in [step.name for step in metadata["steps"]]
    assert answer_quality["coverage"] == [
        {
            "item": "보안",
            "status": "covered",
            "requested_aliases": ["보안"],
            "answer_aliases": ["보안"],
            "revision_recommended": False,
        },
        {
            "item": "DR",
            "status": "missing",
            "requested_aliases": ["DR"],
            "answer_aliases": [],
            "revision_recommended": True,
        },
    ]


def test_answer_quality_marks_requested_item_unavailable():
    report = workflow.review_answer_quality(
        query="보안과 DR 전략",
        answer="보안은 확인됩니다. DR은 문서에서 확인되지 않음.",
        chunks=[_chunk("보안 근거", 0.91)],
        critic_result=_critic_result([_chunk("보안 근거", 0.91)]),
    )

    assert report.coverage == [
        {
            "item": "보안",
            "status": "covered",
            "requested_aliases": ["보안"],
            "answer_aliases": ["보안"],
            "revision_recommended": False,
        },
        {
            "item": "DR",
            "status": "unavailable",
            "requested_aliases": ["DR"],
            "answer_aliases": ["DR"],
            "revision_recommended": False,
        },
    ]
    assert report.revision_triggered is False
    assert report.revision_count == 0
    assert report.evidence_sufficiency["claim_support"]["weak_count"] == 0


def test_answer_quality_flags_weakly_supported_claims():
    report = workflow.review_answer_quality(
        query="보안 전략",
        answer="보안은 암호화 정책을 포함합니다. 위성 통신 계약은 10년입니다.",
        chunks=[_chunk("보안 암호화 정책 근거", 0.91)],
        critic_result=_critic_result([_chunk("보안 암호화 정책 근거", 0.91)]),
    )

    finding = next(
        item for item in report.findings if item.category == "evidence_attribution"
    )
    assert finding.severity == "warning"
    assert finding.detail["weak_claim_count"] == 1
    assert finding.detail["weak_claims"][0]["text"] == "위성 통신 계약은 10년입니다."
    assert report.evidence_sufficiency["claim_support"] == {
        "reviewed_count": 2,
        "weak_count": 1,
        "weak_claims": [
            {
                "text": "위성 통신 계약은 10년입니다.",
                "terms": ["10년입니다", "계약", "계약은", "위성", "통신"],
            }
        ],
    }
    assert report.revision_recommended is True
    assert report.revision_triggered is False
    assert report.revision_count == 0
