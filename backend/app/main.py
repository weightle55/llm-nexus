import httpx
from fastapi import FastAPI

from .config import settings

app = FastAPI(title="Gemma Local Agent", version="0.1.0")


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
