"""Blender 5.1 API/매뉴얼 문서 렉시컬 검색 도구.

Blender Buddy(CGMatter, GPL-3.0)가 공개 Blender 문서로 빌드한 `api_index.jsonl`
(operator / type / function / 매뉴얼 등 11.5k 레코드)을 빌려와 키워드 검색으로 노출.
작은 모델(Gemma)이 bpy API 를 환각하지 않도록 권위 있는 문서로 grounding 하는 용도.

레코드 형태(kind 별로 일부 필드 상이):
- operator : path, name, description, parameters?
- type     : path, name, bases, properties[], functions[]
- function : path, description (시그니처 포함)
- doc/api_doc : path, name, description(본문 발췌), source
- template : path, name, code (예제 코드)
"""

import json
import re

from ..config import settings


class BlenderDocsError(Exception):
    """문서 인덱스 누락 또는 검색 오류."""


_INDEX: list[tuple[dict, str]] | None = None


def _haystack(r: dict) -> str:
    parts = [r.get("path", ""), r.get("name", ""), r.get("description", "")]
    for p in r.get("properties") or []:
        if isinstance(p, dict):
            parts.append(p.get("name", ""))
    for fn in r.get("functions") or []:
        parts.append(fn.get("name", "") if isinstance(fn, dict) else str(fn))
    return " ".join(parts).lower()


def _load() -> list[tuple[dict, str]]:
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    path = settings.blender_docs_index
    if not path.is_file():
        raise BlenderDocsError(
            f"Blender docs index not found at {path}. "
            "Copy Blender Buddy's api_index.jsonl there (see data/ README)."
        )
    records: list[tuple[dict, str]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            records.append((r, _haystack(r)))
    _INDEX = records
    return _INDEX


def _format(r: dict) -> dict:
    out: dict = {"kind": r.get("kind"), "path": r.get("path")}
    if r.get("name"):
        out["name"] = r["name"]
    desc = r.get("description")
    if desc:
        out["description"] = desc[:400]
    if r.get("parameters"):
        out["parameters"] = [
            {"name": p.get("name"), "type": p.get("type"), "default": p.get("default")}
            for p in r["parameters"][:12]
            if isinstance(p, dict)
        ]
    if r.get("kind") == "type":
        props = [p.get("name") for p in (r.get("properties") or []) if isinstance(p, dict)]
        if props:
            out["properties"] = props[:25]
    if r.get("kind") == "template" and r.get("code"):
        out["code_excerpt"] = r["code"][:800]
    return out


def search_blender_docs(
    query: str, kind: str | None = None, max_results: int = 20
) -> dict:
    """Blender 문서를 키워드로 검색. kind 로 operator/type/function/doc 등 한정 가능."""
    index = _load()
    terms = [t for t in re.split(r"[^a-z0-9_.]+", query.lower()) if t]
    if not terms:
        raise BlenderDocsError("empty query")
    max_results = max(1, min(max_results, 50))

    scored: list[tuple[int, dict]] = []
    for r, hay in index:
        if kind and r.get("kind") != kind:
            continue
        path = (r.get("path") or "").lower()
        name = (r.get("name") or "").lower()
        score = 0
        matched = 0
        for t in terms:
            if t in hay:
                matched += 1
                score += 1
                if t in path:
                    score += 3
                if t in name:
                    score += 2
        if matched == 0:
            continue
        if matched == len(terms):  # 모든 단어 매칭 시 가산
            score += 5
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [_format(r) for _, r in scored[:max_results]]
    return {"query": query, "count": len(results), "results": results}
