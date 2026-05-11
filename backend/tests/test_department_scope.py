from fastapi.testclient import TestClient

from app.core.auth import create_token, resolve_department_scope
from app.main import app
from app.models.schemas import UserInfo


def _headers(user_id="user1", department="공공사업팀", is_admin=False):
    return {"Authorization": f"Bearer {create_token(user_id, department, is_admin)}"}


def test_resolve_department_scope_rules():
    admin = UserInfo(user_id="admin", username="admin", department="전체", is_admin=True)
    user = UserInfo(user_id="user1", username="user1", department="공공사업팀")

    assert resolve_department_scope(admin, None) is None
    assert resolve_department_scope(admin, "금융사업팀") == "금융사업팀"
    assert resolve_department_scope(user, None) == "공공사업팀"
    assert resolve_department_scope(user, "금융사업팀") == "공공사업팀"


def test_chat_uses_scope_helper_for_non_admin(monkeypatch):
    captured = {}

    async def fake_retrieve(query, department, top_n=5):
        captured["department"] = department
        return []

    monkeypatch.setattr("app.api.chat.retrieve", fake_retrieve)
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        headers=_headers(),
        json={"query": "테스트", "department": "금융사업팀"},
    )

    assert response.status_code == 200
    assert captured["department"] == "공공사업팀"


def test_chat_stream_uses_scope_helper_for_admin_narrow(monkeypatch):
    captured = {}

    async def fake_retrieve(query, department, top_n=5):
        captured["department"] = department
        return []

    monkeypatch.setattr("app.api.chat.retrieve", fake_retrieve)
    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        headers=_headers("admin", "전체", True),
        json={"query": "테스트", "department": "금융사업팀"},
    )

    assert response.status_code == 200
    assert captured["department"] == "금융사업팀"


def test_proposal_uses_scope_helper_for_non_admin(monkeypatch):
    captured = {}

    async def fake_retrieve_with_metadata(query, department, top_k=20, top_n=5):
        captured["department"] = department
        return [], []

    monkeypatch.setattr("app.api.proposals.retrieve_with_metadata", fake_retrieve_with_metadata)
    client = TestClient(app)
    response = client.post(
        "/api/proposals/draft",
        headers=_headers(),
        json={"query": "제안서 초안", "department": "금융사업팀"},
    )

    assert response.status_code == 200
    assert captured["department"] == "공공사업팀"
