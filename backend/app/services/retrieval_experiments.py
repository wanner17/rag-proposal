from __future__ import annotations

import json
from pydantic import BaseModel, Field


class CandidateIdentity(BaseModel):
    query: str
    department_scope: str | None = None
    top_k: int
    retrieval_variant: str = "hybrid_rrf_dense_bm25"
    chunking_variant: str = "default"
    filters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        return json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False)


def can_reuse_candidates(left: CandidateIdentity, right: CandidateIdentity) -> bool:
    return left.fingerprint() == right.fingerprint()


def comparison_label(left: CandidateIdentity, right: CandidateIdentity, *, rerank_only: bool = False) -> str:
    if can_reuse_candidates(left, right):
        if rerank_only:
            return "same-candidate rerank comparison"
        return "same-candidate comparison"
    if left.query == right.query and left.department_scope == right.department_scope:
        return "independent retrieval variant comparison"
    return "not comparable"


def quality_summary(left: CandidateIdentity, right: CandidateIdentity, *, rerank_only: bool = False) -> str:
    label = comparison_label(left, right, rerank_only=rerank_only)
    if label == "same-candidate rerank comparison":
        return (
            "same-candidate rerank comparison: 동일한 후보 생성 identity 위에서 rerank 적용 여부만 "
            "비교할 수 있습니다. retrieval_score와 rerank_score는 출처가 다르므로 같은 척도로 "
            "해석하지 않습니다."
        )
    if label == "same-candidate comparison":
        return (
            "same-candidate comparison: 후보 생성 identity가 동일하므로 같은 후보 집합 안에서 "
            "표시 전략 차이를 검토할 수 있습니다."
        )
    if label == "independent retrieval variant comparison":
        return (
            "independent retrieval variant comparison: 검색 설정이 다른 독립 후보 집합입니다. "
            "원점수를 직접 순위 비교하지 말고 출처/설정 라벨과 함께 참고하세요."
        )
    return (
        "not comparable: query, filter, top_k, index/chunking/search 설정 중 하나 이상이 달라 "
        "원점수를 직접 비교할 수 없습니다."
    )
