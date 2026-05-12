import asyncio

from app.services import retrieval
from app.services.retrieval_critic import (
    CriticPass,
    assess_retrieval,
    build_retry_plan,
    select_best_pass,
)


def _chunk(text: str, score: float):
    return {
        "text": text,
        "score": score,
        "rerank_score": score,
    }


def test_critic_accepts_strong_evidence():
    decision = assess_retrieval(
        "클라우드 전환 보안 전략",
        [
            _chunk("클라우드 전환 보안 전략과 단계별 이행계획", 0.92),
            _chunk("보안 통제와 전환 리스크 대응", 0.88),
            _chunk("클라우드 운영전략", 0.86),
        ],
        requested_top_n=3,
        retry_triggered=False,
        selected_pass="initial",
    )

    assert decision.sufficient is True
    assert decision.retry_triggered is False
    assert decision.trigger_reasons == []


def test_critic_retries_weak_evidence_and_prefers_better_retry(monkeypatch):
    calls = []

    async def fake_retrieve_with_metadata(query, department, top_k=20, top_n=5, collection_name=None):
        calls.append((top_k, top_n))
        if len(calls) == 1:
            return [_chunk("무관한 텍스트", 0.31)], [_chunk("무관한 텍스트", 0.31)]
        return (
            [_chunk("클라우드 전환 보안 전략", 0.91)],
            [_chunk("클라우드 전환 보안 전략", 0.91)],
        )

    monkeypatch.setattr(retrieval, "retrieve_with_metadata", fake_retrieve_with_metadata)

    result = asyncio.run(retrieval.retrieve_with_critic("클라우드 전환 보안 전략", "공공사업팀"))

    assert calls == [(20, 5), (30, 7)]
    assert result.retry is not None
    assert result.selected.name == "retry"
    assert result.initial.decision.retry_triggered is False
    assert result.retry.decision.retry_triggered is True


def test_retry_plan_caps_parameters():
    plan = build_retry_plan(48, 9, ["low_mean_score"])
    assert plan.top_k == 50
    assert plan.top_n == 10


def test_select_best_pass_keeps_original_when_retry_not_better():
    initial_decision = assess_retrieval(
        "질문",
        [_chunk("질문 관련 근거", 0.8)],
        requested_top_n=1,
        retry_triggered=False,
        selected_pass="initial",
    )
    retry_decision = assess_retrieval(
        "질문",
        [_chunk("질문 관련 근거", 0.79)],
        requested_top_n=1,
        retry_triggered=True,
        selected_pass="retry",
    )
    initial = CriticPass("initial", [], [_chunk("질문 관련 근거", 0.8)], initial_decision)
    retry = CriticPass("retry", [], [_chunk("질문 관련 근거", 0.79)], retry_decision)

    assert select_best_pass(initial, retry).name == "initial"
