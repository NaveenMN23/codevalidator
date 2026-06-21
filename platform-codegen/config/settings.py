from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.2
    openai_max_tokens: int = 4096
    openai_max_tokens_impl: int = 16384  # Phase 2a generates full file trees — needs higher limit
    openai_max_tokens_test: int = 8192   # Phase 2b generates large test suites at HARD tier

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # MinIO / S3
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "password"
    minio_bucket: str = "challenges"

    # RabbitMQ
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "admin"
    rabbitmq_password: str = "password"
    blueprint_queue: str = "blueprint-queue"

    # Backend
    backend_url: str = "http://platform-backend:8080"

    # Local export (dev only — bind-mount path; empty = disabled)
    local_export_path: str = ""

    # Feature flags
    enable_blueprint_generation: bool = True
    enable_llm: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
