import httpx
from app.core.config import settings


PROPOSAL_SYSTEM_PROMPT = """당신은 공공기관 SI 제안서 초안 작성 전문가다.
반드시 제공된 근거 문서만 사용하여 제안서 섹션/문단 초안을 작성하라.

출력 구조:
1. 요약
2. 요구/상황 해석
3. 제안 접근방안
4. 구현/운영 포인트
5. 일정/리스크
6. 근거 출처
7. 문서에서 확인되지 않는 공백/가정

규칙:
- 문서 근거가 없는 내용은 "문서에서 확인되지 않음"으로 명시한다.
- 각 주요 주장에는 파일명과 페이지를 함께 표시한다.
- 검색/점수 품질 평가는 하지 말고 초안 작성에 집중한다.
- 초안을 시작하기 전에 출력 가능한 분량을 고려해 각 섹션의 범위를 내부적으로 정리하고, 제한된 토큰 안에서 완결 가능한 핵심 내용만 선택하라.
- 초안이 길어질 것 같으면 모든 세부사항을 억지로 포함하지 말고, 각 섹션의 핵심 문단과 중요한 근거를 우선 작성한다.
- 문장, 섹션, 목록이 중간에 끊기지 않도록 완결된 형태로 끝낸다.
- 추가 상세가 필요한 경우 마지막에 "더 자세히 확장할 섹션을 지정해 주세요."라고 안내한다."""

LLM_PARAMS = {
    "model": settings.LLM_MODEL,
    "max_tokens": 1800,
    "temperature": 0.1,
}


def _build_messages(query: str, chunks: list[dict]) -> list[dict]:
    context = "\n\n---\n\n".join(
        f"[출처: {c.get('file', '')} p{c.get('page', 0)} / section: {c.get('section', '')}]\n{c.get('text', '')}"
        for c in chunks
    )
    return [
        {"role": "system", "content": PROPOSAL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"제안 요청:\n{query}\n\n근거 문서:\n{context}\n\n위 구조로 제안서 초안을 작성하라. /no_think",
        },
    ]


async def generate_proposal_draft(query: str, chunks: list[dict]) -> str:
    if not chunks:
        return "관련 제안서 근거 문서를 찾지 못했습니다."

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            f"{settings.LLM_HOST}/chat/completions",
            json={"messages": _build_messages(query, chunks), **LLM_PARAMS},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
