from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.2
    openai_max_tokens: int = 1024
    openai_max_tokens_code: int = 2048

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # PostgreSQL
    postgres_dsn: str = "postgresql://admin:password@localhost:5432/interview_db"

    # Session
    session_ttl_seconds: int = 5400  # 90 min

    # Storage backend: "memory" (no DB, for local testing) | "postgres" (production)
    store_backend: str = "memory"

    # Feature flags
    enable_llm: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
