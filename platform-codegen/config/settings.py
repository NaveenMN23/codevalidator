from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.2
    openai_max_tokens: int = 2048
    openai_max_tokens_impl: int = 8192  # Reduced from 16384 to avoid TPM limits
    openai_max_tokens_test: int = 4096  # Reduced from 8192 to avoid TPM limits
    openai_tpm_limit: int = 28000  # headroom under this account's observed 30,000 real TPM cap

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Storage — AWS S3 (boto3 default credential chain: env vars → IAM role)
    aws_s3_challenges_bucket: str = "challenges-repo"  # maps to AWS_S3_CHALLENGES_BUCKET
    gold_masters_bucket: str = "gold-masters"           # maps to GOLD_MASTERS_BUCKET
    aws_region: str = "us-east-1"

    # RabbitMQ
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "admin"
    rabbitmq_password: str = "password"
    blueprint_queue: str = "blueprint-queue"
    codegen_request_queue: str = "codegen-request-queue"
    codegen_results_queue: str = "codegen-results-queue"

    # Backend
    backend_url: str = "http://platform-backend:8080"

    # Postgres (blueprint persistence)
    postgres_dsn: str = "postgresql://admin:password@localhost:5432/interview_db"

    # Local export (dev only — bind-mount path; empty = disabled)
    local_export_path: str = ""

    # Feature flags
    enable_blueprint_generation: bool = True
    enable_llm: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
