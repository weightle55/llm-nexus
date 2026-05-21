import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
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
