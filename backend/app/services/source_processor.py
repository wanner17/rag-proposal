from __future__ import annotations

import fnmatch
import hashlib
import uuid
from pathlib import Path, PurePosixPath
from typing import Literal

from app.models.project_schemas import (
    ProjectSourceConfig,
    DEFAULT_SOURCE_INCLUDE_GLOBS,
    DEFAULT_SOURCE_EXCLUDE_GLOBS,
)

SourceSkipReason = Literal[
    "excluded",
    "missing",
    "not_file",
    "oversized",
    "binary",
    "undecodable",
    "empty",
]
DEFAULT_CHUNKING_VERSION = "source-v1"

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".kt": "kotlin",
    ".sql": "sql",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".html": "html",
    ".css": "css",
    ".sh": "shell",
}


class SourceFileSkip(Exception):
    def __init__(self, reason: SourceSkipReason, detail: str = ""):
        self.reason = reason
        self.detail = detail
        message = reason if not detail else f"{reason}: {detail}"
        super().__init__(message)


def normalize_relative_path(relative_path: str, config: ProjectSourceConfig) -> str:
    if _looks_windows_absolute(relative_path):
        raise ValueError("drive-qualified paths are not allowed")
    raw = PurePosixPath(relative_path.replace("\\", "/"))
    if raw.is_absolute():
        raise ValueError("absolute paths are not allowed")

    parts: list[str] = []
    for part in raw.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError("path traversal is not allowed")
        parts.append(part)
    if not parts:
        raise ValueError("empty relative path is not allowed")

    normalized = PurePosixPath(*parts).as_posix()
    root = Path(config.repo_root or "")
    resolved = (root / normalized).resolve(strict=False)
    try:
        resolved.relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise ValueError("path resolves outside repo_root") from exc
    return normalized


def should_include_source_path(relative_path: str, config: ProjectSourceConfig) -> bool:
    normalized = normalize_relative_path(relative_path, config)

    exclude_globs = config.exclude_globs or DEFAULT_SOURCE_EXCLUDE_GLOBS
    include_globs = config.include_globs or DEFAULT_SOURCE_INCLUDE_GLOBS

    if any(_glob_match(normalized, pattern) for pattern in exclude_globs):
        return False

    return any(_glob_match(normalized, pattern) for pattern in include_globs)


def source_file_path(config: ProjectSourceConfig, relative_path: str) -> Path:
    normalized = normalize_relative_path(relative_path, config)
    return Path(config.repo_root or "") / normalized


def detect_language(relative_path: str) -> str:
    return LANGUAGE_BY_EXTENSION.get(PurePosixPath(relative_path).suffix.lower(), "text")


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def chunk_source_file(
    config: ProjectSourceConfig,
    project_slug: str,
    relative_path: str,
    svn_revision: str | None = None,
    chunking_version: str = DEFAULT_CHUNKING_VERSION,
    max_lines: int = 80,
) -> list[dict]:
    normalized = normalize_relative_path(relative_path, config)
    if not should_include_source_path(normalized, config):
        raise SourceFileSkip("excluded", normalized)

    path = source_file_path(config, normalized)
    if not path.exists():
        raise SourceFileSkip("missing", normalized)
    if not path.is_file():
        raise SourceFileSkip("not_file", normalized)

    size = path.stat().st_size
    if size > config.max_file_size_bytes:
        raise SourceFileSkip("oversized", f"{size} > {config.max_file_size_bytes}")

    raw = path.read_bytes()
    if _looks_binary(raw):
        raise SourceFileSkip("binary", normalized)
    try:
        text = raw.decode(config.encoding)
    except UnicodeDecodeError as exc:
        raise SourceFileSkip("undecodable", str(exc)) from exc

    lines = text.splitlines()
    if not any(line.strip() for line in lines):
        raise SourceFileSkip("empty", normalized)

    file_hash = content_hash(raw)
    language = detect_language(normalized)
    chunks: list[dict] = []
    for start_index in range(0, len(lines), max_lines):
        chunk_lines = lines[start_index : start_index + max_lines]
        chunk_text = "\n".join(chunk_lines).strip()
        if not chunk_text:
            continue
        start_line = start_index + 1
        end_line = start_index + len(chunk_lines)
        chunk_locator = f"{start_line}:{end_line}:{hashlib.sha1(chunk_text.encode('utf-8')).hexdigest()}"
        chunk_id = _chunk_id(project_slug, normalized, chunking_version, chunk_locator)
        chunks.append(
            {
                "chunk_id": chunk_id,
                "source_kind": "source_code",
                "project_slug": project_slug,
                "relative_path": normalized,
                "language": language,
                "start_line": start_line,
                "end_line": end_line,
                "content_hash": file_hash,
                "svn_revision": svn_revision,
                "chunk_type": "line_range",
                "text": chunk_text,
            }
        )
    if not chunks:
        raise SourceFileSkip("empty", normalized)
    return chunks


def _chunk_id(
    project_slug: str,
    relative_path: str,
    chunking_version: str,
    chunk_locator: str,
) -> str:
    path_hash = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:16]
    locator_hash = hashlib.sha1(chunk_locator.encode("utf-8")).hexdigest()[:16]
    stable_key = f"source:{project_slug}:{path_hash}:{chunking_version}:{locator_hash}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key))


def _glob_match(relative_path: str, pattern: str) -> bool:
    path = relative_path.replace("\\", "/")
    normalized_pattern = pattern.replace("\\", "/")
    if fnmatch.fnmatch(path, normalized_pattern):
        return True
    if normalized_pattern.startswith("**/"):
        return fnmatch.fnmatch(path, normalized_pattern[3:])
    if "/" not in normalized_pattern:
        return fnmatch.fnmatch(PurePosixPath(path).name, normalized_pattern)
    return False


def _looks_binary(content: bytes) -> bool:
    return b"\x00" in content[:4096]


def _looks_windows_absolute(path: str) -> bool:
    return len(path) >= 3 and path[1] == ":" and path[2] in ("\\", "/")
