import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Message, Session

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    title: str | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str | None
    tool_calls: object | None
    created_at: datetime


@router.post("", response_model=SessionOut)
async def create_session(
    body: SessionCreate, db: AsyncSession = Depends(get_db)
) -> SessionOut:
    sess = Session(title=body.title)
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return SessionOut(
        id=sess.id,
        title=sess.title,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
    )


@router.get("", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[SessionOut]:
    rows = (
        await db.execute(select(Session).order_by(Session.created_at.desc()))
    ).scalars().all()
    return [
        SessionOut(
            id=s.id, title=s.title, created_at=s.created_at, updated_at=s.updated_at
        )
        for s in rows
    ]


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[MessageOut]:
    sess = await db.get(Session, session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    rows = (
        await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at, Message.id)
        )
    ).scalars().all()
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls,
            created_at=m.created_at,
        )
        for m in rows
    ]
