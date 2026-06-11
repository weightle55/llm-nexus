"""범용 MCP 클라이언트 브리지.

우리 FastAPI 백엔드를 MCP 호스트/클라이언트로 만들어, 설정된 MCP 서버
(stdio, 예: `uvx blender-mcp`)를 띄우고 그 도구를 우리 에이전트의 tool-calling
루프에 합류시킨다. Blender 가 첫 서버이고, 이후 어떤 MCP 서버든 같은 방식으로 꽂힌다.

설계 노트 — 세션 수명/스레드 안전:
  MCP 의 stdio_client / ClientSession 은 anyio task group 기반이라, 세션을 만든
  태스크 밖에서 직접 쓰면 cancel-scope 오류가 난다. 그래서 서버마다 **전용 워커
  태스크**가 세션을 소유하고, 외부(요청 태스크)는 asyncio.Queue + Future 로만
  호출을 위임한다. 워커가 죽거나 서버 연결이 실패해도 앱은 정상 기동한다(복원력).
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

from .config import settings

logger = logging.getLogger("mcp")

_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")
_DEFAULT_APPROVAL_KEYWORDS = ("exec", "code", "run", "delete", "write", "shell")


def _qualified_name(server: str, tool: str) -> str:
    """server+tool 을 OpenAI function name 규칙(^[a-zA-Z0-9_-]{1,64}$)에 맞춰 네임스페이스."""
    raw = f"mcp__{server}__{tool}"
    return _NAME_RE.sub("_", raw)[:64]


def _render_result(result: Any) -> str:
    """MCP CallToolResult 를 우리 도구 결과 규약(JSON 문자열)으로 변환."""
    is_error = getattr(result, "isError", False)
    blocks = getattr(result, "content", None) or []
    texts: list[str] = []
    extra: list[str] = []
    for b in blocks:
        text = getattr(b, "text", None)
        if text is not None:
            texts.append(text)
        else:
            extra.append(getattr(b, "type", type(b).__name__))
    payload = "\n".join(texts)
    if extra:
        payload += f"\n[non-text content: {', '.join(extra)}]"
    if is_error:
        return json.dumps({"error": payload or "tool reported an error"}, ensure_ascii=False)
    return json.dumps({"ok": True, "result": payload}, ensure_ascii=False)


class _Server:
    """단일 MCP 서버 연결 — 전용 워커 태스크가 세션을 소유."""

    def __init__(self, name: str, params: StdioServerParameters, approval_keywords: tuple[str, ...]):
        self.name = name
        self.params = params
        self.approval_keywords = approval_keywords
        self._queue: asyncio.Queue = asyncio.Queue()
        self._ready = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.ok = False
        self.error: str | None = None
        self.tools: list[dict] = []  # OpenAI 포맷 (네임스페이스 적용)
        self._tool_map: dict[str, str] = {}  # qualified -> 원래 tool name

    def _to_openai(self, tool: Any) -> dict:
        qn = _qualified_name(self.name, tool.name)
        self._tool_map[qn] = tool.name
        schema = tool.inputSchema or {"type": "object", "properties": {}}
        desc = (tool.description or tool.name)
        return {
            "type": "function",
            "function": {"name": qn, "description": f"[{self.name}] {desc}", "parameters": schema},
        }

    async def _run(self) -> None:
        try:
            async with stdio_client(self.params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    self.tools = [self._to_openai(t) for t in listed.tools]
                    self.ok = True
                    self._ready.set()
                    logger.info("MCP '%s' connected: %d tools", self.name, len(self.tools))
                    while True:
                        item = await self._queue.get()
                        if item is None:  # 종료 신호
                            break
                        qn, args, fut = item
                        try:
                            res = await session.call_tool(self._tool_map[qn], args)
                            if not fut.done():
                                fut.set_result(_render_result(res))
                        except Exception as e:  # 개별 호출 실패는 future 로 전달
                            if not fut.done():
                                fut.set_result(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        except Exception as e:  # 연결 자체 실패 — 앱은 계속
            self.error = f"{type(e).__name__}: {e}"
            logger.warning("MCP '%s' failed to connect: %s", self.name, self.error)
            self._ready.set()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def wait_ready(self, timeout: float) -> None:
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self.error = f"connect timeout ({timeout}s)"
            logger.warning("MCP '%s' connect timed out", self.name)

    async def call(self, qn: str, args: dict) -> str:
        if not self.ok:
            return json.dumps({"error": f"MCP server '{self.name}' not connected: {self.error}"})
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((qn, args, fut))
        return await fut

    def requires_approval(self, qn: str) -> bool:
        tool = self._tool_map.get(qn, qn).lower()
        return any(k in tool for k in self.approval_keywords)

    async def stop(self) -> None:
        if self._task is None:
            return
        await self._queue.put(None)
        try:
            await asyncio.wait_for(self._task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self._task.cancel()


class McpManager:
    def __init__(self) -> None:
        self._servers: dict[str, _Server] = {}
        self._owner: dict[str, _Server] = {}  # qualified tool name -> server

    async def startup(self) -> None:
        config_path: Path = settings.mcp_config
        if not config_path.is_file():
            logger.info("no MCP config at %s — MCP disabled", config_path)
            return
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("failed to read MCP config: %s", e)
            return

        for entry in cfg.get("servers", []):
            if not entry.get("enabled", False):
                continue
            name = entry["name"]
            # 설정 env 는 기본 환경(PATH 등) 위에 덮어쓴다 — 부분 env 로 PATH 가
            # 사라지면 uvx 같은 런처를 못 찾는다.
            env = get_default_environment()
            if entry.get("env"):
                env.update(entry["env"])
            params = StdioServerParameters(
                command=entry["command"],
                args=entry.get("args", []),
                env=env,
                cwd=entry.get("cwd") or None,
            )
            keywords = tuple(entry.get("approval_keywords", _DEFAULT_APPROVAL_KEYWORDS))
            server = _Server(name, params, keywords)
            server.start()
            self._servers[name] = server

        # 모든 서버 연결을 병렬로 대기 (실패해도 진행)
        await asyncio.gather(*(s.wait_ready(timeout=30) for s in self._servers.values()))
        for s in self._servers.values():
            if s.ok:
                for t in s.tools:
                    self._owner[t["function"]["name"]] = s

    async def shutdown(self) -> None:
        await asyncio.gather(*(s.stop() for s in self._servers.values()), return_exceptions=True)
        self._servers.clear()
        self._owner.clear()

    def openai_tools(self) -> list[dict]:
        out: list[dict] = []
        for s in self._servers.values():
            if s.ok:
                out.extend(s.tools)
        return out

    def has_tool(self, name: str) -> bool:
        return name in self._owner

    def requires_approval(self, name: str) -> bool:
        server = self._owner.get(name)
        return bool(server) and server.requires_approval(name)

    async def call_tool(self, name: str, arguments_json: str) -> str:
        server = self._owner.get(name)
        if server is None:
            return json.dumps({"error": f"unknown MCP tool: {name}"})
        try:
            args = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"invalid JSON arguments: {e}"})
        return await server.call(name, args)


mcp_manager = McpManager()
