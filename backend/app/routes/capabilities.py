from fastapi import APIRouter

from ..capabilities import get_capabilities

router = APIRouter(tags=["capabilities"])


@router.get("/capabilities")
async def capabilities() -> dict:
    """에이전트 기능 카탈로그 (정적). 새 대화의 환영 메시지 렌더용."""
    return get_capabilities()
