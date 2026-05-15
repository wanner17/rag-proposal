from __future__ import annotations

from app.services.chunkers.base import BaseChunker, ChunkResult

DEFAULT_MAX_LINES = 80


class LineChunker(BaseChunker):
    def __init__(self, max_lines: int = DEFAULT_MAX_LINES):
        self.max_lines = max_lines

    def chunk(self, content: str, max_chunk_chars: int = 8000) -> list[ChunkResult]:
        lines = content.splitlines()
        results: list[ChunkResult] = []
        for start_index in range(0, len(lines), self.max_lines):
            chunk_lines = lines[start_index : start_index + self.max_lines]
            text = "\n".join(chunk_lines).strip()[:max_chunk_chars]
            if not text:
                continue
            results.append(ChunkResult(
                text=text,
                start_line=start_index + 1,
                end_line=start_index + len(chunk_lines),
                chunk_type="line_range",
            ))
        return results
