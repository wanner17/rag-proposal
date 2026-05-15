from __future__ import annotations

import re
from app.services.chunkers.base import BaseChunker, ChunkResult
from app.services.chunkers.line_chunker import LineChunker

# Matches class declarations (public/protected/private/abstract/final + class/interface/enum)
_CLASS_RE = re.compile(
    r"^[ \t]*(?:(?:public|protected|private|abstract|final|static)\s+)*"
    r"(?:class|interface|enum)\s+(\w+)",
    re.MULTILINE,
)

# Matches method declarations — return type + name + opening paren
_METHOD_RE = re.compile(
    r"^[ \t]*(?:(?:public|protected|private|static|final|synchronized|abstract|native|default)\s+)*"
    r"(?:[\w<>\[\],\s]+\s+)"   # return type (greedy, may include generics)
    r"(\w+)\s*\(",
    re.MULTILINE,
)

# Annotations to carry with following declaration
_ANNOTATION_RE = re.compile(r"^[ \t]*@\w+", re.MULTILINE)

_MAX_CLASS_LINES = 200  # classes larger than this are split at method boundaries


class JavaChunker(BaseChunker):
    def chunk(self, content: str, max_chunk_chars: int = 8000) -> list[ChunkResult]:
        try:
            return self._chunk_java(content, max_chunk_chars)
        except Exception:
            return LineChunker().chunk(content, max_chunk_chars)

    def _chunk_java(self, content: str, max_chunk_chars: int) -> list[ChunkResult]:
        lines = content.splitlines()
        class_blocks = self._extract_class_blocks(lines)
        if not class_blocks:
            return LineChunker().chunk(content, max_chunk_chars)

        results: list[ChunkResult] = []
        for class_name, class_start, class_end in class_blocks:
            class_lines = lines[class_start:class_end]
            if len(class_lines) <= _MAX_CLASS_LINES:
                text = "\n".join(class_lines).strip()[:max_chunk_chars]
                if text:
                    results.append(ChunkResult(
                        text=text,
                        start_line=class_start + 1,
                        end_line=class_end,
                        chunk_type="java_class",
                        class_name=class_name,
                    ))
            else:
                # Large class: split at method boundaries
                method_chunks = self._split_by_methods(class_lines, class_start, class_name, max_chunk_chars)
                results.extend(method_chunks)

        return results or LineChunker().chunk(content, max_chunk_chars)

    def _extract_class_blocks(self, lines: list[str]) -> list[tuple[str, int, int]]:
        """Return list of (class_name, start_line_idx, end_line_idx)."""
        blocks: list[tuple[str, int, int]] = []
        i = 0
        while i < len(lines):
            m = _CLASS_RE.match(lines[i])
            if m:
                class_name = m.group(1)
                start = i
                depth = 0
                found_open = False
                j = i
                while j < len(lines):
                    depth += lines[j].count("{") - lines[j].count("}")
                    if "{" in lines[j]:
                        found_open = True
                    if found_open and depth <= 0:
                        blocks.append((class_name, start, j + 1))
                        i = j + 1
                        break
                    j += 1
                else:
                    i += 1
            else:
                i += 1
        return blocks

    def _split_by_methods(
        self,
        class_lines: list[str],
        class_offset: int,
        class_name: str,
        max_chunk_chars: int,
    ) -> list[ChunkResult]:
        results: list[ChunkResult] = []
        method_starts: list[tuple[int, str]] = []

        for idx, line in enumerate(class_lines):
            m = _METHOD_RE.match(line)
            if m:
                method_name = m.group(1)
                # Skip common false positives
                if method_name not in ("if", "while", "for", "switch", "catch"):
                    method_starts.append((idx, method_name))

        if not method_starts:
            text = "\n".join(class_lines).strip()[:max_chunk_chars]
            if text:
                results.append(ChunkResult(
                    text=text,
                    start_line=class_offset + 1,
                    end_line=class_offset + len(class_lines),
                    chunk_type="java_class",
                    class_name=class_name,
                ))
            return results

        boundaries = [s for s, _ in method_starts] + [len(class_lines)]
        for i, (start_idx, method_name) in enumerate(method_starts):
            end_idx = boundaries[i + 1]
            chunk_lines = class_lines[start_idx:end_idx]
            text = "\n".join(chunk_lines).strip()[:max_chunk_chars]
            if text:
                results.append(ChunkResult(
                    text=text,
                    start_line=class_offset + start_idx + 1,
                    end_line=class_offset + end_idx,
                    chunk_type="java_method",
                    class_name=class_name,
                    method_name=method_name,
                ))
        return results
