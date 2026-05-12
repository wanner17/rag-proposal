from __future__ import annotations

from dataclasses import dataclass, field
import re
from statistics import mean
from typing import Sequence


@dataclass(frozen=True)
class CriticDecision:
    sufficient: bool
    retry_triggered: bool
    trigger_reasons: list[str]
    selected_pass: str
    sufficiency_score: float
    result_count: int
    mean_score: float
    semantic_coverage: float


@dataclass(frozen=True)
class RetryPlan:
    top_k: int
    top_n: int
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CriticPass:
    name: str
    candidates: list[dict]
    reranked: list[dict]
    decision: CriticDecision


@dataclass(frozen=True)
class CriticResult:
    selected: CriticPass
    initial: CriticPass
    retry: CriticPass | None = None


def assess_retrieval(
    query: str,
    reranked: Sequence[dict],
    *,
    requested_top_n: int,
    retry_triggered: bool,
    selected_pass: str,
) -> CriticDecision:
    result_count = len(reranked)
    scores = [_score(chunk) for chunk in reranked if _score(chunk) is not None]
    mean_score = mean(scores) if scores else 0.0
    semantic_coverage = _semantic_coverage(query, reranked)

    reasons: list[str] = []
    if result_count < max(1, min(requested_top_n, 3)):
        reasons.append("insufficient_result_count")
    if mean_score < 0.55:
        reasons.append("low_mean_score")
    if semantic_coverage < 0.2 and mean_score < 0.8:
        reasons.append("low_semantic_coverage")

    normalized_count = min(result_count / max(requested_top_n, 1), 1.0)
    sufficiency_score = round(
        normalized_count * 0.35 + min(mean_score, 1.0) * 0.35 + semantic_coverage * 0.30,
        4,
    )
    sufficient = not reasons or sufficiency_score >= 0.67

    return CriticDecision(
        sufficient=sufficient,
        retry_triggered=retry_triggered,
        trigger_reasons=reasons,
        selected_pass=selected_pass,
        sufficiency_score=sufficiency_score,
        result_count=result_count,
        mean_score=round(mean_score, 4),
        semantic_coverage=round(semantic_coverage, 4),
    )


def build_retry_plan(top_k: int, top_n: int, reasons: Sequence[str]) -> RetryPlan:
    expanded_top_k = min(max(top_k + 8, int(top_k * 1.5)), 50)
    expanded_top_n = min(max(top_n, min(top_n + 2, 10)), 10)
    return RetryPlan(
        top_k=expanded_top_k,
        top_n=expanded_top_n,
        reason_codes=list(reasons),
    )


def select_best_pass(initial: CriticPass, retry: CriticPass) -> CriticPass:
    if retry.decision.sufficiency_score > initial.decision.sufficiency_score + 0.03:
        return retry
    if retry.decision.sufficient and not initial.decision.sufficient:
        return retry
    return initial


def _score(chunk: dict) -> float | None:
    value = chunk.get("rerank_score")
    if value is None:
        value = chunk.get("score")
    return float(value) if isinstance(value, (int, float)) else None


def _semantic_coverage(query: str, reranked: Sequence[dict]) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 1.0
    chunk_terms: set[str] = set()
    for chunk in reranked:
        chunk_terms.update(_terms(str(chunk.get("text", ""))))
    if not chunk_terms:
        return 0.0
    return len(query_terms & chunk_terms) / len(query_terms)


def _terms(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[0-9A-Za-z가-힣]{2,}", text)}
