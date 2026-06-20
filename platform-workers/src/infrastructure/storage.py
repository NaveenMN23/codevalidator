import io
import json
import zipfile
import boto3
from botocore.exceptions import ClientError
from loguru import logger
from src.config import settings


class GoldMasterStorage:
    """Fetches and caches gold master ZIP contents from MinIO gold-masters/ bucket.

    Each ZIP at gold-masters/{language}/{challenge}-{tier}.zip contains:
      manifest.json   — challenge metadata, locked_files list, scenario info
      src/            — complete gold master source files
      test-hidden/    — hidden test files (one per scenario)

    All three sections are extracted in a single download and cached for the
    process lifetime — MinIO is called once per (challenge, tier, language).
    """

    def __init__(self):
        # { "challenge/tier/lang": { "tests": {filename: str}, "manifest": dict, "src": {rel_path: str} } }
        self._cache: dict[str, dict] = {}
        try:
            self._s3 = boto3.client(
                "s3",
                endpoint_url=settings.minio_endpoint,
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                region_name="us-east-1",
            )
            logger.info(f"GoldMasterStorage: connected to {settings.minio_endpoint}")
        except Exception as e:
            logger.error(f"GoldMasterStorage: failed to init S3 client: {e}")
            self._s3 = None

    def _fetch(self, challenge_name: str, tier: str, language: str) -> dict:
        """Download and extract the gold master ZIP, caching all sections."""
        cache_key = f"{challenge_name}/{tier}/{language}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        empty = {"tests": {}, "manifest": {}, "src": {}}

        if not self._s3:
            logger.warning("GoldMasterStorage: S3 not available")
            return empty

        key = f"{language}/{challenge_name}-{tier}.zip"
        try:
            obj = self._s3.get_object(Bucket=settings.minio_gold_masters_bucket, Key=key)
            zip_bytes = obj["Body"].read()
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("NoSuchKey", "404"):
                logger.warning(f"GoldMasterStorage: no object at {key} — unavailable")
            else:
                logger.error(f"GoldMasterStorage: S3 error fetching {key}: {e}")
            self._cache[cache_key] = empty
            return empty
        except Exception as e:
            logger.error(f"GoldMasterStorage: unexpected error fetching {key}: {e}")
            return empty

        tests: dict[str, str] = {}
        manifest: dict = {}
        src: dict[str, str] = {}
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for name in zf.namelist():
                    if name == "manifest.json":
                        manifest = json.loads(
                            zf.read(name).decode("utf-8", errors="replace")
                        )
                    elif name.startswith("test-hidden/") and not name.endswith("/"):
                        filename = name[len("test-hidden/"):]
                        tests[filename] = zf.read(name).decode("utf-8", errors="replace")
                    elif name.startswith("src/") and not name.endswith("/"):
                        rel = name[len("src/"):]
                        src[rel] = zf.read(name).decode("utf-8", errors="replace")
        except Exception as e:
            logger.error(f"GoldMasterStorage: failed to unzip {key}: {e}")

        result = {"tests": tests, "manifest": manifest, "src": src}
        self._cache[cache_key] = result
        logger.info(
            f"GoldMasterStorage: cached {len(tests)} tests, "
            f"{len(src)} src files from {key}"
        )
        return result

    def get_hidden_tests(self, challenge_name: str, tier: str, language: str) -> dict[str, str]:
        """Return {filename: content} for all hidden test files in this tier."""
        return self._fetch(challenge_name, tier, language)["tests"]

    def get_manifest(self, challenge_name: str, tier: str, language: str) -> dict:
        """Return the manifest dict from the gold master ZIP."""
        return self._fetch(challenge_name, tier, language)["manifest"]

    def get_src_files(self, challenge_name: str, tier: str, language: str) -> dict[str, str]:
        """Return {rel_path: content} for all src/ files in the gold master ZIP."""
        return self._fetch(challenge_name, tier, language)["src"]


gold_master_storage = GoldMasterStorage()
