from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_PROMPTS: dict[str, str] = {
    "project_summary": """당신은 기술 문서 작성 전문가입니다. 아래 소스코드 청크를 분석하여 한국어로 RAG_PROJECT_SUMMARY.md를 작성하세요.

다음 섹션을 포함하세요:
# 프로젝트명
# 시스템 목적
이 시스템이 무엇인지, 누가 사용하는지 설명하세요.
# 업무 도메인
이 시스템이 속한 업무 영역(예: 채용관리, 민원, CMS, ERP 등)을 설명하세요.
# 주요 기능
핵심 기능 목록 (불릿 리스트)
# 사용자 역할
관리자/사용자 등 역할 구분
# 기술 스택
프레임워크, DB, 언어 등
# 운영 형태
시스템 운영 방식 (예: 웹 기반 관리자 포털)

소스코드 청크:
---
{sample_content}
---

한국어로 작성하세요. 추측보다 코드에서 확인된 사실을 우선하세요.""",

    "menu_map": """당신은 기술 문서 작성 전문가입니다. 아래 소스코드 청크(Controller URL 매핑, JSP 화면 등)를 분석하여 메뉴 구조도를 작성하세요.

형식:
# 메뉴 구조

## 관리자 메뉴
- 대메뉴
  - 하위메뉴

## 사용자 메뉴
- 대메뉴
  - 하위메뉴

소스코드 청크:
---
{sample_content}
---

Controller URL 패턴과 JSP 경로를 바탕으로 메뉴 계층을 추론하세요. 확인되지 않은 메뉴는 추가하지 마세요.""",

    "feature_map": """당신은 기술 문서 작성 전문가입니다. 아래 소스코드 청크를 분석하여 업무 기능 목록을 작성하세요.

형식:
# 주요 기능 목록

## 인증/권한
- 기능명: 설명

## [업무 도메인별 그룹]
- 기능명: 설명

소스코드 청크:
---
{sample_content}
---

Service 클래스와 Controller 메서드를 바탕으로 실제 구현된 기능만 나열하세요.""",

    "db_schema_summary": """당신은 기술 문서 작성 전문가입니다. 아래 MyBatis Mapper XML과 SQL 청크를 분석하여 DB 스키마 요약을 작성하세요.

형식:
# DB 스키마 요약

## 테이블 목록
| 테이블명 | 설명 | 주요 컬럼 |
|---------|-----|---------|
| TB_XXX | 설명 | 컬럼들 |

## 주요 관계
- 테이블 간 관계 설명

소스코드 청크:
---
{sample_content}
---

SQL의 FROM, JOIN, INSERT INTO 등에서 테이블명을 추출하세요.""",

    "architecture": """당신은 기술 문서 작성 전문가입니다. 아래 소스코드 청크를 분석하여 아키텍처 문서를 작성하세요.

형식:
# 시스템 아키텍처

## 레이어 구조
Controller → Service → Mapper → DB 형태로 설명

## 주요 컴포넌트
각 레이어의 주요 클래스/파일

## 기술 스택
프레임워크, 미들웨어, DB 등

## 외부 연동
외부 시스템 연동이 있다면 설명

소스코드 청크:
---
{sample_content}
---

pom.xml 의존성과 패키지 구조를 바탕으로 실제 아키텍처를 설명하세요.""",
}

_CHUNK_TYPE_QUERY: dict[str, list[str]] = {
    "project_summary": ["config_file", "java_class"],
    "menu_map": ["java_class", "jsp_section"],
    "feature_map": ["java_class", "java_method"],
    "db_schema_summary": ["xml_query", "java_method"],
    "architecture": ["config_file", "java_class"],
}


async def generate_meta_doc_draft(
    project_slug: str,
    doc_type: str,
    collection_name: str | None = None,
) -> str:
    from app.services.llm import generate as llm_generate
    from app.services.retrieval import get_client, _point_to_chunk
    from app.core.config import settings
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = get_client()
    coll = collection_name or settings.QDRANT_COLLECTION
    chunk_types = _CHUNK_TYPE_QUERY.get(doc_type, ["java_class", "config_file"])

    sample_chunks: list[dict] = []
    for ct in chunk_types:
        points, _ = await client.scroll(
            collection_name=coll,
            scroll_filter=Filter(must=[
                FieldCondition(key="project_slug", match=MatchValue(value=project_slug)),
                FieldCondition(key="chunk_type", match=MatchValue(value=ct)),
            ]),
            limit=8,
            with_payload=True,
            with_vectors=False,
        )
        sample_chunks.extend(_point_to_chunk(p) for p in points)
        if len(sample_chunks) >= 16:
            break

    if not sample_chunks:
        logger.warning("meta_doc_generator: no chunks found for %s/%s", project_slug, doc_type)
        return _empty_template(doc_type, project_slug)

    sample_content = "\n\n---\n\n".join(
        f"[{c.get('relative_path', c.get('chunk_type', ''))}]\n{str(c.get('text', ''))[:800]}"
        for c in sample_chunks[:14]
    )

    prompt_template = _PROMPTS.get(doc_type)
    if not prompt_template:
        return _empty_template(doc_type, project_slug)

    prompt = prompt_template.format(sample_content=sample_content)
    try:
        draft = await llm_generate(prompt, chunks=[], history=[])
        return draft or _empty_template(doc_type, project_slug)
    except Exception as exc:
        logger.warning("meta_doc_generator LLM call failed for %s/%s: %s", project_slug, doc_type, exc)
        return _empty_template(doc_type, project_slug)


def _empty_template(doc_type: str, project_slug: str) -> str:
    templates = {
        "project_summary": f"# {project_slug} — 프로젝트 요약\n\n## 시스템 목적\n<!-- 설명을 입력하세요 -->\n\n## 업무 도메인\n<!-- 설명을 입력하세요 -->\n\n## 주요 기능\n- \n\n## 기술 스택\n- \n",
        "menu_map": "# 메뉴 구조\n\n## 관리자 메뉴\n- \n\n## 사용자 메뉴\n- \n",
        "feature_map": "# 주요 기능 목록\n\n## 인증/권한\n- \n\n## 주요 기능\n- \n",
        "db_schema_summary": "# DB 스키마 요약\n\n## 테이블 목록\n| 테이블명 | 설명 |\n|---------|-----|\n| | |\n",
        "architecture": "# 시스템 아키텍처\n\n## 레이어 구조\nController → Service → Mapper → DB\n\n## 기술 스택\n- \n",
    }
    return templates.get(doc_type, f"# {doc_type}\n\n<!-- 내용을 입력하세요 -->\n")
