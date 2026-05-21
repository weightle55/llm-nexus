import json
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .. import agent
from ..db import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    session_id: uuid.UUID
    message: str


class ChatResumeIn(BaseModel):
    session_id: uuid.UUID


class ChatOut(BaseModel):
    status: str
    reply: str | None = None
    approvals: list[dict[str, Any]] | None = None


def _to_out(result: dict[str, Any]) -> ChatOut:
    return ChatOut(
        status=result.get("status", "ok"),
        reply=result.get("reply"),
        approvals=result.get("approvals"),
    )


def _format_sse(event: str, payload: dict[str, Any]) -> bytes:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n".encode("utf-8")


async def _to_sse(
    gen: AsyncGenerator[tuple[str, dict[str, Any]], None],
) -> AsyncGenerator[bytes, None]:
    try:
        async for event, payload in gen:
            yield _format_sse(event, payload)
    except ValueError as e:
        yield _format_sse("error", {"detail": str(e)})
    except Exception as e:  # noqa: BLE001
        yield _format_sse("error", {"detail": f"{type(e).__name__}: {e}"})


@router.post("", response_model=ChatOut)
async def chat(body: ChatIn, db: AsyncSession = Depends(get_db)) -> ChatOut:
    try:
        result = await agent.run_turn(db, body.session_id, body.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_out(result)


@router.post("/resume", response_model=ChatOut)
async def resume(
    body: ChatResumeIn, db: AsyncSession = Depends(get_db)
) -> ChatOut:
    try:
        result = await agent.resume_turn(db, body.session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_out(result)


@router.post("/stream")
async def chat_stream(
    body: ChatIn, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    gen = agent.run_turn_stream(db, body.session_id, body.message)
    return StreamingResponse(
        _to_sse(gen),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/resume/stream")
async def resume_stream(
    body: ChatResumeIn, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    gen = agent.resume_turn_stream(db, body.session_id)
    return StreamingResponse(
        _to_sse(gen),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
