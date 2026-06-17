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

    def _truncate_log(self, log: str, max_size: int = 51200) -> str:
        """Truncates log string to max_size (default 50KB)."""
        if not log:
            return ""
        if len(log) <= max_size:
            return log
        return log[:max_size] + "\n\n[... Log truncated due to size limits ...]"

    def publish(self, submission_id: str, result: dict):
        # Retry once if the connection is lost
        for attempt in range(2):
            try:
                self._connect()
                
                # Map Python result to Java GradingResult DTO
                # For test failures, use the refined one-at-a-time message from _extract_first_failure.
                # For success/system-errors, fall back to raw stdout/stderr.
                # Optimization: Truncate logs to prevent RabbitMQ bottlenecks
                is_test_failure = not result.get("success") and not result.get("error")
                if is_test_failure and result.get("logs"):
                    output_to_send = result.get("logs", "")
                    error_to_send = ""  # refined message has full context; raw stderr is noise
                else:
                    output_to_send = result.get("stdout", "")
                    error_to_send = result.get("stderr", "")

                message = {
                    "submissionId": submission_id,
                    "status": "COMPLETED" if result.get("success") else "FAILED",
                    "score": result.get("feedback", {}).get("correctness", {}).get("score", 100 if result.get("success") else 0),
                    "output": self._truncate_log(output_to_send),
                    "errorOutput": self._truncate_log(error_to_send),
                    "exitCode": result.get("exit_code", 1 if result.get("error") else 0),
                    "feedback": result.get("feedback")
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
                return # Success
            except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
                logger.warning(f"Connection lost while publishing for {submission_id} (attempt {attempt+1}): {e}")
                if self.connection:
                    try:
                        self.connection.close()
                    except:
                        pass
                self.connection = None
                if attempt == 1: # Last attempt
                    raise
            except Exception as e:
                logger.error(f"Failed to publish result for submission {submission_id}: {e}")
                raise
