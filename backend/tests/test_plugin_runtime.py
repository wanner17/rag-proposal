from pathlib import Path

import pytest
from fastapi import FastAPI

from app.plugin_runtime.loader import load_allowed_plugins, load_plugin_config, parse_plugin_yaml
from app.plugin_runtime.models import BackendRouteConfig, FrontendRouteConfig
from app.plugin_runtime.registry import enabled_plugin_metadata, register_plugin_routers


def test_plugin_manifest_parser_accepts_proposal_yaml():
    data = parse_plugin_yaml(Path("plugins/proposal/plugin.yaml").read_text(encoding="utf-8"))

    assert data["id"] == "proposal"
    assert data["routes"]["backend"]["module"] == "app.plugins.proposal.backend.routes"
    assert data["navigation"]["label"] == "제안서 초안"
    assert data["outputs"]["sections"][0] == "요약"


def test_load_allowed_plugins_is_allowlist_only(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    proposal_dir = plugin_dir / "proposal"
    proposal_dir.mkdir()
    (proposal_dir / "plugin.yaml").write_text(
        """
id: proposal
name: Proposal Draft
version: 0.1.0
enabled: true
routes:
  backend:
    prefix: /api/proposals
    module: app.plugins.proposal.backend.routes
""",
        encoding="utf-8",
    )

    plugins = load_allowed_plugins(["proposal"], plugin_dir=plugin_dir)

    assert [plugin.id for plugin in plugins] == ["proposal"]
    with pytest.raises(ValueError):
        load_allowed_plugins(["../proposal"], plugin_dir=plugin_dir)


def test_plugin_router_registration_preserves_proposal_endpoint():
    app = FastAPI()

    register_plugin_routers(app, api_prefix="/api")

    paths = {route.path for route in app.routes}
    assert "/api/proposals/draft" in paths


def test_enabled_plugin_metadata_exposes_proposal_navigation():
    metadata = enabled_plugin_metadata()

    assert metadata[0]["id"] == "proposal"
    assert metadata[0]["navigation"]["label"] == "제안서 초안"


def test_plugin_config_validates_retrieval_defaults():
    config = load_plugin_config(Path("plugins/proposal/plugin.yaml"))

    assert config.retrieval.top_k == 20
    assert config.retrieval.top_n == 5


def test_backend_route_config_rejects_external_module_path():
    with pytest.raises(ValueError):
        BackendRouteConfig(prefix="/api/proposals", module="external.proposal.routes")


def test_backend_route_config_rejects_invalid_prefix():
    with pytest.raises(ValueError):
        BackendRouteConfig(prefix="/proposals", module="app.plugins.proposal.backend.routes")


def test_frontend_route_config_rejects_invalid_path():
    with pytest.raises(ValueError):
        FrontendRouteConfig(path="proposals", component="plugins/proposal/pages/ProposalPage")
