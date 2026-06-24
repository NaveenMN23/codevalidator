from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from api.routes import router
from config.settings import settings
from infrastructure.logger import log


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.openai_api_key:
        log.warning("OPENAI_API_KEY is not set — LLM calls will fail at runtime")
    else:
        log.info(f"OpenAI API configured, model: {settings.openai_model}")

    # Ensure DB table exists
    try:
        from infrastructure.store import init_schema
        init_schema()
    except Exception as e:
        log.error(f"DB schema init failed: {e}")

    yield


app = FastAPI(title="platform-eval — AI Interview Evaluation Service", lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
