from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import ChatRequest, ChatResponse, Source, UserInfo
from app.core.auth import get_current_user
from app.services.retrieval import retrieve
from app.services.llm import generate

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, user: UserInfo = Depends(get_current_user)):
    # admin은 전체 검색, 일반 사용자는 자기 부서만
    department = None if user.is_admin else user.department
    if req.department and user.is_admin:
        department = req.department  # admin이 부서 지정한 경우

    chunks = await retrieve(req.query, department=department, top_n=5)

    if not chunks:
        return ChatResponse(
            answer="관련 문서를 찾지 못했습니다.",
            sources=[],
            found=False,
        )

    answer = await generate(req.query, chunks)
    sources = [
        Source(
            file=c.get("file", ""),
            page=c.get("page", 0),
            section=c.get("section", ""),
            score=c.get("score", 0.0),
        )
        for c in chunks
    ]
    return ChatResponse(answer=answer, sources=sources, found=True)
