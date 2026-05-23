from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .db import SessionLocal, init_db
from .routes import approvals as approvals_router
from .routes import chat as chat_router
from .routes import sessions as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Gemma Local Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router.router)
app.include_router(chat_router.router)
app.include_router(approvals_router.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_base_url": settings.llama_base_url,
        "model": settings.llama_model,
    }


@app.get("/health/llm")
async def health_llm():
    """llama-server 연결 확인 (OpenAI 호환 /models 엔드포인트 호출)."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.llama_base_url}/models")
            r.raise_for_status()
            return {"status": "ok", "data": r.json()}
    except httpx.HTTPError as e:
        return {"status": "error", "detail": str(e)}


@app.get("/health/db")
async def health_db():
    """PostgreSQL 연결 확인 (SELECT 1)."""
    try:
        async with SessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            return {"status": "ok", "result": value}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
