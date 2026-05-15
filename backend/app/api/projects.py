import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.core.auth import require_admin
from app.models.project_schemas import (
    ProjectCreateRequest,
    ProjectImportRequest,
    ProjectImportResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.models.schemas import UserInfo
from app.services.projects import (
    create_project,
    delete_project,
    export_project,
    get_project,
    import_project,
    list_projects,
    update_project,
)
from app.services.retrieval import delete_project_source_chunks
from app.services.source_index_state import SourceIndexStateRepository
from app.services.summary_generator import (
    generate_summary_draft,
    read_summary,
    write_summary,
)

router = APIRouter(prefix="/projects", tags=["projects"])


class SummaryUpdateRequest(BaseModel):
    content: str


class SummaryResponse(BaseModel):
    content: str | None
    exists: bool


class SummaryDraftResponse(BaseModel):
    draft: str


@router.get("", response_model=list[ProjectResponse])
async def read_projects(_: UserInfo = Depends(require_admin)):
    return list_projects()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project_api(
    request: ProjectCreateRequest,
    _: UserInfo = Depends(require_admin),
):
    return create_project(request)


@router.get("/{project_id}", response_model=ProjectResponse)
async def read_project(project_id: str, _: UserInfo = Depends(require_admin)):
    return get_project(project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project_api(
    project_id: str,
    request: ProjectUpdateRequest,
    _: UserInfo = Depends(require_admin),
):
    return update_project(project_id, request)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_api(project_id: str, _: UserInfo = Depends(require_admin)):
    project = get_project(project_id)
    delete_project(project_id)
    await delete_project_source_chunks(project.slug, collection_name=project.rag_config.collection_name)
    state_repo = SourceIndexStateRepository()
    state_repo.delete_file_records(project.slug)
    state_repo.delete_project_state(project.slug)
    if project.source_config.repo_root:
        repo_path = Path(project.source_config.repo_root)
        if repo_path.exists():
            try:
                shutil.rmtree(repo_path)
            except Exception:
                logging.getLogger(__name__).warning("repo_root 삭제 실패: %s", repo_path)


@router.get("/{project_id}/summary", response_model=SummaryResponse)
async def get_project_summary(project_id: str, _: UserInfo = Depends(require_admin)):
    project = get_project(project_id)
    if not project.source_config.repo_root:
        return SummaryResponse(content=None, exists=False)
    content = read_summary(project.source_config.repo_root)
    return SummaryResponse(content=content, exists=content is not None)


@router.put("/{project_id}/summary", response_model=SummaryResponse)
async def update_project_summary(
    project_id: str,
    request: SummaryUpdateRequest,
    _: UserInfo = Depends(require_admin),
):
    project = get_project(project_id)
    if not project.source_config.repo_root:
        raise HTTPException(status_code=400, detail="repo_root이 설정되지 않았습니다.")
    write_summary(project.source_config.repo_root, request.content)

    # Re-index summary file immediately
    from app.services.source_indexer import SourceIndexRequest, index_project_source
    from app.services.source_processor import SUMMARY_FILENAME
    await index_project_source(
        project,
        SourceIndexRequest(changed_files=[SUMMARY_FILENAME]),
    )
    return SummaryResponse(content=request.content, exists=True)


@router.post("/{project_id}/summary/generate", response_model=SummaryDraftResponse)
async def generate_project_summary(project_id: str, _: UserInfo = Depends(require_admin)):
    project = get_project(project_id)
    if not project.source_config.repo_root:
        raise HTTPException(status_code=400, detail="repo_root이 설정되지 않았습니다.")
    draft = await generate_summary_draft(
        project_slug=project.slug,
        repo_root=project.source_config.repo_root,
    )
    return SummaryDraftResponse(draft=draft)


@router.get("/{project_id}/export")
async def export_project_api(project_id: str, _: UserInfo = Depends(require_admin)):
    return Response(
        content=export_project(project_id),
        media_type="text/yaml",
        headers={"Content-Disposition": f'attachment; filename="{project_id}.yaml"'},
    )


@router.post("/import", response_model=ProjectImportResponse)
async def import_project_api(
    request: ProjectImportRequest,
    _: UserInfo = Depends(require_admin),
):
    return ProjectImportResponse(project=import_project(request.bundle))
