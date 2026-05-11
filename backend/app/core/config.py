from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


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
    QDRANT_COLLECTION: str = "proposals"
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
