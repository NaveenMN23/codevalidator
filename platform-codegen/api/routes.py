from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.sanitizer import sanitizer
from services.scaffold_generator import scaffold_generator

router = APIRouter()


class GoldenRepoRequest(BaseModel):
    prompt: str
    language: str = "node"


@router.post("/admin/generate-golden-repo")
async def generate_golden_repo(request: GoldenRepoRequest):
    """AI-driven Gold Master generation — returns scaffold files, hidden tests, and manifest JSON.

    Two-phase CoT:
      Phase 1 (design_challenge): architecture + strip specifications per difficulty level
      Phase 2 (implement_gold_master_{language}): file tree with @strip-target markers + hidden tests

    Input is sanitized before any LLM call. Generated file paths are validated after.
    Supported languages: node, java, python
    """
    try:
        sanitizer.sanitize_description(request.prompt)
        return scaffold_generator.generate(request.prompt, request.language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health_check():
    return {"status": "healthy"}
