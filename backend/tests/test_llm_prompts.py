import asyncio
import json

import httpx

from app.services.llm import LLM_PARAMS, SYSTEM_PROMPT
from app.services.llm import LLM_UNAVAILABLE_MESSAGE, generate, generate_stream
from app.services.proposal_llm import PROPOSAL_SYSTEM_PROMPT


def test_chat_prompt_guides_complete_bounded_answers():
    assert "중간에 끊기지 않도록" in SYSTEM_PROMPT
    assert "핵심 요약" in SYSTEM_PROMPT
    assert "출력 가능한 분량" in SYSTEM_PROMPT
    assert "다룰 범위를 내부적으로 정리" in SYSTEM_PROMPT
    assert "완결 가능한 핵심 내용" in SYSTEM_PROMPT
    assert "마크다운 표는 사용하지 말라" in SYSTEM_PROMPT
    assert "번호 목록과 짧은 bullet" in SYSTEM_PROMPT
    assert LLM_PARAMS["max_tokens"] >= 1800
    assert "더 자세한 항목을 지정해 다시 질문" in SYSTEM_PROMPT


def test_proposal_prompt_guides_complete_bounded_drafts():
    assert "중간에 끊기지 않도록" in PROPOSAL_SYSTEM_PROMPT
    assert "핵심 문단" in PROPOSAL_SYSTEM_PROMPT
    assert "출력 가능한 분량" in PROPOSAL_SYSTEM_PROMPT
    assert "각 섹션의 범위를 내부적으로 정리" in PROPOSAL_SYSTEM_PROMPT
    assert "완결 가능한 핵심 내용" in PROPOSAL_SYSTEM_PROMPT
    assert "더 자세히 확장할 섹션" in PROPOSAL_SYSTEM_PROMPT


def test_stream_returns_sse_error_instead_of_raising_on_llm_connection_failure(monkeypatch):
    class FailingStream:
        async def __aenter__(self):
            raise httpx.ConnectError("llm unavailable")

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, *args, **kwargs):
            return FailingStream()

    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", FailingClient)

    async def collect():
        chunks = []
        async for chunk in generate_stream("질문", [{"file": "a.pdf", "page": 1, "text": "근거"}]):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(collect())

    payload = json.loads(chunks[0].removeprefix("data: ").strip())
    assert payload["token"] == LLM_UNAVAILABLE_MESSAGE
    assert chunks[-1] == "data: [DONE]\n\n"


def test_generate_returns_error_message_on_llm_connection_failure(monkeypatch):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("llm unavailable")

    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", FailingClient)

    answer = asyncio.run(generate("질문", [{"file": "a.pdf", "page": 1, "text": "근거"}]))

    assert answer == LLM_UNAVAILABLE_MESSAGE


def test_generate_retries_with_streaming_when_non_stream_llm_returns_500(monkeypatch):
    class FailingResponse:
        status_code = 500

        def raise_for_status(self):
            request = httpx.Request("POST", "http://llm/chat/completions")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("server error", request=request, response=response)

    class StreamingResponse:
        def __init__(self):
            self.lines = [
                'data: {"choices":[{"delta":{"content":"재시도 "}}]}',
                'data: {"choices":[{"delta":{"content":"성공"}}]}',
                "data: [DONE]",
            ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for line in self.lines:
                yield line

    class FallbackClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            return FailingResponse()

        def stream(self, *args, **kwargs):
            return StreamingResponse()

    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", FallbackClient)

    answer = asyncio.run(generate("질문", [{"file": "a.pdf", "page": 1, "text": "근거"}]))

    assert answer == "재시도 성공"
