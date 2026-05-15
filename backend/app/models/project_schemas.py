from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ProjectStatus = Literal["active", "archived"]


class ProjectPluginBinding(BaseModel):
    plugin_id: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True
    display_name_override: str | None = Field(default=None, max_length=120)
    config: dict = Field(default_factory=dict)


def _default_collection_name() -> str:
    from app.core.config import settings  # lazy to avoid circular import
    return settings.QDRANT_COLLECTION


class ProjectRagConfig(BaseModel):
    collection_name: str = Field(default_factory=_default_collection_name, max_length=120)
    top_k_default: int = Field(default=20, ge=1, le=50)
    top_n_default: int = Field(default=5, ge=1, le=10)
    prompt_profile: str | None = Field(default=None, max_length=120)
    storage_namespace: str | None = Field(default=None, max_length=120)

    @field_validator("collection_name", mode="before")
    @classmethod
    def validate_collection_name(cls, value: str | None) -> str:
        if not value:
            from app.core.config import settings
            return settings.QDRANT_COLLECTION
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if any(char not in allowed for char in value):
            raise ValueError("collection_name must use letters, numbers, '-' or '_' only")
        return value


DEFAULT_SOURCE_INCLUDE_GLOBS = [
    "**/*.java",
    "**/*.jsp",
    "**/*.xml",
    "**/*.properties",
    "**/*.sql",
    "**/*.md",
    "**/*.json",
    "**/*.js",
]

DEFAULT_SOURCE_EXCLUDE_GLOBS = [
    ".svn/**",
    ".git/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    "target/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    ".pytest_cache/**",
    "*.pyc",
    "*.pyo",
    "*.class",
    "*.jar",
    "*.war",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.7z",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.pdf",
    "*.docx",
    "*.xlsx",
    ".env",
    ".env.*",
    "*secret*",
    "*credential*",
    "*.min.js",
    "*.min.css",
    "*.map",
    "package-lock.json",
    "yarn.lock",
    "src/main/webapp/assets/**",
    "src/main/webapp/vendor/**",
    "src/main/webapp/static/**",
    "**/assets/**",
    "**/vendor/**",
    "**/static/**",
    "**/lib/**",
    "**/libs/**",
    "**/third_party/**",
    "**/webjars/**",
    "src/main/webapp/html/egovframework/**",
    "src/main/webapp/js/**",
    "src/main/webapp/css/**",
    "src/main/webapp/images/**",
    "src/main/webapp/WEB-INF/lib/**",
    "**/jquery/**",
    "**/jquery-ui/**",
    "**/bootstrap/**",
    "**/ckeditor/**",
    "**/tinymce/**",
    "**/summernote/**",
    "**/htmlarea/**",
    "**/kendo*/**",
    "**/jqgrid/**",
    "**/videojs/**",
    "**/plupload*/**",
    "**/*.bak",
    "**/*.old",
    "**/*.log",
    "**/*.bundle.js",
    "**/*.chunk.js",
    "**/bower_components/**",
    "**/ext/**",
    "**/dwr/**",
    "**/*.swf",
    "**/*.woff",
    "**/*.woff2",
    "**/*.ttf",
    "**/*.eot",
]


class ProjectSourceConfig(BaseModel):
    enabled: bool = False
    repo_root: str | None = None
    allowed_base_path: str = "/opt/rag-projects"
    include_globs: list[str] = Field(default_factory=lambda: list(DEFAULT_SOURCE_INCLUDE_GLOBS))
    exclude_globs: list[str] = Field(default_factory=lambda: list(DEFAULT_SOURCE_EXCLUDE_GLOBS))
    max_file_size_bytes: int = Field(default=1048576, ge=1, le=10 * 1024 * 1024)
    encoding: str = "utf-8"
    follow_symlinks: bool = False
    file_type_priority: list[str] = Field(
        default_factory=lambda: [
            "**/*.java",
            "**/*.xml",
            "**/*.sql",
            "**/*.properties",
            "**/*.jsp",
            "**/*.json",
            "**/*.md",
            "**/*.js",
        ]
    )

    # SVN 연결 정보
    svn_url: str | None = None

    @model_validator(mode="after")
    def validate_repo_root(self) -> "ProjectSourceConfig":
        if not self.repo_root:
            if self.enabled:
                raise ValueError("repo_root is required when source config is enabled")
            return self

        base = _normalize_posix_absolute_path(self.allowed_base_path)
        root = _normalize_posix_absolute_path(self.repo_root)
        if not _is_relative_to(root, base):
            raise ValueError("repo_root must resolve inside allowed_base_path")
        return self


def _normalize_posix_absolute_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not path.is_absolute():
        raise ValueError("source paths must be absolute")
    parts: list[str] = []
    for part in path.parts:
        if part in ("", "/"):
            continue
        if part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return PurePosixPath("/", *parts)


def _is_relative_to(path: PurePosixPath, base: PurePosixPath) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


class ProjectCreateRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=80)
    name: str = Field(..., min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    status: ProjectStatus = "active"
    default_language: str = Field(default="ko", min_length=2, max_length=20)
    plugins: list[ProjectPluginBinding] = Field(default_factory=list)
    rag_config: ProjectRagConfig
    source_config: ProjectSourceConfig = Field(default_factory=ProjectSourceConfig)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if any(char not in allowed for char in value) or value.startswith("-") or value.endswith("-"):
            raise ValueError("slug must use lowercase letters, numbers, and interior '-' only")
        return value


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    status: ProjectStatus | None = None
    default_language: str | None = Field(default=None, min_length=2, max_length=20)
    plugins: list[ProjectPluginBinding] | None = None
    rag_config: ProjectRagConfig | None = None
    source_config: ProjectSourceConfig | None = None


class ProjectResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    status: ProjectStatus
    default_language: str
    plugins: list[ProjectPluginBinding]
    rag_config: ProjectRagConfig
    source_config: ProjectSourceConfig = Field(default_factory=ProjectSourceConfig)
    created_at: datetime
    updated_at: datetime


class ProjectImportRequest(BaseModel):
    bundle: str = Field(..., min_length=2)


class ProjectImportResponse(BaseModel):
    project: ProjectResponse
    imported: bool = True


META_DOC_TYPES = ["project_summary", "menu_map", "feature_map", "db_schema_summary", "architecture"]

META_DOC_TO_COLUMN: dict[str, str] = {
    "project_summary": "meta_summary",
    "menu_map": "meta_menu",
    "feature_map": "meta_feature",
    "db_schema_summary": "meta_db",
    "architecture": "meta_arch",
}


class ProjectMetaDocs(BaseModel):
    project_summary: str | None = None
    menu_map: str | None = None
    feature_map: str | None = None
    db_schema_summary: str | None = None
    architecture: str | None = None

    def get(self, doc_type: str) -> str | None:
        return getattr(self, doc_type, None)


class MetaDocUpdateRequest(BaseModel):
    content: str


class MetaDocResponse(BaseModel):
    doc_type: str
    content: str | None
    exists: bool


class MetaDocDraftResponse(BaseModel):
    draft: str


class AllMetaDocsResponse(BaseModel):
    project_summary: MetaDocResponse
    menu_map: MetaDocResponse
    feature_map: MetaDocResponse
    db_schema_summary: MetaDocResponse
    architecture: MetaDocResponse
