import json
import threading
import pika
from tenacity import retry, stop_after_attempt, wait_exponential
from config.settings import settings
from infrastructure.logger import log
from infrastructure.result_publisher import result_publisher


def _handle_design_preview(job_id: str, body: dict) -> None:
    from services.scaffold_generator import scaffold_generator
    try:
        design_output = scaffold_generator.generate_design_only(
            problem_description=body["prompt"],
            languages=body.get("languages", ["node"]),
            tiers=body.get("tiers", ["easy", "medium", "hard"]),
            scenarios_per_tier=body.get("scenariosPerTier", 3),
            debug_scenarios_per_tier=body.get("debugScenariosPerTier", 1),
            feedback=body.get("feedback"),
        )
        result_publisher.publish(job_id, "DESIGN_PREVIEW", "COMPLETED", design_output)
    except Exception as e:
        log.error(f"DESIGN_PREVIEW failed for job {job_id}: {e}")
        result_publisher.publish(job_id, "DESIGN_PREVIEW", "FAILED", str(e))


def _handle_full_generate(job_id: str, body: dict) -> None:
    from services.scaffold_generator import scaffold_generator
    from infrastructure.storage import storage_client
    try:
        storage_client.reset_tracker()
        result = scaffold_generator.generate(
            problem_description=body["prompt"],
            languages=body.get("languages", ["node"]),
            tiers=body.get("tiers", ["easy", "medium", "hard"]),
            scenarios_per_tier=body.get("scenariosPerTier", 3),
            debug_scenarios_per_tier=body.get("debugScenariosPerTier", 1),
            design_json=body.get("designJson"),
        )
        
        failed_scaffolds = result.get("warnings", {}).get("failed_scaffolds", [])
        if failed_scaffolds:
            raise RuntimeError(f"Code generation failed compilation for scaffolds: {failed_scaffolds}")
            
        result_publisher.publish(job_id, "FULL_GENERATE", "COMPLETED", result)
    except Exception as e:
        log.error(f"FULL_GENERATE failed for job {job_id}: {e}")
        storage_client.rollback_uploads()
        result_publisher.publish(job_id, "FULL_GENERATE", "FAILED", str(e))


def _on_message(ch, method, properties, body):
    try:
        message = json.loads(body)
        job_id = message.get("jobId", "unknown")
        msg_type = message.get("type", "")
        log.info(f"Consumed codegen request: type={msg_type} jobId={job_id}")

        if msg_type == "DESIGN_PREVIEW":
            _handle_design_preview(job_id, message)
        elif msg_type == "FULL_GENERATE":
            _handle_full_generate(job_id, message)
        else:
            log.warning(f"Unknown message type: {msg_type}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        log.error(f"Fatal error processing codegen request: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


@retry(stop=stop_after_attempt(10), wait=wait_exponential(multiplier=2, min=2, max=30))
def _connect_and_consume():
    credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)
    params = pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        credentials=credentials,
        connection_attempts=3,
        retry_delay=2,
        heartbeat=300,
    )
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue=settings.codegen_request_queue, durable=True)
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue=settings.codegen_request_queue, on_message_callback=_on_message)
    log.info(f"Codegen consumer listening on '{settings.codegen_request_queue}'")
    ch.start_consuming()


def start():
    while True:
        try:
            _connect_and_consume()
        except Exception as e:
            log.error(f"Codegen consumer disconnected: {e}. Reconnecting...")


def start_in_background():
    t = threading.Thread(target=start, daemon=True, name="codegen-consumer")
    t.start()
    log.info("Codegen RabbitMQ consumer started in background thread")
