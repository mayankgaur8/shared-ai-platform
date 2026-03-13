from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth_models import RefreshToken, User
from app.auth.auth_schemas import (
    AccessTokenResponse,
    TokenResponse,
    UserRegisterRequest,
)
from app.auth.auth_security import (
    create_access_token,
    create_refresh_token_value,
    hash_password,
    verify_password,
)
from app.config.settings import get_settings

settings = get_settings()


async def register_user(db: AsyncSession, data: UserRegisterRequest) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Constant-time path: always call verify_password even on miss to prevent timing attacks
    dummy_hash = "$2b$12$KIXNpMWkWJPXoXh2kp1A7.abcdefghijklmnopqrstuvwxyz01234"
    password_ok = verify_password(password, user.password_hash if user else dummy_hash)

    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return user


async def create_tokens(db: AsyncSession, user: User) -> TokenResponse:
    access_token = create_access_token({"sub": str(user.id), "email": user.email})
    refresh_value = create_refresh_token_value()
    expires_at = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)

    db.add(RefreshToken(user_id=user.id, token=refresh_value, expires_at=expires_at))
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_value)


async def refresh_access_token(db: AsyncSession, refresh_token_value: str) -> str:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == refresh_token_value)
    )
    token_record = result.scalar_one_or_none()

    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if token_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    result = await db.execute(select(User).where(User.id == token_record.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return create_access_token({"sub": str(user.id), "email": user.email})


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
