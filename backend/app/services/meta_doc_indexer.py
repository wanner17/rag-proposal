from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)

_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _chunk_id(project_slug: str, doc_type: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{project_slug}:{doc_type}"))


async def index_meta_doc(
    project_slug: str,
    doc_type: str,
    content: str,
    collection_name: str | None = None,
) -> None:
    """Delete old Qdrant chunk for this meta doc type then index the new content."""
    from app.services.retrieval import delete_meta_doc_chunk_type, index_chunks, ensure_collection
    from app.core.config import settings

    coll = collection_name or settings.QDRANT_COLLECTION
    await ensure_collection(coll)
    await delete_meta_doc_chunk_type(project_slug, doc_type, coll)

    chunk = {
        "chunk_id": _chunk_id(project_slug, doc_type),
        "text": content,
        "chunk_type": doc_type,
        "source_kind": "source_code",
        "project_slug": project_slug,
        "relative_path": f"RAG_{doc_type.upper()}.md",
        "language": "markdown",
        "start_line": 0,
        "end_line": 0,
        "file": f"RAG_{doc_type.upper()}.md",
        "page": 0,
        "section": doc_type,
        "department": "",
    }
    await index_chunks([chunk], collection_name=coll)
    logger.info("meta_doc_indexer: indexed %s for project %s", doc_type, project_slug)
