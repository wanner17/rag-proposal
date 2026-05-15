from pathlib import Path
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, resolve_department_scope
from app.models.schemas import (
    DocumentDeleteResponse,
    DocumentSearchHit,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentSummary,
    UserInfo,
)
from app.services.retrieval import delete_document_chunks, hybrid_search, list_indexed_chunks
from app.services.projects import get_project, get_default_project

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOAD_DIR = Path("/app/documents")


def _summarize_documents(chunks: list[dict]) -> list[DocumentSummary]:
    grouped: dict[str, dict] = {}
    for chunk in chunks:
        file_name = chunk.get("file", "")
        if not file_name:
            continue
        item = grouped.setdefault(
            file_name,
            {
                "file": file_name,
                "department": chunk.get("department"),
                "pages": set(),
                "sections": set(),
                "chunk_count": 0,
            },
        )
        item["chunk_count"] += 1
        if chunk.get("page") is not None:
            item["pages"].add(chunk.get("page"))
        if chunk.get("section"):
            item["sections"].add(chunk.get("section"))

    return [
        DocumentSummary(
            **{
                **item,
                "pages": sorted(item["pages"]),
                "sections": sorted(item["sections"]),
            }
        )
        for item in sorted(grouped.values(), key=lambda value: value["file"])
    ]


def _search_hit(chunk: dict) -> DocumentSearchHit:
    return DocumentSearchHit(
        point_id=str(chunk.get("point_id") or chunk.get("chunk_id") or ""),
        file=chunk.get("file", ""),
        page=chunk.get("page", 0),
        section=chunk.get("section", ""),
        department=chunk.get("department"),
        score=chunk.get("score"),
        score_source=chunk.get("score_source", "retrieval"),
        text=chunk.get("text", ""),
    )


@router.get("", response_model=DocumentSearchResponse)
async def list_documents(
    project_id: str | None = None,
    user: UserInfo = Depends(get_current_user),
):
    project = get_project(project_id) if project_id else get_default_project()
    department_scope = resolve_department_scope(user, None)
    chunks = await list_indexed_chunks(department_scope, collection_name=project.rag_config.collection_name, project_slug=project.slug)
    documents = _summarize_documents(chunks)
    return DocumentSearchResponse(found=bool(documents), documents=documents, hits=[])


@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(req: DocumentSearchRequest, user: UserInfo = Depends(get_current_user)):
    project = get_project(req.project_id) if req.project_id else get_default_project()
    department_scope = resolve_department_scope(user, None)
    all_chunks = await list_indexed_chunks(department_scope, collection_name=project.rag_config.collection_name, project_slug=project.slug)
    hits = [
        _search_hit(chunk)
        for chunk in await hybrid_search(
            req.query, department_scope, top_k=req.top_k, collection_name=project.rag_config.collection_name, project_slug=project.slug
        )
    ]
    documents = _summarize_documents(all_chunks)
    return DocumentSearchResponse(found=bool(hits), documents=documents, hits=hits)


@router.delete("/{file_name}", response_model=DocumentDeleteResponse)
async def delete_document(file_name: str, project_id: str | None = None, user: UserInfo = Depends(get_current_user)):
    project = get_project(project_id) if project_id else get_default_project()
    department_scope = resolve_department_scope(user, None)
    chunks = await list_indexed_chunks(department_scope, collection_name=project.rag_config.collection_name, project_slug=project.slug)
    matching_chunks = [chunk for chunk in chunks if chunk.get("file") == file_name]

    if not matching_chunks:
        return DocumentDeleteResponse(
            deleted=False,
            file=file_name,
            indexed_chunks_deleted=False,
            source_file_deleted=False,
            message="삭제할 수 있는 등록 문서를 찾지 못했습니다.",
        )

    indexed_deleted = await delete_document_chunks(file_name, department_scope, collection_name=project.rag_config.collection_name, project_slug=project.slug)
    source_path = (UPLOAD_DIR / file_name).resolve()
    source_deleted = False
    try:
        source_path.relative_to(UPLOAD_DIR.resolve())
        if source_path.is_file():
            source_path.unlink()
            source_deleted = True
    except ValueError:
        source_deleted = False

    return DocumentDeleteResponse(
        deleted=True,
        file=file_name,
        indexed_chunks_deleted=indexed_deleted,
        source_file_deleted=source_deleted,
        message="등록 문서를 삭제했습니다." if source_deleted else "검색 인덱스를 삭제했습니다. 원본 파일은 이미 없거나 삭제할 수 없습니다.",
    )
