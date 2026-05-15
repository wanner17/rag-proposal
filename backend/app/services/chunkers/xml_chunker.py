from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from app.services.chunkers.base import BaseChunker, ChunkResult
from app.services.chunkers.line_chunker import LineChunker

# MyBatis mapper SQL tags
_MYBATIS_SQL_TAGS = {"select", "insert", "update", "delete", "sql"}

# Config files emitted as a single chunk
_CONFIG_FILE_PATTERNS = re.compile(
    r"(?:web\.xml|pom\.xml|applicationContext|spring.*\.xml|logback.*\.xml|context.*\.xml)",
    re.IGNORECASE,
)


class XmlChunker(BaseChunker):
    def __init__(self, filename: str = ""):
        self.filename = filename

    def chunk(self, content: str, max_chunk_chars: int = 8000) -> list[ChunkResult]:
        try:
            return self._chunk_xml(content, max_chunk_chars)
        except Exception:
            return LineChunker().chunk(content, max_chunk_chars)

    def _chunk_xml(self, content: str, max_chunk_chars: int) -> list[ChunkResult]:
        lines = content.splitlines()

        # Config files → single chunk
        if _CONFIG_FILE_PATTERNS.search(self.filename):
            text = content.strip()[:max_chunk_chars]
            if text:
                return [ChunkResult(
                    text=text,
                    start_line=1,
                    end_line=len(lines),
                    chunk_type="config_file",
                )]

        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return LineChunker().chunk(content, max_chunk_chars)

        results: list[ChunkResult] = []

        # MyBatis mapper: chunk per SQL statement
        if self._is_mybatis_mapper(root):
            for child in root:
                tag = child.tag.split("}")[-1].lower()  # strip namespace
                if tag in _MYBATIS_SQL_TAGS:
                    stmt_id = child.get("id", "")
                    text = ET.tostring(child, encoding="unicode").strip()[:max_chunk_chars]
                    if text:
                        start, end = self._find_element_lines(content, lines, stmt_id, tag)
                        results.append(ChunkResult(
                            text=text,
                            start_line=start,
                            end_line=end,
                            chunk_type="xml_query",
                            method_name=stmt_id,
                        ))
            if results:
                return results

        # Spring beans: chunk per <bean> definition
        if self._is_spring_beans(root):
            for child in root:
                tag = child.tag.split("}")[-1].lower()
                if tag == "bean":
                    class_attr = child.get("class", child.get("id", ""))
                    text = ET.tostring(child, encoding="unicode").strip()[:max_chunk_chars]
                    if text:
                        class_name = class_attr.split(".")[-1] if class_attr else None
                        results.append(ChunkResult(
                            text=text,
                            start_line=1,
                            end_line=len(lines),
                            chunk_type="xml_bean",
                            class_name=class_name,
                        ))
            if results:
                return results

        # Fallback: line range
        return LineChunker().chunk(content, max_chunk_chars)

    def _is_mybatis_mapper(self, root: ET.Element) -> bool:
        tag = root.tag.split("}")[-1].lower()
        return tag == "mapper" or root.get("namespace") is not None

    def _is_spring_beans(self, root: ET.Element) -> bool:
        tag = root.tag.split("}")[-1].lower()
        return tag == "beans"

    def _find_element_lines(
        self, content: str, lines: list[str], element_id: str, tag: str
    ) -> tuple[int, int]:
        pattern = re.compile(rf"<{tag}[^>]*\bid\s*=\s*[\"']{re.escape(element_id)}[\"']")
        for i, line in enumerate(lines):
            if pattern.search(line):
                return i + 1, min(i + 30, len(lines))
        return 1, len(lines)
