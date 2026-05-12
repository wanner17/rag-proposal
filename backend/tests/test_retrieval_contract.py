import asyncio
import pytest

from app.services import retrieval


def _candidate(idx=1):
    return {
        "point_id": f"point-{idx}",
        "file": "proposal.pdf",
        "page": idx,
        "section": "개요",
        "department": "공공사업팀",
        "text": f"본문 {idx}",
        "retrieval_score": 0.7 + idx / 100,
        "score": 0.7 + idx / 100,
        "score_source": "retrieval",
    }


def test_merge_rerank_scores_preserves_retrieval_metadata():
    candidates = [_candidate(1), _candidate(2)]
    reranked = [{"original_index": 1, "score": 0.95}]

    result = retrieval.merge_rerank_scores(candidates, reranked)

    assert result[0]["point_id"] == "point-2"
    assert result[0]["retrieval_score"] == pytest.approx(0.72)
    assert result[0]["rerank_score"] == pytest.approx(0.95)
    assert result[0]["score"] == pytest.approx(0.95)
    assert result[0]["score_source"] == "rerank"


def test_retrieve_call_shape_stays_backward_compatible(monkeypatch):
    async def fake_hybrid_search(query, department, top_k=20, collection_name=None):
        assert query == "질문"
        assert department == "공공사업팀"
        assert top_k == 20
        return [_candidate(1)]

    async def fake_rerank(query, passages, top_n=5):
        assert top_n == 5
        return [{"original_index": 0, "score": 0.91}]

    monkeypatch.setattr(retrieval, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(retrieval, "rerank", fake_rerank)

    result = asyncio.run(retrieval.retrieve("질문", "공공사업팀", top_n=5))
    assert isinstance(result, list)
    assert result[0]["file"] == "proposal.pdf"
    assert result[0]["score"] == pytest.approx(0.91)


def test_retrieve_with_metadata_returns_candidates_and_reranked(monkeypatch):
    async def fake_hybrid_search(query, department, top_k=20, collection_name=None):
        return [_candidate(1)]

    async def fake_rerank(query, passages, top_n=5):
        return [{"original_index": 0, "score": 0.88}]

    monkeypatch.setattr(retrieval, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(retrieval, "rerank", fake_rerank)

    candidates, reranked = asyncio.run(
        retrieval.retrieve_with_metadata("질문", "공공사업팀", top_k=10, top_n=1)
    )
    assert candidates[0]["point_id"] == "point-1"
    assert candidates[0]["retrieval_score"] is not None
    assert reranked[0]["rerank_score"] == pytest.approx(0.88)
    assert reranked[0]["retrieval_score"] == candidates[0]["retrieval_score"]
