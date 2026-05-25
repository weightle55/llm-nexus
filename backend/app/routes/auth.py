from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..db import get_db
from ..models import Session, User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: EmailStr
    password: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    created_at: datetime


def _to_userout(u: User) -> UserOut:
    return UserOut(id=str(u.id), email=u.email, created_at=u.created_at)


@router.post("/register", response_model=TokenOut)
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)) -> TokenOut:
    if len(body.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="password must be at least 6 characters",
        )
    user = User(email=str(body.email), password_hash=hash_password(body.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        )
    await db.refresh(user)

    # 첫 user 인 경우, owner 가 없던 기존 세션을 모두 이 user 에게 귀속.
    total_users = (
        await db.execute(select(func.count(User.id)))
    ).scalar_one()
    if total_users == 1:
        await db.execute(
            update(Session)
            .where(Session.owner_id.is_(None))
            .values(owner_id=user.id)
        )
        await db.commit()

    return TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenOut)
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)) -> TokenOut:
    result = await db.execute(select(User).where(User.email == str(body.email)))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return _to_userout(user)
