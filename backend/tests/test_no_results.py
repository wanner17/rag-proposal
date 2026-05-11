import json
from fastapi.testclient import TestClient

from app.core.auth import create_token
from app.main import app

NO_RESULTS_MESSAGE = "관련 제안서 근거 문서를 찾지 못했습니다."


def _headers():
    return {"Authorization": f"Bearer {create_token('user1', '공공사업팀', False)}"}


def test_proposal_no_results_is_deterministic_and_skips_llm(monkeypatch):
    async def fake_retrieve_with_metadata(query, department, top_k=20, top_n=5):
        return [], []

    async def fail_generate(*args, **kwargs):
        raise AssertionError("proposal LLM must not be called without evidence")

    monkeypatch.setattr("app.api.proposals.retrieve_with_metadata", fake_retrieve_with_metadata)
    monkeypatch.setattr("app.api.proposals.generate_proposal_draft", fail_generate)

    client = TestClient(app)
    response = client.post(
        "/api/proposals/draft",
        headers=_headers(),
        json={"query": "없는 근거"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["found"] is False
    assert data["status"] == "no_results"
    assert data["shared_sources"] == []
    assert data["variants"] == []
    assert NO_RESULTS_MESSAGE in data["no_results_message"]


def test_existing_chat_no_results_is_stable(monkeypatch):
    async def fake_retrieve(query, department, top_n=5):
        return []

    monkeypatch.setattr("app.api.chat.retrieve", fake_retrieve)
    client = TestClient(app)
    response = client.post("/api/chat", headers=_headers(), json={"query": "없는 근거"})

    assert response.status_code == 200
    data = response.json()
    assert data["found"] is False
    assert data["sources"] == []
    assert data["answer"] == "관련 문서를 찾지 못했습니다."


def test_existing_stream_no_results_is_deterministic(monkeypatch):
    async def fake_retrieve(query, department, top_n=5):
        return []

    monkeypatch.setattr("app.api.chat.retrieve", fake_retrieve)
    client = TestClient(app)
    response = client.post("/api/chat/stream", headers=_headers(), json={"query": "없는 근거"})

    assert response.status_code == 200
    payloads = [
        line.removeprefix("data:").strip()
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]
    tokens = []
    for payload in payloads:
        if payload == "[DONE]":
            continue
        data = json.loads(payload)
        if "token" in data:
            tokens.append(data["token"])
    assert "관련 문서를 찾지 못했습니다." in tokens
    assert "[DONE]" in payloads
