import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import RevokedToken, User


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, username: str, expiry_days: int = 1) -> str:
    jwt_secret = os.environ["JWT_SECRET"]
    iat = datetime.now(timezone.utc)
    exp = iat + timedelta(days=expiry_days)
    jti = str(uuid4())
    payload = {
        "sub": str(user_id),
        "username": username,
        "jti": jti,
        "exp": exp,
        "iat": iat,
        "type": "access",
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def create_service_token(user_id: int, username: str) -> str:
    jwt_secret = os.environ["JWT_SECRET"]
    expiry_days = int(os.environ.get("JWT_SERVICE_EXPIRY_DAYS", 365))
    iat = datetime.now(timezone.utc)
    exp = iat + timedelta(days=expiry_days)
    jti = str(uuid4())
    payload = {
        "sub": str(user_id),
        "username": username,
        "jti": jti,
        "exp": exp,
        "iat": iat,
        "type": "service",
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def _extract_token(request: Request) -> str:
    token = request.cookies.get("token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token


def _decode_token(token: str) -> dict | None:
    jwt_secret = os.environ["JWT_SECRET"]
    try:
        return jwt.decode(token, jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = _decode_token(token)
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="Token revoked")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_current_user_optional(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None
