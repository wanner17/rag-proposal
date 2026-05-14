from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

DEFAULT_RAG_COLLECTION = "rag_data"


class Settings(BaseSettings):
    LLM_HOST: str = Field(
        default="http://localhost:8080/v1",
        validation_alias=AliasChoices("LLM_HOST", "VLLM_HOST"),
    )
    LLM_MODEL: str = Field(
        default="Qwen3-8B-Q4_K_M.gguf",
        validation_alias=AliasChoices("LLM_MODEL", "VLLM_MODEL"),
    )
    EMBEDDING_HOST: str = "http://localhost:8001"
    RERANKER_HOST: str = "http://localhost:8002"
    QDRANT_HOST: str = "http://qdrant:6333"
    QDRANT_COLLECTION: str = Field(
        # Temporary compatibility default for existing indexed deployments.
        # New deployments may prefer the domain-neutral RAG_COLLECTION alias.
        default=DEFAULT_RAG_COLLECTION,
        validation_alias=AliasChoices("QDRANT_COLLECTION", "RAG_COLLECTION"),
    )
    PROJECT_DB_PATH: str = "data/projects.sqlite3"
    SOURCE_INDEX_LOCK_TIMEOUT_SECONDS: int = 3600
    SOURCE_INDEX_API_TOKEN: str | None = None
    RAG_ENABLED_PLUGINS: str = "proposal"
    # SVN VPN (L2TP/IPsec) — 서버 전역 설정. 값이 없으면 VPN 없이 직접 체크아웃
    SVN_VPN_NAME: str | None = None        # ipsec/xl2tpd 프로파일명
    SVN_VPN_SERVER_IP: str | None = None   # SVN 서버 IP (라우팅용)
    SVN_VPN_GATEWAY: str | None = None     # ppp0 게이트웨이 IP
    ENABLE_AGENT_ORCHESTRATION: bool = False
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        populate_by_name = True

    @property
    def VLLM_HOST(self) -> str:
        return self.LLM_HOST

    @property
    def VLLM_MODEL(self) -> str:
        return self.LLM_MODEL


settings = Settings()
