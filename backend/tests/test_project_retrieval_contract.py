import asyncio

from app.services import retrieval


def test_retrieve_with_metadata_passes_project_collection(monkeypatch):
    captured = {}

    async def fake_hybrid(query, department, top_k=20, collection_name=None):
        captured["collection_name"] = collection_name
        return [{"text": "근거"}]

    async def fake_rerank(query, passages, top_n=5):
        return [{"original_index": 0, "score": 0.9}]

    monkeypatch.setattr(retrieval, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(retrieval, "rerank", fake_rerank)

    _, reranked = asyncio.run(
        retrieval.retrieve_with_metadata(
            "질문",
            "공공사업팀",
            collection_name="manual-qa-docs",
        )
    )

    assert captured["collection_name"] == "manual-qa-docs"
    assert reranked[0]["score"] == 0.9
