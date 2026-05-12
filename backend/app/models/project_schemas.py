from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ProjectStatus = Literal["active", "archived"]


class ProjectPluginBinding(BaseModel):
    plugin_id: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True
    display_name_override: str | None = Field(default=None, max_length=120)
    config: dict = Field(default_factory=dict)


class ProjectRagConfig(BaseModel):
    collection_name: str = Field(..., min_length=1, max_length=120)
    top_k_default: int = Field(default=20, ge=1, le=50)
    top_n_default: int = Field(default=5, ge=1, le=10)
    prompt_profile: str | None = Field(default=None, max_length=120)
    storage_namespace: str | None = Field(default=None, max_length=120)

    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, value: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if any(char not in allowed for char in value):
            raise ValueError("collection_name must use letters, numbers, '-' or '_' only")
        return value


class ProjectCreateRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=80)
    name: str = Field(..., min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    status: ProjectStatus = "active"
    default_language: str = Field(default="ko", min_length=2, max_length=20)
    plugins: list[ProjectPluginBinding] = Field(default_factory=list)
    rag_config: ProjectRagConfig

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


class ProjectResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    status: ProjectStatus
    default_language: str
    plugins: list[ProjectPluginBinding]
    rag_config: ProjectRagConfig
    created_at: datetime
    updated_at: datetime


class ProjectImportRequest(BaseModel):
    bundle: str = Field(..., min_length=2)


class ProjectImportResponse(BaseModel):
    project: ProjectResponse
    imported: bool = True
