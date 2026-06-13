import os
import re
import zipfile
import io
import shutil
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import uvicorn
import boto3

app = FastAPI(title="Challenge Code Generator Service")

MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'http://localhost:9000')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', 'admin')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', 'password123')

try:
    s3_client = boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name='us-east-1'
    )
except Exception as e:
    print(f"Failed to initialize S3 client: {e}")
    s3_client = None

# Base directories
BASE_DIR = Path(__file__).parent.parent
CHALLENGES_DIR = BASE_DIR / "challenges"

class GenerationRequest(BaseModel):
    challenge_name: str
    language: str
    scenario: str

def get_scenario_description(scenario: str) -> str:
    descriptions = {
        'beginner-broken-refund': 'The ticketing system has a flaw in its cancellation logic. Currently, users can cancel tickets even after a movie has started. Additionally, while the system issues a refund, it fails to release the seat back to the available inventory. You must fix both issues.',
        'intermediate-webhook-idempotency': 'Our payment gateway occasionally sends duplicate webhook notifications due to network retries. The system currently processes every notification it receives, leading to duplicate loyalty points being awarded to users. You must implement idempotency to ensure each payment event is processed exactly once.',
        'advanced-cache-stampede': 'Under heavy peak load, the system experiences a "Cache Stampede" when the movie details cache expires. Thousands of requests hit the database simultaneously to refresh the same data. You must implement a "Single-flight" pattern using a Mutex to protect the database.'
    }
    return descriptions.get(scenario, 'The system is not behaving as expected. Investigate the failing tests and fix the implementation.')

def generate_challenge_task(challenge_name: str, language: str, scenario: str):
    source_dir = CHALLENGES_DIR / challenge_name / "apps" / f"gold-master-{language}"
    dist_dir = CHALLENGES_DIR / challenge_name / "dist" / language
    
    if not source_dir.exists():
        print(f"Source directory {source_dir} does not exist.")
        return

    dist_dir.mkdir(parents=True, exist_ok=True)
    output_path = dist_dir / f"{scenario}.zip"

    # Files to ignore
    ignore_patterns = [
        'node_modules', 'dist', 'database.db', 'package-lock.json', 
        'venv', '__pycache__', '.DS_Store', '.git'
    ]

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(source_dir):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in ignore_patterns]
            
            for file in files:
                if file in ignore_patterns:
                    continue
                
                file_path = Path(root) / file
                relative_path = file_path.relative_to(source_dir)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Multi-language parsing logic
                    # 1. Strip target scenario: keep prefix, replace content
                    # Regex: (//|#) @strip-target: scenario[\s\S]*?\1 @strip-end
                    target_regex = fr'(//|#) @strip-target: {scenario}[\s\S]*?(\1) @strip-end'
                    
                    def strip_replace(match):
                        prefix = match.group(1)
                        return f"{prefix} [REMOVED FOR CHALLENGE: {scenario}]"
                    
                    content = re.sub(target_regex, strip_replace, content)

                    # 2. Strip ALL other tags (clean up metadata)
                    # Regex: (//|#) @strip-target:.*[\s\S]*?(//|#) @strip-end
                    all_tags_regex = r'(//|#) @strip-target:.*[\s\S]*?(//|#) @strip-end'
                    
                    def clean_tags(match):
                        m = match.group(0)
                        # Remove the @strip-target and @strip-end lines, keep what's inside if it wasn't the target
                        # Actually the original logic was:
                        # return match.replace(/(?:\/\/|#) @strip-target:.*\n/g, '').replace(/(?:\/\/|#) @strip-end/g, '');
                        # But wait, if it wasn't the target scenario, we want to KEEP the code but REMOVE the tag markers.
                        m = re.sub(r'(//|#) @strip-target:.*\n?', '', m)
                        m = re.sub(r'(//|#) @strip-end\n?', '', m)
                        return m

                    content = re.sub(all_tags_regex, clean_tags, content)
                    
                    zip_file.writestr(str(relative_path), content)
                except (UnicodeDecodeError, PermissionError):
                    # For binary files or files we can't read as text, just copy them as is
                    zip_file.write(file_path, relative_path)

        # Add README.md
        readme_content = f"""# Challenge: {scenario}

## Problem Statement
{get_scenario_description(scenario)}

## Your Task
1. Diagnose the root cause of the failure by running the tests.
2. Navigate the codebase to find the relevant service.
3. Implement the fix to ensure the business requirements are met.
4. Ensure all tests in `test/integration.test.ts` pass.

## How to Run
1. Install dependencies: `npm install`
2. Run tests: `npm test`
"""
        zip_file.writestr("README.md", readme_content)

    print(f"Successfully generated {output_path}")

    if s3_client:
        try:
            s3_key = f"{language}/{scenario}.zip"
            s3_client.upload_file(str(output_path), 'challenges', s3_key)
            print(f"Successfully uploaded {s3_key} to MinIO bucket 'challenges'")
        except Exception as e:
            print(f"Failed to upload {scenario} to MinIO: {e}")

@app.post("/generate")
async def generate_challenge(request: GenerationRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        generate_challenge_task, 
        request.challenge_name, 
        request.language, 
        request.scenario
    )
    return {
        "message": "Challenge generation started in background", 
        "challenge_name": request.challenge_name,
        "language": request.language, 
        "scenario": request.scenario
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
