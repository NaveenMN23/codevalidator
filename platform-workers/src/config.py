from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "admin"
    rabbitmq_password: str = "password"

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"

    grading_queue: str = "grading-queue"
    grading_results_queue: str = "grading-results-queue"

    docker_mem_limit: str = "512m"
    docker_pids_limit: int = 50
    docker_timeout_seconds: int = 30

    # AI Evaluation — OpenAI GPT-4o mini
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    enable_ai_evaluation: bool = False

    # Redis (for blueprints and semantic caching)
    redis_host: str = "localhost"
    redis_port: int = 6379

    # MinIO — for on-demand hidden test fetching
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "password"
    minio_gold_masters_bucket: str = "gold-masters"

    # Backend URL — for Redis blueprint cache fallback
    backend_url: str = "http://backend:8080"

    class Config:
        env_file = ".env"

settings = Settings()
