import json
import pika
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import settings
from infrastructure.logger import log


class ResultPublisher:
    def _connect(self):
        credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)
        params = pika.ConnectionParameters(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            credentials=credentials,
            connection_attempts=3,
            retry_delay=2,
        )
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.queue_declare(queue=settings.codegen_results_queue, durable=True)
        return conn, ch

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def publish(self, job_id: str, msg_type: str, status: str, payload: dict | str | None) -> None:
        conn, ch = self._connect()
        message = {
            "type": msg_type,
            "jobId": job_id,
            "status": status,
            "payload": payload,
        }
        try:
            ch.basic_publish(
                exchange="",
                routing_key=settings.codegen_results_queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            log.info(f"Published result for job {job_id}: type={msg_type} status={status}")
        finally:
            conn.close()


result_publisher = ResultPublisher()
