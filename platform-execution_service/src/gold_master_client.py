import io
import os
import re
import zipfile
from typing import Optional

import boto3
from loguru import logger

_GOLD_MASTERS_BUCKET = "gold-masters"

_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_PUBLIC_CLASS_RE = re.compile(r"\bpublic\s+(?:final\s+|abstract\s+)?class\s+(\w+)")


class GoldMasterClient:
    """Fetches a published challenge's gold master (locked files + hidden test) from the
    private gold-masters S3/MinIO bucket — same bucket/key convention platform-codegen already
    writes to (see platform-codegen/infrastructure/storage.py). Used only by Submit; Run never
    touches this."""

    def __init__(self):
        endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
        access_key = os.environ.get("MINIO_ACCESS_KEY", "admin")
        secret_key = os.environ.get("MINIO_SECRET_KEY", "password")
        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="us-east-1",
            )
            logger.info(f"GoldMasterClient connected to {endpoint}")
        except Exception as e:
            logger.error(f"Failed to initialize GoldMasterClient S3 client: {e}")
            self.s3_client = None

    def fetch(self, challenge_id: str, tier: str, language: str) -> dict:
        """Returns {"locked_files": {rel_path: content}, "hidden_test_path": str,
        "hidden_test_content": str}. Raises on any failure — Submit has nothing
        meaningful to fall back to if the gold master can't be fetched."""
        if not self.s3_client:
            raise RuntimeError("Gold master S3 client not initialized")

        key = f"{language}/{challenge_id}-{tier}.zip"
        obj = self.s3_client.get_object(Bucket=_GOLD_MASTERS_BUCKET, Key=key)
        zip_bytes = obj["Body"].read()

        locked_files: dict = {}
        hidden_test_content: Optional[str] = None
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                if name.startswith("src/"):
                    locked_files[name[len("src/"):]] = zf.read(name).decode("utf-8", errors="replace")
                elif name.startswith("test-hidden/"):
                    hidden_test_content = zf.read(name).decode("utf-8", errors="replace")

        if hidden_test_content is None:
            raise ValueError(f"No hidden test found in {key}")

        hidden_test_path = self._resolve_hidden_test_path(hidden_test_content, language)
        return {
            "locked_files": locked_files,
            "hidden_test_path": hidden_test_path,
            "hidden_test_content": hidden_test_content,
        }

    def _resolve_hidden_test_path(self, content: str, language: str) -> str:
        """Derives where the hidden test file needs to be written so the build tool actually
        discovers and runs it. For Java/Maven this means matching its package declaration
        under src/test/java/ with a filename matching its public class — Java requires both,
        so we derive placement from the file's own content rather than assuming a fixed name."""
        if language != "java":
            raise ValueError(f"Unsupported language for hidden test placement: {language}")

        package_match = _PACKAGE_RE.search(content)
        class_match = _PUBLIC_CLASS_RE.search(content)
        if not package_match or not class_match:
            raise ValueError("Hidden Java test is missing a package declaration or public class")

        package_path = package_match.group(1).replace(".", "/")
        class_name = class_match.group(1)
        return f"src/test/java/{package_path}/{class_name}.java"


gold_master_client = GoldMasterClient()
