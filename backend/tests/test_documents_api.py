from fastapi.testclient import TestClient

from app.core.auth import create_token
from app.main import app


def _headers(user_id="user1", department="공공사업팀", is_admin=False):
    return {"Authorization": f"Bearer {create_token(user_id, department, is_admin)}"}


def _chunk(file="sample.pdf", department="공공사업팀", score=0.8):
    return {
        "point_id": "point-1",
        "file": file,
        "page": 2,
        "section": "개요",
        "department": department,
        "year": 2024,
        "client": "교육청",
        "domain": "공공 SI",
        "project_type": "고도화",
        "text": "업로드 문서 원문 조각",
        "score": score,
        "score_source": "retrieval",
    }


def test_list_documents_is_authenticated():
    client = TestClient(app)
    response = client.get("/api/documents")
    assert response.status_code == 401


def test_list_documents_summarizes_permitted_chunks(monkeypatch):
    captured = {}

    async def fake_list_indexed_chunks(department):
        captured["department"] = department
        return [_chunk(), _chunk()]

    monkeypatch.setattr("app.api.documents.list_indexed_chunks", fake_list_indexed_chunks)

    client = TestClient(app)
    response = client.get("/api/documents", headers=_headers())

    assert response.status_code == 200
    data = response.json()
    assert captured["department"] == "공공사업팀"
    assert data["found"] is True
    assert data["hits"] == []
    assert data["documents"][0]["file"] == "sample.pdf"
    assert data["documents"][0]["chunk_count"] == 2


def test_search_documents_returns_hits_without_llm(monkeypatch):
    captured = {}

    async def fake_list_indexed_chunks(department):
        captured["list_department"] = department
        return [_chunk()]

    async def fake_hybrid_search(query, department, top_k=10):
        captured["query"] = query
        captured["search_department"] = department
        captured["top_k"] = top_k
        return [_chunk(score=0.91)]

    monkeypatch.setattr("app.api.documents.list_indexed_chunks", fake_list_indexed_chunks)
    monkeypatch.setattr("app.api.documents.hybrid_search", fake_hybrid_search)

    client = TestClient(app)
    response = client.post(
        "/api/documents/search",
        headers=_headers(),
        json={"query": "LMS", "top_k": 7},
    )

    assert response.status_code == 200
    data = response.json()
    assert captured == {
        "list_department": "공공사업팀",
        "query": "LMS",
        "search_department": "공공사업팀",
        "top_k": 7,
    }
    assert data["found"] is True
    assert data["hits"][0]["text"] == "업로드 문서 원문 조각"
    assert data["hits"][0]["score_source"] == "retrieval"


def test_admin_document_search_uses_all_departments(monkeypatch):
    captured = {}

    async def fake_list_indexed_chunks(department):
        captured["list_department"] = department
        return []

    async def fake_hybrid_search(query, department, top_k=10):
        captured["search_department"] = department
        return []

    monkeypatch.setattr("app.api.documents.list_indexed_chunks", fake_list_indexed_chunks)
    monkeypatch.setattr("app.api.documents.hybrid_search", fake_hybrid_search)

    client = TestClient(app)
    response = client.post(
        "/api/documents/search",
        headers=_headers("admin", "전체", True),
        json={"query": "LMS"},
    )

    assert response.status_code == 200
    assert captured["list_department"] is None
    assert captured["search_department"] is None
