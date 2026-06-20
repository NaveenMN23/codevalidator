import docker
import docker.errors
import time
import os
from loguru import logger
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, Retrying

# Name of the persistent internal bridge network used for sandboxed execution.
# internal=True means no external internet access, but loopback (127.0.0.1) works —
# which is required by test code that binds Fastify/Express servers to localhost.
GRADING_NETWORK_NAME = "platform_grading_isolated"


class DockerExecutor:
    def __init__(self, mem_limit: str = "512m", pids_limit: int = 50, timeout: int = 30):
        self.client = docker.from_env()
        self.mem_limit = mem_limit
        self.pids_limit = pids_limit
        self.timeout = timeout
        self.grading_network_id = self._ensure_grading_network()

    def _ensure_grading_network(self) -> str:
        """Create the isolated grading network if it doesn't exist, then return its ID.

        internal=True: containers can use loopback (localhost binds work) but
        have no route to the external internet — equivalent security to network_disabled
        without removing the loopback interface that test servers depend on."""
        try:
            return self.client.networks.get(GRADING_NETWORK_NAME).id
        except docker.errors.NotFound:
            net = self.client.networks.create(
                GRADING_NETWORK_NAME,
                driver="bridge",
                internal=True,
                check_duplicate=True,
            )
            logger.info(f"Created isolated grading network: {GRADING_NETWORK_NAME}")
            return net.id
        except Exception as e:
            logger.error(f"Failed to create/get grading network: {e}")
            return None

    def pre_pull_images(self):
        """Pre-pulls public execution images to reduce cold-start latency.
        Locally-built images (platform/*) are excluded — they can't be pulled from Docker Hub."""
        images = ["openjdk:17-jdk-slim"]
        for image in images:
            try:
                logger.info(f"Pre-pulling Docker image: {image}")
                self.client.images.pull(image)
            except Exception as e:
                logger.warning(f"Failed to pre-pull image {image}: {e}")

    def execute(self, local_dir: str, language: str, command: str, challenge_id: str = "default") -> Dict[str, Any]:
        image = self._get_image_for_language(language)
        if not image:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Unsupported language: {language}",
                "error": True
            }

        logger.info(f"Executing {language} code in {local_dir} using image {image}")

        # Java still needs dependency installation (Maven); Node/Python deps are baked into executor images
        if language == "java":
            self._install_dependencies(local_dir, language, image, challenge_id)

        # Right-size memory per language: JVM needs more headroom than Node/Python tests
        lang_mem_limits = {"java": "512m"}
        mem_limit = lang_mem_limits.get(language.lower(), "256m")

        container = None
        start_time = time.time()
        try:
            volumes = {}
            if language in ["node", "javascript", "typescript"]:
                # Mount submission at /tmp/submission
                volumes[local_dir] = {'bind': '/tmp/submission', 'mode': 'ro'}

                command = (
                    f'sh -c "cp -r /tmp/submission/. /app/ && '
                    f'rm -rf /app/node_modules && '
                    f'ln -s /node_modules /app/node_modules && '
                    f'cd /app && {command}"'
                )
            elif language == "java":
                volumes[local_dir] = {'bind': '/app', 'mode': 'rw'}
                volumes["platform_maven_cache"] = {'bind': '/root/.m2', 'mode': 'rw'}
            else:
                volumes[local_dir] = {'bind': '/app', 'mode': 'rw'}

            network_kwargs = {}
            if self.grading_network_id:
                # Internal bridge: loopback works (test servers can bind to localhost),
                # no external internet access (internal=True on the network).
                network_kwargs["network"] = self.grading_network_id
            else:
                # Fallback if network creation failed — at least disable networking entirely
                network_kwargs["network_disabled"] = True

            # esbuild (used by tsx) spawns OS threads for GC goroutines; 50 is too low
            effective_pids = 200 if language in ["node", "javascript", "typescript"] else self.pids_limit
            # JVM startup + compilation needs more time than interpreted languages
            effective_timeout = 45 if language == "java" else self.timeout

            container = self.client.containers.run(
                image,
                command=command,
                volumes=volumes,
                working_dir='/app',
                detach=True,
                mem_limit=mem_limit,
                pids_limit=effective_pids,
                environment={"NODE_OPTIONS": "--dns-result-order=ipv4first"},
                **network_kwargs,
            )

            # Wait for completion or timeout
            while True:
                for attempt in Retrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=4),
                    retry=retry_if_exception_type((docker.errors.APIError, ConnectionError))
                ):
                    with attempt:
                        container.reload()

                if container.status not in ["created", "running"]:
                    break

                if time.time() - start_time > effective_timeout:
                    container.stop(timeout=1)
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Execution timed out after {self.timeout} seconds",
                        "error": True
                    }
                time.sleep(0.1)

            for attempt in Retrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=4),
                retry=retry_if_exception_type((docker.errors.APIError, ConnectionError))
            ):
                with attempt:
                    result = container.wait()
                    stdout_logs = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
                    stderr_logs = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')

            return {
                "success": result.get("StatusCode") == 0,
                "stdout": stdout_logs,
                "stderr": stderr_logs,
                "error": False,
                "exit_code": result.get("StatusCode")
            }

        except docker.errors.ContainerError as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "error": True
            }
        except Exception as e:
            logger.exception("Docker execution error")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "error": True
            }
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception as e:
                    logger.warning(f"Failed to remove container: {e}")

    def _install_dependencies(self, local_dir: str, language: str, image: str, challenge_id: str = "default"):
        """Pre-execution phase: Install dependencies with network access enabled and persistent caching.
        Only called for Java — Node.js and Python deps are baked into their executor images."""
        install_cmd = None
        volumes = {local_dir: {'bind': '/app', 'mode': 'rw'}}
        environment = {"NODE_ENV": "development"}

        if language == "java":
            install_cmd = "mvn dependency:go-offline"
            volumes["platform_maven_cache"] = {'bind': '/root/.m2', 'mode': 'rw'}
            environment["MAVEN_OPTS"] = "-Dmaven.repo.local=/root/.m2/repository"

        if not install_cmd:
            return

        logger.info(f"Running pre-execution dependency install for {language} with caching (challenge: {challenge_id})")
        try:
            self.client.containers.run(
                image,
                command=install_cmd,
                volumes=volumes,
                working_dir='/app',
                remove=True,
                network_disabled=False,
                mem_limit="1g",
                environment=environment
            )
        except docker.errors.ContainerError as e:
            logger.warning(f"Dependency installation failed: {e.stderr.decode('utf-8') if e.stderr else str(e)}")
        except Exception as e:
            logger.error(f"Error during dependency installation: {e}")

    def _get_image_for_language(self, language: str) -> Optional[str]:
        mapping = {
            "python": "platform/python-executor:latest",
            "node": "platform/node-executor:latest",
            "javascript": "platform/node-executor:latest",
            "typescript": "platform/node-executor:latest",
            "java": "openjdk:17-jdk-slim",
            "cpp": "gcc:13",
            "c": "gcc:13"
        }
        return mapping.get(language.lower())
