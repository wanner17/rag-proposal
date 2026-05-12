from pathlib import Path


CORE_PATHS = [
    Path("backend/app/main.py"),
    Path("backend/app/services/llm.py"),
    Path("backend/app/services/retrieval.py"),
]


def test_proposal_prompt_lives_in_plugin_not_core_services():
    forbidden = "당신은 공공기관 SI 제안서 초안 작성 전문가다"

    for path in CORE_PATHS:
        assert forbidden not in path.read_text(encoding="utf-8")


def test_proposal_api_module_is_compatibility_shim():
    content = Path("backend/app/api/proposals.py").read_text(encoding="utf-8")

    assert "Compatibility shim" in content
    assert "sys.modules[__name__]" in content


def test_airgap_scripts_do_not_install_from_online_sources():
    airgap_files = [
        Path("deploy/airgap-compose/compose.yml"),
        Path("deploy/bundle-scripts/load-images.sh"),
        Path("deploy/bundle-scripts/verify-offline-install.sh"),
    ]
    forbidden = ["docker pull", "npm install", "git clone", "huggingface.co"]

    for path in airgap_files:
        content = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in content
