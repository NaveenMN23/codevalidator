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
        log.info("OpenAI API key configured")
    yield


app = FastAPI(title="Scalable Challenge CodeGen Service", lifespan=lifespan)

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
