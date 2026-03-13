import base64
import hashlib
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.config.settings import get_settings

settings = get_settings()


def _normalize_password(password: str) -> str:
    # NFKC normalization reduces Unicode representation ambiguity.
    normalized = unicodedata.normalize("NFKC", password)
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("utf-8")


def hash_password(password: str) -> str:
    normalized = _normalize_password(password).encode("utf-8")
    return bcrypt.hashpw(normalized, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    normalized = _normalize_password(plain_password).encode("utf-8")
    try:
        return bcrypt.checkpw(normalized, hashed_password.encode("utf-8"))
    except ValueError:
        # Invalid/legacy hash format should fail closed.
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token_value() -> str:
    """Generate a cryptographically secure opaque refresh token."""
    return secrets.token_urlsafe(64)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Raises:
        jose.JWTError: if the token is invalid, expired, or not an access token.
    """
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Token type is not 'access'")
    return payload
