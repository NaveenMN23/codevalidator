import pika
import json
import os
import shutil
import uuid
from typing import Dict
from pydantic import BaseModel, ValidationError, Field
from loguru import logger
from src.config import settings
from src.engine.docker_executor import DockerExecutor
from src.queue.publisher import ResultPublisher
from tenacity import retry, wait_exponential, stop_after_attempt

class GradingJob(BaseModel):
    submissionId: str = Field(alias="submissionId")
    challengeId: str = Field(alias="challengeId")
    language: str
    files: Dict[str, str]

class GradingConsumer:
    def __init__(self):
        self.executor = DockerExecutor(
            mem_limit=settings.docker_mem_limit,
            pids_limit=settings.docker_pids_limit,
            timeout=settings.docker_timeout_seconds
        )
        self.publisher = ResultPublisher()
        self.connection = None
        self.channel = None

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10))
    def start_consuming(self):
        try:
            logger.info(f"Connecting to RabbitMQ at {settings.rabbitmq_url}")
            parameters = pika.URLParameters(settings.rabbitmq_url)
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            self.channel.queue_declare(queue=settings.grading_queue, durable=True)
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=settings.grading_queue,
                on_message_callback=self._on_message
            )

            logger.info(f"Waiting for messages in {settings.grading_queue}")
            self.channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Connection error: {e}. Reconnecting...")
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            raise
        except Exception as e:
            logger.error(f"Unexpected consumer error: {e}")
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            raise

    def stop_consuming(self):
        if self.channel:
            self.channel.stop_consuming()
        if self.connection:
            self.connection.close()
        logger.info("Consumer stopped.")

    def _on_message(self, ch, method, properties, body):
        logger.info(f"Received message: {body[:100]}...")
        staging_dir = None
        submission_id = None
        try:
            data = json.loads(body)
            job = GradingJob(**data)
            submission_id = job.submissionId
            
            # Setup staging dir
            staging_dir = f"/tmp/grading_stages/{uuid.uuid4()}"
            os.makedirs(staging_dir, exist_ok=True)
            
            # Write all files to the staging directory
            for path, content in job.files.items():
                full_path = os.path.join(staging_dir, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(content)
            
            # Determine command
            command = self._get_default_command(job.language)
            
            # Execute
            result = self.executor.execute(staging_dir, job.language, command)
            
            # Publish back to Java backend (via grading-results-queue)
            self.publisher.publish(submission_id, result)
            
            # Ack
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except ValidationError as e:
            logger.error(f"Invalid message format: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.exception(f"Error processing job: {e}")
            if submission_id:
                try:
                    self.publisher.publish(submission_id, {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Internal error: {str(e)}",
                        "error": True
                    })
                except:
                    pass
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        finally:
            if staging_dir and os.path.exists(staging_dir):
                shutil.rmtree(staging_dir, ignore_errors=True)

    def _get_default_command(self, language: str) -> str:
        if language == "python":
            return "python3 -m pytest"
        elif language in ["node", "javascript", "typescript"]:
            return "npm test"
        elif language == "java":
            return "mvn test"
        return "ls -R"
