from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.project_schemas import (
    ProjectCreateRequest,
    ProjectPluginBinding,
    ProjectRagConfig,
    ProjectResponse,
    ProjectSourceConfig,
    ProjectUpdateRequest,
)
from app.plugin_runtime import get_enabled_plugins

DEFAULT_PROJECT_SLUG = "proposal-default"
DEFAULT_PROJECT_ID = "project-proposal-default"
EXPORT_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    path = Path(settings.PROJECT_DB_PATH)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            default_language TEXT NOT NULL,
            plugins_json TEXT NOT NULL,
            rag_json TEXT NOT NULL,
            source_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()}
    if "source_json" not in columns:
        conn.execute("ALTER TABLE projects ADD COLUMN source_json TEXT")
    conn.commit()
    return conn


def _allowed_plugin_ids() -> set[str]:
    return {plugin.id for plugin in get_enabled_plugins()}


def _validate_plugins(bindings: list[ProjectPluginBinding]) -> None:
    allowed = _allowed_plugin_ids()
    unknown = sorted({binding.plugin_id for binding in bindings if binding.plugin_id not in allowed})
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"활성화되지 않은 플러그인입니다: {', '.join(unknown)}",
        )


def _row_to_project(row: sqlite3.Row) -> ProjectResponse:
    return ProjectResponse(
        id=row["id"],
        slug=row["slug"],
        name=row["name"],
        description=row["description"],
        status=row["status"],
        default_language=row["default_language"],
        plugins=[ProjectPluginBinding.model_validate(item) for item in json.loads(row["plugins_json"])],
        rag_config=ProjectRagConfig.model_validate(json.loads(row["rag_json"])),
        source_config=ProjectSourceConfig.model_validate(
            json.loads(row["source_json"]) if row["source_json"] else {}
        ),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def ensure_default_project() -> ProjectResponse:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE slug = ?", (DEFAULT_PROJECT_SLUG,)).fetchone()
        if row:
            return _row_to_project(row)

        now = _utc_now()
        plugins = []
        if "proposal" in _allowed_plugin_ids():
            plugins = [ProjectPluginBinding(plugin_id="proposal", enabled=True)]
        rag = ProjectRagConfig(
            collection_name=settings.QDRANT_COLLECTION,
            top_k_default=20,
            top_n_default=5,
            prompt_profile="proposal-default",
            storage_namespace=DEFAULT_PROJECT_SLUG,
        )
        conn.execute(
            """
            INSERT INTO projects (
                id, slug, name, description, status, default_language,
                plugins_json, rag_json, source_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_PROJECT_ID,
                DEFAULT_PROJECT_SLUG,
                "기본 제안서 프로젝트",
                "기존 제안서 플러그인 호환을 위한 기본 프로젝트",
                "active",
                "ko",
                json.dumps([plugin.model_dump() for plugin in plugins], ensure_ascii=False),
                json.dumps(rag.model_dump(), ensure_ascii=False),
                json.dumps(ProjectSourceConfig().model_dump(), ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (DEFAULT_PROJECT_ID,)).fetchone()
        return _row_to_project(row)


def list_projects() -> list[ProjectResponse]:
    ensure_default_project()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at ASC").fetchall()
        return [_row_to_project(row) for row in rows]


def get_project(project_id: str) -> ProjectResponse:
    ensure_default_project()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로젝트를 찾을 수 없습니다")
        return _row_to_project(row)


def get_project_by_slug(project_slug: str) -> ProjectResponse:
    ensure_default_project()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE slug = ?", (project_slug,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로젝트를 찾을 수 없습니다")
        return _row_to_project(row)


def get_default_project() -> ProjectResponse:
    return ensure_default_project()


def create_project(request: ProjectCreateRequest) -> ProjectResponse:
    _validate_plugins(request.plugins)
    now = _utc_now()
    project_id = f"project-{uuid4()}"
    with _connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO projects (
                    id, slug, name, description, status, default_language,
                    plugins_json, rag_json, source_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    request.slug,
                    request.name,
                    request.description,
                    request.status,
                    request.default_language,
                    json.dumps([plugin.model_dump() for plugin in request.plugins], ensure_ascii=False),
                    json.dumps(request.rag_config.model_dump(), ensure_ascii=False),
                    json.dumps(request.source_config.model_dump(), ensure_ascii=False),
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="동일한 slug 프로젝트가 이미 있습니다") from exc
        conn.commit()
    return get_project(project_id)


def update_project(project_id: str, request: ProjectUpdateRequest) -> ProjectResponse:
    current = get_project(project_id)
    plugins = request.plugins if request.plugins is not None else current.plugins
    rag = request.rag_config if request.rag_config is not None else current.rag_config
    source = request.source_config if request.source_config is not None else current.source_config
    _validate_plugins(plugins)
    with _connect() as conn:
        conn.execute(
            """
            UPDATE projects
               SET name = ?, description = ?, status = ?, default_language = ?,
                   plugins_json = ?, rag_json = ?, source_json = ?, updated_at = ?
             WHERE id = ?
            """,
            (
                request.name if request.name is not None else current.name,
                request.description if request.description is not None else current.description,
                request.status if request.status is not None else current.status,
                request.default_language if request.default_language is not None else current.default_language,
                json.dumps([plugin.model_dump() for plugin in plugins], ensure_ascii=False),
                json.dumps(rag.model_dump(), ensure_ascii=False),
                json.dumps(source.model_dump(), ensure_ascii=False),
                _utc_now(),
                project_id,
            ),
        )
        conn.commit()
    return get_project(project_id)


def export_project(project_id: str) -> str:
    project = get_project(project_id)
    bundle = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "project": project.model_dump(mode="json"),
    }
    # JSON is valid YAML 1.2, keeping the portable handoff dependency-free.
    return json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True)


def import_project(bundle: str) -> ProjectResponse:
    try:
        payload = json.loads(bundle)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="가져오기 번들이 유효한 YAML/JSON 형식이 아닙니다") from exc
    if payload.get("schema_version") != EXPORT_SCHEMA_VERSION:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 프로젝트 번들 버전입니다")
    raw_project = payload.get("project")
    if not isinstance(raw_project, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="프로젝트 번들에 project가 없습니다")

    rag = ProjectRagConfig.model_validate(raw_project.get("rag_config") or {})
    source = ProjectSourceConfig.model_validate(raw_project.get("source_config") or {})
    plugins = [ProjectPluginBinding.model_validate(item) for item in raw_project.get("plugins") or []]
    _validate_plugins(plugins)
    existing_slug = raw_project.get("slug")
    if not existing_slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="프로젝트 slug가 없습니다")

    with _connect() as conn:
        row = conn.execute("SELECT id FROM projects WHERE slug = ?", (existing_slug,)).fetchone()
    if row:
        return update_project(
            row["id"],
            ProjectUpdateRequest(
                name=raw_project.get("name"),
                description=raw_project.get("description", ""),
                status=raw_project.get("status", "active"),
                default_language=raw_project.get("default_language", "ko"),
                plugins=plugins,
                rag_config=rag,
                source_config=source,
            ),
        )

    return create_project(
        ProjectCreateRequest(
            slug=existing_slug,
            name=raw_project.get("name") or existing_slug,
            description=raw_project.get("description", ""),
            status=raw_project.get("status", "active"),
            default_language=raw_project.get("default_language", "ko"),
            plugins=plugins,
            rag_config=rag,
            source_config=source,
        )
    )
