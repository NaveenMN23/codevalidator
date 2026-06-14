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
    
    class Config:
        env_file = ".env"

settings = Settings()
