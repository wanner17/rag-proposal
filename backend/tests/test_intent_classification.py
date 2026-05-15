import pytest
from app.services.llm import _classify_intent, get_retrieval_config, INTENT_RETRIEVAL_CONFIG


@pytest.mark.parametrize("query,expected", [
    ("이 시스템 전체 아키텍처를 설명해줘", "system_overview"),
    ("전반적인 구조가 어떻게 되나요?", "system_overview"),
    ("인증 모듈 어떻게 구현됨?", "code_structure"),
    ("jwt 토큰 처리 코드 보여줘", "code_structure"),
    ("api 엔드포인트 목록이 뭐야?", "code_structure"),
    ("A 제안서 납기일이 언제야?", "specific_fact"),
    ("계약 비용이 얼마야?", "specific_fact"),
    ("클라우드 관련 제안서 있어?", "general"),
    ("최근 제안서 검색해줘", "general"),
    ("개요를 알려줘", "system_overview"),
])
def test_classify_intent(query, expected):
    assert _classify_intent(query) == expected


def test_get_retrieval_config_returns_valid_config():
    for intent in ("specific_fact", "code_structure", "system_overview", "general"):
        config = INTENT_RETRIEVAL_CONFIG[intent]
        assert "top_k" in config
        assert "rerank_top_n" in config
        assert "score_threshold" in config


def test_get_retrieval_config_system_overview():
    config = get_retrieval_config("전체 시스템 아키텍처 설명해줘")
    assert config["top_k"] == 100
    assert config["rerank_top_n"] == 20
    assert config["score_threshold"] is None


def test_get_retrieval_config_code_structure():
    config = get_retrieval_config("인증 코드 어떻게 구현됨?")
    assert config["top_k"] == 50
    assert config["score_threshold"] == 0.1


def test_get_retrieval_config_specific_fact():
    config = get_retrieval_config("납기일이 언제야?")
    assert config["top_k"] == 10
    assert config["score_threshold"] == 0.4


def test_each_intent_type_covered():
    intents = {_classify_intent(q) for q in [
        "전체 아키텍처",
        "코드 구현 방식",
        "납기 얼마",
        "제안서 검색",
    ]}
    assert intents == {"system_overview", "code_structure", "specific_fact", "general"}
