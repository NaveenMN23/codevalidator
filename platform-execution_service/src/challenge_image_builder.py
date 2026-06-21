import os
import shutil
import tempfile
from typing import Optional

import docker
import docker.errors
from loguru import logger

CHALLENGES_ROOT = "/challenges"

# Per-language base image to build per-challenge images FROM. Building on top of the base
# (rather than from scratch) reuses its already-cached build-lifecycle plugins (compiler,
# resources, surefire) — a per-challenge build only needs to resolve that challenge's
# specific extra dependencies via `dependency:go-offline`, not the full `mvn test` placeholder
# cycle the base image itself needed (see executors/java/Dockerfile).
BASE_IMAGE_FOR_LANGUAGE = {
    "java": "platform/java-executor:latest",
}

DOCKERFILE_TEMPLATE = """\
FROM {base_image}
WORKDIR /build
COPY pom.xml .
RUN mvn -B dependency:go-offline
WORKDIR /app
"""


class ChallengeImageBuilder:
    """Builds a per-challenge Docker image at publish time (triggered by
    platform-codegen after generating a challenge's zip), so Run/Submit never pays a
    dependency-install cost at click time. See
    docs/design/repo-execution-architecture.md §8 item 6."""

    def __init__(self):
        self.client = docker.from_env()

    def build(self, challenge_id: str, language: str) -> Optional[str]:
        base_image = BASE_IMAGE_FOR_LANGUAGE.get(language)
        if not base_image:
            logger.warning(f"No base image for language '{language}'; skipping per-challenge build")
            return None

        pom_path = os.path.join(CHALLENGES_ROOT, challenge_id, "apps", f"gold-master-{language}", "pom.xml")
        if not os.path.exists(pom_path):
            logger.warning(f"No pom.xml found at {pom_path}; skipping per-challenge build for {challenge_id}")
            return None

        tag = f"platform/{language}-executor-{challenge_id}:latest"
        build_dir = tempfile.mkdtemp(prefix=f"challenge-image-{challenge_id}-")
        try:
            shutil.copy2(pom_path, os.path.join(build_dir, "pom.xml"))
            with open(os.path.join(build_dir, "Dockerfile"), "w") as f:
                f.write(DOCKERFILE_TEMPLATE.format(base_image=base_image))

            logger.info(f"Building per-challenge image {tag} from {pom_path}")
            self.client.images.build(path=build_dir, tag=tag, rm=True)
            logger.info(f"Built per-challenge image {tag}")
            return tag
        except docker.errors.BuildError as e:
            logger.error(f"Failed to build image {tag}: {e}")
            raise
        finally:
            shutil.rmtree(build_dir, ignore_errors=True)
