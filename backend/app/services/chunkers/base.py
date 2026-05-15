from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChunkResult:
    text: str
    start_line: int
    end_line: int
    chunk_type: str
    class_name: str | None = None
    method_name: str | None = None
    extra: dict = field(default_factory=dict)


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, content: str, max_chunk_chars: int = 8000) -> list[ChunkResult]:
        """Split content into chunks. Falls back to LineChunker on any error."""
