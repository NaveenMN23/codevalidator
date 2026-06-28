import hashlib
import os
from pathlib import Path
from infrastructure.cache import cache_client
from infrastructure.storage import storage_client
from infrastructure.logger import log
from generator.engine import generator
from services.llm import llm_service

class ChallengeOrchestrator:
    def _hash_challenge_source(self, challenge_name: str, language: str) -> str:
        """Hash all gold-master source files so cache auto-invalidates when files change."""
        challenge_dir = Path(f"/challenges/{challenge_name}/apps/gold-master-{language}")
        if not challenge_dir.exists():
            return ""
        h = hashlib.sha256()
        for f in sorted(challenge_dir.rglob("*")):
            if f.is_file() and "node_modules" not in str(f):
                h.update(f.read_bytes())
        return h.hexdigest()[:12]

    def orchestrate_generation(self, challenge_name: str, language: str, tags: list) -> str:
        # 1. Check Cache — key includes source hash so new/changed files auto-bust the cache
        source_hash = self._hash_challenge_source(challenge_name, language)
        cache_key = cache_client.get_cache_key(challenge_name, language, tags, source_hash)
        cached_url = cache_client.get(cache_key)
        
        if cached_url:
            log.info(f"Cache hit for {challenge_name} with tags {tags}")
            return cached_url

        log.info(f"Cache miss for {challenge_name} with tags {tags}. Generating...")

        # 2. Generate ZIP
        try:
            zip_path = generator.generate(challenge_name, language, tags)
        except Exception as e:
            log.error(f"Generation failed: {e}")
            raise e

        # 3. Upload to S3
        s3_key = f"{language}/{zip_path.name}"
        success = storage_client.upload_file(zip_path, s3_key)
        
        if not success:
            raise Exception("Failed to upload generated challenge to storage")

        # 4. Generate and Dispatch Blueprint (AI Evaluation Context)
        # We use a challenge ID that matches what the backend expects
        challenge_id = zip_path.stem # e.g. "lru-cache-java"
        blueprint = llm_service.generate_blueprint(challenge_id, challenge_name, language)
        llm_service.dispatch_blueprint(blueprint)

        # 5. Update Cache (URL format matches what backend expects)
        s3_url = f"/challenges/{s3_key}"
        cache_client.set(cache_key, s3_url)
        
        return s3_url

orchestrator = ChallengeOrchestrator()
