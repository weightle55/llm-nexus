import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .. import agent
from ..db import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    session_id: uuid.UUID
    message: str


class ChatOut(BaseModel):
    reply: str


@router.post("", response_model=ChatOut)
async def chat(body: ChatIn, db: AsyncSession = Depends(get_db)) -> ChatOut:
    try:
        result = await agent.run_turn(db, body.session_id, body.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ChatOut(reply=result["reply"])
