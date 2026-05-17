import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import llm
from .models import AuditLog, Message, Session
from .tools.registry import TOOLS, call_tool

MAX_TOOL_ITERATIONS = 8

SYSTEM_PROMPT = (
    "You are a local computer-control agent. You can read, write, and list "
    "files inside the user's workspace via the fs_* tools. When the user "
    "asks for a file operation, call the appropriate tool instead of just "
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


async def run_turn(
    db: AsyncSession, session_id: uuid.UUID, user_text: str
) -> dict[str, Any]:
    sess = await db.get(Session, session_id)
    if sess is None:
        raise ValueError(f"session {session_id} not found")

    convo = await _load_history(db, session_id)
    await _persist(db, session_id, "user", user_text)
    convo.append({"role": "user", "content": user_text})

    for _ in range(MAX_TOOL_ITERATIONS):
        resp = await llm.chat(convo, tools=TOOLS)
        choice = resp.choices[0].message
        content = choice.content or ""

        if not choice.tool_calls:
            await _persist(db, session_id, "assistant", content)
            await db.commit()
            return {"reply": content, "tool_calls": []}

        serialized = [_serialize_tool_call(tc) for tc in choice.tool_calls]
        await _persist(db, session_id, "assistant", content, tool_calls=serialized)
        convo.append(
            {"role": "assistant", "content": content, "tool_calls": serialized}
        )

        for tc in choice.tool_calls:
            name = tc.function.name
            args = tc.function.arguments or "{}"
            result = call_tool(name, args)
            await _audit(
                db,
                session_id,
                "tool_call",
                {"tool": name, "arguments": args, "result": result},
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

    fallback = "[agent stopped: tool iteration limit reached]"
    await _audit(db, session_id, "error", {"reason": "max tool iterations exceeded"})
    await _persist(db, session_id, "assistant", fallback)
    await db.commit()
    return {"reply": fallback, "tool_calls": []}
