from fastapi import APIRouter, Depends, Response, status

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

router = APIRouter(prefix="/projects", tags=["projects"])


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
