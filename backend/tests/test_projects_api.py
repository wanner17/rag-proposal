from fastapi.testclient import TestClient

from app.core.auth import create_token
from app.core.config import settings
from app.main import app


def _headers(user_id="admin", department="전체", is_admin=True):
    return {"Authorization": f"Bearer {create_token(user_id, department, is_admin)}"}


def _payload(slug="manual-qa"):
    return {
        "slug": slug,
        "name": "매뉴얼 QA",
        "description": "운영 매뉴얼 질의응답",
        "status": "active",
        "default_language": "ko",
        "plugins": [{"plugin_id": "proposal", "enabled": True, "config": {}}],
        "rag_config": {
            "collection_name": f"{slug}-docs",
            "top_k_default": 18,
            "top_n_default": 4,
            "prompt_profile": "manual-qa",
            "storage_namespace": slug,
        },
    }


def test_projects_are_admin_only(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    client = TestClient(app)

    response = client.get("/api/projects", headers=_headers("user1", "공공사업팀", False))

    assert response.status_code == 403


def test_project_crud_export_import_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    client = TestClient(app)

    created = client.post("/api/projects", headers=_headers(), json=_payload())
    assert created.status_code == 201
    project = created.json()
    assert project["slug"] == "manual-qa"
    assert project["rag_config"]["collection_name"] == "manual-qa-docs"

    patched = client.patch(
        f"/api/projects/{project['id']}",
        headers=_headers(),
        json={
            "name": "매뉴얼 QA 운영",
            "rag_config": {**project["rag_config"], "top_n_default": 6},
            "plugins": project["plugins"],
        },
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "매뉴얼 QA 운영"
    assert patched.json()["rag_config"]["top_n_default"] == 6

    exported = client.get(f"/api/projects/{project['id']}/export", headers=_headers())
    assert exported.status_code == 200
    assert '"schema_version": 1' in exported.text

    imported = client.post(
        "/api/projects/import",
        headers=_headers(),
        json={"bundle": exported.text},
    )
    assert imported.status_code == 200
    assert imported.json()["project"]["slug"] == "manual-qa"
    assert imported.json()["project"]["rag_config"]["top_n_default"] == 6
