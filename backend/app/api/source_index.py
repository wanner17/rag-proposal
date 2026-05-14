from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import settings
from app.models.schemas import UserInfo
from app.services.projects import get_project, get_project_by_slug
from app.services.source_index_state import SourceIndexStateRepository
from app.services.source_indexer import (
    SourceIndexRequest,
    index_project_source,
    repair_project_source,
    reindex_project_source,
)

router = APIRouter(tags=["source-index"])


class SourceIndexApiRequest(BaseModel):
    changed_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)
    svn_revision: str | None = None
    project_id: str | None = None


class SourceReindexApiRequest(BaseModel):
    svn_revision: str | None = None


class SourceIndexFailureResponse(BaseModel):
    relative_path: str
    reason: str
    detail: str = ""


class SourceIndexResponse(BaseModel):
    mode: str
    project_slug: str
    collection_name: str
    indexed: int
    changed: int
    deleted: int
    skipped: int
    failed: int
    status: str
    failures: list[SourceIndexFailureResponse]


class SourceIndexStatusResponse(BaseModel):
    project_slug: str
    collection_name: str
    enabled: bool
    status: str
    last_full_indexed_at: str | None = None
    last_incremental_indexed_at: str | None = None
    last_successful_revision: str | None = None
    stale_lock: bool = False
    counts: dict[str, int] = Field(default_factory=dict)
    recent_failures: list[SourceIndexFailureResponse] = Field(default_factory=list)


async def _require_source_index_access(request: Request) -> UserInfo:
    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if (
        settings.SOURCE_INDEX_API_TOKEN
        and scheme.lower() == "bearer"
        and token == settings.SOURCE_INDEX_API_TOKEN
    ):
        return UserInfo(
            user_id="source-index-batch",
            username="source-index-batch",
            department="system",
            is_admin=True,
        )

    user = await get_current_user(token=token if scheme.lower() == "bearer" else "")
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다")
    return user


@router.post("/projects/{project_id}/source-index", response_model=SourceIndexResponse)
async def index_project_source_by_id(
    project_id: str,
    request: SourceIndexApiRequest,
    _: UserInfo = Depends(_require_source_index_access),
):
    if request.project_id and request.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload project_id conflicts with route project_id",
        )
    project = get_project(project_id)
    result = await index_project_source(
        project,
        SourceIndexRequest(
            changed_files=request.changed_files,
            deleted_files=request.deleted_files,
            svn_revision=request.svn_revision,
        ),
    )
    return asdict(result)


@router.post("/project-sources/{project_slug}/source-index", response_model=SourceIndexResponse)
async def index_project_source_by_slug(
    project_slug: str,
    request: SourceIndexApiRequest,
    _: UserInfo = Depends(_require_source_index_access),
):
    project = get_project_by_slug(project_slug)
    if project.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="활성 프로젝트를 찾을 수 없습니다",
        )
    if request.project_id and request.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload project_id conflicts with route project slug",
        )
    result = await index_project_source(
        project,
        SourceIndexRequest(
            changed_files=request.changed_files,
            deleted_files=request.deleted_files,
            svn_revision=request.svn_revision,
        ),
    )
    return asdict(result)


@router.post(
    "/projects/{project_id}/source-index/reindex",
    response_model=SourceIndexResponse,
)
async def reindex_project_source_by_id(
    project_id: str,
    request: SourceReindexApiRequest,
    _: UserInfo = Depends(_require_source_index_access),
):
    project = get_project(project_id)
    result = await reindex_project_source(project, svn_revision=request.svn_revision)
    return asdict(result)


@router.post(
    "/projects/{project_id}/source-index/repair",
    response_model=SourceIndexResponse,
)
async def repair_project_source_by_id(
    project_id: str,
    request: SourceReindexApiRequest,
    _: UserInfo = Depends(_require_source_index_access),
):
    project = get_project(project_id)
    result = await repair_project_source(project, svn_revision=request.svn_revision)
    return asdict(result)


@router.get(
    "/projects/{project_id}/source-index/status",
    response_model=SourceIndexStatusResponse,
)
async def source_index_status(
    project_id: str,
    _: UserInfo = Depends(_require_source_index_access),
):
    project = get_project(project_id)
    repo = SourceIndexStateRepository()
    state = repo.get_project_state(project.slug)
    if state is None:
        return SourceIndexStatusResponse(
            project_slug=project.slug,
            collection_name=project.rag_config.collection_name,
            enabled=project.source_config.enabled,
            status="never_indexed",
            counts={},
            recent_failures=[],
        )

    return SourceIndexStatusResponse(
        project_slug=project.slug,
        collection_name=state.collection_name,
        enabled=project.source_config.enabled,
        status=state.status,
        last_full_indexed_at=state.last_full_indexed_at,
        last_incremental_indexed_at=state.last_incremental_indexed_at,
        last_successful_revision=state.last_successful_revision,
        stale_lock=_is_stale_lock(state.status, state.lock_started_at),
        counts=repo.count_files_by_status(project.slug),
        recent_failures=[
            SourceIndexFailureResponse(
                relative_path=record.relative_path,
                reason=record.failure_detail or "failed",
                detail="",
            )
            for record in repo.recent_failures(project.slug)
        ],
    )


class SvnInfoResponse(BaseModel):
    working_revision: str | None = None
    head_revision: str | None = None


class CheckoutStatusResponse(BaseModel):
    status: str
    message: str
    progress: int


@router.get("/projects/{project_id}/source-index/svn-info", response_model=SvnInfoResponse)
async def get_svn_info(
    project_id: str,
    _: UserInfo = Depends(_require_source_index_access),
):
    project = get_project(project_id)
    config = project.source_config
    if not config or not config.svn_url:
        return SvnInfoResponse()
    webhook_url = f"{settings.SVN_CHECKOUT_WEBHOOK_URL.rstrip('/')}/svn-info/{project.slug}"
    payload = {"svn_url": config.svn_url, "repo_root": config.repo_root or ""}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json=payload)
        if resp.status_code == 200:
            return SvnInfoResponse(**resp.json())
    except Exception:
        pass
    return SvnInfoResponse()


@router.post("/projects/{project_id}/source-index/checkout", response_model=CheckoutStatusResponse)
async def trigger_checkout(
    project_id: str,
    background_tasks: BackgroundTasks,
    _: UserInfo = Depends(_require_source_index_access),
):
    from app.services.svn_checkout import get_checkout_status, run_checkout

    project = get_project(project_id)
    config = project.source_config
    if not config or not config.svn_url:
        raise HTTPException(status_code=400, detail="svn_url이 설정되지 않았습니다")
    if not config.repo_root:
        raise HTTPException(status_code=400, detail="repo_root가 설정되지 않았습니다")

    current = get_checkout_status(project.slug)
    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="이미 체크아웃이 진행 중입니다")

    background_tasks.add_task(run_checkout, project.slug, config)
    return CheckoutStatusResponse(status="running", message="체크아웃을 시작했습니다", progress=10)


@router.get("/projects/{project_id}/source-index/checkout/status", response_model=CheckoutStatusResponse)
async def checkout_status(
    project_id: str,
    _: UserInfo = Depends(_require_source_index_access),
):
    from app.services.svn_checkout import get_checkout_status

    project = get_project(project_id)
    state = get_checkout_status(project.slug)
    return CheckoutStatusResponse(**state)


def _is_stale_lock(status_value: str, lock_started_at: str | None) -> bool:
    if status_value != "indexing" or not lock_started_at:
        return False
    try:
        started = datetime.fromisoformat(lock_started_at)
    except ValueError:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - started).total_seconds()
    return age_seconds > settings.SOURCE_INDEX_LOCK_TIMEOUT_SECONDS
