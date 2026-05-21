import json
from typing import Any, Callable

from . import fs, shell

APPROVAL_REQUIRED: set[str] = {"shell_exec"}

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "fs_read",
            "description": "Read a UTF-8 text file from the agent workspace. Path is relative to the workspace root; '..' and absolute paths are rejected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative path to the file."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_write",
            "description": "Write (or overwrite) a UTF-8 text file in the agent workspace. Creates parent directories as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative path."},
                    "content": {"type": "string", "description": "Full file contents."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_list",
            "description": "List entries in a workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative directory path. Defaults to workspace root.", "default": "."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": "Execute a system shell command. REQUIRES USER APPROVAL — the call will pause the agent until a human approves or denies it via the approvals API. Use sparingly and only when a file-system tool cannot accomplish the task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."},
                    "cwd": {"type": "string", "description": "Working directory (absolute or workspace-relative). Optional."},
                    "timeout": {"type": "integer", "description": "Timeout in seconds. Defaults to 30."},
                },
                "required": ["command"],
            },
        },
    },
]

DISPATCH: dict[str, Callable[..., Any]] = {
    "fs_read": fs.fs_read,
    "fs_write": fs.fs_write,
    "fs_list": fs.fs_list,
    "shell_exec": shell.shell_exec,
}


def call_tool(name: str, arguments_json: str) -> str:
    """Execute a registered tool by name with JSON arguments; return JSON-encoded result string."""
    if name not in DISPATCH:
        return json.dumps({"error": f"unknown tool: {name}"})
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON arguments: {e}"})
    try:
        result = DISPATCH[name](**args)
    except fs.WorkspaceError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
    return json.dumps({"ok": True, "result": result}, ensure_ascii=False)
