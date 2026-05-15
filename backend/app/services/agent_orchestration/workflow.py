from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from time import perf_counter
from typing import Any, AsyncGenerator, NotRequired, TypedDict
from uuid import uuid4

from fastapi import HTTPException, status

from app.models.schemas import DocumentSource, Source, SourceCodeSource
from app.services.agent_orchestration.answer_quality import review_answer_quality
from app.services.agent_orchestration.contamination_detector import detect_contamination
from app.services.agent_orchestration.question_classifier import QuestionType, classify_question
from app.services.agent_orchestration.retrieval_planner import RetrievalPlan, build_retrieval_plan
from app.services.agent_orchestration.types import (
    AnswerQualityReport,
    AgentWorkflowInput,
    AgentWorkflowResult,
    AgentWorkflowTraceStep,
)
from app.services.llm import generate, generate_tokens, get_retrieval_config
from app.services.retrieval import ensure_collection, retrieve_with_critic
from app.services.retrieval_critic import CriticResult

logger = logging.getLogger(__name__)

NO_RESULTS_MESSAGE = "관련 문서를 찾지 못했습니다."


class _AgentGraphState(TypedDict):
    query: str
    department: str | None
    retrieval_scope: str
    collection_name: str
    top_k: int
    top_n: int
    graph_run_id: str
    project_id: str
    project_slug: str
    conversation_history: list[dict]
    score_threshold: NotRequired[float | None]
    answer: NotRequired[str]
    found: NotRequired[bool]
    sources: NotRequired[list[Source]]
    chunks: NotRequired[list[dict]]
    critic_result: NotRequired[CriticResult]
    answer_quality: NotRequired[AnswerQualityReport]
    steps: list[AgentWorkflowTraceStep]
    # Phase 3: agentic retrieval fields
    question_type: NotRequired[str]
    retrieval_plan: NotRequired[RetrievalPlan | None]
    retry_count: NotRequired[int]
    max_retries: NotRequired[int]
    retry_reason: NotRequired[list[str]]
    should_retry: NotRequired[bool]


async def run_agent_query(workflow_input: AgentWorkflowInput) -> AgentWorkflowResult:
    graph = _build_graph()
    initial_state: _AgentGraphState = {
        "query": workflow_input.query,
        "department": workflow_input.department,
        "retrieval_scope": workflow_input.retrieval_scope,
        "collection_name": workflow_input.collection_name,
        "top_k": workflow_input.top_k,
        "top_n": workflow_input.top_n,
        "graph_run_id": str(uuid4()),
        "project_id": workflow_input.project_id,
        "project_slug": workflow_input.project_slug,
        "conversation_history": list(workflow_input.conversation_history),
        "steps": [],
    }
    state = await asyncio.wait_for(graph.ainvoke(initial_state), timeout=60.0)
    critic_result = state.get("critic_result")
    selected_pass = critic_result.selected.name if critic_result else None
    retry_triggered = bool(critic_result and critic_result.retry is not None)
    return AgentWorkflowResult(
        answer=state.get("answer", NO_RESULTS_MESSAGE),
        sources=state.get("sources", []),
        found=state.get("found", False),
        graph_run_id=state["graph_run_id"],
        selected_pass=selected_pass,
        retry_triggered=retry_triggered,
        steps=state["steps"],
        critic_result=critic_result,
        answer_quality=state.get("answer_quality"),
    )


async def stream_agent_query(
    workflow_input: AgentWorkflowInput,
) -> AsyncGenerator[dict[str, Any], None]:
    state: _AgentGraphState = {
        "query": workflow_input.query,
        "department": workflow_input.department,
        "retrieval_scope": workflow_input.retrieval_scope,
        "collection_name": workflow_input.collection_name,
        "top_k": workflow_input.top_k,
        "top_n": workflow_input.top_n,
        "graph_run_id": str(uuid4()),
        "project_id": workflow_input.project_id,
        "project_slug": workflow_input.project_slug,
        "conversation_history": list(workflow_input.conversation_history),
        "steps": [],
    }

    yield {"step_start": {"name": "classify_question", "index": 0}}
    t = perf_counter()
    state.update(await _classify_question(state))
    yield {"step_end": {"name": "classify_question", "index": 0, "duration_ms": round((perf_counter() - t) * 1000, 1)}}

    yield {"step_start": {"name": "prepare_context", "index": 1}}
    t = perf_counter()
    state.update(await _prepare_context(state))
    yield {"step_end": {"name": "prepare_context", "index": 1, "duration_ms": round((perf_counter() - t) * 1000, 1)}}

    yield {"step_start": {"name": "plan_retrieval", "index": 2}}
    t = perf_counter()
    state.update(await _plan_retrieval(state))
    yield {"step_end": {"name": "plan_retrieval", "index": 2, "duration_ms": round((perf_counter() - t) * 1000, 1)}}

    # Retrieval + validation retry loop
    retrieve_index = 3
    while True:
        yield {"step_start": {"name": "retrieve_evidence", "index": retrieve_index}}
        t = perf_counter()
        state.update(await _retrieve_evidence(state))
        yield {"step_end": {"name": "retrieve_evidence", "index": retrieve_index, "duration_ms": round((perf_counter() - t) * 1000, 1)}}

        yield {"step_start": {"name": "validate_retrieval", "index": retrieve_index + 1}}
        t = perf_counter()
        state.update(await _validate_retrieval(state))
        yield {"step_end": {"name": "validate_retrieval", "index": retrieve_index + 1, "duration_ms": round((perf_counter() - t) * 1000, 1)}}

        if state.get("should_retry"):
            yield {"step_start": {"name": "replan_retrieval", "index": retrieve_index + 2}}
            t = perf_counter()
            state.update(await _replan_retrieval(state))
            yield {"step_end": {"name": "replan_retrieval", "index": retrieve_index + 2, "duration_ms": round((perf_counter() - t) * 1000, 1)}}
            retrieve_index += 3
            continue
        break

    chunks = state.get("chunks", [])
    if not chunks:
        yield {"step_start": {"name": "finalize_response", "index": retrieve_index + 2}}
        t = perf_counter()
        state.update(await _finalize_response(state))
        yield {"step_end": {"name": "finalize_response", "index": retrieve_index + 2, "duration_ms": round((perf_counter() - t) * 1000, 1)}}
        yield {"sources": []}
        yield {"token": state["answer"]}
        yield {"metadata": _metadata_from_state(state)}
        return

    sources = [_source_from_chunk(chunk) for chunk in chunks]
    yield {"sources": sources}

    gen_index = retrieve_index + 2
    yield {"step_start": {"name": "generate_answer", "index": gen_index}}
    started = perf_counter()
    tokens: list[str] = []
    async for token in generate_tokens(state["query"], chunks, history=state.get("conversation_history")):
        tokens.append(token)
        yield {"token": token}
    gen_duration = round((perf_counter() - started) * 1000, 1)
    state.update(
        {
            "answer": "".join(tokens),
            "sources": sources,
            "found": True,
            "steps": state["steps"]
            + [_step("generate_answer", started, source_count=len(sources), streamed=True)],
        }
    )
    yield {"step_end": {"name": "generate_answer", "index": gen_index, "duration_ms": gen_duration}}

    yield {"step_start": {"name": "review_answer_quality", "index": gen_index + 1}}
    t = perf_counter()
    state.update(await _review_answer_quality(state))
    yield {"step_end": {"name": "review_answer_quality", "index": gen_index + 1, "duration_ms": round((perf_counter() - t) * 1000, 1)}}

    yield {"step_start": {"name": "finalize_response", "index": gen_index + 2}}
    t = perf_counter()
    state.update(await _finalize_response(state))
    yield {"step_end": {"name": "finalize_response", "index": gen_index + 2, "duration_ms": round((perf_counter() - t) * 1000, 1)}}

    yield {"metadata": _metadata_from_state(state)}


def _build_graph():
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent orchestration is enabled but langgraph is not installed.",
        ) from exc

    graph = StateGraph(_AgentGraphState)
    graph.add_node("classify_question", _classify_question)
    graph.add_node("prepare_context", _prepare_context)
    graph.add_node("plan_retrieval", _plan_retrieval)
    graph.add_node("retrieve_evidence", _retrieve_evidence)
    graph.add_node("validate_retrieval", _validate_retrieval)
    graph.add_node("replan_retrieval", _replan_retrieval)
    graph.add_node("generate_answer", _generate_answer)
    graph.add_node("review_answer_quality", _review_answer_quality)
    graph.add_node("finalize_response", _finalize_response)
    graph.set_entry_point("classify_question")
    graph.add_edge("classify_question", "prepare_context")
    graph.add_edge("prepare_context", "plan_retrieval")
    graph.add_edge("plan_retrieval", "retrieve_evidence")
    graph.add_edge("retrieve_evidence", "validate_retrieval")
    graph.add_conditional_edges(
        "validate_retrieval",
        _route_after_validation,
        {
            "replan_retrieval": "replan_retrieval",
            "generate_answer": "generate_answer",
            "finalize_response": "finalize_response",
        },
    )
    graph.add_edge("replan_retrieval", "retrieve_evidence")
    graph.add_edge("generate_answer", "review_answer_quality")
    graph.add_edge("review_answer_quality", "finalize_response")
    graph.add_edge("finalize_response", END)
    return graph.compile()


async def _classify_question(state: _AgentGraphState) -> dict[str, Any]:
    started = perf_counter()
    q_type = classify_question(state["query"])
    step = _step("classify_question", started, question_type=q_type.value)
    logger.info("agent graph classified run=%s type=%s", state["graph_run_id"], q_type.value)
    return {"question_type": q_type.value, "steps": state["steps"] + [step]}


async def _plan_retrieval(state: _AgentGraphState) -> dict[str, Any]:
    started = perf_counter()
    q_type = QuestionType(state.get("question_type", QuestionType.GENERAL))
    plan = build_retrieval_plan(q_type)
    step = _step("plan_retrieval", started, question_type=q_type.value, top_k=plan.top_k, top_n=plan.top_n)
    return {
        "retrieval_plan": plan,
        "top_k": plan.top_k,
        "top_n": plan.top_n,
        "score_threshold": plan.score_threshold,
        "retry_count": 0,
        "max_retries": 3,
        "should_retry": False,
        "retry_reason": [],
        "steps": state["steps"] + [step],
    }


async def _validate_retrieval(state: _AgentGraphState) -> dict[str, Any]:
    started = perf_counter()
    chunks = state.get("chunks", [])
    contamination = detect_contamination(chunks)
    critic_result = state.get("critic_result")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    issues: list[str] = []
    if contamination.is_contaminated:
        issues.append("frontend_contamination")
    if critic_result and not critic_result.selected.decision.sufficient:
        issues.append("insufficient_evidence")

    should_retry = bool(issues) and retry_count < max_retries
    step = _step(
        "validate_retrieval",
        started,
        contamination_ratio=round(contamination.contamination_ratio, 2),
        issues=issues,
        should_retry=should_retry,
        retry_count=retry_count,
    )
    logger.info(
        "agent graph validated run=%s issues=%s retry=%s count=%s/%s",
        state["graph_run_id"], issues, should_retry, retry_count, max_retries,
    )
    return {
        "should_retry": should_retry,
        "retry_reason": issues,
        "steps": state["steps"] + [step],
    }


async def _replan_retrieval(state: _AgentGraphState) -> dict[str, Any]:
    started = perf_counter()
    reasons = state.get("retry_reason", [])
    retry_count = state.get("retry_count", 0)
    top_k = state["top_k"]
    top_n = state["top_n"]
    threshold = state.get("score_threshold") or 0.4

    if "insufficient_evidence" in reasons:
        top_k = min(top_k * 2, 60)
        top_n = min(top_n + 2, 12)
        threshold = max(threshold - 0.05, 0.2)

    step = _step(
        "replan_retrieval",
        started,
        reasons=reasons,
        new_top_k=top_k,
        new_top_n=top_n,
        retry_count=retry_count + 1,
    )
    return {
        "top_k": top_k,
        "top_n": top_n,
        "score_threshold": threshold,
        "retry_count": retry_count + 1,
        "should_retry": False,
        "steps": state["steps"] + [step],
    }


def _route_after_validation(state: _AgentGraphState) -> str:
    if state.get("should_retry"):
        return "replan_retrieval"
    return "generate_answer" if state.get("chunks") else "finalize_response"


async def _prepare_context(state: _AgentGraphState) -> dict[str, Any]:
    started = perf_counter()
    await ensure_collection(state["collection_name"])
    retrieval_config = get_retrieval_config(state["query"])
    step = _step(
        "prepare_context",
        started,
        collection_name=state["collection_name"],
        project_id=state["project_id"],
        project_slug=state["project_slug"],
        retrieval_intent=retrieval_config,
    )
    logger.info(
        "agent graph prepared run=%s project=%s collection=%s intent_top_k=%s",
        state["graph_run_id"],
        state["project_id"],
        state["collection_name"],
        retrieval_config["top_k"],
    )
    return {
        "top_k": retrieval_config["top_k"],
        "top_n": retrieval_config["rerank_top_n"],
        "score_threshold": retrieval_config["score_threshold"],
        "steps": state["steps"] + [step],
    }


async def _retrieve_evidence(state: _AgentGraphState) -> dict[str, Any]:
    started = perf_counter()
    critic_result = await retrieve_with_critic(
        state["query"],
        department=state["department"],
        top_k=state["top_k"],
        top_n=state["top_n"],
        collection_name=state["collection_name"],
        retrieval_scope=state["retrieval_scope"],
        project_slug=state["project_slug"],
        score_threshold=state.get("score_threshold"),
    )
    chunks = critic_result.selected.reranked
    decision = critic_result.selected.decision
    step = _step(
        "retrieve_evidence",
        started,
        selected_pass=critic_result.selected.name,
        retry_triggered=critic_result.retry is not None,
        result_count=len(chunks),
        sufficiency_score=decision.sufficiency_score,
        trigger_reasons=decision.trigger_reasons,
    )
    logger.info(
        "agent graph retrieved run=%s selected_pass=%s retry=%s result_count=%s",
        state["graph_run_id"],
        critic_result.selected.name,
        critic_result.retry is not None,
        len(chunks),
    )
    return {
        "critic_result": critic_result,
        "chunks": chunks,
        "found": bool(chunks),
        "steps": state["steps"] + [step],
    }


async def _generate_answer(state: _AgentGraphState) -> dict[str, Any]:
    started = perf_counter()
    chunks = state.get("chunks", [])
    answer = await generate(state["query"], chunks, history=state.get("conversation_history"))
    sources = [_source_from_chunk(chunk) for chunk in chunks]
    step = _step("generate_answer", started, source_count=len(sources))
    return {
        "answer": answer,
        "sources": sources,
        "found": True,
        "steps": state["steps"] + [step],
    }


async def _review_answer_quality(state: _AgentGraphState) -> dict[str, Any]:
    started = perf_counter()
    report = review_answer_quality(
        query=state["query"],
        answer=state.get("answer", ""),
        chunks=state.get("chunks", []),
        critic_result=state.get("critic_result"),
    )
    step = _step(
        "review_answer_quality",
        started,
        status=report.status,
        finding_count=len(report.findings),
        revision_recommended=report.revision_recommended,
        revision_triggered=report.revision_triggered,
        revision_count=report.revision_count,
    )
    return {
        "answer_quality": report,
        "steps": state["steps"] + [step],
    }


async def _finalize_response(state: _AgentGraphState) -> dict[str, Any]:
    started = perf_counter()
    found = state.get("found", False)
    update: dict[str, Any] = {"found": found}
    if not found:
        update["answer"] = NO_RESULTS_MESSAGE
        update["sources"] = []
    update["steps"] = state["steps"] + [_step("finalize_response", started, found=found)]
    return update


def _route_after_retrieval(state: _AgentGraphState) -> str:
    return "generate_answer" if state.get("chunks") else "finalize_response"


def _source_from_chunk(chunk: dict) -> Source:
    if chunk.get("source_kind") == "source_code":
        return SourceCodeSource(
            project_slug=chunk.get("project_slug", ""),
            relative_path=chunk.get("relative_path", ""),
            language=chunk.get("language", ""),
            start_line=int(chunk.get("start_line") or 0),
            end_line=int(chunk.get("end_line") or 0),
            score=float(chunk.get("score") or 0.0),
            score_source=chunk.get("score_source", "retrieval"),
        )
    return DocumentSource(
        file=chunk.get("file", ""),
        page=chunk.get("page", 0),
        section=chunk.get("section", ""),
        score=float(chunk.get("score") or 0.0),
        score_source=chunk.get("score_source", "retrieval"),
    )


def _step(name: str, started: float, **detail: Any) -> AgentWorkflowTraceStep:
    return AgentWorkflowTraceStep(
        name=name,
        duration_ms=round((perf_counter() - started) * 1000, 3),
        detail=detail,
    )


def _metadata_from_state(state: _AgentGraphState) -> dict[str, Any]:
    critic_result = state.get("critic_result")
    selected_pass = critic_result.selected.name if critic_result else None
    retry_triggered = bool(critic_result and critic_result.retry is not None)
    return {
        "framework": "langgraph",
        "graph_version": "agent-query-v1",
        "graph_run_id": state["graph_run_id"],
        "project_id": state["project_id"],
        "project_slug": state["project_slug"],
        "collection_name": state["collection_name"],
        "selected_pass": selected_pass,
        "retry_triggered": retry_triggered,
        "fallback_used": False,
        "steps": state["steps"],
        "answer_quality": _answer_quality_metadata(state.get("answer_quality")),
    }


def _answer_quality_metadata(report: AnswerQualityReport | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return asdict(report)
