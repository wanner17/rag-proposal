from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, resolve_department_scope
from app.models.schemas import (
    DocumentSearchHit,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentSummary,
    UserInfo,
)
from app.services.retrieval import hybrid_search, list_indexed_chunks

router = APIRouter(prefix="/documents", tags=["documents"])


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
                "year": chunk.get("year"),
                "client": chunk.get("client"),
                "domain": chunk.get("domain"),
                "project_type": chunk.get("project_type"),
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
async def list_documents(user: UserInfo = Depends(get_current_user)):
    department_scope = resolve_department_scope(user, None)
    chunks = await list_indexed_chunks(department_scope)
    documents = _summarize_documents(chunks)
    return DocumentSearchResponse(found=bool(documents), documents=documents, hits=[])


@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(req: DocumentSearchRequest, user: UserInfo = Depends(get_current_user)):
    department_scope = resolve_department_scope(user, None)
    all_chunks = await list_indexed_chunks(department_scope)
    hits = [_search_hit(chunk) for chunk in await hybrid_search(req.query, department_scope, top_k=req.top_k)]
    documents = _summarize_documents(all_chunks)
    return DocumentSearchResponse(found=bool(hits), documents=documents, hits=hits)
