from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from services.sanitizer import sanitizer
from services.scaffold_generator import scaffold_generator

router = APIRouter()


class GoldenRepoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    languages: list[str] = ["node"]
    use_local_few_shots: bool = False
    tiers: list[str] = ["easy", "medium", "hard"]
    scenarios_per_tier: int = 3

    @field_validator("languages")
    @classmethod
    def valid_languages(cls, v: list[str]) -> list[str]:
        allowed = {"node", "java", "python"}
        invalid = set(v) - allowed
        if invalid:
            raise ValueError(f"Invalid languages: {invalid}. Choose from: {allowed}")
        if not v:
            raise ValueError("languages must not be empty")
        return v

    @field_validator("tiers")
    @classmethod
    def valid_tiers(cls, v: list[str]) -> list[str]:
        allowed = {"easy", "medium", "hard"}
        invalid = set(v) - allowed
        if invalid:
            raise ValueError(f"Invalid tiers: {invalid}. Choose from: {allowed}")
        if not v:
            raise ValueError("tiers must not be empty")
        return [t for t in ["easy", "medium", "hard"] if t in v]

    @field_validator("scenarios_per_tier")
    @classmethod
    def valid_scenario_count(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("scenarios_per_tier must be between 1 and 5")
        return v


@router.post("/admin/generate-golden-repo")
async def generate_golden_repo(request: GoldenRepoRequest):
    """AI-driven Gold Master generation — returns scaffold files, hidden tests, and manifest JSON.

    Three-phase CoT:
      Phase 1 (design_challenge): architecture + scenario specs — runs once per request
      Phase 2a (implement_skeleton_{lang}): full codebase per tier per language
      Phase 2b (implement_function_{lang}): function body + hidden test per scenario

    Supported languages: node, java, python
    """
    try:
        sanitizer.sanitize_description(request.prompt)
        return scaffold_generator.generate(
            request.prompt,
            languages=request.languages,
            use_local_few_shots=request.use_local_few_shots,
            tiers=request.tiers,
            scenarios_per_tier=request.scenarios_per_tier,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health_check():
    return {"status": "healthy"}
