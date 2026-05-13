from __future__ import annotations

import re

from app.services.agent_orchestration.types import (
    AnswerQualityFinding,
    AnswerQualityReport,
)
from app.services.retrieval_critic import CriticResult


REQUESTED_ITEM_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("보안", ("보안",)),
    ("DR", ("DR", "재해 복구", "재해복구")),
    ("단계별 이행계획", ("단계별 이행계획", "단계별", "이행계획")),
    ("운영 조직", ("운영 조직", "운영조직")),
    ("장애 대응", ("장애 대응", "장애대응", "장애")),
)

_CLAIM_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
_TERM_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")
_UNAVAILABLE_MARKERS = ("확인되지 않음", "찾지 못", "없습니다")
_PARTICLE_SUFFIXES = (
    "에서",
    "으로",
    "부터",
    "까지",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "과",
    "와",
    "의",
    "에",
    "로",
    "도",
    "만",
)


def review_answer_quality(
    *,
    query: str,
    answer: str,
    chunks: list[dict],
    critic_result: CriticResult | None,
) -> AnswerQualityReport:
    findings: list[AnswerQualityFinding] = []
    coverage = _coverage(query, answer)
    evidence_sufficiency = _evidence_sufficiency(chunks, critic_result)
    claim_support = _claim_support(answer, chunks)
    evidence_sufficiency["claim_support"] = claim_support

    if not answer.strip():
        findings.append(
            AnswerQualityFinding(
                category="output_completeness",
                severity="error",
                message="답변이 비어 있습니다.",
            )
        )

    if chunks and not _has_source_marker(answer):
        findings.append(
            AnswerQualityFinding(
                category="source_attribution",
                severity="warning",
                message="답변에 명시적인 출처 표시가 부족할 수 있습니다.",
            )
        )

    missing_items = [item for item in coverage if item["status"] == "missing"]
    if missing_items:
        findings.append(
            AnswerQualityFinding(
                category="requirement_coverage",
                severity="warning",
                message="질문에서 요구한 일부 항목이 답변에 명시적으로 포함되지 않았습니다.",
                detail={"missing_items": [item["item"] for item in missing_items]},
            )
        )

    if claim_support["weak_count"]:
        findings.append(
            AnswerQualityFinding(
                category="evidence_attribution",
                severity="warning",
                message="일부 답변 문장이 검색 근거와 약하게 연결되어 있습니다.",
                detail={
                    "weak_claim_count": claim_support["weak_count"],
                    "weak_claims": claim_support["weak_claims"],
                },
            )
        )

    if evidence_sufficiency.get("sufficient") is False:
        findings.append(
            AnswerQualityFinding(
                category="evidence_sufficiency",
                severity="warning",
                message="검색 근거 충분성 점수가 낮거나 재검색 트리거 사유가 있습니다.",
                detail={
                    "sufficiency_score": evidence_sufficiency.get("sufficiency_score"),
                    "trigger_reasons": evidence_sufficiency.get("trigger_reasons", []),
                },
            )
        )

    return AnswerQualityReport(
        status="issues_found" if findings else "passed",
        findings=findings,
        coverage=coverage,
        evidence_sufficiency=evidence_sufficiency,
        revision_recommended=bool(findings),
        revision_triggered=False,
        revision_count=0,
    )


def _coverage(query: str, answer: str) -> list[dict]:
    normalized_query = query.lower()
    normalized_answer = answer.lower()
    coverage: list[dict] = []
    for item, aliases in REQUESTED_ITEM_ALIASES:
        requested_aliases = [alias for alias in aliases if alias.lower() in normalized_query]
        if not requested_aliases:
            continue
        answer_aliases = [alias for alias in aliases if alias.lower() in normalized_answer]
        answer_has_item = bool(answer_aliases)
        unavailable = item in answer and any(marker in answer for marker in _UNAVAILABLE_MARKERS)
        status = "unavailable" if unavailable else "covered" if answer_has_item else "missing"
        coverage.append(
            {
                "item": item,
                "status": status,
                "requested_aliases": requested_aliases,
                "answer_aliases": answer_aliases,
                "revision_recommended": status == "missing",
            }
        )
    return coverage


def _claim_support(answer: str, chunks: list[dict]) -> dict:
    claims = _answer_claims(answer)
    if not chunks:
        return {"reviewed_count": len(claims), "weak_count": 0, "weak_claims": []}

    evidence_terms = _evidence_terms(chunks)
    weak_claims: list[dict] = []
    for claim in claims:
        terms = _terms(claim)
        if terms and not evidence_terms.intersection(terms):
            weak_claims.append({"text": claim, "terms": sorted(terms)[:8]})

    return {
        "reviewed_count": len(claims),
        "weak_count": len(weak_claims),
        "weak_claims": weak_claims,
    }


def _answer_claims(answer: str) -> list[str]:
    claims: list[str] = []
    for raw_claim in _CLAIM_SPLIT_RE.split(answer):
        claim = raw_claim.strip(" \t\r\n-•")
        if not claim:
            continue
        if _is_metadata_or_unavailable_claim(claim):
            continue
        if len(_terms(claim)) < 2:
            continue
        claims.append(claim)
    return claims


def _is_metadata_or_unavailable_claim(claim: str) -> bool:
    if claim.startswith(("출처", "Source", "source")):
        return True
    return any(marker in claim for marker in _UNAVAILABLE_MARKERS)


def _evidence_terms(chunks: list[dict]) -> set[str]:
    terms: set[str] = set()
    for chunk in chunks:
        terms.update(_terms(str(chunk.get("text") or "")))
        terms.update(_terms(str(chunk.get("section") or "")))
        terms.update(_terms(str(chunk.get("file") or "")))
    return terms


def _terms(text: str) -> set[str]:
    terms: set[str] = set()
    for match in _TERM_RE.findall(text.lower()):
        terms.add(match)
        for suffix in _PARTICLE_SUFFIXES:
            if match.endswith(suffix) and len(match) > len(suffix) + 1:
                terms.add(match[: -len(suffix)])
                break
    return terms


def _evidence_sufficiency(
    chunks: list[dict],
    critic_result: CriticResult | None,
) -> dict:
    if critic_result is None:
        return {
            "available": False,
            "result_count": len(chunks),
            "sufficient": None,
            "sufficiency_score": None,
            "trigger_reasons": [],
        }

    decision = critic_result.selected.decision
    return {
        "available": True,
        "selected_pass": critic_result.selected.name,
        "retry_triggered": critic_result.retry is not None,
        "result_count": len(chunks),
        "sufficient": decision.sufficient,
        "sufficiency_score": decision.sufficiency_score,
        "trigger_reasons": decision.trigger_reasons,
    }


def _has_source_marker(answer: str) -> bool:
    return any(marker in answer for marker in ("출처", ".pdf", " p", "p."))
