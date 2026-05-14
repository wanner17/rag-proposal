import json
import logging
import asyncio
import httpx
import re
from typing import AsyncGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 업로드된 업무 문서를 분석하는 RAG 질의응답 전문가다.
제공된 참고 문서를 바탕으로 질문에 충실하고 상세하게 답변하라.

답변 원칙:
- 핵심 내용을 먼저 요약한 후, 세부 내용을 구체적으로 설명하라.
- 수치, 일정, 기술 스펙 등 구체적인 정보가 있으면 반드시 포함하라.
- 관련 내용이 여러 문서에 걸쳐 있으면 종합하여 설명하라.
- 각 주요 내용마다 출처(파일명, 페이지)를 표시하라.
- 문서에 없는 내용은 추측하지 말고 '문서에서 확인되지 않음'으로 명시하라.
- 관련 문서가 전혀 없으면 '관련 문서를 찾지 못했습니다'라고만 답하라.
- 답변을 시작하기 전에 출력 가능한 분량을 고려해 다룰 범위를 내부적으로 정리하고, 제한된 토큰 안에서 완결 가능한 핵심 내용만 선택하라.
- 답변이 길어질 것 같으면 모든 내용을 억지로 포함하지 말고, 핵심 요약과 가장 중요한 근거 3~5개만 우선 작성하라.
- 마크다운 표는 사용하지 말라. 표는 길어져 중간에 끊기기 쉬우므로 번호 목록과 짧은 bullet만 사용하라.
- 각 항목은 제목 1줄, 설명 1~2문장, 출처 1줄 이내로 제한하라.
- 문장이나 항목이 중간에 끊기지 않도록 완결된 문장과 완결된 목록으로 끝내라. 마지막 줄은 반드시 '요약: 위 항목을 우선 반영하는 것이 적절합니다.' 형식의 완결 문장으로 끝내라.
- 세부 내용이 더 필요하면 마지막에 '더 자세한 항목을 지정해 다시 질문해 주세요.'라고 안내하라."""

LLM_PARAMS = {
    "model": settings.LLM_MODEL,
    "max_tokens": 1800,
    "temperature": 0.1,
}
COMPACT_LLM_PARAMS = {**LLM_PARAMS, "max_tokens": 1200}
CHUNK_TEXT_LIMIT = 1200
COMPACT_CHUNK_TEXT_LIMIT = 700
COMPACT_CHUNK_COUNT = 3
LLM_RETRY_DELAYS = (0.75, 1.5)
MIN_COMPLETE_ANSWER_CHARS = 180

LLM_UNAVAILABLE_MESSAGE = (
    "답변 생성 모델에 연결하지 못했습니다. "
    "llama.cpp 서버가 실행 중인지와 LLM_HOST 설정을 확인해 주세요."
)
LLM_INTERRUPTED_MESSAGE = (
    "\n\n※ 답변 생성이 중간에 중단되었습니다. 위 내용은 부분 응답일 수 있으니 다시 시도해 주세요."
)
OUTPUT_LIMIT_MESSAGE = (
    "\n\n※ 출력 한도에 도달해 답변을 압축했습니다. 더 자세한 항목을 지정해 다시 질문해 주세요."
)
INCOMPLETE_RETRY_NOTICE = "※ 답변이 너무 짧아 번호 목록 형식으로 다시 생성합니다."
RETRY_ITEM_KEYWORDS = ("보안", "DR", "재해", "단계별", "이행", "운영 조직", "장애 대응", "장애")
RETRY_REQUIRED_ITEMS = (
    ("보안", ("보안",)),
    ("DR", ("DR", "재해 복구")),
    ("단계별 이행계획", ("단계별 이행계획", "단계별", "이행계획")),
    ("운영 조직", ("운영 조직", "운영조직")),
    ("장애 대응", ("장애 대응", "장애대응")),
)


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}\n...[근거 일부 생략]"


def _build_messages(
    query: str, chunks: list[dict], chunk_text_limit: int = CHUNK_TEXT_LIMIT
) -> list[dict]:
    context = "\n\n---\n\n".join(
        f"[출처: {_source_label(c)}]\n{_truncate_text(c['text'], chunk_text_limit)}"
        for c in chunks
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"참고 문서:\n{context}\n\n질문: {query} /no_think"},
    ]


def _source_label(chunk: dict) -> str:
    if chunk.get("source_kind") == "source_code":
        relative_path = chunk.get("relative_path", "")
        start_line = chunk.get("start_line")
        end_line = chunk.get("end_line")
        if start_line and end_line:
            return f"{relative_path}:{start_line}-{end_line}"
        return relative_path
    return f"{chunk['file']} p{chunk['page']}"


def _requested_item_count(query: str) -> int:
    numbered_requests = re.findall(r"(?<!\d)([3-7])\s*개", query)
    if numbered_requests:
        return max(3, min(5, int(numbered_requests[-1])))

    required_items = _required_retry_items(query)
    if required_items:
        return max(3, min(5, len(required_items)))

    keyword_count = sum(1 for keyword in RETRY_ITEM_KEYWORDS if keyword in query)
    if "DR" in query and "재해" in query:
        keyword_count -= 1
    if "장애 대응" in query and "장애" in query:
        keyword_count -= 1
    return max(3, min(5, keyword_count))


def _required_retry_items(query: str) -> list[str]:
    items = []
    for item, aliases in RETRY_REQUIRED_ITEMS:
        if any(alias in query for alias in aliases):
            items.append(item)
    return items


def _completion_retry_query(query: str) -> str:
    item_count = _requested_item_count(query)
    required_items = _required_retry_items(query)
    required_instruction = (
        f"필수 항목은 {', '.join(required_items)}이며, 이 항목명을 다른 항목으로 대체하지 말라. "
        if required_items
        else ""
    )
    return (
        f"{query}\n\n"
        f"중요: 도입문 없이 바로 1번부터 {item_count}번까지 번호 목록으로 답하라. "
        f"정확히 {item_count}개 항목만 작성하라. 각 항목은 3줄만 사용하라: "
        "제목, 근거 강도, 한 문장 설명과 출처. "
        f"{required_instruction}"
        "마크다운 표와 긴 bullet을 쓰지 말라. "
        "마지막은 반드시 '요약: 위 항목을 우선 반영하는 것이 적절합니다.'로 끝내라."
    )


def _looks_incomplete_answer(answer: str, query: str | None = None) -> bool:
    normalized = answer.strip()
    if not normalized:
        return True
    required_count = _requested_item_count(query) if query else 3
    numbered_count = sum(
        1
        for index in range(1, required_count + 1)
        for marker in (f"{index}.", f"{index})")
        if marker in normalized
    )
    has_completion_marker = "요약:" in normalized or "더 자세한 항목을 지정해 다시 질문" in normalized
    ends_like_intro = normalized.endswith(("다음과", "다음과 같습니다", "다음과 같습니다.", "정리하면 다음과 같습니다."))
    return (
        len(normalized) < MIN_COMPLETE_ANSWER_CHARS
        or numbered_count < required_count
        or not has_completion_marker
        or ends_like_intro
    )


def _has_completion_marker(answer: str) -> bool:
    return "요약:" in answer or "더 자세한 항목을 지정해 다시 질문" in answer


async def _iter_stream_tokens(
    client: httpx.AsyncClient,
    query: str,
    chunks: list[dict],
    params: dict | None = None,
    chunk_text_limit: int = CHUNK_TEXT_LIMIT,
) -> AsyncGenerator[str, None]:
    async with client.stream(
        "POST",
        f"{settings.LLM_HOST}/chat/completions",
        json={
            "messages": _build_messages(query, chunks, chunk_text_limit),
            "stream": True,
            **(params or LLM_PARAMS),
        },
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
                choice = data["choices"][0]
                token = choice["delta"].get("content", "")
                if token:
                    yield token
                if choice.get("finish_reason") == "length":
                    yield OUTPUT_LIMIT_MESSAGE
            except (KeyError, json.JSONDecodeError):
                continue


async def _generate_from_stream(query: str, chunks: list[dict]) -> str:
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            tokens = []
            async for token in _iter_stream_tokens(client, query, chunks):
                tokens.append(token)
            return "".join(tokens) or LLM_UNAVAILABLE_MESSAGE
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            logger.warning("LLM streaming fallback failed with %s; retrying compact request", exc.response.status_code)
            return await _generate_from_compact_stream(query, chunks)
        logger.exception("LLM streaming fallback failed")
        return LLM_UNAVAILABLE_MESSAGE
    except httpx.HTTPError:
        logger.exception("LLM streaming fallback failed")
        return LLM_UNAVAILABLE_MESSAGE


async def _generate_from_compact_stream(query: str, chunks: list[dict]) -> str:
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            tokens = []
            async for token in _iter_stream_tokens(
                client,
                query,
                chunks[:COMPACT_CHUNK_COUNT],
                COMPACT_LLM_PARAMS,
                COMPACT_CHUNK_TEXT_LIMIT,
            ):
                tokens.append(token)
            return "".join(tokens) or LLM_UNAVAILABLE_MESSAGE
    except httpx.HTTPError:
        logger.exception("LLM compact streaming request failed")
        return LLM_UNAVAILABLE_MESSAGE


async def generate_tokens(query: str, chunks: list[dict]) -> AsyncGenerator[str, None]:
    if not chunks:
        yield "관련 문서를 찾지 못했습니다."
        return

    for attempt, delay in enumerate((0.0, *LLM_RETRY_DELAYS), start=1):
        if delay:
            await asyncio.sleep(delay)
        yielded = False
        tokens = []
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async for token in _iter_stream_tokens(client, query, chunks):
                    yielded = True
                    tokens.append(token)
                    yield token
                if not yielded:
                    yield LLM_UNAVAILABLE_MESSAGE
                elif _looks_incomplete_answer("".join(tokens), query):
                    async for retry_token in _retry_incomplete_answer(query, chunks):
                        yield retry_token
                return
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500 and attempt <= len(LLM_RETRY_DELAYS):
                logger.warning(
                    "LLM streaming token request failed with %s; retrying after %.2fs",
                    exc.response.status_code,
                    LLM_RETRY_DELAYS[attempt - 1],
                )
                continue
            if exc.response.status_code >= 500:
                logger.warning(
                    "LLM streaming token request failed with %s after retries; retrying compact request",
                    exc.response.status_code,
                )
                async for token in _compact_stream_tokens(query, chunks):
                    yield token
                return
            logger.exception("LLM streaming token request failed")
            yield LLM_INTERRUPTED_MESSAGE if yielded else LLM_UNAVAILABLE_MESSAGE
            return
        except httpx.HTTPError:
            logger.exception("LLM streaming token request failed")
            yield LLM_INTERRUPTED_MESSAGE if yielded else LLM_UNAVAILABLE_MESSAGE
            return


async def _compact_stream_tokens(query: str, chunks: list[dict]) -> AsyncGenerator[str, None]:
    yielded = False
    tokens = []
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async for token in _iter_stream_tokens(
                client,
                query,
                chunks[:COMPACT_CHUNK_COUNT],
                COMPACT_LLM_PARAMS,
                COMPACT_CHUNK_TEXT_LIMIT,
            ):
                yielded = True
                tokens.append(token)
                yield token
            if yielded:
                if not _has_completion_marker("".join(tokens)):
                    yield "\n\n요약: 위 항목을 우선 반영하는 것이 적절합니다."
                yield "\n\n※ LLM 서버 제한으로 상위 근거만 사용해 압축 답변했습니다."
            else:
                yield LLM_UNAVAILABLE_MESSAGE
    except httpx.HTTPError:
        logger.exception("LLM compact streaming token request failed")
        yield LLM_INTERRUPTED_MESSAGE if yielded else LLM_UNAVAILABLE_MESSAGE


async def _retry_incomplete_answer(query: str, chunks: list[dict]) -> AsyncGenerator[str, None]:
    yield f"\n\n{INCOMPLETE_RETRY_NOTICE}\n\n"
    async for token in _compact_stream_tokens(_completion_retry_query(query), chunks):
        yield token


async def generate(query: str, chunks: list[dict]) -> str:
    if not chunks:
        return "관련 문서를 찾지 못했습니다."

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{settings.LLM_HOST}/chat/completions",
                json={"messages": _build_messages(query, chunks), **LLM_PARAMS},
            )
            resp.raise_for_status()
            choice = resp.json()["choices"][0]
            content = choice["message"]["content"]
            if choice.get("finish_reason") == "length":
                return f"{content}{OUTPUT_LIMIT_MESSAGE}"
            if _looks_incomplete_answer(content, query):
                retry = await _generate_from_compact_stream(_completion_retry_query(query), chunks)
                return f"{INCOMPLETE_RETRY_NOTICE}\n\n{retry}"
            return content
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            logger.warning(
                "LLM non-stream completion failed with %s; retrying with streaming completion",
                exc.response.status_code,
            )
            return await _generate_from_stream(query, chunks)
        return LLM_UNAVAILABLE_MESSAGE
    except httpx.HTTPError:
        logger.exception("LLM completion request failed")
        return LLM_UNAVAILABLE_MESSAGE


async def generate_stream(query: str, chunks: list[dict]) -> AsyncGenerator[str, None]:
    """SSE 형식으로 토큰을 스트리밍. 각 줄: 'data: <json>\n\n'"""
    if not chunks:
        yield f"data: {json.dumps({'token': '관련 문서를 찾지 못했습니다.'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    try:
        async for token in generate_tokens(query, chunks):
            yield f"data: {json.dumps({'token': token})}\n\n"
    except httpx.HTTPError:
        logger.exception("LLM streaming response failed")
        yield f"data: {json.dumps({'token': LLM_UNAVAILABLE_MESSAGE})}\n\n"

    yield "data: [DONE]\n\n"
