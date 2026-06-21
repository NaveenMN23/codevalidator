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

        # Dead-letter exchange: consistently-rejected messages land in blueprint-dlq
        ch.exchange_declare(exchange="blueprint-dlx", exchange_type="fanout", durable=True)
        ch.queue_declare(queue="blueprint-dlq", durable=True)
        ch.queue_bind(queue="blueprint-dlq", exchange="blueprint-dlx")

        ch.queue_declare(
            queue=settings.blueprint_queue,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "blueprint-dlx",
                "x-message-ttl": 86_400_000,  # 24h before dead-lettering
            },
        )
        return conn, ch

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
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
