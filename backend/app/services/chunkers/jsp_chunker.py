from __future__ import annotations

import re
from app.services.chunkers.base import BaseChunker, ChunkResult
from app.services.chunkers.line_chunker import LineChunker

# Section boundary markers in JSP
_SECTION_MARKERS = re.compile(
    r"<!--\s*[=\-]{2,}\s*(.+?)\s*[=\-]{2,}\s*-->|"   # <!-- ===  SECTION NAME  === -->
    r"<%--\s*[=\-]{2,}\s*(.+?)\s*[=\-]{2,}\s*--%>",   # <%-- === SECTION NAME === --%>
    re.IGNORECASE,
)

# JSP structural tags that start a logical block
_BLOCK_TAGS = re.compile(
    r"<(form:form|c:forEach|c:if|c:choose|fn:|tiles:|s:|spring:)\b",
    re.IGNORECASE,
)

_MAX_SECTION_LINES = 120


class JspChunker(BaseChunker):
    def chunk(self, content: str, max_chunk_chars: int = 8000) -> list[ChunkResult]:
        try:
            return self._chunk_jsp(content, max_chunk_chars)
        except Exception:
            return LineChunker().chunk(content, max_chunk_chars)

    def _chunk_jsp(self, content: str, max_chunk_chars: int) -> list[ChunkResult]:
        lines = content.splitlines()
        section_starts: list[tuple[int, str]] = []

        for i, line in enumerate(lines):
            m = _SECTION_MARKERS.search(line)
            if m:
                label = (m.group(1) or m.group(2) or "section").strip()
                section_starts.append((i, label))

        if not section_starts:
            return self._chunk_by_blocks(lines, max_chunk_chars)

        results: list[ChunkResult] = []
        boundaries = [s for s, _ in section_starts] + [len(lines)]
        for i, (start_idx, label) in enumerate(section_starts):
            end_idx = boundaries[i + 1]
            chunk_lines = lines[start_idx:end_idx]
            text = "\n".join(chunk_lines).strip()[:max_chunk_chars]
            if text:
                results.append(ChunkResult(
                    text=text,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    chunk_type="jsp_section",
                    method_name=label,
                ))

        return results or LineChunker().chunk(content, max_chunk_chars)

    def _chunk_by_blocks(self, lines: list[str], max_chunk_chars: int) -> list[ChunkResult]:
        """Fallback: chunk at JSTL/Spring tag block boundaries."""
        block_starts: list[int] = []
        for i, line in enumerate(lines):
            if _BLOCK_TAGS.search(line):
                block_starts.append(i)

        if not block_starts:
            return LineChunker().chunk("\n".join(lines), max_chunk_chars)

        results: list[ChunkResult] = []
        boundaries = block_starts + [len(lines)]
        for i, start_idx in enumerate(block_starts):
            end_idx = min(boundaries[i + 1], start_idx + _MAX_SECTION_LINES)
            chunk_lines = lines[start_idx:end_idx]
            text = "\n".join(chunk_lines).strip()[:max_chunk_chars]
            if text:
                results.append(ChunkResult(
                    text=text,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    chunk_type="jsp_section",
                ))
        return results or LineChunker().chunk("\n".join(lines), max_chunk_chars)
