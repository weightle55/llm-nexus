import shutil
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


def _rel(target: Path) -> str:
    return target.relative_to(settings.workspace_dir.resolve()).as_posix()


def is_directory(rel_path: str) -> bool:
    """승인 판정용 — 경로가 워크스페이스 내 디렉터리인지 안전하게 검사 (예외 없이)."""
    try:
        return _resolve_inside_workspace(rel_path).is_dir()
    except WorkspaceError:
        return False


def fs_read(path: str) -> str:
    target = _resolve_inside_workspace(path)
    if not target.is_file():
        raise WorkspaceError(f"not a file: {path}")
    return target.read_text(encoding="utf-8")


def fs_write(path: str, content: str) -> dict:
    target = _resolve_inside_workspace(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": _rel(target), "bytes": len(content.encode("utf-8"))}


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


def fs_tree(path: str = ".", depth: int = 3) -> dict:
    root = _resolve_inside_workspace(path)
    if not root.is_dir():
        raise WorkspaceError(f"not a directory: {path}")
    depth = max(1, min(depth, 8))

    def walk(d: Path, level: int) -> list[dict]:
        out: list[dict] = []
        for entry in sorted(d.iterdir()):
            if entry.is_dir():
                node: dict = {"name": entry.name, "type": "dir"}
                if level < depth:
                    node["children"] = walk(entry, level + 1)
                else:
                    node["truncated"] = True
                out.append(node)
            else:
                out.append({"name": entry.name, "type": "file"})
        return out

    return {"path": _rel(root), "depth": depth, "tree": walk(root, 1)}


def fs_search(
    query: str,
    path: str = ".",
    glob: str = "**/*",
    max_results: int = 100,
) -> dict:
    """파일 내용에서 query 를 포함하는 줄을 찾는다. glob 으로 대상 파일 한정."""
    root = _resolve_inside_workspace(path)
    if not root.is_dir():
        raise WorkspaceError(f"not a directory: {path}")
    max_results = max(1, min(max_results, 500))
    matches: list[dict] = []
    truncated = False
    for entry in sorted(root.glob(glob)):
        if not entry.is_file():
            continue
        try:
            text = entry.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # 바이너리/접근불가 파일 skip
        for i, line in enumerate(text.splitlines(), start=1):
            if query in line:
                matches.append(
                    {"file": _rel(entry), "line_no": i, "line": line.strip()[:300]}
                )
                if len(matches) >= max_results:
                    truncated = True
                    break
        if truncated:
            break
    return {"query": query, "count": len(matches), "matches": matches,
            "truncated": truncated}


def fs_mkdir(path: str) -> dict:
    target = _resolve_inside_workspace(path)
    target.mkdir(parents=True, exist_ok=True)
    return {"path": _rel(target), "type": "dir"}


def fs_move(src: str, dst: str) -> dict:
    src_t = _resolve_inside_workspace(src)
    dst_t = _resolve_inside_workspace(dst)
    if not src_t.exists():
        raise WorkspaceError(f"source not found: {src}")
    if dst_t.exists():
        raise WorkspaceError(f"destination already exists: {dst}")
    dst_t.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_t), str(dst_t))
    return {"src": _rel(src_t), "dst": _rel(dst_t)}


def fs_delete(path: str) -> dict:
    target = _resolve_inside_workspace(path)
    if target == settings.workspace_dir.resolve():
        raise WorkspaceError("refusing to delete the workspace root")
    if target.is_dir():
        shutil.rmtree(target)
        return {"deleted": _rel(target), "type": "dir"}
    if target.is_file():
        target.unlink()
        return {"deleted": _rel(target), "type": "file"}
    raise WorkspaceError(f"not found: {path}")
