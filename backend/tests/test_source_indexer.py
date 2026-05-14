import asyncio

from app.core.config import settings
from app.models.project_schemas import ProjectCreateRequest, ProjectRagConfig, ProjectSourceConfig
from app.services.projects import create_project
from app.services.source_processor import content_hash
from app.services.source_index_state import SourceIndexStateRepository, SourceFileRecord
from app.services.source_indexer import (
    SourceIndexRequest,
    index_project_source,
    repair_project_source,
    reindex_project_source,
)


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
                include_globs=["**/*.py"],
                exclude_globs=[".svn/**"],
            ),
        )
    )


def test_source_indexer_indexes_changed_and_deletes_removed_files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    source = tmp_path / "app.py"
    source.write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    project = _project(tmp_path)
    calls = {"index": [], "delete": []}

    async def fake_index_chunks(chunks, collection_name=None):
        calls["index"].append((chunks, collection_name))

    async def fake_delete_source_chunks(project_slug, relative_path, collection_name=None):
        calls["delete"].append((project_slug, relative_path, collection_name))
        return True

    monkeypatch.setattr("app.services.source_indexer.index_chunks", fake_index_chunks)
    monkeypatch.setattr("app.services.source_indexer.delete_source_chunks", fake_delete_source_chunks)

    result = asyncio.run(
        index_project_source(
            project,
            SourceIndexRequest(
                changed_files=["app.py"],
                deleted_files=["old.py"],
                svn_revision="12345",
            ),
        )
    )

    assert result.indexed == 1
    assert result.deleted == 1
    assert result.failed == 0
    assert calls["index"][0][1] == "manual-code"
    assert calls["index"][0][0][0]["relative_path"] == "app.py"
    assert calls["delete"] == [
        ("manual-code", "old.py", "manual-code"),
    ]

    repo = SourceIndexStateRepository()
    assert repo.get_file_record("manual-code", "app.py").status == "indexed"
    assert repo.get_file_record("manual-code", "old.py").status == "deleted"


def test_source_indexer_skips_unchanged_content(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    source = tmp_path / "app.py"
    source.write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    project = _project(tmp_path)
    repo = SourceIndexStateRepository()
    repo.upsert_file_record(
        SourceFileRecord(
            project_slug="manual-code",
            relative_path="app.py",
            content_hash=content_hash(source.read_bytes()),
            svn_revision="1",
            chunk_ids=["existing"],
            status="indexed",
        )
    )

    async def fail_index_chunks(*args, **kwargs):
        raise AssertionError("unchanged files must not be embedded")

    monkeypatch.setattr("app.services.source_indexer.index_chunks", fail_index_chunks)
    result = asyncio.run(
        index_project_source(
            project,
            SourceIndexRequest(changed_files=["app.py"], svn_revision="2"),
        )
    )

    assert result.skipped == 1


def test_source_indexer_initial_call_scans_full_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    (tmp_path / "app.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "worker.py").write_text("def work():\n    return 1\n", encoding="utf-8")
    (tmp_path / ".svn").mkdir()
    (tmp_path / ".svn" / "entries").write_text("skip", encoding="utf-8")
    project = _project(tmp_path)
    indexed_paths = []

    async def fake_index_chunks(chunks, collection_name=None):
        indexed_paths.append(chunks[0]["relative_path"])

    async def fake_delete_source_chunks(*args, **kwargs):
        return True

    monkeypatch.setattr("app.services.source_indexer.index_chunks", fake_index_chunks)
    monkeypatch.setattr("app.services.source_indexer.delete_source_chunks", fake_delete_source_chunks)

    result = asyncio.run(index_project_source(project, SourceIndexRequest(svn_revision="99")))

    assert result.mode == "initial_full"
    assert result.changed == 2
    assert result.indexed == 2
    assert sorted(indexed_paths) == ["app.py", "pkg/worker.py"]


def test_source_reindex_clears_project_vectors_and_scans_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    (tmp_path / "app.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    project = _project(tmp_path)
    calls = {"delete_project": 0, "index": 0}

    async def fake_delete_project_source_chunks(project_slug, collection_name=None):
        calls["delete_project"] += 1
        assert project_slug == "manual-code"
        assert collection_name == "manual-code"
        return True

    async def fake_delete_source_chunks(*args, **kwargs):
        return True

    async def fake_index_chunks(chunks, collection_name=None):
        calls["index"] += 1

    monkeypatch.setattr(
        "app.services.source_indexer.delete_project_source_chunks",
        fake_delete_project_source_chunks,
    )
    monkeypatch.setattr("app.services.source_indexer.delete_source_chunks", fake_delete_source_chunks)
    monkeypatch.setattr("app.services.source_indexer.index_chunks", fake_index_chunks)

    result = asyncio.run(reindex_project_source(project, svn_revision="100"))

    assert result.mode == "full_reindex"
    assert result.indexed == 1
    assert calls == {"delete_project": 1, "index": 1}


def test_source_repair_rebuilds_with_repair_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", str(tmp_path / "projects.sqlite3"))
    (tmp_path / "app.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    project = _project(tmp_path)

    async def fake_delete_project_source_chunks(*args, **kwargs):
        return True

    async def fake_delete_source_chunks(*args, **kwargs):
        return True

    async def fake_index_chunks(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.source_indexer.delete_project_source_chunks",
        fake_delete_project_source_chunks,
    )
    monkeypatch.setattr("app.services.source_indexer.delete_source_chunks", fake_delete_source_chunks)
    monkeypatch.setattr("app.services.source_indexer.index_chunks", fake_index_chunks)

    result = asyncio.run(repair_project_source(project, svn_revision="101"))

    assert result.mode == "repair"
    assert result.status == "ready"
