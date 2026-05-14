from pathlib import Path
from uuid import UUID

import pytest

from app.models.project_schemas import ProjectSourceConfig
from app.services.source_processor import (
    SourceFileSkip,
    chunk_source_file,
    detect_language,
    normalize_relative_path,
    should_include_source_path,
)


def _config(tmp_path: Path) -> ProjectSourceConfig:
    return ProjectSourceConfig(
        enabled=True,
        repo_root=tmp_path.as_posix(),
        allowed_base_path=tmp_path.parent.as_posix(),
        include_globs=["**/*.py", "**/*.java"],
        exclude_globs=[".svn/**", "build/**", ".env"],
        max_file_size_bytes=1024,
    )


def test_normalize_relative_path_rejects_traversal_and_absolute_paths(tmp_path):
    config = _config(tmp_path)

    assert normalize_relative_path("src/App.java", config) == "src/App.java"

    with pytest.raises(ValueError):
        normalize_relative_path("../secret.py", config)
    with pytest.raises(ValueError):
        normalize_relative_path("/etc/passwd", config)
    with pytest.raises(ValueError):
        normalize_relative_path("C:/Windows/win.ini", config)


def test_should_include_source_path_applies_include_and_exclude_globs(tmp_path):
    config = _config(tmp_path)

    assert should_include_source_path("src/App.java", config) is True
    assert should_include_source_path("src/app.py", config) is True
    assert should_include_source_path("README.md", config) is False
    assert should_include_source_path(".svn/entries", config) is False
    assert should_include_source_path("build/generated/App.java", config) is False
    assert should_include_source_path(".env", config) is False


def test_chunk_source_file_returns_source_payloads_with_stable_ids(tmp_path):
    source_file = tmp_path / "src" / "App.java"
    source_file.parent.mkdir()
    source_file.write_text(
        "\n".join(
            [
                "public class App {",
                "  public void run() {",
                "    System.out.println(\"ok\");",
                "  }",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    config = _config(tmp_path)

    chunks = chunk_source_file(
        config=config,
        project_slug="manual-code",
        relative_path="src/App.java",
        svn_revision="12345",
        chunking_version="source-v1",
        max_lines=3,
    )
    repeated = chunk_source_file(
        config=config,
        project_slug="manual-code",
        relative_path="src/App.java",
        svn_revision="12345",
        chunking_version="source-v1",
        max_lines=3,
    )

    assert [chunk["chunk_id"] for chunk in chunks] == [
        chunk["chunk_id"] for chunk in repeated
    ]
    UUID(chunks[0]["chunk_id"])
    assert chunks[0]["source_kind"] == "source_code"
    assert chunks[0]["project_slug"] == "manual-code"
    assert chunks[0]["relative_path"] == "src/App.java"
    assert chunks[0]["language"] == "java"
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 3
    assert chunks[0]["svn_revision"] == "12345"
    assert chunks[0]["content_hash"]


def test_chunk_source_file_skips_binary_and_oversized_files(tmp_path):
    binary_file = tmp_path / "src" / "bad.py"
    binary_file.parent.mkdir()
    binary_file.write_bytes(b"\x00\x01\x02")
    config = _config(tmp_path)

    with pytest.raises(SourceFileSkip) as binary_skip:
        chunk_source_file(config, "manual-code", "src/bad.py")
    assert binary_skip.value.reason == "binary"

    big_file = tmp_path / "src" / "big.py"
    big_file.write_text("x" * 2048, encoding="utf-8")
    with pytest.raises(SourceFileSkip) as size_skip:
        chunk_source_file(config, "manual-code", "src/big.py")
    assert size_skip.value.reason == "oversized"


def test_detect_language_uses_extension():
    assert detect_language("src/app.py") == "python"
    assert detect_language("src/App.java") == "java"
    assert detect_language("unknown.xyz") == "text"
