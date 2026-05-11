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


def test_delete_document_removes_permitted_index_and_source_file(monkeypatch, tmp_path):
    captured = {}
    source = tmp_path / "sample.pdf"
    source.write_text("source", encoding="utf-8")

    async def fake_list_indexed_chunks(department):
        captured["list_department"] = department
        return [_chunk()]

    async def fake_delete_document_chunks(file_name, department):
        captured["delete_file"] = file_name
        captured["delete_department"] = department
        return True

    monkeypatch.setattr("app.api.documents.UPLOAD_DIR", tmp_path)
    monkeypatch.setattr("app.api.documents.list_indexed_chunks", fake_list_indexed_chunks)
    monkeypatch.setattr("app.api.documents.delete_document_chunks", fake_delete_document_chunks)

    client = TestClient(app)
    response = client.delete("/api/documents/sample.pdf", headers=_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["indexed_chunks_deleted"] is True
    assert data["source_file_deleted"] is True
    assert not source.exists()
    assert captured == {
        "list_department": "공공사업팀",
        "delete_file": "sample.pdf",
        "delete_department": "공공사업팀",
    }


def test_delete_document_blocks_out_of_scope_file(monkeypatch):
    async def fake_list_indexed_chunks(department):
        return []

    async def fail_delete(*args, **kwargs):
        raise AssertionError("out-of-scope delete must not touch qdrant")

    monkeypatch.setattr("app.api.documents.list_indexed_chunks", fake_list_indexed_chunks)
    monkeypatch.setattr("app.api.documents.delete_document_chunks", fail_delete)

    client = TestClient(app)
    response = client.delete("/api/documents/other.pdf", headers=_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is False
    assert data["indexed_chunks_deleted"] is False


def test_admin_delete_uses_all_department_scope(monkeypatch, tmp_path):
    captured = {}

    async def fake_list_indexed_chunks(department):
        captured["list_department"] = department
        return [_chunk(file="admin.pdf", department="제조DX팀")]

    async def fake_delete_document_chunks(file_name, department):
        captured["delete_department"] = department
        return True

    monkeypatch.setattr("app.api.documents.UPLOAD_DIR", tmp_path)
    monkeypatch.setattr("app.api.documents.list_indexed_chunks", fake_list_indexed_chunks)
    monkeypatch.setattr("app.api.documents.delete_document_chunks", fake_delete_document_chunks)

    client = TestClient(app)
    response = client.delete(
        "/api/documents/admin.pdf",
        headers=_headers("admin", "전체", True),
    )

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert captured["list_department"] is None
    assert captured["delete_department"] is None
