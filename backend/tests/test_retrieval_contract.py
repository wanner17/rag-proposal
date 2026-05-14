import asyncio
import pytest
from qdrant_client.models import FieldCondition, MatchValue

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


def test_source_filter_uses_source_kind_and_project_slug_without_department():
    query_filter = retrieval._retrieval_filter(
        department="공공사업팀",
        retrieval_scope="source_code",
        project_slug="manual-qa",
    )

    assert query_filter is not None
    conditions = query_filter.must
    assert conditions == [
        FieldCondition(key="source_kind", match=MatchValue(value="source_code")),
        FieldCondition(key="project_slug", match=MatchValue(value="manual-qa")),
    ]


def test_source_retrieve_with_metadata_passes_project_slug_and_scope(monkeypatch):
    captured = {}

    async def fake_hybrid_search(
        query,
        department,
        top_k=20,
        collection_name=None,
        retrieval_scope="documents",
        project_slug=None,
    ):
        captured.update(
            {
                "department": department,
                "collection_name": collection_name,
                "retrieval_scope": retrieval_scope,
                "project_slug": project_slug,
            }
        )
        return [
            {
                "text": "class App {}",
                "source_kind": "source_code",
                "project_slug": "manual-qa",
                "relative_path": "src/App.java",
                "language": "java",
                "start_line": 10,
                "end_line": 20,
                "score": 0.7,
            }
        ]

    async def fake_rerank(query, passages, top_n=5):
        return [{"original_index": 0, "score": 0.93}]

    monkeypatch.setattr(retrieval, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(retrieval, "rerank", fake_rerank)

    _, reranked = asyncio.run(
        retrieval.retrieve_with_metadata(
            "질문",
            "공공사업팀",
            collection_name="manual-code",
            retrieval_scope="source_code",
            project_slug="manual-qa",
        )
    )

    assert captured == {
        "department": "공공사업팀",
        "collection_name": "manual-code",
        "retrieval_scope": "source_code",
        "project_slug": "manual-qa",
    }
    assert reranked[0]["source_kind"] == "source_code"
    assert reranked[0]["relative_path"] == "src/App.java"
    assert reranked[0]["score_source"] == "rerank"
