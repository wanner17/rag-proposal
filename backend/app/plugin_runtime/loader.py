from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.plugin_runtime.models import PluginConfig


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "plugins").is_dir():
            return parent
    return current.parents[3]


def default_plugin_dir() -> Path:
    return repo_root() / "plugins"


def parse_plugin_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset used by repo-local plugin manifests."""
    stripped = text.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any, Any, str | None]] = [(-1, root, None, None)]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        content = raw_line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]
        if content.startswith("- "):
            item = _parse_scalar(content[2:].strip())
            if not isinstance(parent, list):
                parent_info = stack[-1]
                grandparent = parent_info[2]
                key = parent_info[3]
                if not isinstance(grandparent, dict) or key is None:
                    raise ValueError("List item is not attached to a mapping key")
                replacement: list[Any] = []
                grandparent[key] = replacement
                stack[-1] = (parent_info[0], replacement, grandparent, key)
                parent = replacement
            parent.append(item)
            continue

        key, sep, value = content.partition(":")
        if not sep:
            raise ValueError(f"Invalid plugin manifest line: {raw_line}")
        key = key.strip()
        value = value.strip()

        if not isinstance(parent, dict):
            raise ValueError(f"Cannot assign mapping key under list: {raw_line}")

        if value:
            parent[key] = _parse_scalar(value)
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child, parent, key))

    return root


def load_plugin_config(path: Path) -> PluginConfig:
    return PluginConfig.model_validate(parse_plugin_yaml(path.read_text(encoding="utf-8")))


def load_allowed_plugins(plugin_ids: list[str], plugin_dir: Path | None = None) -> list[PluginConfig]:
    base_dir = plugin_dir or default_plugin_dir()
    seen: set[str] = set()
    configs: list[PluginConfig] = []

    for plugin_id in plugin_ids:
        safe_id = plugin_id.strip()
        if not safe_id:
            continue
        if safe_id in seen:
            raise ValueError(f"Duplicate plugin id: {safe_id}")
        if "/" in safe_id or "\\" in safe_id or safe_id in {".", ".."}:
            raise ValueError(f"Invalid plugin id: {safe_id}")

        manifest = base_dir / safe_id / "plugin.yaml"
        if not manifest.is_file():
            raise FileNotFoundError(f"Plugin manifest not found: {manifest}")

        config = load_plugin_config(manifest)
        if config.id != safe_id:
            raise ValueError(f"Plugin id mismatch: expected {safe_id}, got {config.id}")
        if config.enabled:
            configs.append(config)
        seen.add(safe_id)

    return sorted(configs, key=lambda item: item.navigation.order if item.navigation else 100)


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value
