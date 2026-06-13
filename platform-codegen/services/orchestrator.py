from pathlib import Path
from infrastructure.cache import cache_client
from infrastructure.storage import storage_client
from infrastructure.logger import log
from generator.engine import generator

class ChallengeOrchestrator:
    def orchestrate_generation(self, challenge_name: str, language: str, tags: list) -> str:
        # 1. Check Cache
        cache_key = cache_client.get_cache_key(challenge_name, language, tags)
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
        # S3 Key structure: node/tag1-tag2.zip
        s3_key = f"{language}/{zip_path.name}"
        success = storage_client.upload_file(zip_path, s3_key)
        
        if not success:
            raise Exception("Failed to upload generated challenge to storage")

        # 4. Update Cache (URL format matches what backend expects)
        s3_url = f"/challenges/{s3_key}"
        cache_client.set(cache_key, s3_url)
        
        return s3_url

orchestrator = ChallengeOrchestrator()
