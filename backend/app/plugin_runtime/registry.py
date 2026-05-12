from __future__ import annotations

import importlib
import logging
from typing import Any

from fastapi import FastAPI

from app.core.config import settings
from app.plugin_runtime.loader import load_allowed_plugins
from app.plugin_runtime.models import PluginConfig

logger = logging.getLogger(__name__)
_enabled_plugins: list[PluginConfig] | None = None


def get_enabled_plugins() -> list[PluginConfig]:
    global _enabled_plugins
    if _enabled_plugins is None:
        plugin_ids = [item.strip() for item in settings.RAG_ENABLED_PLUGINS.split(",")]
        _enabled_plugins = load_allowed_plugins(plugin_ids)
        logger.info("Enabled RAG plugins: %s", [plugin.id for plugin in _enabled_plugins])
    return _enabled_plugins


def register_plugin_routers(app: FastAPI, api_prefix: str = "/api") -> None:
    for plugin in get_enabled_plugins():
        backend_route = plugin.routes.backend
        if backend_route is None:
            continue
        module = importlib.import_module(backend_route.module)

        if hasattr(module, "register_routes"):
            module.register_routes(app, api_prefix=api_prefix, plugin_config=plugin)
            continue

        router = getattr(module, "router", None)
        if router is None:
            raise RuntimeError(f"Plugin {plugin.id} does not expose router or register_routes")
        expected_router_prefix = _router_prefix_from_manifest(backend_route.prefix, api_prefix)
        if router.prefix != expected_router_prefix:
            raise RuntimeError(
                f"Plugin {plugin.id} router prefix {router.prefix!r} does not match "
                f"manifest prefix {backend_route.prefix!r}"
            )
        app.include_router(router, prefix=api_prefix)


def enabled_plugin_metadata() -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for plugin in get_enabled_plugins():
        metadata.append(
            {
                "id": plugin.id,
                "name": plugin.name,
                "version": plugin.version,
                "navigation": plugin.navigation.model_dump() if plugin.navigation else None,
                "routes": plugin.routes.model_dump(),
                "retrieval": plugin.retrieval.model_dump(),
                "outputs": plugin.outputs.model_dump(),
            }
        )
    return metadata


def _router_prefix_from_manifest(manifest_prefix: str, api_prefix: str) -> str:
    if not manifest_prefix.startswith(f"{api_prefix}/"):
        raise RuntimeError(f"Plugin backend prefix must be under {api_prefix}: {manifest_prefix}")
    return manifest_prefix.removeprefix(api_prefix)
