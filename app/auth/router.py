from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import auth_service
from app.auth.auth_schemas import (
    AccessTokenResponse,
    RefreshRequest,
    TokenRequest,
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)
from app.auth.auth_security import decode_access_token
from app.config.database import get_db

router = APIRouter()

# Points to our token endpoint so Swagger's "Authorize" button knows where to send credentials.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token", auto_error=True)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """FastAPI dependency — decodes the Bearer JWT and returns the authenticated User."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return await auth_service.get_user_by_id(db, int(user_id))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(data: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new user account.

    - Hashes the password with bcrypt before storing.
    - Returns 409 if the email is already registered.
    """
    user = await auth_service.register_user(db, data)
    return user


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Login — obtain access + refresh tokens",
)
async def login(data: TokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate with email + password.

    Returns a short-lived JWT **access token** (60 min) and a long-lived
    **refresh token** (stored in the database).
    """
    user = await auth_service.authenticate_user(db, data.email, data.password)
    return await auth_service.create_tokens(db, user)


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Refresh — exchange a refresh token for a new access token",
)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Issue a new access token using a valid, unexpired refresh token.
    """
    access_token = await auth_service.refresh_access_token(db, data.refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current user — requires Bearer token",
)
async def me(current_user=Depends(get_current_user)):
    """
    Return the profile of the currently authenticated user.

    Requires `Authorization: Bearer <access_token>` header.
    """
    return current_user
