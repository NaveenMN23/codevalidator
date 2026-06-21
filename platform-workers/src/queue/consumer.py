import pika
import json
import os
import shutil
import uuid
from typing import Dict, Optional
from pydantic import BaseModel, ValidationError, Field
from loguru import logger
from src.config import settings
from src.engine.docker_executor import DockerExecutor
from src.engine.llm_evaluator import LLMEvaluator
from src.infrastructure.cache import cache_client
from src.queue.publisher import ResultPublisher
from tenacity import retry, wait_exponential, stop_after_attempt

class GradingJob(BaseModel):
    submissionId: str = Field(alias="submissionId")
    challengeId: str = Field(alias="challengeId")
    language: str
    files: Dict[str, str]
    # New fields for AI Evaluation
    isPremium: bool = Field(False, alias="premium")
    remainingTimeSeconds: Optional[int] = 0
    userType: Optional[str] = "B2C"

class GradingConsumer:
    def __init__(self):
        self.executor = DockerExecutor(
            mem_limit=settings.docker_mem_limit,
            pids_limit=settings.docker_pids_limit,
            timeout=settings.docker_timeout_seconds
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
            self.channel.basic_qos(prefetch_count=5) # Increased from 1 for better throughput
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
            
            # Determine base challenge name (e.g., book-my-show-beginner -> book-my-show)
            base_challenge_id = job.challengeId
            for suffix in ["-beginner", "-intermediate", "-advanced"]:
                if base_challenge_id.endswith(suffix):
                    base_challenge_id = base_challenge_id[:-len(suffix)]
                    break

            # INJECT LOCKED FILES (infrastructure files students must not change)
            # These are always taken from the gold master, overwriting whatever the student submitted.
            gold_master_dir = f"/challenges/{base_challenge_id}/apps/gold-master-{job.language}"
            manifest_path = f"/challenges/{base_challenge_id}/manifest.json"
            locked_files = []
            if os.path.exists(manifest_path):
                with open(manifest_path) as mf:
                    locked_files = json.load(mf).get("locked_files", [])
            for rel_path in locked_files:
                src = os.path.join(gold_master_dir, rel_path)
                dst = os.path.join(staging_dir, rel_path)
                if os.path.exists(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    logger.info(f"Injected locked file: {rel_path}")

            # INJECT HIDDEN TESTS (scenario-specific based on challenge level)
            hidden_tests_src = f"/challenges/{base_challenge_id}/apps/gold-master-{job.language}/test-hidden"
            has_hidden_tests = False
            if os.path.exists(hidden_tests_src):
                # Extract level from challengeId (e.g. "book-my-show-beginner" → "beginner")
                level = job.challengeId[len(base_challenge_id)+1:] if len(job.challengeId) > len(base_challenge_id) else ""
                candidate = os.path.join(hidden_tests_src, f"hidden-{level}.test.ts") if level else None
                src_file = candidate if (candidate and os.path.exists(candidate)) else os.path.join(hidden_tests_src, "hidden.test.ts")
                if os.path.exists(src_file):
                    dest_dir = os.path.join(staging_dir, "test-hidden")
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(src_file, os.path.join(dest_dir, "hidden.test.ts"))
                    has_hidden_tests = True
                    logger.info(f"Injected hidden tests: {src_file} → test-hidden/hidden.test.ts")
                else:
                    logger.warning(f"No hidden test file found for level '{level}' in {hidden_tests_src}")
            else:
                logger.warning(f"Hidden tests source NOT FOUND at {hidden_tests_src}")

            # Determine command
            command = self._get_default_command(job.language, has_hidden_tests)
            logger.info(f"Executing grading command: {command}")
            
            # Execute
            result = self.executor.execute(staging_dir, job.language, command, job.challengeId)
            logger.info(f"Raw execution result: stdout={result.get('stdout', '')[:200]}... stderr={result.get('stderr', '')[:200]}...")

            
            # Refine output: Extract first failure for 'one-at-a-time' feedback
            if not result.get("success") and not result.get("error"):
                refined_logs = self._extract_first_failure(
                    result.get("stdout", ""), 
                    result.get("stderr", ""), 
                    job.language
                )
                # Overwrite logs with focused feedback for the UI
                result["logs"] = refined_logs
            else:
                # Fallback: combine stdout/stderr for full context on system errors
                result["logs"] = f"{result.get('stdout', '')}\n{result.get('stderr', '')}"

            # Instant Feedback: Publish base test results immediately
            logger.info(f"Publishing initial test results for submission {submission_id}")
            self.publisher.publish(submission_id, result)
            
            # AI Evaluation (Global toggle + Premium Only + Successful Run)
            if settings.enable_ai_evaluation and job.isPremium and result.get("success"):
                try:
                    logger.info(f"Triggering AI Evaluation for premium submission: {submission_id}")
                    
                    # 1. Fetch Blueprint (Fast O(1) from Redis)
                    blueprint = cache_client.get_blueprint(job.challengeId)
                    
                    if blueprint:
                        # 2. Semantic Caching
                        submission_str = json.dumps(job.files, sort_keys=True)
                        diff_hash = cache_client.get_diff_hash(submission_str)

                        cached_feedback = cache_client.get_semantic_cache(job.challengeId, diff_hash)

                        if cached_feedback:
                            logger.info("Semantic cache hit for AI feedback")
                            result["feedback"] = cached_feedback
                        else:
                            # 3. Filter files for AI evaluation (Optimization)
                            filtered_submission_str = self.llm_evaluator._filter_files(job.files, blueprint)

                            # 4. Call LLM (With Prompt Caching support)
                            feedback = self.llm_evaluator.evaluate(
                                blueprint=blueprint,
                                submission_diff=filtered_submission_str,
                                remaining_time=job.remainingTimeSeconds,
                                user_type=job.userType
                            )
                            result["feedback"] = feedback
                            # Store in semantic cache
                            cache_client.set_semantic_cache(job.challengeId, diff_hash, feedback)

                        # Publish again with AI feedback
                        logger.info(f"Publishing AI feedback for submission {submission_id}")
                        self.publisher.publish(submission_id, result)
                    else:
                        logger.warning(f"AI Evaluation skipped: No blueprint found for challenge {job.challengeId}")
                        result["feedback"] = {
                            "skipped": True,
                            "reason": "evaluation_context_unavailable",
                        }
                        self.publisher.publish(submission_id, result)
                except Exception as eval_error:
                    logger.error(f"AI Evaluation failed (non-blocking): {eval_error}")
            
            # Ack
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except ValidationError as e:
            logger.error(f"Invalid message format: {e}")
            # Try to extract submission_id manually from raw data to notify backend
            try:
                raw_data = json.loads(body)
                sid = raw_data.get("submissionId")
                if sid:
                    self.publisher.publish(sid, {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Message validation error: {str(e)}",
                        "error": True
                    })
            except:
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

    def _get_default_command(self, language: str, has_hidden_tests: bool = False) -> str:
        if language == "python":
            return "python3 -m pytest -x" # -x for fail-fast
        elif language in ["node", "javascript", "typescript"]:
            # node:test directory traversal ignores .ts files by default.
            # We must use 'find' to explicitly pass the .test.ts file paths to the runner.
            dirs = "test test-hidden" if has_hidden_tests else "test"
            return f"node --import tsx/esm --test --test-concurrency=1 $(find {dirs} -name '*.test.ts' 2>/dev/null | sort)"
        elif language == "java":
            return "mvn test -Dsurefire.skipAfterFailureCount=1"
        return "ls -R"

    def _extract_first_failure(self, stdout: str, stderr: str, language: str) -> str:
        """
        Parses test output and extracts the first failing test case and its error.
        Provides a focused 'one-at-a-time' feedback experience.
        """
        combined = f"{stdout}\n{stderr}"
        
        if language in ["node", "javascript", "typescript"]:
            # Node.js TAP output parsing — find first "not ok" and extract just the error message
            lines = combined.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("not ok"):
                    # Strip "not ok N - " prefix to get the test name
                    parts = line.strip().split(" - ", 1)
                    test_name = parts[-1].strip() if len(parts) > 1 else line.strip()

                    # Parse YAML block for the human-readable error: field
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
                                break  # returned to parent indent level — block is done
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
            # Pytest output parsing: Extract the first failure block
            if "FAILURES" in combined:
                try:
                    failure_section = combined.split("FAILURES")[1].split("short test summary info")[0]
                    return failure_section.strip()
                except IndexError:
                    pass
        
        elif language == "java":
            # Maven/Surefire output parsing
            if "Failed tests:" in combined:
                try:
                    failure_section = combined.split("Failed tests:")[1].split("Tests run:")[0]
                    return failure_section.strip()
                except IndexError:
                    pass

        # Fallback: return the last 1000 chars if parsing is unclear
        return combined[-1000:].strip()
