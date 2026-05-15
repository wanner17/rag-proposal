from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import require_admin
from app.models.project_schemas import (
    META_DOC_TYPES,
    AllMetaDocsResponse,
    MetaDocDraftResponse,
    MetaDocResponse,
    MetaDocUpdateRequest,
)
from app.models.schemas import UserInfo
from app.services.meta_doc_generator import generate_meta_doc_draft
from app.services.meta_doc_indexer import index_meta_doc
from app.services.projects import get_meta_docs, get_project, update_meta_doc

router = APIRouter(prefix="/projects", tags=["meta-docs"])


@router.get("/{project_id}/meta-docs", response_model=AllMetaDocsResponse)
async def get_all_meta_docs(project_id: str, _: UserInfo = Depends(require_admin)):
    meta = get_meta_docs(project_id)
    return AllMetaDocsResponse(
        **{
            doc_type: MetaDocResponse(
                doc_type=doc_type,
                content=meta.get(doc_type),
                exists=meta.get(doc_type) is not None,
            )
            for doc_type in META_DOC_TYPES
        }
    )


@router.put("/{project_id}/meta-docs/{doc_type}", response_model=MetaDocResponse)
async def save_meta_doc(
    project_id: str,
    doc_type: str,
    request: MetaDocUpdateRequest,
    _: UserInfo = Depends(require_admin),
):
    project = get_project(project_id)
    update_meta_doc(project_id, doc_type, request.content)
    await index_meta_doc(
        project.slug,
        doc_type,
        request.content,
        collection_name=project.rag_config.collection_name,
    )
    return MetaDocResponse(doc_type=doc_type, content=request.content, exists=True)


@router.post("/{project_id}/meta-docs/{doc_type}/generate", response_model=MetaDocDraftResponse)
async def generate_meta_doc(
    project_id: str,
    doc_type: str,
    _: UserInfo = Depends(require_admin),
):
    project = get_project(project_id)
    draft = await generate_meta_doc_draft(
        project_slug=project.slug,
        doc_type=doc_type,
        collection_name=project.rag_config.collection_name,
    )
    return MetaDocDraftResponse(draft=draft)
