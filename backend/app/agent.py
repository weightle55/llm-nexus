import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import llm
from .mcp_client import mcp_manager
from .models import Approval, AuditLog, Message, Session
from .tools.registry import TOOLS, call_tool, requires_approval


def _all_tools() -> list[dict]:
    """로컬 도구 + 연결된 MCP 서버 도구."""
    return TOOLS + mcp_manager.openai_tools()


async def _execute_tool(name: str, args_json: str) -> str:
    """MCP 도구면 워커로 위임(async), 아니면 로컬 동기 실행."""
    if mcp_manager.has_tool(name):
        return await mcp_manager.call_tool(name, args_json)
    return call_tool(name, args_json)


def _needs_approval(name: str, args_json: str | None) -> bool:
    return requires_approval(name, args_json) or mcp_manager.requires_approval(name)

MAX_TOOL_ITERATIONS = 8

SYSTEM_PROMPT = (
    "You are a local computer-control agent operating inside a sandboxed "
    "workspace. Available tools:\n"
    "- fs_read / fs_write / fs_list — read, write, and list workspace files.\n"
    "- fs_tree — inspect directory structure recursively before editing.\n"
    "- fs_search — grep file contents (optionally limited by a glob).\n"
    "- fs_mkdir / fs_move — create directories, move or rename entries.\n"
    "- fs_delete — delete a file (automatic) or directory (needs approval).\n"
    "- web_fetch — fetch a public web page as text for documentation/research.\n"
    "- search_blender_docs — authoritative Blender 5.1 API/manual lookup; call "
    "it BEFORE writing bpy code or answering a Blender question (your bpy "
    "knowledge may be wrong for 5.1).\n"
    "- shell_exec — run a shell command (requires human approval).\n"
    "Prefer fs_tree/fs_search to orient yourself before making changes. When "
    "the user asks for an operation, call the appropriate tool instead of just "
    "describing what you would do. After every tool result, always reply with "
    "a short confirmation sentence summarizing what happened — never leave the "
    "final response empty."
)

Event = tuple[str, dict[str, Any]]


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


async def _stream_completion(
    convo: list[dict[str, Any]],
    out: dict[str, Any],
) -> AsyncGenerator[Event, None]:
    """LLM 호출을 스트림으로 소비하면서 'token' 이벤트를 yield. 결과는 `out` 딕셔너리에 저장."""
    stream = await llm.chat(convo, tools=_all_tools(), stream=True)
    content_parts: list[str] = []
    tc_buf: dict[int, dict[str, Any]] = {}

    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            content_parts.append(delta.content)
            yield ("token", {"delta": delta.content})
        if delta.tool_calls:
            for tcd in delta.tool_calls:
                idx = tcd.index
                slot = tc_buf.setdefault(
                    idx, {"id": "", "name": "", "arguments": ""}
                )
                if tcd.id:
                    slot["id"] = tcd.id
                if tcd.function:
                    if tcd.function.name:
                        slot["name"] += tcd.function.name
                    if tcd.function.arguments:
                        slot["arguments"] += tcd.function.arguments

    out["content"] = "".join(content_parts)
    out["tool_calls"] = [
        {
            "id": tc_buf[i]["id"],
            "type": "function",
            "function": {
                "name": tc_buf[i]["name"],
                "arguments": tc_buf[i]["arguments"],
            },
        }
        for i in sorted(tc_buf)
    ]


async def _run_auto_tool(
    db: AsyncSession,
    session_id: uuid.UUID,
    s_tc: dict[str, Any],
    convo: list[dict[str, Any]],
) -> str:
    name = s_tc["function"]["name"]
    args_json = s_tc["function"].get("arguments") or "{}"
    tc_id = s_tc["id"]

    result = await _execute_tool(name, args_json)
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
        tool_calls={"tool_call_id": tc_id, "name": name},
    )
    convo.append(
        {"role": "tool", "tool_call_id": tc_id, "name": name, "content": result}
    )
    return result


async def _queue_approval(
    db: AsyncSession,
    session_id: uuid.UUID,
    s_tc: dict[str, Any],
) -> None:
    name = s_tc["function"]["name"]
    args_json = s_tc["function"].get("arguments") or "{}"
    tc_id = s_tc["id"]
    try:
        args_obj = json.loads(args_json)
    except json.JSONDecodeError:
        args_obj = {"_raw": args_json}
    db.add(
        Approval(
            session_id=session_id,
            tool_name=name,
            tool_call_id=tc_id,
            arguments=args_obj,
            status="pending",
        )
    )
    await _audit(
        db,
        session_id,
        "approval_requested",
        {"tool": name, "arguments": args_json, "tool_call_id": tc_id},
    )
    await db.flush()


async def _loop_stream(
    db: AsyncSession,
    session_id: uuid.UUID,
    convo: list[dict[str, Any]],
) -> AsyncGenerator[Event, None]:
    for _ in range(MAX_TOOL_ITERATIONS):
        completion: dict[str, Any] = {}
        async for ev in _stream_completion(convo, completion):
            yield ev
        content: str = completion["content"]
        tool_calls: list[dict[str, Any]] = completion["tool_calls"]

        if not tool_calls:
            await _persist(db, session_id, "assistant", content)
            await db.commit()
            yield ("done", {"status": "ok", "reply": content})
            return

        await _persist(db, session_id, "assistant", content, tool_calls=tool_calls)
        convo.append(
            {"role": "assistant", "content": content, "tool_calls": tool_calls}
        )

        deferred_any = False
        for s_tc in tool_calls:
            yield ("tool_call", s_tc)
            name = s_tc["function"]["name"]
            if _needs_approval(name, s_tc["function"].get("arguments")):
                await _queue_approval(db, session_id, s_tc)
                deferred_any = True
            else:
                result = await _run_auto_tool(db, session_id, s_tc, convo)
                yield (
                    "tool_result",
                    {"tool_call_id": s_tc["id"], "name": name, "content": result},
                )

        if deferred_any:
            await db.commit()
            pendings = await _pending_approvals(db, session_id)
            yield (
                "approval_required",
                {"approvals": [_approval_dict(a) for a in pendings]},
            )
            yield ("done", {"status": "pending_approval"})
            return

    fallback = "[agent stopped: tool iteration limit reached]"
    await _audit(db, session_id, "error", {"reason": "max tool iterations exceeded"})
    await _persist(db, session_id, "assistant", fallback)
    await db.commit()
    yield ("done", {"status": "stopped", "reply": fallback})


async def run_turn_stream(
    db: AsyncSession, session_id: uuid.UUID, user_text: str
) -> AsyncGenerator[Event, None]:
    sess = await db.get(Session, session_id)
    if sess is None:
        raise ValueError(f"session {session_id} not found")

    pendings = await _pending_approvals(db, session_id)
    if pendings:
        yield (
            "approval_required",
            {"approvals": [_approval_dict(a) for a in pendings]},
        )
        yield ("done", {"status": "pending_approval"})
        return

    convo = await _load_history(db, session_id)
    await _persist(db, session_id, "user", user_text)
    convo.append({"role": "user", "content": user_text})

    async for ev in _loop_stream(db, session_id, convo):
        yield ev


async def resume_turn_stream(
    db: AsyncSession, session_id: uuid.UUID
) -> AsyncGenerator[Event, None]:
    sess = await db.get(Session, session_id)
    if sess is None:
        raise ValueError(f"session {session_id} not found")

    pendings = await _pending_approvals(db, session_id)
    if pendings:
        yield (
            "approval_required",
            {"approvals": [_approval_dict(a) for a in pendings]},
        )
        yield ("done", {"status": "pending_approval"})
        return

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
        yield ("done", {"status": "ok", "reply": "[nothing to resume]"})
        return

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
            continue

        if appr.status == "approved":
            result = await _execute_tool(name, args_json)
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
        yield ("tool_result", {"tool_call_id": tc_id, "name": name, "content": result})

    convo = await _load_history(db, session_id)
    async for ev in _loop_stream(db, session_id, convo):
        yield ev


async def _drain(gen: AsyncGenerator[Event, None]) -> dict[str, Any]:
    """비스트리밍 호출용 — generator 를 다 소비하고 마지막 done/approval_required 의 결과만 합산."""
    result: dict[str, Any] = {"status": "ok", "reply": None, "approvals": None}
    async for event, payload in gen:
        if event == "done":
            result["status"] = payload.get("status", result["status"])
            if "reply" in payload:
                result["reply"] = payload["reply"]
        elif event == "approval_required":
            result["approvals"] = payload.get("approvals")
    return result


async def run_turn(
    db: AsyncSession, session_id: uuid.UUID, user_text: str
) -> dict[str, Any]:
    return await _drain(run_turn_stream(db, session_id, user_text))


async def resume_turn(
    db: AsyncSession, session_id: uuid.UUID
) -> dict[str, Any]:
    return await _drain(resume_turn_stream(db, session_id))


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
