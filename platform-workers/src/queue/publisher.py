import pika
import json
from loguru import logger
from tenacity import retry, wait_exponential, stop_after_attempt
from src.config import settings

class ResultPublisher:
    def __init__(self):
        self.connection = None
        self.channel = None
        self._connect()

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(5))
    def _connect(self):
        if self.connection and not self.connection.is_closed:
            return

        logger.info(f"Connecting to RabbitMQ for publishing...")
        parameters = pika.URLParameters(settings.rabbitmq_url)
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=settings.grading_results_queue, durable=True)
        logger.info("Publisher connected to RabbitMQ.")

    def publish(self, submission_id: str, result: dict):
        try:
            self._connect()
            
            # Map Python result to Java GradingResult DTO
            message = {
                "submissionId": submission_id,
                "status": "SUCCESS" if result.get("success") else "FAILED",
                "score": 100 if result.get("success") else 0, # Placeholder for real scoring logic
                "output": result.get("stdout", ""),
                "errorOutput": result.get("stderr", ""),
                "exitCode": result.get("exit_code", 1 if result.get("error") else 0)
            }
            
            if "timed out" in result.get("stderr", "").lower():
                message["status"] = "TIMEOUT"

            self.channel.basic_publish(
                exchange='',
                routing_key=settings.grading_results_queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                )
            )
            logger.info(f"Published result for submission {submission_id}")
        except Exception as e:
            logger.error(f"Failed to publish result for submission {submission_id}: {e}")
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
            self.connection = None
            raise
