from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from pydantic import BaseModel

from src.challenge_image_builder import ChallengeImageBuilder
from src.session_container_manager import SessionContainerManager

session_manager = SessionContainerManager()
image_builder = ChallengeImageBuilder()


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager.start()
    yield
    session_manager.stop()


app = FastAPI(title="Execution Service", lifespan=lifespan)


class ExecuteRequest(BaseModel):
    sessionId: str
    challengeId: str
    language: str
    files: Dict[str, str]
    command: str


class ExecuteResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: int


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    # docker-py is a blocking SDK; run_in_threadpool keeps this off FastAPI's event loop
    # so one slow/hung exec can't stall every other concurrent request to this service.
    try:
        return await run_in_threadpool(
            session_manager.execute,
            req.sessionId, req.challengeId, req.language, req.files, req.command,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Execution failed")
        raise HTTPException(status_code=500, detail=str(e))


class BuildChallengeImageRequest(BaseModel):
    challengeId: str
    language: str


class BuildChallengeImageResponse(BaseModel):
    image: str | None


@app.post("/build-challenge-image", response_model=BuildChallengeImageResponse)
async def build_challenge_image(req: BuildChallengeImageRequest):
    # Triggered by platform-codegen at publish time, never at Run/Submit click time —
    # see docs/design/repo-execution-architecture.md §4 on why dependency installation
    # must happen at publish time, not session time.
    try:
        image = await run_in_threadpool(image_builder.build, req.challengeId, req.language)
        return BuildChallengeImageResponse(image=image)
    except Exception as e:
        logger.exception("Challenge image build failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": session_manager.session_count()}
