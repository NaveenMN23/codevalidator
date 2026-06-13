from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from services.orchestrator import orchestrator
from services.llm import llm_service

router = APIRouter()

class GenerationRequest(BaseModel):
    challenge_name: str
    language: str
    tags: List[str]

class GoldenRepoRequest(BaseModel):
    prompt: str

@router.post("/generate")
async def generate_challenge(request: GenerationRequest):
    """
    Generate a challenge ZIP by combining multiple tags from a manual Gold Master.
    """
    try:
        url = orchestrator.orchestrate_generation(
            request.challenge_name, 
            request.language, 
            request.tags
        )
        return {"status": "success", "zip_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/generate-golden-repo")
async def generate_golden_repo(request: GoldenRepoRequest):
    """
    Future endpoint for AI-driven Gold Master generation.
    """
    result = llm_service.generate_gold_repo(request.prompt)
    return {"message": result}

@router.get("/health")
def health_check():
    return {"status": "healthy"}
