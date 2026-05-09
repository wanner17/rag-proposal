import json
import httpx
from typing import AsyncGenerator
from app.core.config import settings

SYSTEM_PROMPT = """당신은 공공기관 SI 제안 전문가다.
반드시 제공된 참고 문서를 기반으로만 답변하라.
문서에 없는 내용은 절대 추측하지 마라.
답변 시 반드시 출처(파일명, 페이지)를 함께 표시하라.
관련 문서가 없으면 '관련 문서를 찾지 못했습니다'라고만 답하라."""

LLM_PARAMS = {
    "model": settings.VLLM_MODEL,
    "max_tokens": 300,
    "temperature": 0.1,
}


def _build_messages(query: str, chunks: list[dict]) -> list[dict]:
    context = "\n\n---\n\n".join(
        f"[출처: {c['file']} p{c['page']}]\n{c['text']}" for c in chunks
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"참고 문서:\n{context}\n\n질문: {query} /no_think"},
    ]


async def generate(query: str, chunks: list[dict]) -> str:
    if not chunks:
        return "관련 문서를 찾지 못했습니다."

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            f"{settings.VLLM_HOST}/chat/completions",
            json={"messages": _build_messages(query, chunks), **LLM_PARAMS},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def generate_stream(query: str, chunks: list[dict]) -> AsyncGenerator[str, None]:
    """SSE 형식으로 토큰을 스트리밍. 각 줄: 'data: <json>\n\n'"""
    if not chunks:
        yield f"data: {json.dumps({'token': '관련 문서를 찾지 못했습니다.'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream(
            "POST",
            f"{settings.VLLM_HOST}/chat/completions",
            json={"messages": _build_messages(query, chunks), "stream": True, **LLM_PARAMS},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                    token = data["choices"][0]["delta"].get("content", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                except (KeyError, json.JSONDecodeError):
                    continue

    yield "data: [DONE]\n\n"
