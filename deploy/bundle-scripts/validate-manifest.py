#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path


REQUIRED_TOP_LEVEL = {
    "bundle_format_version",
    "created_at",
    "target_platform",
    "source_git_revision",
    "compose_file",
    "enabled_plugins",
    "images",
    "models",
    "plugin_configs",
    "verification",
}

REQUIRED_IMAGE_NAMES = {
    "rag-proposal-backend",
    "rag-proposal-frontend",
    "rag-qdrant",
    "rag-nginx",
    "rag-embedding",
    "rag-reranker",
    "rag-llm",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(root: Path, relative: str, expected: str | None = None) -> None:
    path = root / relative
    if not path.is_file():
        raise SystemExit(f"missing artifact: {relative}")
    if not expected or expected == "replace-with-sha256":
        raise SystemExit(f"missing concrete checksum: {relative}")
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(f"checksum mismatch: {relative}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate-manifest.py <manifest.json>")
    manifest_path = Path(sys.argv[1]).resolve()
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    missing = REQUIRED_TOP_LEVEL - set(manifest)
    if missing:
        raise SystemExit(f"manifest missing keys: {sorted(missing)}")

    image_names = {image["name"] for image in manifest["images"]}
    missing_images = REQUIRED_IMAGE_NAMES - image_names
    if missing_images:
        raise SystemExit(f"manifest missing required images: {sorted(missing_images)}")

    for image in manifest["images"]:
        require_file(root, image["tar"], image.get("sha256"))
    for model in manifest["models"]:
        require_file(root, model["path"], model.get("sha256"))
    for plugin in manifest["plugin_configs"]:
        require_file(root, plugin["path"], plugin.get("sha256"))

    print("manifest ok")


if __name__ == "__main__":
    main()
