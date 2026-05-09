import httpx
from app.core.config import settings

SYSTEM_PROMPT = """당신은 공공기관 SI 제안 전문가다.
반드시 제공된 참고 문서를 기반으로만 답변하라.
문서에 없는 내용은 절대 추측하지 마라.
답변 시 반드시 출처(파일명, 페이지)를 함께 표시하라.
관련 문서가 없으면 '관련 문서를 찾지 못했습니다'라고만 답하라."""


async def generate(query: str, chunks: list[dict]) -> str:
    if not chunks:
        return "관련 문서를 찾지 못했습니다."

    context_parts = []
    for c in chunks:
        context_parts.append(f"[출처: {c['file']} p{c['page']}]\n{c['text']}")
    context = "\n\n---\n\n".join(context_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"참고 문서:\n{context}\n\n질문: {query}"},
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.VLLM_HOST}/chat/completions",
            json={
                "model": settings.VLLM_MODEL,
                "messages": messages,
                "max_tokens": 1024,
                "temperature": 0.1,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
