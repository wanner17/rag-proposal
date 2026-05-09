from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VLLM_HOST: str = "http://localhost:8080/v1"
    VLLM_MODEL: str = "qwen3-14b"
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


settings = Settings()
