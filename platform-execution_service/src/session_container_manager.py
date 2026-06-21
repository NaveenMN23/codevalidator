import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import Dict, Optional

import docker
import docker.errors
from loguru import logger

from src.gold_master_client import gold_master_client

SESSION_STAGING_ROOT = "/tmp/sessions"

# Name of the persistent internal bridge network used for sandboxed execution.
# internal=True means no external internet access, but loopback (127.0.0.1) works —
# required by test code that binds servers to localhost (e.g. Spring Boot web tests).
GRADING_NETWORK_NAME = "platform_grading_isolated"

SUPPORTED_LANGUAGES = {"java"}

# Containers are created long-running (not one-shot) so they can be reused across
# multiple Run/Submit calls for the same session — the actual point of Deferred Eager.
KEEPALIVE_COMMAND = "sleep infinity"


@dataclass
class SessionEntry:
    container_id: str
    challenge_id: str
    language: str
    staging_dir: str
    last_activity: float = field(default_factory=time.time)
    # Guards this session's own write+exec sequence — NOT the manager's global self._lock
    # (which only protects the _sessions dict itself). Holding the global lock across a
    # multi-second exec would serialize every session through the whole service; this lock
    # only ever blocks another Run/Submit on the *same* session, which is fine since one
    # browser tab can't really do two things on one session at once anyway. Submit relies on
    # this to keep the hidden test file safe from a concurrent Run on the same session.
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionContainerManager:
    """Owns the session->container registry for Deferred Eager: creates a container on
    a session's first call, reuses it for subsequent calls, and reaps it after an idle
    timeout. One container is always single-session — never shared across concurrent users."""

    def __init__(
        self,
        idle_timeout_seconds: int = 600,
        reap_interval_seconds: int = 30,
        mem_limit: str = "512m",
        pids_limit: int = 200,
        exec_timeout_seconds: int = 60,
    ):
        self.client = docker.from_env()
        self.idle_timeout_seconds = idle_timeout_seconds
        self.reap_interval_seconds = reap_interval_seconds
        self.mem_limit = mem_limit
        self.pids_limit = pids_limit
        self.exec_timeout_seconds = exec_timeout_seconds
        self._sessions: Dict[str, SessionEntry] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._reaper_thread = threading.Thread(target=self._reap_loop, daemon=True)
        self._network_id = self._ensure_network()
        self._exec_pool = ThreadPoolExecutor(max_workers=32, thread_name_prefix="session-exec")

    def start(self):
        self._reaper_thread.start()
        logger.info(f"Session reaper started (idle timeout {self.idle_timeout_seconds}s)")

    def stop(self):
        self._stop_event.set()

    def execute(self, session_id: str, challenge_id: str, language: str,
                files: Dict[str, str], command: str) -> dict:
        entry = self._get_or_create_entry(session_id, challenge_id, language)

        with entry.lock:
            self._write_files(entry.staging_dir, files)
            with self._lock:
                entry.last_activity = time.time()
            return self._run_with_timeout(session_id, entry.container_id, command)

    def submit(self, session_id: str, challenge_id: str, tier: str, language: str,
               files: Dict[str, str], command: str) -> dict:
        entry = self._get_or_create_entry(session_id, challenge_id, language)

        with entry.lock:
            self._write_files(entry.staging_dir, files)

            gold_master = gold_master_client.fetch(challenge_id, tier, language)
            self._write_files(entry.staging_dir, gold_master["locked_files"])
            hidden_test_path = gold_master["hidden_test_path"]
            self._write_files(entry.staging_dir, {hidden_test_path: gold_master["hidden_test_content"]})

            with self._lock:
                entry.last_activity = time.time()

            try:
                return self._run_with_timeout(session_id, entry.container_id, command)
            finally:
                # Hidden test never lingers past this one Submit call — locked files are left
                # in place (they're not secret, just infra a student shouldn't have tampered
                # with, and correcting them benefits any later Run on this session too).
                self._delete_file(entry.staging_dir, hidden_test_path)

    def _get_or_create_entry(self, session_id: str, challenge_id: str, language: str) -> SessionEntry:
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None or not self._container_alive(entry.container_id):
                entry = self._create_session(session_id, challenge_id, language)
            return entry

    def _run_with_timeout(self, session_id: str, container_id: str, command: str) -> dict:
        future = self._exec_pool.submit(self._exec_in_container, container_id, command)
        try:
            return future.result(timeout=self.exec_timeout_seconds)
        except FutureTimeoutError:
            logger.warning(
                f"Exec timed out after {self.exec_timeout_seconds}s for session {session_id}; "
                f"killing container {container_id[:12]} (hung command leaves it unusable for reuse)"
            )
            self._force_remove(container_id)
            with self._lock:
                self._sessions.pop(session_id, None)
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.exec_timeout_seconds} seconds",
                "exit_code": -1,
            }

    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _ensure_network(self) -> Optional[str]:
        try:
            return self.client.networks.get(GRADING_NETWORK_NAME).id
        except docker.errors.NotFound:
            net = self.client.networks.create(GRADING_NETWORK_NAME, driver="bridge", internal=True)
            logger.info(f"Created isolated network: {GRADING_NETWORK_NAME}")
            return net.id
        except Exception as e:
            logger.error(f"Failed to create/get network: {e}")
            return None

    def _container_alive(self, container_id: str) -> bool:
        try:
            container = self.client.containers.get(container_id)
            return container.status == "running"
        except docker.errors.NotFound:
            return False

    def _resolve_image(self, challenge_id: str, language: str) -> str:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")

        image = f"platform/{language}-executor-{challenge_id}:latest"
        try:
            self.client.images.get(image)
        except docker.errors.NotFound:
            # No fallback to a generic base image: a challenge must be published (which
            # triggers ChallengeImageBuilder) before it can be Run. Silently degrading to
            # a generic image would mean running against the wrong dependency set.
            raise ValueError(
                f"No published image found for challenge '{challenge_id}' ({language}). "
                f"Publish the challenge first so its image can be built."
            )
        return image

    def _create_session(self, session_id: str, challenge_id: str, language: str) -> SessionEntry:
        image = self._resolve_image(challenge_id, language)

        staging_dir = os.path.join(SESSION_STAGING_ROOT, session_id)
        os.makedirs(staging_dir, exist_ok=True)

        network_kwargs = {"network": self._network_id} if self._network_id else {"network_disabled": True}

        container = self.client.containers.run(
            image,
            command=KEEPALIVE_COMMAND,
            volumes={staging_dir: {"bind": "/app", "mode": "rw"}},
            working_dir="/app",
            detach=True,
            mem_limit=self.mem_limit,
            pids_limit=self.pids_limit,
            **network_kwargs,
        )
        logger.info(
            f"Created warm container {container.id[:12]} for session {session_id} "
            f"({challenge_id}/{language})"
        )

        entry = SessionEntry(
            container_id=container.id,
            challenge_id=challenge_id,
            language=language,
            staging_dir=staging_dir,
        )
        self._sessions[session_id] = entry
        return entry

    def _write_files(self, staging_dir: str, files: Dict[str, str]):
        for rel_path, content in files.items():
            full_path = os.path.join(staging_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)

    def _delete_file(self, staging_dir: str, rel_path: str):
        full_path = os.path.join(staging_dir, rel_path)
        try:
            os.remove(full_path)
        except FileNotFoundError:
            pass

    def _exec_in_container(self, container_id: str, command: str) -> dict:
        container = self.client.containers.get(container_id)
        exit_code, output = container.exec_run(
            cmd=["sh", "-c", command],
            workdir="/app",
            demux=True,
        )
        stdout, stderr = output
        return {
            "success": exit_code == 0,
            "stdout": (stdout or b"").decode("utf-8", errors="replace"),
            "stderr": (stderr or b"").decode("utf-8", errors="replace"),
            "exit_code": exit_code,
        }

    def _force_remove(self, container_id: str):
        try:
            self.client.containers.get(container_id).remove(force=True)
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logger.warning(f"Failed to force-remove container {container_id[:12]}: {e}")

    def _reap_loop(self):
        while not self._stop_event.wait(self.reap_interval_seconds):
            self._reap_idle_sessions()

    def _reap_idle_sessions(self):
        now = time.time()
        with self._lock:
            idle_ids = [
                sid for sid, entry in self._sessions.items()
                if now - entry.last_activity > self.idle_timeout_seconds
            ]
            reaped = [(sid, self._sessions.pop(sid)) for sid in idle_ids]

        for session_id, entry in reaped:
            self._destroy_session(session_id, entry)

    def _destroy_session(self, session_id: str, entry: SessionEntry):
        try:
            container = self.client.containers.get(entry.container_id)
            container.remove(force=True)
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logger.warning(f"Failed to remove container for session {session_id}: {e}")
        shutil.rmtree(entry.staging_dir, ignore_errors=True)
        logger.info(f"Reaped idle session {session_id} (container {entry.container_id[:12]})")
