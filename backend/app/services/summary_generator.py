from __future__ import annotations

import logging
from pathlib import Path

from app.services.source_processor import SUMMARY_FILENAME

logger = logging.getLogger(__name__)

_DRAFT_PROMPT_TEMPLATE = """You are a technical documentation assistant. Based on the following source files from a project, write a concise RAG_PROJECT_SUMMARY.md in Korean and English.

The summary must include these sections:
# 프로젝트 개요 (Project Overview)
# 비즈니스 도메인 (Business Domain)
# 주요 기능 (Major Features)
# 기술 스택 (Tech Stack)
# 아키텍처 (Architecture Overview)
# 주요 패키지/모듈 (Key Packages/Modules)

Source files:
---
{sample_content}
---

Write the summary now. Be concise and factual. Use markdown formatting."""


def get_summary_path(repo_root: str) -> Path:
    return Path(repo_root) / SUMMARY_FILENAME


def read_summary(repo_root: str) -> str | None:
    path = get_summary_path(repo_root)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("summary read failed: %s", exc)
    return None


def write_summary(repo_root: str, content: str) -> None:
    path = get_summary_path(repo_root)
    path.write_text(content, encoding="utf-8")
    logger.info("summary written: %s", path)


async def generate_summary_draft(
    project_slug: str,
    repo_root: str,
    sample_chunks: list[dict] | None = None,
) -> str:
    """Generate a RAG_PROJECT_SUMMARY.md draft using LLM from sample source chunks."""
    from app.services.llm import generate as llm_generate

    if not sample_chunks:
        sample_chunks = _collect_sample_chunks(repo_root)

    sample_content = "\n\n---\n\n".join(
        f"[{c.get('relative_path', '')}]\n{c.get('text', '')[:1000]}"
        for c in sample_chunks[:12]
    )

    if not sample_content.strip():
        return _empty_template(project_slug)

    prompt = _DRAFT_PROMPT_TEMPLATE.format(sample_content=sample_content)
    try:
        draft = await llm_generate(prompt, chunks=[], history=[])
        return draft or _empty_template(project_slug)
    except Exception as exc:
        logger.warning("summary draft LLM call failed: %s", exc)
        return _empty_template(project_slug)


def _collect_sample_chunks(repo_root: str) -> list[dict]:
    """Collect representative files: pom.xml, web.xml, properties, top-level java."""
    from app.services.source_processor import detect_language

    priority_patterns = [
        "pom.xml", "web.xml", "application.properties",
        "application.yml", "README.md", "README.txt",
    ]
    root = Path(repo_root)
    chunks: list[dict] = []
    max_size = 4000

    # Priority files first
    for name in priority_patterns:
        for p in root.rglob(name):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")[:max_size]
                if text.strip():
                    chunks.append({"relative_path": p.relative_to(root).as_posix(), "text": text})
            except Exception:
                pass
            if len(chunks) >= 6:
                break

    # Fallback: top-level Java controller/service files
    if len(chunks) < 6:
        for p in root.rglob("*.java"):
            name = p.name.lower()
            if any(x in name for x in ("controller", "service", "application")):
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")[:max_size]
                    if text.strip():
                        chunks.append({"relative_path": p.relative_to(root).as_posix(), "text": text})
                except Exception:
                    pass
                if len(chunks) >= 12:
                    break

    return chunks


def _empty_template(project_slug: str) -> str:
    return f"""# {project_slug} — Project Summary

## 프로젝트 개요 (Project Overview)
<!-- 프로젝트의 목적과 역할을 기술하세요 -->

## 비즈니스 도메인 (Business Domain)
<!-- 비즈니스 영역과 주요 이해관계자를 기술하세요 -->

## 주요 기능 (Major Features)
<!-- 핵심 기능 목록 -->

## 기술 스택 (Tech Stack)
<!-- 프레임워크, DB, 외부 시스템 등 -->

## 아키텍처 (Architecture Overview)
<!-- 계층 구조, 주요 컴포넌트 -->

## 주요 패키지/모듈 (Key Packages/Modules)
<!-- 핵심 패키지와 역할 -->
"""
