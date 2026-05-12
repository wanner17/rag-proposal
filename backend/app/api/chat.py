import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, ChatResponse, Source, UserInfo
from app.core.auth import get_current_user, resolve_department_scope
from app.services.retrieval import retrieve_with_critic
from app.services.llm import generate, generate_stream

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, user: UserInfo = Depends(get_current_user)):
    department = resolve_department_scope(user, req.department)

    critic_result = await retrieve_with_critic(req.query, department=department, top_n=5)
    chunks = critic_result.selected.reranked

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


@router.post("/stream")
async def chat_stream(req: ChatRequest, user: UserInfo = Depends(get_current_user)):
    """SSE 스트리밍 엔드포인트. 먼저 검색하고 LLM 답변을 토큰 단위로 스트리밍."""
    department = resolve_department_scope(user, req.department)

    critic_result = await retrieve_with_critic(req.query, department=department, top_n=5)
    chunks = critic_result.selected.reranked
    sources = [
        Source(file=c.get("file", ""), page=c.get("page", 0),
               section=c.get("section", ""), score=c.get("score", 0.0))
        for c in chunks
    ]

    async def event_stream():
        # 출처를 먼저 전송
        yield f"data: {json.dumps({'sources': [s.model_dump() for s in sources]})}\n\n"
        # LLM 토큰 스트리밍
        async for chunk in generate_stream(req.query, chunks):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")
