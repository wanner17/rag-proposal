from fastapi.testclient import TestClient

from app.core.auth import create_token
from app.main import app


def _headers(user_id="user1", department="공공사업팀", is_admin=False):
    return {"Authorization": f"Bearer {create_token(user_id, department, is_admin)}"}


def _chunk(department="공공사업팀"):
    return {
        "point_id": "point-1",
        "file": "sample.pdf",
        "page": 3,
        "section": "추진방안",
        "department": department,
        "text": "근거 본문",
        "score": 0.96,
        "retrieval_score": 0.76,
        "rerank_score": 0.96,
        "score_source": "rerank",
    }


def test_unauthorized_proposal_request_returns_401():
    client = TestClient(app)
    response = client.post("/api/proposals/draft", json={"query": "제안서"})
    assert response.status_code == 401


def test_successful_proposal_response_shape(monkeypatch):
    async def fake_retrieve_with_metadata(query, department, top_k=20, top_n=5, **kwargs):
        return [_chunk()], [_chunk()]

    async def fake_generate(query, chunks):
        return "## 요약\n근거 기반 초안입니다."

    monkeypatch.setattr("app.api.proposals.retrieve_with_metadata", fake_retrieve_with_metadata)
    monkeypatch.setattr("app.api.proposals.generate_proposal_draft", fake_generate)

    client = TestClient(app)
    response = client.post(
        "/api/proposals/draft",
        headers=_headers(),
        json={"query": "제안서 초안", "scenario_id": "demo-public-si"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert data["status"] == "ok"
    assert data["variants"][0]["draft_markdown"].startswith("## 요약")
    assert data["variants"][0]["strategy"]
    assert data["variants"][0]["quality_summary"]
    assert data["shared_sources"][0]["point_id"] == "point-1"
    assert data["shared_sources"][0]["score_source"] == "rerank"
    assert data["shared_sources"][0]["retrieval_score"] == 0.76
    assert data["shared_sources"][0]["rerank_score"] == 0.96


def test_non_admin_proposal_cannot_widen_department(monkeypatch):
    captured = {}

    async def fake_retrieve_with_metadata(query, department, top_k=20, top_n=5, **kwargs):
        captured["department"] = department
        return [_chunk(department)], [_chunk(department)]

    async def fake_generate(query, chunks):
        return "초안"

    monkeypatch.setattr("app.api.proposals.retrieve_with_metadata", fake_retrieve_with_metadata)
    monkeypatch.setattr("app.api.proposals.generate_proposal_draft", fake_generate)

    client = TestClient(app)
    response = client.post(
        "/api/proposals/draft",
        headers=_headers(),
        json={"query": "제안서 초안", "department": "금융사업팀"},
    )

    assert response.status_code == 200
    assert captured["department"] == "공공사업팀"
    assert response.json()["department_scope"] == "공공사업팀"


def test_admin_proposal_can_narrow_department(monkeypatch):
    captured = {}

    async def fake_retrieve_with_metadata(query, department, top_k=20, top_n=5, **kwargs):
        captured["department"] = department
        return [_chunk(department)], [_chunk(department)]

    async def fake_generate(query, chunks):
        return "초안"

    monkeypatch.setattr("app.api.proposals.retrieve_with_metadata", fake_retrieve_with_metadata)
    monkeypatch.setattr("app.api.proposals.generate_proposal_draft", fake_generate)

    client = TestClient(app)
    response = client.post(
        "/api/proposals/draft",
        headers=_headers("admin", "전체", True),
        json={"query": "제안서 초안", "department": "금융사업팀"},
    )

    assert response.status_code == 200
    assert captured["department"] == "금융사업팀"
    assert response.json()["department_scope"] == "금융사업팀"


def test_known_scenario_id_can_drive_query_without_custom_prompt(monkeypatch):
    captured = {}

    async def fake_retrieve_with_metadata(query, department, top_k=20, top_n=5, **kwargs):
        captured["query"] = query
        return [_chunk(department)], [_chunk(department)]

    async def fake_generate(query, chunks):
        return "초안"

    monkeypatch.setattr("app.api.proposals.retrieve_with_metadata", fake_retrieve_with_metadata)
    monkeypatch.setattr("app.api.proposals.generate_proposal_draft", fake_generate)

    client = TestClient(app)
    response = client.post(
        "/api/proposals/draft",
        headers=_headers("admin", "전체", True),
        json={"scenario_id": "demo-public-si-modernization"},
    )

    assert response.status_code == 200
    assert "교육청 노후 업무시스템 고도화" in captured["query"]
    assert response.json()["found"] is True


def test_retrieval_failure_returns_error_contract(monkeypatch):
    async def fail_retrieve(*args, **kwargs):
        raise RuntimeError("search unavailable")

    async def fail_generate(*args, **kwargs):
        raise AssertionError("LLM must not be called when retrieval fails")

    monkeypatch.setattr("app.api.proposals.retrieve_with_metadata", fail_retrieve)
    monkeypatch.setattr("app.api.proposals.generate_proposal_draft", fail_generate)

    client = TestClient(app)
    response = client.post(
        "/api/proposals/draft",
        headers=_headers(),
        json={"query": "제안서 초안"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["found"] is False
    assert data["status"] == "error"
    assert data["variants"] == []
    assert "검색 서비스를 확인하세요" in data["warnings"][0]


def test_llm_failure_returns_partial_with_sources(monkeypatch):
    async def fake_retrieve_with_metadata(query, department, top_k=20, top_n=5, **kwargs):
        return [_chunk()], [_chunk()]

    async def fail_generate(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.api.proposals.retrieve_with_metadata", fake_retrieve_with_metadata)
    monkeypatch.setattr("app.api.proposals.generate_proposal_draft", fail_generate)

    client = TestClient(app)
    response = client.post(
        "/api/proposals/draft",
        headers=_headers(),
        json={"query": "제안서 초안"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert data["status"] == "partial"
    assert data["shared_sources"][0]["point_id"] == "point-1"
    assert "근거 문서는 찾았지만" in data["variants"][0]["draft_markdown"]
    assert data["warnings"]
