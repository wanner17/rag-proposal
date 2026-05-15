from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class QuestionType(str, Enum):
    PROJECT_OVERVIEW = "project_overview"
    FEATURE_FLOW     = "feature_flow"
    DB_SQL_TRACING   = "db_sql_tracing"
    UI_JSP           = "ui_jsp"
    DEPLOY_CONFIG    = "deploy_config"
    ERROR_DEBUG      = "error_debug"
    GENERAL          = "general"


@dataclass(frozen=True)
class ClassificationResult:
    question_type: QuestionType
    confidence: float  # top-score / total-score across all matched types


_KEYWORD_RULES: dict[QuestionType, list[str]] = {
    QuestionType.PROJECT_OVERVIEW: [
        "전체", "개요", "아키텍처", "구조", "overview", "architecture",
        "어떤 시스템", "어떤 프로젝트", "주요 기능", "소개", "설명해줘",
        "무슨 시스템", "무슨 프로젝트", "어떤 역할",
        # site / service / app variants — previously missing
        "무슨 사이트", "어떤 사이트", "이 사이트", "사이트야", "사이트인",
        "어떤 서비스", "무슨 서비스", "서비스 소개", "사이트 소개",
        "무슨 앱", "어떤 앱", "이 시스템", "이 프로젝트",
    ],
    QuestionType.DB_SQL_TRACING: [
        "쿼리", "sql", "테이블", "컬럼", "조회", "insert", "update",
        "mapper", "mybatis", "데이터베이스", " db ", "dao", "repository",
        "select ", "where ", " join ", "스키마",
    ],
    QuestionType.FEATURE_FLOW: [
        "흐름", "플로우", "처리 과정", "로직", "flow", "process",
        "어떻게 동작", "순서", "단계", "기능 구현", "어떻게 처리",
    ],
    QuestionType.UI_JSP: [
        "화면", ".jsp", " ui ", "페이지", "폼", "버튼", "그리드",
        "화면단", "프론트", " 뷰 ", "view", "레이아웃",
    ],
    QuestionType.DEPLOY_CONFIG: [
        "배포", "설정 파일", "properties", "web.xml", "pom.xml",
        "환경 설정", "config", "deploy", "서버 설정", "포트",
    ],
    QuestionType.ERROR_DEBUG: [
        "에러", "오류", "예외", "exception", "npe", " 500 ", "디버그",
        "왜 안", "문제", "실패", "안 됨", "오작동", "버그",
    ],
}


def classify_question(query: str) -> QuestionType:
    return _classify(query).question_type


def classify_question_with_confidence(query: str) -> ClassificationResult:
    return _classify(query)


def _classify(query: str) -> ClassificationResult:
    q = " " + query.lower() + " "
    scores: dict[QuestionType, int] = {}
    for q_type, keywords in _KEYWORD_RULES.items():
        score = sum(1 for kw in keywords if kw in q)
        if score > 0:
            scores[q_type] = score

    if not scores:
        return ClassificationResult(QuestionType.GENERAL, 0.0)

    total = sum(scores.values())
    sorted_scores = sorted(scores.values(), reverse=True)
    best_type = max(scores, key=lambda t: scores[t])
    confidence = round(sorted_scores[0] / total, 4)

    if len(sorted_scores) == 1 or sorted_scores[0] >= sorted_scores[1] * 1.5:
        return ClassificationResult(best_type, confidence)

    return ClassificationResult(QuestionType.GENERAL, 0.0)
