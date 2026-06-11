import json
from typing import Any, Callable

from . import blender_docs, fs, shell, web

# 이름만으로 항상 승인이 필요한 도구
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
            "name": "fs_tree",
            "description": "Show a recursive directory tree of the workspace (read-only). Use this to understand project structure before editing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative directory. Defaults to root.", "default": "."},
                    "depth": {"type": "integer", "description": "Max recursion depth (1-8). Defaults to 3.", "default": 3},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_search",
            "description": "Search file CONTENTS for a substring across the workspace (read-only, like grep). Returns matching {file, line_no, line}. Optionally restrict files with a glob.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Substring to search for in file contents."},
                    "path": {"type": "string", "description": "Workspace-relative directory to search under. Defaults to root.", "default": "."},
                    "glob": {"type": "string", "description": "Glob to limit files, e.g. '**/*.py'. Defaults to all files.", "default": "**/*"},
                    "max_results": {"type": "integer", "description": "Max matches to return (1-500). Defaults to 100.", "default": 100},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_mkdir",
            "description": "Create a directory (and parents) in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative directory path."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_move",
            "description": "Move or rename a file/directory within the workspace. Fails if the destination already exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Workspace-relative source path."},
                    "dst": {"type": "string", "description": "Workspace-relative destination path."},
                },
                "required": ["src", "dst"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fs_delete",
            "description": "Delete a file or directory in the workspace. Deleting a file is automatic; deleting a DIRECTORY (recursive) REQUIRES USER APPROVAL and will pause the agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative path to delete."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch a public web page over http/https and return its text (HTML is stripped to readable text). Internal/private addresses are blocked. Use for documentation lookup and research.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Absolute http(s) URL to fetch."},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (1-60). Defaults to 20.", "default": 20},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_blender_docs",
            "description": "Search the authoritative Blender 5.1 API & manual index (operators, bpy types/properties, functions, node sockets, example templates). Call this BEFORE writing bpy code or answering a Blender question — your training knowledge of bpy may be outdated or wrong for 5.1; this index is verbatim. Lexical keyword search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords, e.g. 'bevel modifier width' or 'principled bsdf emission'."},
                    "kind": {"type": "string", "description": "Optional filter: operator | type | function | doc | api_doc | template | module | class | constant.", "enum": ["operator", "type", "function", "doc", "api_doc", "template", "module", "class", "constant"]},
                    "max_results": {"type": "integer", "description": "Max results (1-50). Defaults to 20.", "default": 20},
                },
                "required": ["query"],
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
    "fs_tree": fs.fs_tree,
    "fs_search": fs.fs_search,
    "fs_mkdir": fs.fs_mkdir,
    "fs_move": fs.fs_move,
    "fs_delete": fs.fs_delete,
    "web_fetch": web.web_fetch,
    "search_blender_docs": blender_docs.search_blender_docs,
    "shell_exec": shell.shell_exec,
}


def requires_approval(name: str, arguments_json: str | None) -> bool:
    """도구 호출에 사람 승인이 필요한지 판정. 이름 기반 + 인자 기반 규칙을 합산."""
    if name in APPROVAL_REQUIRED:
        return True
    if name == "fs_delete":
        # 디렉터리(재귀) 삭제만 승인 필요. 파일 삭제는 자동.
        try:
            args = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError:
            return True  # 파싱 불가 시 안전하게 승인 요구
        path = args.get("path")
        return bool(path) and fs.is_directory(path)
    return False


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
    except (fs.WorkspaceError, web.WebError, blender_docs.BlenderDocsError) as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
    return json.dumps({"ok": True, "result": result}, ensure_ascii=False)
