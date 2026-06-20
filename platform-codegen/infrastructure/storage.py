import io
import os
import zipfile
import boto3
from pathlib import Path
from config.settings import settings
from infrastructure.logger import log

_GOLD_MASTERS_BUCKET = "gold-masters"


class StorageClient:
    def __init__(self):
        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=settings.minio_endpoint,
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                region_name="us-east-1",
            )
            log.info(f"Initialized S3 client connected to {settings.minio_endpoint}")
        except Exception as e:
            log.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None

    def upload_file(self, local_path: Path, s3_key: str) -> bool:
        if not self.s3_client:
            log.warning("S3 client not initialized. Skipping upload.")
            return False
        try:
            self.s3_client.upload_file(str(local_path), settings.minio_bucket, s3_key)
            log.info(f"Uploaded {local_path.name} → {settings.minio_bucket}/{s3_key}")
            return True
        except Exception as e:
            log.error(f"Failed to upload {local_path} to MinIO: {e}")
            return False

    def upload_gold_master(
        self, tier_dir: Path, challenge_name: str, tier: str, language: str
    ) -> bool:
        """Zip src/ + test-hidden/ from tier_dir and upload to gold-masters/ (private bucket).

        The resulting object at gold-masters/{language}/{challenge_name}-{tier}.zip contains:
          src/           — complete reference implementation
          test-hidden/   — hidden test files used by the grading pipeline
        """
        if not self.s3_client:
            log.warning("S3 client not initialized. Skipping gold master upload.")
            return False

        zip_buffer = io.BytesIO()
        files_added = 0
        try:
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for subdir in ("src", "test-hidden"):
                    source_path = tier_dir / subdir
                    if not source_path.exists():
                        continue
                    for f in sorted(source_path.rglob("*")):
                        if f.is_file():
                            arcname = f"{subdir}/{f.relative_to(source_path)}"
                            zf.writestr(arcname, f.read_text(encoding="utf-8", errors="replace"))
                            files_added += 1
        except Exception as e:
            log.error(f"Failed to create gold master ZIP for {challenge_name}-{tier}: {e}")
            return False

        if files_added == 0:
            log.warning(f"Gold master ZIP for {challenge_name}-{tier} is empty — skipping upload")
            return False

        zip_buffer.seek(0)
        s3_key = f"{language}/{challenge_name}-{tier}.zip"
        try:
            self.s3_client.put_object(
                Bucket=_GOLD_MASTERS_BUCKET,
                Key=s3_key,
                Body=zip_buffer.getvalue(),
                ContentType="application/zip",
            )
            log.info(
                f"Uploaded gold master → {_GOLD_MASTERS_BUCKET}/{s3_key} "
                f"({files_added} files)"
            )
            return True
        except Exception as e:
            log.error(f"Failed to upload gold master {s3_key}: {e}")
            return False


    def upload_gold_master_from_dict(
        self,
        files: dict,
        test_hidden: dict,
        manifest: dict,
        challenge_name: str,
        tier: str,
        language: str,
    ) -> bool:
        """Create gold master ZIP from in-memory dicts and upload to gold-masters bucket.

        ZIP structure:
          manifest.json        — challenge metadata and scenario info
          src/{rel_path}       — complete gold master source files
          test-hidden/{name}   — hidden test files, one per scenario
        """
        if not self.s3_client:
            log.warning("S3 client not initialized. Skipping gold master upload.")
            return False

        import json as _json
        ext_map = {"java": "java", "python": "py"}
        test_ext = ext_map.get(language, "test.ts")

        zip_buffer = io.BytesIO()
        files_added = 0
        try:
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("manifest.json", _json.dumps(manifest, indent=2))
                files_added += 1
                for rel_path, content in files.items():
                    zf.writestr(f"src/{rel_path}", content)
                    files_added += 1
                for scenario_tag, test_content in test_hidden.items():
                    filename = f"hidden-{scenario_tag}.{test_ext}"
                    zf.writestr(f"test-hidden/{filename}", test_content)
                    files_added += 1
        except Exception as e:
            log.error(f"Failed to create gold master ZIP for {challenge_name}-{tier}: {e}")
            return False

        if files_added == 0:
            log.warning(f"Gold master ZIP for {challenge_name}-{tier} is empty — skipping upload")
            return False

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()
        s3_key = f"{language}/{challenge_name}-{tier}.zip"

        if settings.local_export_path:
            self._export_gold_master_locally(zip_bytes, files, manifest, challenge_name, tier, language)

        try:
            self.s3_client.put_object(
                Bucket=_GOLD_MASTERS_BUCKET,
                Key=s3_key,
                Body=zip_bytes,
                ContentType="application/zip",
            )
            log.info(
                f"Uploaded gold master → {_GOLD_MASTERS_BUCKET}/{s3_key} "
                f"({files_added} entries)"
            )
            return True
        except Exception as e:
            log.error(f"Failed to upload gold master {s3_key}: {e}")
            return False

    # ── Local export helpers (dev-only, non-blocking) ─────────────────────────

    def export_scaffold_locally(
        self, zip_bytes: bytes, challenge_name: str, scenario_tag: str, language: str
    ) -> None:
        if not settings.local_export_path:
            return
        try:
            self._export_scaffold_locally(zip_bytes, challenge_name, scenario_tag, language)
        except Exception as e:
            log.warning(f"Local scaffold export failed (non-blocking): {e}")

    def _export_scaffold_locally(
        self, zip_bytes: bytes, challenge_name: str, scenario_tag: str, language: str
    ) -> None:
        base = settings.local_export_path
        # 1. dist ZIP — mirrors MinIO challenges bucket for re-seeding
        dist_dir = os.path.join(base, "dist", "challenges", language)
        os.makedirs(dist_dir, exist_ok=True)
        with open(os.path.join(dist_dir, f"{challenge_name}-{scenario_tag}.zip"), "wb") as f:
            f.write(zip_bytes)
        # 2. Extracted scaffold — human-readable, no unzip needed
        extract_dir = os.path.join(base, challenge_name, language, "scaffold", scenario_tag)
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(extract_dir)
        log.info(f"Local export: scaffold → {extract_dir}")

    def _export_gold_master_locally(
        self,
        zip_bytes: bytes,
        files: dict,
        manifest: dict,
        challenge_name: str,
        tier: str,
        language: str,
    ) -> None:
        import json as _json
        base = settings.local_export_path
        try:
            # 1. dist ZIP — mirrors MinIO gold-masters bucket for re-seeding
            dist_dir = os.path.join(base, "dist", "gold-masters", language)
            os.makedirs(dist_dir, exist_ok=True)
            with open(os.path.join(dist_dir, f"{challenge_name}-{tier}.zip"), "wb") as f:
                f.write(zip_bytes)
            # 2. Extracted src + manifest — hidden tests intentionally excluded
            extract_dir = os.path.join(base, challenge_name, language, "gold-master", tier)
            os.makedirs(extract_dir, exist_ok=True)
            with open(os.path.join(extract_dir, "manifest.json"), "w", encoding="utf-8") as f:
                _json.dump(manifest, f, indent=2)
            for rel_path, content in files.items():
                file_path = os.path.join(extract_dir, "src", rel_path)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            log.info(f"Local export: gold-master → {extract_dir}")
        except Exception as e:
            log.warning(f"Local gold master export failed (non-blocking): {e}")

    def upload_bytes(self, data: bytes, bucket: str, s3_key: str) -> bool:
        """Upload raw bytes to a MinIO bucket."""
        if not self.s3_client:
            log.warning("S3 client not initialized. Skipping upload.")
            return False
        try:
            self.s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=data,
                ContentType="application/zip",
            )
            log.info(f"Uploaded bytes → {bucket}/{s3_key} ({len(data)} bytes)")
            return True
        except Exception as e:
            log.error(f"Failed to upload bytes to {bucket}/{s3_key}: {e}")
            return False

    def get_gold_master_source(
        self, challenge_name: str, tier: str, language: str
    ) -> dict:
        """Download gold master ZIP and return src/ files as {rel_path: content} dict.

        Keys do NOT include the 'src/' prefix. Returns empty dict on any error.
        """
        if not self.s3_client:
            log.warning("S3 client not available — gold master source unavailable")
            return {}

        s3_key = f"{language}/{challenge_name}-{tier}.zip"
        try:
            obj = self.s3_client.get_object(Bucket=_GOLD_MASTERS_BUCKET, Key=s3_key)
            zip_bytes = obj["Body"].read()
        except Exception as e:
            log.warning(f"get_gold_master_source: failed to fetch {s3_key}: {e}")
            return {}

        source_files: dict = {}
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for name in zf.namelist():
                    if name.startswith("src/") and not name.endswith("/"):
                        rel = name[len("src/"):]
                        source_files[rel] = zf.read(name).decode("utf-8", errors="replace")
        except Exception as e:
            log.error(f"get_gold_master_source: failed to unzip {s3_key}: {e}")

        log.info(
            f"get_gold_master_source: loaded {len(source_files)} files from {s3_key}"
        )
        return source_files


storage_client = StorageClient()
