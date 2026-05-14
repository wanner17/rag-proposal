from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.core.config import settings


SourceProjectStatus = Literal[
    "never_indexed",
    "indexing",
    "ready",
    "partial_failed",
    "failed",
    "needs_full_reindex",
]
SourceFileStatus = Literal["indexed", "deleted", "skipped", "failed"]


@dataclass(frozen=True)
class SourceProjectState:
    project_id: str
    project_slug: str
    repo_root: str
    collection_name: str
    status: SourceProjectStatus = "never_indexed"
    last_full_indexed_at: str | None = None
    last_incremental_indexed_at: str | None = None
    last_successful_revision: str | None = None
    embedding_model: str | None = None
    chunking_version: str | None = None
    include_exclude_profile_hash: str | None = None
    source_config_hash: str | None = None
    lock_started_at: str | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class SourceFileRecord:
    project_slug: str
    relative_path: str
    content_hash: str | None
    svn_revision: str | None
    chunk_ids: list[str] = field(default_factory=list)
    status: SourceFileStatus = "indexed"
    failure_detail: str | None = None
    indexed_at: str | None = None


class SourceIndexStateRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path or settings.PROJECT_DB_PATH)
        if not self.db_path.is_absolute():
            self.db_path = Path.cwd() / self.db_path

    def get_project_state(self, project_slug: str) -> SourceProjectState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM source_index_projects WHERE project_slug = ?",
                (project_slug,),
            ).fetchone()
        return _project_state_from_row(row) if row else None

    def upsert_project_state(self, state: SourceProjectState) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO source_index_projects (
                    project_id, project_slug, repo_root, collection_name, status,
                    last_full_indexed_at, last_incremental_indexed_at,
                    last_successful_revision, embedding_model, chunking_version,
                    include_exclude_profile_hash, source_config_hash,
                    lock_started_at, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_slug) DO UPDATE SET
                    project_id = excluded.project_id,
                    repo_root = excluded.repo_root,
                    collection_name = excluded.collection_name,
                    status = excluded.status,
                    last_full_indexed_at = excluded.last_full_indexed_at,
                    last_incremental_indexed_at = excluded.last_incremental_indexed_at,
                    last_successful_revision = excluded.last_successful_revision,
                    embedding_model = excluded.embedding_model,
                    chunking_version = excluded.chunking_version,
                    include_exclude_profile_hash = excluded.include_exclude_profile_hash,
                    source_config_hash = excluded.source_config_hash,
                    lock_started_at = excluded.lock_started_at,
                    last_error = excluded.last_error,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    state.project_id,
                    state.project_slug,
                    state.repo_root,
                    state.collection_name,
                    state.status,
                    state.last_full_indexed_at,
                    state.last_incremental_indexed_at,
                    state.last_successful_revision,
                    state.embedding_model,
                    state.chunking_version,
                    state.include_exclude_profile_hash,
                    state.source_config_hash,
                    state.lock_started_at,
                    state.last_error,
                ),
            )
            conn.commit()

    def get_file_record(
        self,
        project_slug: str,
        relative_path: str,
    ) -> SourceFileRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM source_index_files
                 WHERE project_slug = ? AND relative_path = ?
                """,
                (project_slug, relative_path),
            ).fetchone()
        return _file_record_from_row(row) if row else None

    def upsert_file_record(self, record: SourceFileRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO source_index_files (
                    project_slug, relative_path, content_hash, svn_revision,
                    chunk_ids_json, status, failure_detail, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_slug, relative_path) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    svn_revision = excluded.svn_revision,
                    chunk_ids_json = excluded.chunk_ids_json,
                    status = excluded.status,
                    failure_detail = excluded.failure_detail,
                    indexed_at = excluded.indexed_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    record.project_slug,
                    record.relative_path,
                    record.content_hash,
                    record.svn_revision,
                    json.dumps(record.chunk_ids, ensure_ascii=False),
                    record.status,
                    record.failure_detail,
                    record.indexed_at,
                ),
            )
            conn.commit()

    def mark_file_deleted(
        self,
        project_slug: str,
        relative_path: str,
        svn_revision: str | None = None,
    ) -> None:
        current = self.get_file_record(project_slug, relative_path)
        self.upsert_file_record(
            SourceFileRecord(
                project_slug=project_slug,
                relative_path=relative_path,
                content_hash=current.content_hash if current else None,
                svn_revision=svn_revision,
                chunk_ids=[],
                status="deleted",
            )
        )

    def count_files_by_status(self, project_slug: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS count
                  FROM source_index_files
                 WHERE project_slug = ?
                 GROUP BY status
                 ORDER BY status
                """,
                (project_slug,),
            ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    def delete_file_records(self, project_slug: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM source_index_files WHERE project_slug = ?",
                (project_slug,),
            )
            conn.commit()

    def delete_project_state(self, project_slug: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM source_index_projects WHERE project_slug = ?",
                (project_slug,),
            )
            conn.commit()

    def recent_failures(self, project_slug: str, limit: int = 10) -> list[SourceFileRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM source_index_files
                 WHERE project_slug = ? AND status = 'failed'
                 ORDER BY updated_at DESC
                 LIMIT ?
                """,
                (project_slug, limit),
            ).fetchall()
        return [_file_record_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_index_projects (
                project_slug TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                repo_root TEXT NOT NULL,
                collection_name TEXT NOT NULL,
                status TEXT NOT NULL,
                last_full_indexed_at TEXT,
                last_incremental_indexed_at TEXT,
                last_successful_revision TEXT,
                embedding_model TEXT,
                chunking_version TEXT,
                include_exclude_profile_hash TEXT,
                source_config_hash TEXT,
                lock_started_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_index_files (
                project_slug TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                content_hash TEXT,
                svn_revision TEXT,
                chunk_ids_json TEXT NOT NULL,
                status TEXT NOT NULL,
                failure_detail TEXT,
                indexed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (project_slug, relative_path)
            )
            """
        )
        conn.commit()
        return conn


def _project_state_from_row(row: sqlite3.Row) -> SourceProjectState:
    return SourceProjectState(
        project_id=row["project_id"],
        project_slug=row["project_slug"],
        repo_root=row["repo_root"],
        collection_name=row["collection_name"],
        status=row["status"],
        last_full_indexed_at=row["last_full_indexed_at"],
        last_incremental_indexed_at=row["last_incremental_indexed_at"],
        last_successful_revision=row["last_successful_revision"],
        embedding_model=row["embedding_model"],
        chunking_version=row["chunking_version"],
        include_exclude_profile_hash=row["include_exclude_profile_hash"],
        source_config_hash=row["source_config_hash"],
        lock_started_at=row["lock_started_at"],
        last_error=row["last_error"],
    )


def _file_record_from_row(row: sqlite3.Row) -> SourceFileRecord:
    return SourceFileRecord(
        project_slug=row["project_slug"],
        relative_path=row["relative_path"],
        content_hash=row["content_hash"],
        svn_revision=row["svn_revision"],
        chunk_ids=json.loads(row["chunk_ids_json"]),
        status=row["status"],
        failure_detail=row["failure_detail"],
        indexed_at=row["indexed_at"],
    )
