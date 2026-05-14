from fastapi.testclient import TestClient

from app.core.auth import create_token
from app.core.config import settings
from app.main import app
from app.models.project_schemas import ProjectCreateRequest, ProjectRagConfig, ProjectSourceConfig
from app.services.projects import create_project
from app.services.source_index_state import SourceFileRecord, SourceIndexStateRepository, SourceProjectState
from app.services.source_indexer import SourceIndexResult


def _headers(user_id="admin", department="전체", is_admin=True):
    return {"Authorization": f"Bearer {create_token(user_id, department, is_admin)}"}


def _project(tmp_path):
    return create_project(
        ProjectCreateRequest(
            slug="manual-code",
            name="매뉴얼 코드",
            description="소스 코드 질의응답",
            plugins=[],
            rag_config=ProjectRagConfig(collection_name="manual-code"),
            source_config=ProjectSourceConfig(
                enabled=True,
                repo_root=tmp_path.as_posix(),
                allowed_base_path=tmp_path.parent.as_posix(),
                svn_url="svn://example.local/manual-code",
                include_globs=["**/*.py"],
                exclude_globs=[".svn/**"],
            ),
        )
    )


def test_source_index_slug_route_requires_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    _project(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/project-sources/manual-code/source-index",
        headers=_headers("user1", "공공사업팀", False),
        json={"changed_files": ["app.py"], "deleted_files": []},
    )

    assert response.status_code == 403


def test_source_index_slug_route_accepts_source_index_token(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    monkeypatch.setattr(settings, "SOURCE_INDEX_API_TOKEN", "batch-secret")
    _project(tmp_path)

    async def fake_index_project_source(project, request):
        return SourceIndexResult(
            mode="incremental",
            project_slug=project.slug,
            collection_name=project.rag_config.collection_name,
            indexed=0,
            changed=0,
            deleted=0,
            skipped=0,
            failed=0,
            status="ready",
            failures=[],
        )

    monkeypatch.setattr("app.api.source_index.index_project_source", fake_index_project_source)
    client = TestClient(app)

    response = client.post(
        "/api/project-sources/manual-code/source-index",
        headers={"Authorization": "Bearer batch-secret"},
        json={"changed_files": [], "deleted_files": []},
    )

    assert response.status_code == 200


def test_source_index_slug_route_calls_indexer(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    _project(tmp_path)
    captured = {}

    async def fake_index_project_source(project, request):
        captured["slug"] = project.slug
        captured["collection_name"] = project.rag_config.collection_name
        captured["changed_files"] = request.changed_files
        captured["deleted_files"] = request.deleted_files
        captured["svn_revision"] = request.svn_revision
        return SourceIndexResult(
            mode="incremental",
            project_slug=project.slug,
            collection_name=project.rag_config.collection_name,
            indexed=1,
            changed=1,
            deleted=1,
            skipped=0,
            failed=0,
            status="ready",
            failures=[],
        )

    monkeypatch.setattr("app.api.source_index.index_project_source", fake_index_project_source)
    client = TestClient(app)

    response = client.post(
        "/api/project-sources/manual-code/source-index",
        headers=_headers(),
        json={
            "changed_files": ["app.py"],
            "deleted_files": ["old.py"],
            "svn_revision": "12345",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "slug": "manual-code",
        "collection_name": "manual-code",
        "changed_files": ["app.py"],
        "deleted_files": ["old.py"],
        "svn_revision": "12345",
    }
    assert response.json()["indexed"] == 1
    assert response.json()["deleted"] == 1


def test_source_index_slug_route_rejects_unknown_project(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    client = TestClient(app)

    response = client.post(
        "/api/project-sources/missing/source-index",
        headers=_headers(),
        json={"changed_files": [], "deleted_files": []},
    )

    assert response.status_code == 404


def test_source_index_status_route_returns_state_and_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    project = _project(tmp_path)
    repo = SourceIndexStateRepository()
    repo.upsert_project_state(
        SourceProjectState(
            project_id=project.id,
            project_slug=project.slug,
            repo_root=tmp_path.as_posix(),
            collection_name="manual-code",
            status="partial_failed",
            last_successful_revision="12345",
        )
    )
    repo.upsert_file_record(
        SourceFileRecord(
            project_slug=project.slug,
            relative_path="app.py",
            content_hash="abc",
            svn_revision="12345",
            chunk_ids=["chunk-1"],
            status="indexed",
        )
    )
    repo.upsert_file_record(
        SourceFileRecord(
            project_slug=project.slug,
            relative_path="bad.py",
            content_hash=None,
            svn_revision="12345",
            chunk_ids=[],
            status="failed",
            failure_detail="decode error",
        )
    )
    client = TestClient(app)

    response = client.get(
        f"/api/projects/{project.id}/source-index/status",
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_slug"] == "manual-code"
    assert payload["status"] == "partial_failed"
    assert payload["last_successful_revision"] == "12345"
    assert payload["counts"] == {"failed": 1, "indexed": 1}


def test_source_index_status_reports_stale_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    monkeypatch.setattr(settings, "SOURCE_INDEX_LOCK_TIMEOUT_SECONDS", 60)
    project = _project(tmp_path)
    repo = SourceIndexStateRepository()
    repo.upsert_project_state(
        SourceProjectState(
            project_id=project.id,
            project_slug=project.slug,
            repo_root=tmp_path.as_posix(),
            collection_name="manual-code",
            status="indexing",
            lock_started_at="2020-01-01T00:00:00+00:00",
        )
    )
    client = TestClient(app)

    response = client.get(
        f"/api/projects/{project.id}/source-index/status",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["stale_lock"] is True


def test_source_reindex_route_calls_reindexer(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    project = _project(tmp_path)
    captured = {}

    async def fake_reindex_project_source(project_arg, svn_revision=None):
        captured["project_id"] = project_arg.id
        captured["svn_revision"] = svn_revision
        return SourceIndexResult(
            mode="full_reindex",
            project_slug=project_arg.slug,
            collection_name=project_arg.rag_config.collection_name,
            indexed=2,
            changed=2,
            deleted=0,
            skipped=0,
            failed=0,
            status="ready",
            failures=[],
        )

    monkeypatch.setattr("app.api.source_index.reindex_project_source", fake_reindex_project_source)
    client = TestClient(app)

    response = client.post(
        f"/api/projects/{project.id}/source-index/reindex",
        headers=_headers(),
        json={"svn_revision": "100"},
    )

    assert response.status_code == 200
    assert captured == {"project_id": project.id, "svn_revision": "100"}
    assert response.json()["mode"] == "full_reindex"


def test_source_repair_route_calls_repairer(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    project = _project(tmp_path)
    captured = {}

    async def fake_repair_project_source(project_arg, svn_revision=None):
        captured["project_id"] = project_arg.id
        captured["svn_revision"] = svn_revision
        return SourceIndexResult(
            mode="repair",
            project_slug=project_arg.slug,
            collection_name=project_arg.rag_config.collection_name,
            indexed=1,
            changed=1,
            deleted=0,
            skipped=0,
            failed=0,
            status="ready",
            failures=[],
        )

    monkeypatch.setattr("app.api.source_index.repair_project_source", fake_repair_project_source)
    client = TestClient(app)

    response = client.post(
        f"/api/projects/{project.id}/source-index/repair",
        headers=_headers(),
        json={"svn_revision": "101"},
    )

    assert response.status_code == 200
    assert captured == {"project_id": project.id, "svn_revision": "101"}
    assert response.json()["mode"] == "repair"


def test_checkout_route_returns_running_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    project = _project(tmp_path)
    captured = {}

    from app.services import svn_checkout

    monkeypatch.setattr(svn_checkout, "_checkout_state", {})

    async def fake_run_checkout(project_slug, config):
        captured["project_slug"] = project_slug
        captured["svn_url"] = config.svn_url
        captured["repo_root"] = config.repo_root

    monkeypatch.setattr("app.services.svn_checkout.run_checkout", fake_run_checkout)
    client = TestClient(app)

    response = client.post(
        f"/api/projects/{project.id}/source-index/checkout",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "running",
        "message": "체크아웃을 시작했습니다",
        "progress": 10,
    }
    assert captured == {
        "project_slug": "manual-code",
        "svn_url": "svn://example.local/manual-code",
        "repo_root": tmp_path.as_posix(),
    }


def test_checkout_route_rejects_running_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    project = _project(tmp_path)

    from app.services import svn_checkout

    monkeypatch.setattr(svn_checkout, "_checkout_state", {})
    svn_checkout._set_status(project.slug, "running", "진행 중", 20)
    client = TestClient(app)

    response = client.post(
        f"/api/projects/{project.id}/source-index/checkout",
        headers=_headers(),
    )

    assert response.status_code == 409
