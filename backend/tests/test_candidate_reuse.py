from app.services.retrieval_experiments import (
    CandidateIdentity,
    can_reuse_candidates,
    comparison_label,
    quality_summary,
)


def _identity(**overrides):
    data = {
        "query": "LMS 제안서",
        "department_scope": "공공사업팀",
        "top_k": 20,
        "retrieval_variant": "hybrid_rrf_dense_bm25",
        "chunking_variant": "default",
        "filters": {"department": "공공사업팀"},
    }
    data.update(overrides)
    return CandidateIdentity(**data)


def test_same_identity_may_reuse_candidates():
    assert can_reuse_candidates(_identity(), _identity())


def test_identity_changes_prevent_reuse():
    base = _identity()
    assert not can_reuse_candidates(base, _identity(query="보안 제안서"))
    assert not can_reuse_candidates(base, _identity(department_scope="금융사업팀"))
    assert not can_reuse_candidates(base, _identity(top_k=10))
    assert not can_reuse_candidates(base, _identity(retrieval_variant="dense_only"))


def test_rerank_comparison_label_requires_same_candidates():
    assert comparison_label(_identity(), _identity(), rerank_only=True) == "same-candidate rerank comparison"


def test_independent_variants_are_not_direct_score_comparisons():
    base = _identity()
    other = _identity(retrieval_variant="dense_only")

    assert comparison_label(base, other) == "independent retrieval variant comparison"
    summary = quality_summary(base, other)
    assert "원점수를 직접 순위 비교하지 말고" in summary


def test_not_comparable_summary_blocks_fake_score_ranking():
    summary = quality_summary(_identity(), _identity(query="다른 질문"))
    assert "원점수를 직접 비교할 수 없습니다" in summary
