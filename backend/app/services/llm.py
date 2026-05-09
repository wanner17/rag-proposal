import json
import httpx
from typing import AsyncGenerator
from app.core.config import settings

SYSTEM_PROMPT = """당신은 공공기관 SI 제안서 전문 분석가다.
제공된 참고 문서를 바탕으로 질문에 충실하고 상세하게 답변하라.

답변 원칙:
- 핵심 내용을 먼저 요약한 후, 세부 내용을 구체적으로 설명하라.
- 수치, 일정, 기술 스펙 등 구체적인 정보가 있으면 반드시 포함하라.
- 관련 내용이 여러 문서에 걸쳐 있으면 종합하여 설명하라.
- 각 주요 내용마다 출처(파일명, 페이지)를 표시하라.
- 문서에 없는 내용은 추측하지 말고 '문서에서 확인되지 않음'으로 명시하라.
- 관련 문서가 전혀 없으면 '관련 문서를 찾지 못했습니다'라고만 답하라."""

LLM_PARAMS = {
    "model": settings.VLLM_MODEL,
    "max_tokens": 800,
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
