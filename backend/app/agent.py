import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import llm
from .models import Approval, AuditLog, Message, Session
from .tools.registry import APPROVAL_REQUIRED, TOOLS, call_tool

MAX_TOOL_ITERATIONS = 8

SYSTEM_PROMPT = (
    "You are a local computer-control agent. You can read, write, and list "
    "files inside the user's workspace via the fs_* tools, and you can run "
    "shell commands via shell_exec (which requires human approval). When the "
    "user asks for an operation, call the appropriate tool instead of just "
    "describing what you would do. After every tool result, always reply "
    "with a short confirmation sentence summarizing what happened — never "
    "leave the final response empty."
)


def _message_to_openai(m: Message) -> dict[str, Any]:
    if m.role == "assistant" and m.tool_calls:
        return {
            "role": "assistant",
            "content": m.content or "",
            "tool_calls": m.tool_calls,
        }
    if m.role == "tool":
        meta = m.tool_calls or {}
        return {
            "role": "tool",
            "tool_call_id": meta.get("tool_call_id", ""),
            "name": meta.get("name", ""),
            "content": m.content or "",
        }
    return {"role": m.role, "content": m.content or ""}


def _serialize_tool_call(tc) -> dict[str, Any]:
    return {
        "id": tc.id,
        "type": "function",
        "function": {
            "name": tc.function.name,
            "arguments": tc.function.arguments,
        },
    }


def _approval_dict(a: Approval) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "tool_name": a.tool_name,
        "tool_call_id": a.tool_call_id,
        "arguments": a.arguments,
        "status": a.status,
        "created_at": a.created_at.isoformat(),
    }


async def _load_history(
    db: AsyncSession, session_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at, Message.id)
        )
    ).scalars().all()
    return [{"role": "system", "content": SYSTEM_PROMPT}] + [
        _message_to_openai(m) for m in rows
    ]


async def _persist(
    db: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: str | None,
    tool_calls: Any | None = None,
) -> None:
    db.add(
        Message(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
    )
    await db.flush()


async def _audit(
    db: AsyncSession,
    session_id: uuid.UUID,
    event_type: str,
    payload: dict,
) -> None:
    db.add(AuditLog(session_id=session_id, event_type=event_type, payload=payload))
    await db.flush()


async def _pending_approvals(
    db: AsyncSession, session_id: uuid.UUID
) -> list[Approval]:
    return (
        await db.execute(
            select(Approval)
            .where(Approval.session_id == session_id, Approval.status == "pending")
            .order_by(Approval.created_at)
        )
    ).scalars().all()


async def _execute_or_defer(
    db: AsyncSession,
    session_id: uuid.UUID,
    tc,
    convo: list[dict[str, Any]],
) -> bool:
    """tool_call 을 자동 실행하거나 승인 큐에 적재. 적재된 경우 True 반환."""
    name = tc.function.name
    args_json = tc.function.arguments or "{}"

    if name in APPROVAL_REQUIRED:
        try:
            args_obj = json.loads(args_json)
        except json.JSONDecodeError:
            args_obj = {"_raw": args_json}
        db.add(
            Approval(
                session_id=session_id,
                tool_name=name,
                tool_call_id=tc.id,
                arguments=args_obj,
                status="pending",
            )
        )
        await _audit(
            db,
            session_id,
            "approval_requested",
            {"tool": name, "arguments": args_json, "tool_call_id": tc.id},
        )
        await db.flush()
        return True

    result = call_tool(name, args_json)
    await _audit(
        db,
        session_id,
        "tool_call",
        {"tool": name, "arguments": args_json, "result": result},
    )
    await _persist(
        db,
        session_id,
        "tool",
        result,
        tool_calls={"tool_call_id": tc.id, "name": name},
    )
    convo.append(
        {
            "role": "tool",
            "tool_call_id": tc.id,
            "name": name,
            "content": result,
        }
    )
    return False


async def _loop(
    db: AsyncSession,
    session_id: uuid.UUID,
    convo: list[dict[str, Any]],
) -> dict[str, Any]:
    for _ in range(MAX_TOOL_ITERATIONS):
        resp = await llm.chat(convo, tools=TOOLS)
        choice = resp.choices[0].message
        content = choice.content or ""

        if not choice.tool_calls:
            await _persist(db, session_id, "assistant", content)
            await db.commit()
            return {"status": "ok", "reply": content}

        serialized = [_serialize_tool_call(tc) for tc in choice.tool_calls]
        await _persist(db, session_id, "assistant", content, tool_calls=serialized)
        convo.append(
            {"role": "assistant", "content": content, "tool_calls": serialized}
        )

        deferred_any = False
        for tc in choice.tool_calls:
            deferred = await _execute_or_defer(db, session_id, tc, convo)
            deferred_any = deferred_any or deferred

        if deferred_any:
            await db.commit()
            pendings = await _pending_approvals(db, session_id)
            return {
                "status": "pending_approval",
                "approvals": [_approval_dict(a) for a in pendings],
            }

    fallback = "[agent stopped: tool iteration limit reached]"
    await _audit(db, session_id, "error", {"reason": "max tool iterations exceeded"})
    await _persist(db, session_id, "assistant", fallback)
    await db.commit()
    return {"status": "stopped", "reply": fallback}


async def run_turn(
    db: AsyncSession, session_id: uuid.UUID, user_text: str
) -> dict[str, Any]:
    sess = await db.get(Session, session_id)
    if sess is None:
        raise ValueError(f"session {session_id} not found")

    pendings = await _pending_approvals(db, session_id)
    if pendings:
        return {
            "status": "pending_approval",
            "approvals": [_approval_dict(a) for a in pendings],
        }

    convo = await _load_history(db, session_id)
    await _persist(db, session_id, "user", user_text)
    convo.append({"role": "user", "content": user_text})

    return await _loop(db, session_id, convo)


async def resume_turn(
    db: AsyncSession, session_id: uuid.UUID
) -> dict[str, Any]:
    sess = await db.get(Session, session_id)
    if sess is None:
        raise ValueError(f"session {session_id} not found")

    pendings = await _pending_approvals(db, session_id)
    if pendings:
        return {
            "status": "pending_approval",
            "approvals": [_approval_dict(a) for a in pendings],
        }

    last_assistant = (
        await db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.role == "assistant",
                Message.tool_calls.isnot(None),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if last_assistant is None or not last_assistant.tool_calls:
        return {"status": "ok", "reply": "[nothing to resume]"}

    existing_tool_msgs = (
        await db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.role == "tool",
                Message.created_at >= last_assistant.created_at,
            )
        )
    ).scalars().all()
    answered_ids = {
        (m.tool_calls or {}).get("tool_call_id") for m in existing_tool_msgs
    }

    for tc in last_assistant.tool_calls:
        tc_id = tc.get("id")
        if tc_id in answered_ids:
            continue
        name = tc["function"]["name"]
        args_json = tc["function"].get("arguments") or "{}"

        appr = (
            await db.execute(
                select(Approval).where(Approval.tool_call_id == tc_id)
            )
        ).scalar_one_or_none()

        if appr is None or appr.status == "pending":
            # 안전망 — 정상 흐름에선 도달 안 함
            continue

        if appr.status == "approved":
            result = call_tool(name, args_json)
            await _audit(
                db,
                session_id,
                "tool_call",
                {
                    "tool": name,
                    "arguments": args_json,
                    "result": result,
                    "approval_id": str(appr.id),
                },
            )
        else:
            result = json.dumps(
                {
                    "error": "denied by user",
                    "reason": appr.decision_reason or "",
                }
            )
            await _audit(
                db,
                session_id,
                "approval_denied",
                {
                    "tool": name,
                    "arguments": args_json,
                    "approval_id": str(appr.id),
                    "reason": appr.decision_reason,
                },
            )

        await _persist(
            db,
            session_id,
            "tool",
            result,
            tool_calls={"tool_call_id": tc_id, "name": name},
        )

    convo = await _load_history(db, session_id)
    return await _loop(db, session_id, convo)


async def decide_approval(
    db: AsyncSession,
    approval_id: uuid.UUID,
    decision: str,
    reason: str | None = None,
) -> Approval:
    appr = await db.get(Approval, approval_id)
    if appr is None:
        raise ValueError(f"approval {approval_id} not found")
    if appr.status != "pending":
        raise ValueError(f"approval already decided: {appr.status}")
    if decision not in {"approve", "deny"}:
        raise ValueError(f"invalid decision: {decision}")

    appr.status = "approved" if decision == "approve" else "denied"
    appr.decision_reason = reason
    appr.decided_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(appr)
    return appr
