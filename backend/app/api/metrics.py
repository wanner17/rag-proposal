from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import require_admin
from app.models.schemas import UserInfo
from app.services.projects import list_projects
from app.services.source_index_state import SourceIndexStateRepository

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/indexing")
async def indexing_metrics(_: UserInfo = Depends(require_admin)):
    repo = SourceIndexStateRepository()
    projects = list_projects()
    result = []
    for project in projects:
        state = repo.get_project_state(project.slug)
        counts = repo.count_files_by_status(project.slug) if state else {}
        result.append({
            "project_slug": project.slug,
            "project_name": project.name,
            "status": state.status if state else "never_indexed",
            "last_full_indexed_at": state.last_full_indexed_at if state else None,
            "last_incremental_indexed_at": state.last_incremental_indexed_at if state else None,
            "last_successful_revision": state.last_successful_revision if state else None,
            "counts": counts,
        })
    return {"projects": result}
