from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    database_url: str = "postgresql+asyncpg://hr:hr@postgres:5432/hr"
    redis_url: str = "redis://redis:6379/0"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "hr_policies"

    ollama_base_url: str = "http://ollama:11434"
    chat_model: str = "llama3.1:8b"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768  # nomic-embed-text; change if you change the embedding model

    oidc_issuer: str
    oidc_jwks_url: str
    oidc_audience: str = "hr-assistant"

    rate_limit_per_min: int = 20
    max_message_chars: int = 2000
    request_timeout_s: int = 120

    retrieval_k: int = 4
    retrieval_min_score: float = 0.45
    history_turns: int = 6

    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 20
    hrms_base_url: str | None = None


settings = Settings()
