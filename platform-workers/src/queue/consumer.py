import pika
import json
import os
import shutil
import uuid
import requests
from typing import Dict, Optional
from pydantic import BaseModel, ValidationError, Field
from loguru import logger
from src.config import settings
from src.engine.docker_executor import DockerExecutor
from src.engine.llm_evaluator import LLMEvaluator
from src.infrastructure.cache import cache_client
from src.infrastructure.storage import gold_master_storage
from src.queue.publisher import ResultPublisher
from tenacity import retry, wait_exponential, stop_after_attempt

_KNOWN_TIERS = {"easy", "medium", "hard", "advanced", "beginner", "intermediate"}


class GradingJob(BaseModel):
    submissionId: str = Field(alias="submissionId")
    challengeId: str = Field(alias="challengeId")
    language: str
    files: Dict[str, str]
    isPremium: bool = Field(False, alias="premium")
    remainingTimeSeconds: Optional[int] = 0
    userType: Optional[str] = "B2C"


def _split_challenge_id(challenge_id: str) -> tuple[str, str, str]:
    """Split a challengeId into (challenge_name, tier, scenario_tag).

    Handles both formats:
      New: 'vending-machine-easy-dispense-product' → ('vending-machine', 'easy', 'easy-dispense-product')
      Legacy: 'book-my-show-easy' → ('book-my-show', 'easy', 'easy')
    """
    parts = challenge_id.split("-")
    for i, part in enumerate(parts):
        if part in _KNOWN_TIERS and i > 0:
            challenge_name = "-".join(parts[:i])
            tier = part
            scenario_tag = "-".join(parts[i:])
            return challenge_name, tier, scenario_tag
    return challenge_id, "", challenge_id


class GradingConsumer:
    def __init__(self):
        self.executor = DockerExecutor(
            mem_limit=settings.docker_mem_limit,
            pids_limit=settings.docker_pids_limit,
            timeout=settings.docker_timeout_seconds,
        )
        self.llm_evaluator = LLMEvaluator()
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
            self.channel.basic_qos(prefetch_count=5)
            self.channel.basic_consume(
                queue=settings.grading_queue,
                on_message_callback=self._on_message,
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

            staging_dir = f"/tmp/grading_stages/{uuid.uuid4()}"
            os.makedirs(staging_dir, exist_ok=True)

            # Write submission files to staging dir
            for path, content in job.files.items():
                full_path = os.path.join(staging_dir, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(content)

            base_challenge_id, tier, scenario_tag = _split_challenge_id(job.challengeId)

            # INJECT LOCKED FILES from gold master in MinIO (if any)
            if tier:
                manifest = gold_master_storage.get_manifest(base_challenge_id, tier, job.language)
                locked_files = manifest.get("locked_files", [])
                if locked_files:
                    src_files = gold_master_storage.get_src_files(
                        base_challenge_id, tier, job.language
                    )
                    for rel_path in locked_files:
                        content = src_files.get(rel_path)
                        if content:
                            dst = os.path.join(staging_dir, rel_path)
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            with open(dst, "w", encoding="utf-8") as f:
                                f.write(content)
                            logger.info(f"Injected locked file from MinIO: {rel_path}")

            # INJECT HIDDEN TESTS — on-demand from MinIO (no filesystem dependency)
            # Fetches all tests for the tier, then selects only the scenario-specific one.
            has_hidden_tests = False
            if tier:
                all_hidden = gold_master_storage.get_hidden_tests(
                    base_challenge_id, tier, job.language
                )
                # Pick the test file for this specific scenario (hidden-{scenario_tag}.*)
                hidden_tests = {
                    k: v for k, v in all_hidden.items()
                    if scenario_tag and scenario_tag in k
                } if scenario_tag else all_hidden

                # Fallback to any available test if scenario-specific one is missing
                if not hidden_tests and all_hidden:
                    hidden_tests = dict(list(all_hidden.items())[:1])
                    logger.warning(
                        f"Scenario-specific test for {scenario_tag!r} not found, "
                        f"falling back to first available test"
                    )

                if hidden_tests:
                    dest_dir = os.path.join(staging_dir, "test-hidden")
                    os.makedirs(dest_dir, exist_ok=True)
                    for filename, content in hidden_tests.items():
                        with open(os.path.join(dest_dir, filename), "w") as f:
                            f.write(content)
                    # Canonicalise to hidden.test.ts so the run command is consistent
                    first_test = next(iter(hidden_tests))
                    canonical = os.path.join(dest_dir, "hidden.test.ts")
                    if not os.path.exists(canonical) and first_test != "hidden.test.ts":
                        shutil.copy2(os.path.join(dest_dir, first_test), canonical)
                    has_hidden_tests = True
                    logger.info(
                        f"Injected hidden test for {scenario_tag!r} "
                        f"({base_challenge_id}/{tier}/{job.language})"
                    )
                else:
                    logger.warning(
                        f"No hidden tests found in MinIO for "
                        f"{base_challenge_id}/{tier}/{job.language} — grading without them"
                    )
            else:
                logger.warning(
                    f"No tier for challengeId={job.challengeId!r} — skipping hidden test injection"
                )

            # Execute in Docker sandbox
            command = self._get_default_command(job.language, has_hidden_tests)
            logger.info(f"Executing grading command: {command}")
            result = self.executor.execute(staging_dir, job.language, command, job.challengeId)
            logger.info(
                f"Execution result: stdout={result.get('stdout', '')[:200]}... "
                f"stderr={result.get('stderr', '')[:200]}..."
            )

            # Extract first failure for one-at-a-time feedback UX
            if not result.get("success") and not result.get("error"):
                result["logs"] = self._extract_first_failure(
                    result.get("stdout", ""),
                    result.get("stderr", ""),
                    job.language,
                )
            else:
                result["logs"] = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".strip()

            # Publish initial test results immediately
            logger.info(f"Publishing initial test results for submission {submission_id}")
            self.publisher.publish(submission_id, result)

            # AI Evaluation — premium submissions only
            if settings.enable_ai_evaluation and job.isPremium and result.get("success"):
                try:
                    logger.info(f"Triggering AI evaluation for {submission_id}")

                    # 1. Fetch blueprint: Redis → Postgres fallback
                    blueprint = self._get_blueprint(job.challengeId)

                    if blueprint:
                        submission_str = json.dumps(job.files, sort_keys=True)
                        diff_hash = cache_client.get_diff_hash(submission_str)
                        cached_feedback = cache_client.get_semantic_cache(
                            job.challengeId, diff_hash
                        )

                        if cached_feedback:
                            logger.info("Semantic cache hit for AI feedback")
                            result["feedback"] = cached_feedback
                        else:
                            filtered_submission_str = self.llm_evaluator._filter_files(
                                job.files, blueprint
                            )
                            feedback = self.llm_evaluator.evaluate(
                                blueprint=blueprint,
                                submission_diff=filtered_submission_str,
                                test_results=result.get("logs", ""),
                                remaining_time=job.remainingTimeSeconds,
                                user_type=job.userType,
                            )
                            result["feedback"] = feedback
                            cache_client.set_semantic_cache(
                                job.challengeId, diff_hash, feedback
                            )

                        logger.info(f"Publishing AI feedback for {submission_id}")
                        self.publisher.publish(submission_id, result)
                    else:
                        logger.warning(
                            f"AI evaluation skipped: no blueprint for {job.challengeId}"
                        )
                except Exception as eval_error:
                    logger.error(f"AI evaluation failed (non-blocking): {eval_error}")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except ValidationError as e:
            logger.error(f"Invalid message format: {e}")
            try:
                raw_data = json.loads(body)
                sid = raw_data.get("submissionId")
                if sid:
                    self.publisher.publish(sid, {
                        "success": False, "stdout": "",
                        "stderr": f"Message validation error: {str(e)}", "error": True,
                    })
            except Exception:
                pass
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.exception(f"Error processing job: {e}")
            if submission_id:
                try:
                    self.publisher.publish(submission_id, {
                        "success": False, "stdout": "",
                        "stderr": f"Internal error: {str(e)}", "error": True,
                    })
                except Exception:
                    pass
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        finally:
            if staging_dir and os.path.exists(staging_dir):
                shutil.rmtree(staging_dir, ignore_errors=True)

    def _get_blueprint(self, challenge_id: str) -> Optional[dict]:
        """Fetch blueprint from Redis; fall back to Postgres via backend API on cache miss."""
        blueprint = cache_client.get_blueprint(challenge_id)
        if blueprint:
            return blueprint

        try:
            resp = requests.get(
                f"{settings.backend_url}/api/admin/blueprints/{challenge_id}",
                timeout=5,
            )
            if resp.ok:
                blueprint = resp.json()
                # Re-warm Redis so future requests are fast
                try:
                    cache_client.redis.set(
                        f"blueprint:{challenge_id}",
                        json.dumps(blueprint),
                        ex=86400,
                    )
                except Exception:
                    pass
                logger.info(f"Blueprint fetched from Postgres and Redis re-warmed for {challenge_id}")
                return blueprint
        except Exception as e:
            logger.warning(f"Postgres blueprint fallback failed for {challenge_id}: {e}")
        return None

    def _get_default_command(self, language: str, has_hidden_tests: bool = False) -> str:
        if language == "python":
            return "python3 -m pytest -x"
        elif language in ["node", "javascript", "typescript"]:
            dirs = "test test-hidden" if has_hidden_tests else "test"
            return (
                f"node --import tsx/esm --test --test-concurrency=1 "
                f"$(find {dirs} -name '*.test.ts' 2>/dev/null | sort)"
            )
        elif language == "java":
            return "mvn test -Dsurefire.skipAfterFailureCount=1"
        return "ls -R"

    def _extract_first_failure(self, stdout: str, stderr: str, language: str) -> str:
        combined = f"{stdout}\n{stderr}"

        if language in ["node", "javascript", "typescript"]:
            lines = combined.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("not ok"):
                    parts = line.strip().split(" - ", 1)
                    test_name = parts[-1].strip() if len(parts) > 1 else line.strip()
                    error_msg = ""
                    multiline_next = False
                    block_lines = []
                    error_indent = 0
                    for j in range(i + 1, min(i + 40, len(lines))):
                        raw = lines[j]
                        stripped = raw.strip()
                        if stripped == "...":
                            break
                        if multiline_next:
                            cur_indent = len(raw) - len(raw.lstrip()) if stripped else error_indent + 4
                            if stripped and cur_indent <= error_indent:
                                break
                            block_lines.append(stripped)
                        elif stripped.startswith("error:"):
                            val = stripped[len("error:"):].strip().strip("'\"")
                            if val and val not in ("|-", "|"):
                                error_msg = val
                                break
                            else:
                                multiline_next = True
                                error_indent = len(raw) - len(raw.lstrip())
                    if not error_msg and block_lines:
                        error_msg = "\n".join(block_lines).strip()
                    if error_msg:
                        return f"❌ Failed: {test_name}\n\n{error_msg}"
                    return f"❌ Failed: {test_name}"

        elif language == "python":
            if "FAILURES" in combined:
                try:
                    failure_section = combined.split("FAILURES")[1].split("short test summary info")[0]
                    return failure_section.strip()
                except IndexError:
                    pass

        elif language == "java":
            if "Failed tests:" in combined:
                try:
                    failure_section = combined.split("Failed tests:")[1].split("Tests run:")[0]
                    return failure_section.strip()
                except IndexError:
                    pass

        return combined[-1000:].strip()
