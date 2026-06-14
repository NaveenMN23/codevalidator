import os
import boto3
from pathlib import Path
from infrastructure.logger import log

class StorageClient:
    def __init__(self):
        self.endpoint = os.environ.get('MINIO_ENDPOINT', 'http://localhost:9000')
        self.access_key = os.environ.get('MINIO_ACCESS_KEY', 'admin')
        self.secret_key = os.environ.get('MINIO_SECRET_KEY', 'password')
        self.bucket = 'challenges'
        
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name='us-east-1'
            )
            log.info(f"Initialized S3 client connected to {self.endpoint}")
        except Exception as e:
            log.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None

    def upload_file(self, local_path: Path, s3_key: str) -> bool:
        if not self.s3_client:
            log.warning("S3 client not initialized. Skipping upload.")
            return False
        
        try:
            self.s3_client.upload_file(str(local_path), self.bucket, s3_key)
            log.info(f"Successfully uploaded {local_path} to {self.bucket}/{s3_key}")
            return True
        except Exception as e:
            log.error(f"Failed to upload {local_path} to MinIO: {e}")
            return False

storage_client = StorageClient()
