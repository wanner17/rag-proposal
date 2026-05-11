from app.core.config import Settings


def test_llm_host_reads_current_env_name(monkeypatch):
    monkeypatch.setenv("LLM_HOST", "http://llama-host:8080/v1")
    monkeypatch.delenv("VLLM_HOST", raising=False)

    settings = Settings(_env_file=None)

    assert settings.LLM_HOST == "http://llama-host:8080/v1"


def test_llm_host_keeps_legacy_vllm_env_name(monkeypatch):
    monkeypatch.delenv("LLM_HOST", raising=False)
    monkeypatch.setenv("VLLM_HOST", "http://legacy-host:8080/v1")

    settings = Settings(_env_file=None)

    assert settings.LLM_HOST == "http://legacy-host:8080/v1"


def test_llm_model_reads_current_env_name(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "Qwen3-8B-Q4_K_M.gguf")
    monkeypatch.delenv("VLLM_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.LLM_MODEL == "Qwen3-8B-Q4_K_M.gguf"
