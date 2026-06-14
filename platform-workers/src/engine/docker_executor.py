import docker
import time
from loguru import logger
from typing import Dict, Any, Optional

class DockerExecutor:
    def __init__(self, mem_limit: str = "512m", pids_limit: int = 50, timeout: int = 30):
        self.client = docker.from_env()
        self.mem_limit = mem_limit
        self.pids_limit = pids_limit
        self.timeout = timeout

    def execute(self, local_dir: str, language: str, command: str) -> Dict[str, Any]:
        image = self._get_image_for_language(language)
        if not image:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Unsupported language: {language}",
                "error": True
            }

        logger.info(f"Executing {language} code in {local_dir} using image {image}")
        container = None
        start_time = time.time()
        try:
            container = self.client.containers.run(
                image,
                command=command,
                volumes={local_dir: {'bind': '/app', 'mode': 'rw'}},
                working_dir='/app',
                detach=True,
                mem_limit=self.mem_limit,
                pids_limit=self.pids_limit,
                network_disabled=True,
            )

            # Wait for completion or timeout
            while container.status in ["created", "running"]:
                if time.time() - start_time > self.timeout:
                    container.stop(timeout=1)
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Execution timed out after {self.timeout} seconds",
                        "error": True
                    }
                time.sleep(0.1)
                container.reload()

            result = container.wait()
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            stderr_logs = container.logs(stdout=False, stderr=True).decode('utf-8')
            stdout_logs = container.logs(stdout=True, stderr=False).decode('utf-8')

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

    def _get_image_for_language(self, language: str) -> Optional[str]:
        mapping = {
            "python": "python:3.11-slim",
            "node": "node:20-alpine",
            "javascript": "node:20-alpine",
            "typescript": "node:20-alpine",
            "java": "openjdk:17-jdk-slim",
            "cpp": "gcc:13",
            "c": "gcc:13"
        }
        return mapping.get(language.lower())
