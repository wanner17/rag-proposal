from app.core.config import settings
from app.services.source_index_state import (
    SourceFileRecord,
    SourceProjectState,
    SourceIndexStateRepository,
)


def test_source_project_state_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    repo = SourceIndexStateRepository()

    state = SourceProjectState(
        project_id="project-1",
        project_slug="manual-code",
        repo_root="/opt/rag-projects/e-myjob/manual-code",
        collection_name="manual-code",
        status="ready",
        last_full_indexed_at="2026-05-14T00:00:00+00:00",
        last_successful_revision="12345",
        embedding_model="bge-m3",
        chunking_version="source-v1",
        include_exclude_profile_hash="profile-hash",
        source_config_hash="source-hash",
    )

    repo.upsert_project_state(state)

    loaded = repo.get_project_state("manual-code")
    assert loaded is not None
    assert loaded.project_id == "project-1"
    assert loaded.project_slug == "manual-code"
    assert loaded.status == "ready"
    assert loaded.last_successful_revision == "12345"
    assert loaded.source_config_hash == "source-hash"


def test_source_file_record_round_trip_and_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    repo = SourceIndexStateRepository()

    repo.upsert_file_record(
        SourceFileRecord(
            project_slug="manual-code",
            relative_path="src/App.java",
            content_hash="abc",
            svn_revision="12345",
            chunk_ids=["chunk-1", "chunk-2"],
            status="indexed",
        )
    )
    repo.upsert_file_record(
        SourceFileRecord(
            project_slug="manual-code",
            relative_path="src/Bad.java",
            content_hash=None,
            svn_revision="12345",
            chunk_ids=[],
            status="failed",
            failure_detail="decode error",
        )
    )

    loaded = repo.get_file_record("manual-code", "src/App.java")
    assert loaded is not None
    assert loaded.chunk_ids == ["chunk-1", "chunk-2"]
    assert loaded.status == "indexed"

    counts = repo.count_files_by_status("manual-code")
    assert counts == {"failed": 1, "indexed": 1}


def test_source_file_can_be_marked_deleted(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    repo = SourceIndexStateRepository()
    repo.upsert_file_record(
        SourceFileRecord(
            project_slug="manual-code",
            relative_path="src/Old.java",
            content_hash="old",
            svn_revision="10",
            chunk_ids=["old-chunk"],
            status="indexed",
        )
    )

    repo.mark_file_deleted("manual-code", "src/Old.java", svn_revision="11")

    loaded = repo.get_file_record("manual-code", "src/Old.java")
    assert loaded is not None
    assert loaded.status == "deleted"
    assert loaded.chunk_ids == []
    assert loaded.svn_revision == "11"
