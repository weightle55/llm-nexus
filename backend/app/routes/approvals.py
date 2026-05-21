import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import agent
from ..db import get_db
from ..models import Approval

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    tool_name: str
    tool_call_id: str
    arguments: object | None
    status: str
    decision_reason: str | None
    created_at: datetime
    decided_at: datetime | None


class DecisionIn(BaseModel):
    decision: Literal["approve", "deny"]
    reason: str | None = None


def _to_out(a: Approval) -> ApprovalOut:
    return ApprovalOut(
        id=a.id,
        session_id=a.session_id,
        tool_name=a.tool_name,
        tool_call_id=a.tool_call_id,
        arguments=a.arguments,
        status=a.status,
        decision_reason=a.decision_reason,
        created_at=a.created_at,
        decided_at=a.decided_at,
    )


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    session_id: uuid.UUID | None = None,
    status: str | None = "pending",
    db: AsyncSession = Depends(get_db),
) -> list[ApprovalOut]:
    stmt = select(Approval).order_by(Approval.created_at.desc())
    if session_id is not None:
        stmt = stmt.where(Approval.session_id == session_id)
    if status is not None:
        stmt = stmt.where(Approval.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_out(a) for a in rows]


@router.post("/{approval_id}/decide", response_model=ApprovalOut)
async def decide(
    approval_id: uuid.UUID,
    body: DecisionIn,
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    try:
        appr = await agent.decide_approval(
            db, approval_id, body.decision, body.reason
        )
    except ValueError as e:
        msg = str(e)
        status_code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status_code, detail=msg)
    return _to_out(appr)
