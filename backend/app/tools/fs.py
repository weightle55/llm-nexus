from pathlib import Path

from ..config import settings


class WorkspaceError(Exception):
    """워크스페이스 샌드박스 위반."""


def _resolve_inside_workspace(rel_path: str) -> Path:
    root = settings.workspace_dir.resolve()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as e:
        raise WorkspaceError(
            f"path {rel_path!r} escapes workspace root {root}"
        ) from e
    return target


def fs_read(path: str) -> str:
    target = _resolve_inside_workspace(path)
    if not target.is_file():
        raise WorkspaceError(f"not a file: {path}")
    return target.read_text(encoding="utf-8")


def fs_write(path: str, content: str) -> dict:
    target = _resolve_inside_workspace(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "path": target.relative_to(settings.workspace_dir.resolve()).as_posix(),
        "bytes": len(content.encode("utf-8")),
    }


def fs_list(path: str = ".") -> list[dict]:
    target = _resolve_inside_workspace(path)
    if not target.is_dir():
        raise WorkspaceError(f"not a directory: {path}")
    entries = []
    for entry in sorted(target.iterdir()):
        entries.append(
            {
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            }
        )
    return entries
