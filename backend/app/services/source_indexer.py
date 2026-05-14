from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.models.project_schemas import ProjectResponse
from app.services.retrieval import delete_project_source_chunks, delete_source_chunks, index_chunks
from app.services.source_index_state import (
    SourceFileRecord,
    SourceIndexStateRepository,
    SourceProjectState,
)
from app.services.source_processor import (
    SourceFileSkip,
    chunk_source_file,
    normalize_relative_path,
    should_include_source_path,
)


SourceIndexMode = Literal["initial_full", "incremental", "full_reindex", "repair"]


@dataclass(frozen=True)
class SourceIndexRequest:
    changed_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    svn_revision: str | None = None
    force_full_scan: bool = False
    result_mode: SourceIndexMode | None = None


@dataclass(frozen=True)
class SourceIndexFailure:
    relative_path: str
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class SourceIndexResult:
    mode: SourceIndexMode
    project_slug: str
    collection_name: str
    indexed: int
    changed: int
    deleted: int
    skipped: int
    failed: int
    status: str
    failures: list[SourceIndexFailure]


async def index_project_source(
    project: ProjectResponse,
    request: SourceIndexRequest,
    state_repo: SourceIndexStateRepository | None = None,
) -> SourceIndexResult:
    if not project.source_config.enabled:
        return _result(project, skipped=len(request.changed_files), status="never_indexed")

    repo = state_repo or SourceIndexStateRepository()
    current_state = repo.get_project_state(project.slug)
    mode: SourceIndexMode = request.result_mode or (
        "initial_full" if current_state is None else "incremental"
    )
    changed_files = list(request.changed_files)
    if request.force_full_scan or (mode == "initial_full" and not changed_files and not request.deleted_files):
        changed_files = _scan_source_files(project)
    repo.upsert_project_state(
        SourceProjectState(
            project_id=project.id,
            project_slug=project.slug,
            repo_root=project.source_config.repo_root or "",
            collection_name=project.rag_config.collection_name,
            status="indexing",
            lock_started_at=_utc_now(),
            last_successful_revision=request.svn_revision,
        )
    )

    indexed = 0
    deleted = 0
    skipped = 0
    failures: list[SourceIndexFailure] = []

    for relative_path in request.deleted_files:
        try:
            normalized = normalize_relative_path(relative_path, project.source_config)
            await delete_source_chunks(
                project.slug,
                normalized,
                collection_name=project.rag_config.collection_name,
            )
            repo.mark_file_deleted(project.slug, normalized, request.svn_revision)
            deleted += 1
        except Exception as exc:
            failures.append(SourceIndexFailure(relative_path, type(exc).__name__, str(exc)))

    for relative_path in changed_files:
        try:
            chunks = chunk_source_file(
                project.source_config,
                project.slug,
                relative_path,
                svn_revision=request.svn_revision,
            )
            file_hash = chunks[0]["content_hash"]
            existing = repo.get_file_record(project.slug, chunks[0]["relative_path"])
            if existing and existing.content_hash == file_hash and existing.status == "indexed":
                skipped += 1
                continue
            await delete_source_chunks(
                project.slug,
                chunks[0]["relative_path"],
                collection_name=project.rag_config.collection_name,
            )
            await index_chunks(chunks, collection_name=project.rag_config.collection_name)
            repo.upsert_file_record(
                SourceFileRecord(
                    project_slug=project.slug,
                    relative_path=chunks[0]["relative_path"],
                    content_hash=file_hash,
                    svn_revision=request.svn_revision,
                    chunk_ids=[chunk["chunk_id"] for chunk in chunks],
                    status="indexed",
                )
            )
            indexed += 1
        except SourceFileSkip as exc:
            repo.upsert_file_record(
                SourceFileRecord(
                    project_slug=project.slug,
                    relative_path=relative_path,
                    content_hash=None,
                    svn_revision=request.svn_revision,
                    chunk_ids=[],
                    status="skipped",
                    failure_detail=exc.reason,
                )
            )
            skipped += 1
        except Exception as exc:
            repo.upsert_file_record(
                SourceFileRecord(
                    project_slug=project.slug,
                    relative_path=relative_path,
                    content_hash=None,
                    svn_revision=request.svn_revision,
                    chunk_ids=[],
                    status="failed",
                    failure_detail=f"{type(exc).__name__}: {exc}",
                )
            )
            failures.append(SourceIndexFailure(relative_path, type(exc).__name__, str(exc)))

    status = "ready" if not failures else "partial_failed"
    now = _utc_now()
    previous_state = repo.get_project_state(project.slug)
    repo.upsert_project_state(
        SourceProjectState(
            project_id=project.id,
            project_slug=project.slug,
            repo_root=project.source_config.repo_root or "",
            collection_name=project.rag_config.collection_name,
            status=status,
            last_full_indexed_at=(
                now
                if mode in ("initial_full", "full_reindex")
                else previous_state.last_full_indexed_at if previous_state else None
            ),
            last_incremental_indexed_at=(
                now
                if mode == "incremental"
                else previous_state.last_incremental_indexed_at if previous_state else None
            ),
            last_successful_revision=request.svn_revision,
            lock_started_at=None,
        )
    )
    return SourceIndexResult(
        mode=mode,
        project_slug=project.slug,
        collection_name=project.rag_config.collection_name,
        indexed=indexed,
        changed=len(changed_files),
        deleted=deleted,
        skipped=skipped,
        failed=len(failures),
        status=status,
        failures=failures,
    )


async def reindex_project_source(
    project: ProjectResponse,
    svn_revision: str | None = None,
    state_repo: SourceIndexStateRepository | None = None,
) -> SourceIndexResult:
    return await _rebuild_project_source(project, "full_reindex", svn_revision, state_repo)


async def repair_project_source(
    project: ProjectResponse,
    svn_revision: str | None = None,
    state_repo: SourceIndexStateRepository | None = None,
) -> SourceIndexResult:
    return await _rebuild_project_source(project, "repair", svn_revision, state_repo)


async def _rebuild_project_source(
    project: ProjectResponse,
    mode: SourceIndexMode,
    svn_revision: str | None,
    state_repo: SourceIndexStateRepository | None,
) -> SourceIndexResult:
    if not project.source_config.enabled:
        return _result(project, status="never_indexed")

    repo = state_repo or SourceIndexStateRepository()
    repo.upsert_project_state(
        SourceProjectState(
            project_id=project.id,
            project_slug=project.slug,
            repo_root=project.source_config.repo_root or "",
            collection_name=project.rag_config.collection_name,
            status="indexing",
            lock_started_at=_utc_now(),
            last_successful_revision=svn_revision,
        )
    )
    await delete_project_source_chunks(
        project.slug,
        collection_name=project.rag_config.collection_name,
    )
    repo.delete_file_records(project.slug)
    return await index_project_source(
        project,
        SourceIndexRequest(
            svn_revision=svn_revision,
            force_full_scan=True,
            result_mode=mode,
        ),
        state_repo=repo,
    )


def _scan_source_files(project: ProjectResponse) -> list[str]:
    repo_root = Path(project.source_config.repo_root or "")
    if not repo_root.exists():
        return []
    relative_paths: list[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(repo_root).as_posix()
        try:
            if should_include_source_path(relative_path, project.source_config):
                relative_paths.append(relative_path)
        except ValueError:
            continue
    return sorted(relative_paths)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result(
    project: ProjectResponse,
    skipped: int = 0,
    status: str = "ready",
) -> SourceIndexResult:
    return SourceIndexResult(
        mode="incremental",
        project_slug=project.slug,
        collection_name=project.rag_config.collection_name,
        indexed=0,
        changed=0,
        deleted=0,
        skipped=skipped,
        failed=0,
        status=status,
        failures=[],
    )
