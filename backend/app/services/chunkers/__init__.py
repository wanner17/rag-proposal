from __future__ import annotations

from app.services.chunkers.base import BaseChunker, ChunkResult
from app.services.chunkers.java_chunker import JavaChunker
from app.services.chunkers.xml_chunker import XmlChunker
from app.services.chunkers.jsp_chunker import JspChunker
from app.services.chunkers.line_chunker import LineChunker

LANGUAGE_CHUNKER_MAP: dict[str, type[BaseChunker]] = {
    "java": JavaChunker,
    "xml": XmlChunker,
    "jsp": JspChunker,
}


def get_chunker(language: str, filename: str = "", max_lines: int = 80) -> BaseChunker:
    if language == "xml":
        return XmlChunker(filename=filename)
    cls = LANGUAGE_CHUNKER_MAP.get(language, LineChunker)
    if cls is LineChunker:
        return LineChunker(max_lines=max_lines)
    return cls()


__all__ = [
    "BaseChunker",
    "ChunkResult",
    "JavaChunker",
    "XmlChunker",
    "JspChunker",
    "LineChunker",
    "get_chunker",
]
