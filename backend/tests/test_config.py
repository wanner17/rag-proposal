from app.core.config import DEFAULT_RAG_COLLECTION, Settings


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


def test_qdrant_collection_keeps_rag_collection_alias(monkeypatch):
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
    monkeypatch.setenv("RAG_COLLECTION", "rag-documents")

    settings = Settings(_env_file=None)

    assert settings.QDRANT_COLLECTION == "rag-documents"


def test_qdrant_collection_default_is_documented_compatibility_value(monkeypatch):
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
    monkeypatch.delenv("RAG_COLLECTION", raising=False)

    settings = Settings(_env_file=None)

    assert DEFAULT_RAG_COLLECTION == "proposals"
    assert settings.QDRANT_COLLECTION == DEFAULT_RAG_COLLECTION
