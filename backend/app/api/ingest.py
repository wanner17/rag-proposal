import os
import shutil
import subprocess
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.models.schemas import DocumentMetadata, UserInfo
from app.core.auth import get_current_user
from app.services.document_processor import extract_pages, semantic_chunk
from app.services.retrieval import index_chunks
from app.services.projects import get_project, get_default_project

router = APIRouter(prefix="/ingest", tags=["ingest"])

UPLOAD_DIR = "/app/documents"


@router.post("")
async def ingest(
    files: list[UploadFile] = File(...),
    project_id: str | None = Form(None),
    user: UserInfo = Depends(get_current_user),
):
    project = get_project(project_id) if project_id else get_default_project()
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    total_chunks = 0
    results = []
    for file in files:
        save_path = f"{UPLOAD_DIR}/{file.filename}"
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        metadata = DocumentMetadata(
            file=file.filename,
            page=0,
            department=user.department,
        )

        try:
            pages = extract_pages(save_path)
            chunks = semantic_chunk(pages, metadata)
            if not chunks:
                results.append({"filename": file.filename, "error": "텍스트를 추출할 수 없습니다"})
                continue
            chunk_dicts = [c.model_dump() for c in chunks]
            for chunk in chunk_dicts:
                chunk["project_slug"] = project.slug
            await index_chunks(chunk_dicts, collection_name=project.rag_config.collection_name)
            total_chunks += len(chunks)
            results.append({"filename": file.filename, "chunks_indexed": len(chunks)})
        except subprocess.CalledProcessError:
            results.append({"filename": file.filename, "error": "변환 실패. LibreOffice 상태를 확인하세요."})

    return {"chunks_indexed": total_chunks, "files": results}
