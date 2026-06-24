from fastapi import APIRouter, HTTPException
from models.dtos import CodeSubmitRequest, ConversationalAnswerRequest
from services import eval_core
from infrastructure.store import session_store
from infrastructure.logger import log

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "healthy"}


@router.post("/eval/submit")
def submit(request: CodeSubmitRequest):
    """
    Initial code submission or IMPLEMENTATION re-submission.
    Idempotency: if session is closed, returns 409.
    """
    existing = session_store.load(request.session_id)
    if existing and existing.get("closed"):
        raise HTTPException(status_code=409, detail="session closed")

    try:
        result = eval_core.handle_code_submission(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {e}")
    except Exception as e:
        log.error(f"Unexpected error in /eval/submit: {e}")
        raise HTTPException(status_code=500, detail="Internal evaluation error")


@router.post("/eval/answer")
def answer(request: ConversationalAnswerRequest):
    """
    Conversational answer to a follow-up question.
    Stage legality: session must be in FOLLOWUP_CONVERSATIONAL.
    """
    existing = session_store.load(request.session_id)
    if not existing:
        raise HTTPException(status_code=404, detail="session not found")
    if existing.get("closed"):
        raise HTTPException(status_code=409, detail="session closed")
    if existing.get("stage") not in ("FOLLOWUP_CONVERSATIONAL",):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot answer in stage '{existing.get('stage')}'. Submit code first.",
        )

    try:
        result = eval_core.handle_conversational_answer(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {e}")
    except Exception as e:
        log.error(f"Unexpected error in /eval/answer: {e}")
        raise HTTPException(status_code=500, detail="Internal evaluation error")


@router.get("/eval/session/{session_id}")
def get_session(session_id: str):
    """Read-only session state retrieval (Java reads only)."""
    data = session_store.load(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="session not found")
    return data
