import os
import subprocess
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict

app = FastAPI()


class ExecuteRequest(BaseModel):
    files: Dict[str, str]
    command: str


class ExecuteResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: int


@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest) -> ExecuteResponse:
    for rel_path, content in req.files.items():
        full_path = os.path.join("/app", rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)

    result = subprocess.run(
        req.command,
        shell=True,
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=60,
    )

    return ExecuteResponse(
        success=result.returncode == 0,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
