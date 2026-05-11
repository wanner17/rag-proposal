from app.services.llm import SYSTEM_PROMPT
from app.services.proposal_llm import PROPOSAL_SYSTEM_PROMPT


def test_chat_prompt_guides_complete_bounded_answers():
    assert "중간에 끊기지 않도록" in SYSTEM_PROMPT
    assert "핵심 요약" in SYSTEM_PROMPT
    assert "더 자세한 항목을 지정해 다시 질문" in SYSTEM_PROMPT


def test_proposal_prompt_guides_complete_bounded_drafts():
    assert "중간에 끊기지 않도록" in PROPOSAL_SYSTEM_PROMPT
    assert "핵심 문단" in PROPOSAL_SYSTEM_PROMPT
    assert "더 자세히 확장할 섹션" in PROPOSAL_SYSTEM_PROMPT
