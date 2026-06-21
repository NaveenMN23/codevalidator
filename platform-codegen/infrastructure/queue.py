import json
import pika
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import settings
from infrastructure.logger import log


class QueuePublisher:
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
        ch.queue_declare(queue=settings.blueprint_queue, durable=True)
        return conn, ch

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def publish(self, queue: str, payload: dict) -> None:
        conn, ch = self._connect()
        try:
            ch.basic_publish(
                exchange="",
                routing_key=queue,
                body=json.dumps(payload),
                properties=pika.BasicProperties(delivery_mode=2),  # persistent
            )
            log.info(f"Published message to queue '{queue}'")
        finally:
            conn.close()


queue_publisher = QueuePublisher()
